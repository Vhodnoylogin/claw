"""Pinned surface attachment constraints, independent of Blender and NIF parsing.

All positions are in one frozen world/rest frame. UV splits are joined only in
the solver graph; exported vertices, triangles, UVs and skin weights are untouched.
The collar preserves the donor offset from a source triangle and changes only a
narrow geodesic band. Its interior/outer boundary remains exactly unchanged.
"""
from __future__ import annotations

import hashlib
import heapq
import numpy as np


def positions(value):
    value = np.asarray(value, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] != 3 or not np.isfinite(value).all():
        raise ValueError("Expected finite N by 3 positions")
    return value


def triangles(value, count):
    raw = np.asarray(value)
    if raw.ndim != 2 or raw.shape[1] != 3 or raw.dtype.kind not in "iu":
        raise ValueError("Expected integer triangle indices")
    value = raw.astype(np.int64)
    if not len(value) or value.min() < 0 or value.max() >= count:
        raise ValueError("Triangle indices outside the vertex array")
    return value


def signature(vertices, faces):
    vertices = positions(vertices)
    faces = triangles(faces, len(vertices))
    return {"vertexCount": len(vertices), "triangleCount": len(faces),
            "topologySha256": hashlib.sha256(faces.astype("<i8").tobytes()).hexdigest(),
            "bounds": [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()]}


def validate_geometry(vertices, faces, expected, tolerance):
    actual = signature(vertices, faces)
    for name in ("vertexCount", "triangleCount", "topologySha256"):
        if actual[name] != expected[name]:
            raise ValueError("Pinned donor geometry mismatch: " + name)
    if not np.allclose(actual["bounds"], expected["bounds"], rtol=0, atol=tolerance):
        raise ValueError("Pinned donor geometry mismatch: bounds/rest frame")
    return actual


def boundary_vertices(faces):
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                                    faces[:, [2, 0]]]), axis=1)
    edges, count = np.unique(edges, axis=0, return_counts=True)
    return np.unique(edges[count == 1])


def region_weight(vertices, bounds, fade=None):
    vertices = positions(vertices)
    bounds = np.asarray(bounds, dtype=float)
    if bounds.shape != (2, 3) or not np.isfinite(bounds).all() or np.any(bounds[1] <= bounds[0]):
        raise ValueError("Invalid surface region bounds")
    if fade is None:
        return ((vertices >= bounds[0]) & (vertices <= bounds[1])).all(axis=1).astype(float)
    fade = np.asarray(fade, dtype=float)
    if fade.shape != (3,) or not np.isfinite(fade).all() or np.any(fade <= 0):
        raise ValueError("Invalid surface region fade")
    left = np.clip((vertices - bounds[0]) / fade, 0, 1)
    right = np.clip((bounds[1] - vertices) / fade, 0, 1)
    return np.prod(left * left * (3 - 2 * left) * right * right * (3 - 2 * right), axis=1)


def barycentric(point, triangle):
    a, b, c = positions(triangle)
    ab, ac, ap = b - a, c - a, np.asarray(point) - a
    d00, d01, d11 = ab @ ab, ab @ ac, ac @ ac
    denominator = d00 * d11 - d01 * d01
    if denominator <= np.finfo(float).eps:
        raise ValueError("Degenerate attachment triangle")
    v = (d11 * (ap @ ab) - d01 * (ap @ ac)) / denominator
    w = (d00 * (ap @ ac) - d01 * (ap @ ab)) / denominator
    result = np.clip([1 - v - w, v, w], 0, 1)
    return result / result.sum()


