"""Choose a repeatable static aim for the two-sided FSMP sphere/triangle check."""

import hashlib
import json
import struct

import numpy as np


def provider_faces(faces, packed_driver_weights):
    mobile_vertices = (packed_driver_weights > np.finfo(np.float32).eps).any(axis=1)
    return np.flatnonzero(mobile_vertices[faces].any(axis=1))


def face_incenter(triangle):
    side_lengths = np.linalg.norm(triangle[[1, 2, 0]] - triangle[[2, 0, 1]], axis=1)
    cross = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
    twice_area = np.linalg.norm(cross)
    if twice_area <= np.finfo(np.float32).eps:
        return None
    perimeter = side_lengths.sum()
    return side_lengths @ triangle / perimeter, cross / twice_area, twice_area / perimeter


def plan(vertices, faces, exposed, packed_driver_weights, peer_points, radius, outside, triangle_distance):
    """Use the furthest probe point as a bound for any rigid peer rotation."""
    retained = provider_faces(faces, packed_driver_weights)
    surfaces = vertices[faces[retained]]
    fully_mobile = (packed_driver_weights[faces] > np.finfo(np.float32).eps).all(axis=1)
    outside_faces = exposed[faces].all(axis=1)
    spread = float(np.linalg.norm(peer_points, axis=1).max())
    approach = radius / 4
    picks = []
    for driver in range(packed_driver_weights.shape[1]):
        trials = []
        for index in retained[fully_mobile[retained, driver] & outside_faces[retained]]:
            geometry = face_incenter(vertices[faces[index]])
            if geometry is None:
                continue
            center, normal, inradius = geometry
            projection_margin = inradius - spread
            plane_margin = radius - approach - spread
            if min(projection_margin, plane_margin) <= 1e-4:
                continue
            for side in (normal, -normal):
                near = center + approach * side
                far = center + (radius + spread + 1.0) * side
                if not outside(near) or not outside(far):
                    continue
                clearance = float(triangle_distance(far[None], surfaces)[0]) - radius - spread
                if clearance > 1e-4:
                    trials.append({
                        "face": int(index), "indices": faces[index].tolist(), "near": near.tolist(),
                        "far": far.tolist(), "normal": side.tolist(), "faceInradius": float(inradius),
                        "projectionMargin": float(projection_margin), "planeMargin": float(plane_margin),
                        "farClearance": clearance,
                    })
        picks.append(max(trials, key=lambda row: min(row["projectionMargin"], row["planeMargin"],
                                                    row["farClearance"]), default=None))
    return retained, picks


def read_pinned_probe(report_path):
    data = report_path.read_bytes()
    report = json.loads(data)
    points = np.asarray(report["localPoints"], dtype=float)
    radius = float(report["probeMargin"])
    files = report["files"]
    payload = report_path.parent / "payload"
    if (report["status"] != "verified-offline-peer-mesh-and-policy" or points.shape != (4, 3)
            or not np.isfinite(points).all() or not np.isfinite(radius) or radius <= 0 or len(files) != 4):
        raise ValueError("Expected the verified four-point FSMP fixture")
    for name, digest in files.items():
        path = (payload / name).resolve()
        if not path.is_relative_to(payload.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Peer artifact outside payload or changed: " + name)
    return points, radius, hashlib.sha256(data).hexdigest()


def expected_face_digest(report_path, nif_digest):
    data = report_path.read_bytes()
    report = json.loads(data)
    matches = [endpoint["proof"]["nativeReadback"]["packedProviderSupport"]["retainedTriangleIndicesSha256"]
               for family in report["families"].values() for endpoint in family["endpoints"]
               if endpoint["sha256"] == nif_digest]
    if not matches or len(set(matches)) != 1:
        raise ValueError("Collision receipt does not identify the exact target NIF and triangle set")
    return matches[0], hashlib.sha256(data).hexdigest()


def verify_face_digest(retained, expected):
    actual = hashlib.sha256(struct.pack("<" + str(len(retained)) + "I", *retained)).hexdigest()
    if actual != expected:
        raise ValueError("Target face order differs from the packed provider receipt")
    return actual