def closest_surface(point, vertices, faces):
    """Exact point/triangle distance; production may supply a BVH projector."""
    a, b, c = [vertices[faces[:, index]] for index in range(3)]
    ab, ac, ap = b - a, c - a, np.asarray(point) - a
    normal = np.cross(ab, ac)
    length = np.sum(normal * normal, axis=1)
    projected = point - normal * (np.sum(ap * normal, axis=1) / np.maximum(length, 1e-30))[:, None]
    aq = projected - a
    d00, d01, d11 = np.sum(ab * ab, axis=1), np.sum(ab * ac, axis=1), np.sum(ac * ac, axis=1)
    d20, d21 = np.sum(aq * ab, axis=1), np.sum(aq * ac, axis=1)
    den = d00 * d11 - d01 * d01
    v = (d11 * d20 - d01 * d21) / np.maximum(den, 1e-30)
    w = (d00 * d21 - d01 * d20) / np.maximum(den, 1e-30)
    u = 1 - v - w
    valid = (u >= 0) & (v >= 0) & (w >= 0) & (length > 1e-30)
    distance = np.where(valid, np.sum((projected - point) ** 2, axis=1), np.inf)
    index = int(distance.argmin())
    best = (float(distance[index]), index, projected[index])
    for start, end in ((a, b), (b, c), (c, a)):
        edge = end - start
        fraction = np.clip(np.sum((point - start) * edge, axis=1) /
                           np.maximum(np.sum(edge * edge, axis=1), 1e-30), 0, 1)
        projected = start + fraction[:, None] * edge
        distance = np.sum((projected - point) ** 2, axis=1)
        index = int(distance.argmin())
        if distance[index] < best[0]:
            best = (float(distance[index]), index, projected[index])
    return best[2], best[1], float(np.sqrt(best[0]))


class Bindings:
    def __init__(self, points, vertices, faces, projector=None):
        self.points = positions(points).copy()
        self.faces = triangles(faces, len(vertices)).copy()
        vertices = positions(vertices)
        self.indices, self.weights, self.distances = [], [], []
        for point in self.points:
            nearest, index, distance = (projector(point) if projector else
                                        closest_surface(point, vertices, self.faces))
            self.indices.append(index)
            self.weights.append(barycentric(nearest, vertices[self.faces[index]]))
            self.distances.append(distance)
        self.indices = np.asarray(self.indices, dtype=int)
        self.weights = np.asarray(self.weights, dtype=float).reshape(-1, 3)
        self.distances = np.asarray(self.distances, dtype=float)
        self.offsets = self.points - self.evaluate(vertices)

    def evaluate(self, values):
        values = positions(values)
        return np.sum(values[self.faces[self.indices]] * self.weights[:, :, None], axis=1)


def welded_graph(vertices, faces, decimals):
    _, first, inverse = np.unique(np.round(vertices, decimals), axis=0,
                                  return_index=True, return_inverse=True)
    vertices = vertices[first]
    faces = inverse[faces]
    edges = np.unique(np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]],
                                              faces[:, [2, 0]]]), axis=1), axis=0)
    edges = edges[edges[:, 0] != edges[:, 1]]
    adjacency = [[] for _ in vertices]
    for (a, b), length in zip(edges, np.linalg.norm(vertices[edges[:, 0]] - vertices[edges[:, 1]], axis=1)):
        if length <= 0:
            raise ValueError("Zero length solver edge")
        adjacency[a].append((int(b), float(length)))
        adjacency[b].append((int(a), float(length)))
    return first, inverse, adjacency


class Collar:
    def __init__(self, source_vertices, source_faces, target_vertices, target_faces,
                 rule, projector=None):
        self.source = positions(source_vertices).copy()
        self.target = positions(target_vertices).copy()
        source_faces = triangles(source_faces, len(self.source))
        target_faces = triangles(target_faces, len(self.target))
        self.rule = rule
        candidates = boundary_vertices(target_faces)
        candidates = candidates[region_weight(self.target[candidates], rule["anchorBounds"]) > 0]
        binding = Bindings(self.target[candidates], self.source, source_faces, projector)
        take = binding.distances <= float(rule["anchorMaxDistance"])
        self.anchors = candidates[take]
        self.binding = Bindings(self.target[self.anchors], self.source, source_faces, projector)
        low, high = rule["anchorCountRange"]
        if not low <= len(self.anchors) <= high:
            raise ValueError("Attachment anchor count outside pinned range")
        self.first, self.inverse, self.adjacency = welded_graph(self.target, target_faces,
                                                              int(rule["weldDecimals"]))
        self.seed = self.inverse[self.anchors]
        self.distance = np.full(len(self.first), np.inf)
        queue = []
        for index in self.seed:
            self.distance[index] = 0
            heapq.heappush(queue, (0, int(index)))
        width = float(rule["width"])
        if not np.isfinite(width) or width <= 0:
            raise ValueError("Invalid collar width")
        while queue:
            distance, index = heapq.heappop(queue)
            if distance != self.distance[index] or distance >= width:
                continue
            for neighbor, length in self.adjacency[index]:
                proposed = distance + length
                if proposed < self.distance[neighbor]:
                    self.distance[neighbor] = proposed
                    heapq.heappush(queue, (proposed, neighbor))
        seeds = set(self.seed.tolist())
        self.free = np.asarray([i for i in np.flatnonzero(self.distance < width)
                                if i not in seeds], dtype=int)

    def reconcile(self, source_delta, target_delta):
        source_delta, target_delta = positions(source_delta), positions(target_delta)
        if source_delta.shape != self.source.shape or target_delta.shape != self.target.shape:
            raise ValueError("Attachment field does not match frozen geometry")
        wanted = self.binding.evaluate(source_delta) - target_delta[self.anchors]
        correction = np.zeros((len(self.first), 3))
        count = np.zeros(len(self.first))
        for index, value in zip(self.seed, wanted):
            correction[index] += value
            count[index] += 1
        fixed = count > 0
        correction[fixed] /= count[fixed, None]
        for _ in range(int(self.rule["maxIterations"])):
            new = correction.copy()
            for index in self.free:
                neighbors = self.adjacency[index]
                weights = np.asarray([1 / length for _, length in neighbors])
                new[index] = np.sum(correction[[j for j, _ in neighbors]] * weights[:, None], axis=0) / weights.sum()
            error = np.max(np.abs(new - correction))
            correction = new
            if error <= float(self.rule["solverTolerance"]):
                break
        else:
            raise ValueError("Surface collar solver did not converge")
        return target_delta + correction[self.inverse]

    def metrics(self, source_positions, target_positions):
        difference = positions(target_positions)[self.anchors] - self.binding.evaluate(source_positions)
        distances = np.linalg.norm(difference, axis=1)
        offset_error = np.linalg.norm(difference - self.binding.offsets, axis=1)
        return {"anchors": len(self.anchors), "distanceP50": float(np.median(distances)),
                "distanceP95": float(np.quantile(distances, .95)), "distanceMax": float(distances.max()),
                "donorOffsetErrorMax": float(offset_error.max())}


class Layer:
    """Bind card roots to skin; full replacement translates a card intact.

    In a fade region the common per-card weight blends the original per-vertex
    field with the attachment translation, retaining some original deformation.
    """
    def __init__(self, vertices, faces, skin_vertices, skin_faces, rule, projector=None):
        if rule.get("mode") not in ("cards", "vertices"):
            raise ValueError("Unknown surface follower mode")
        vertices = positions(vertices)
        first, inverse, adjacency = welded_graph(vertices, triangles(faces, len(vertices)),
                                                 int(rule["weldDecimals"]))
        groups, seen = [], set()
        for index in range(len(first)):
            if index in seen:
                continue
            queue, group = [index], []
            seen.add(index)
            while queue:
                current = queue.pop()
                group.append(current)
                for neighbor, _ in adjacency[current]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        queue.append(neighbor)
            groups.append(np.flatnonzero(np.isin(inverse, group)))
        self.groups = groups if rule["mode"] == "cards" else [np.asarray([i]) for i in range(len(vertices))]
        # The closest vertex of each card is its skin attachment, not its distant tip.
        representatives, enabled, weights = [], [], []
        spatial = region_weight(vertices, rule["bounds"], rule["fade"])
        for group in self.groups:
            choices = group[spatial[group] > 0]
            if not len(choices):
                representatives.append(vertices[group[0]])
                enabled.append(False)
                weights.append(0.0)
                continue
            local = Bindings(vertices[choices], skin_vertices, skin_faces, projector)
            best = int(local.distances.argmin())
            index = choices[best]
            distance = local.distances[best]
            full, cutoff = map(float, rule["distanceFade"])
            if not 0 <= full < cutoff:
                raise ValueError("Invalid skin/fur distance fade")
            factor = np.clip((cutoff - distance) / (cutoff - full), 0, 1)
            factor = factor * factor * (3 - 2 * factor)
            representatives.append(vertices[index])
            enabled.append(bool(factor))
            weights.append(float(factor * spatial[index]))
        self.binding = Bindings(representatives, skin_vertices, skin_faces, projector)
        self.weights = np.asarray(weights)
        self.enabled = np.asarray(enabled)

    def reconcile(self, original_delta, skin_delta):
        result = positions(original_delta).copy()
        inherited = self.binding.evaluate(skin_delta)
        for group, value, weight in zip(self.groups, inherited, self.weights):
            if weight:
                result[group] = result[group] * (1 - weight) + value * weight
        return result
