"""Reconstruct the retained FSMP probe pair at observed actor poses."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import sys

import numpy as np

from fsmp_contact_windows import DRIVERS, require
from peer_contact_geometry import face_incenter, read_pinned_probe, verify_face_digest


REPO = Path(__file__).resolve().parents[4]
for tool in ("src/main/python/build-tools", "src/main/python/physics", "src/test/python/integration"):
    directory = str(REPO / tool)
    if directory not in sys.path:
        sys.path.insert(0, directory)

from breast_rig import load_pynifly, matrix
from contact_fit import triangle_distance
from fsmp_probe import transform
from player_only_materials import container


PELVIS = "NPC Pelvis [Pelv]"
NAMES = (PELVIS, *DRIVERS)
MIN_MARGIN = .025  # World units, separate from the positive provider contact depth.
SOURCE_PATH = "SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/"
FAMILIES = {
    "anatomy3": SOURCE_PATH + "CLAWNeutralAnatomyContact.xml",
    "combined12": SOURCE_PATH + "CLAWMotionNeutralAnatomyContactMale.xml",
}


def pinned_file(root, relative, expected):
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()) and hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            "Asset bytes differ: " + str(relative))
    return path


def world_matrix(pose):
    pose = transform(pose)
    result = np.eye(4)
    result[:3, :3] = np.asarray(pose["rotationRowMajor"]).reshape(3, 3) * pose["scale"]
    result[:3, 3] = pose["translation"]
    return result


@dataclass(frozen=True)
class Geometry:
    faces: np.ndarray
    planned_face: int
    local_points: np.ndarray  # Vertex x bone x 4, raw packed weights folded into the rows.
    probe_points: np.ndarray  # Homogeneous coordinates in the real peer pelvis frame.
    probe_radius: float
    sign: int
    driver: str
    target_path: str
    probe_path: str
    control_path: str
    morphs: tuple[str, ...]
    identity: dict

    def triangles(self, nodes):
        matrices = np.stack([world_matrix(nodes[name]) for name in NAMES])
        points = np.einsum("bij,vbj->vi", matrices, self.local_points)[:, :3]
        require(np.isfinite(points).all(), "Nonfinite posed vertex")
        return points[self.faces]

    def aims(self, nodes, probe_pelvis):
        faces = self.triangles(nodes)
        geometry = face_incenter(faces[self.planned_face])
        require(geometry is not None, "Observed target triangle is degenerate")
        center, normal, inradius = geometry
        scale = world_matrix(probe_pelvis)[0:3, 0:3]
        spread = np.linalg.norm(self.probe_points[:, :3] @ scale.T, axis=1).max()
        radius = self.probe_radius * probe_pelvis["scale"]
        require(inradius > spread + MIN_MARGIN and radius * .75 > spread + MIN_MARGIN,
                "Current target face cannot hold all four probe points")
        near = center + self.sign * normal * (radius / 4)
        for extra in (1., 2., 3., 5.):
            far = center + self.sign * normal * (radius + spread + extra)
            if triangle_distance(far[None], faces)[0] > radius + spread + MIN_MARGIN:
                return near, far
        raise ValueError("No separated probe aim within the local fixture envelope")

    def bracket(self, nodes, probe_pelvis, near):
        faces = self.triangles(nodes)
        points = (self.probe_points @ world_matrix(probe_pelvis).T)[:, :3]
        radius = self.probe_radius * probe_pelvis["scale"]
        triangle = faces[self.planned_face]
        geometry = face_incenter(triangle)
        require(geometry is not None, "Observed target triangle is degenerate")
        _, unit_normal, _ = geometry
        plane = (points - triangle[0]) @ unit_normal
        projection = points - plane[:, None] * unit_normal
        edges = np.roll(triangle, -1, axis=0) - triangle
        signed_edges = (np.cross(edges[None], projection[:, None] - triangle[None]) @ unit_normal
                        / np.linalg.norm(edges, axis=1))
        margin = float(min((radius - abs(plane)).min(), signed_edges.min()) if near
                       else triangle_distance(points, faces).min() - radius)
        return {"valid": margin >= MIN_MARGIN, "marginGU": margin,
                "probePoints": points.tolist(), "targetTriangle": triangle.tolist(), "probeRadiusGU": radius}


def packed_geometry(raw, shape):
    _, _, types, indices, blocks, _ = container(raw)
    raw_shape = blocks[shape.id]
    extra, = struct.unpack_from("<I", raw_shape, 4)
    skin, = struct.unpack_from("<I", raw_shape, 88 + 4 * extra)
    data, partition, _, count = struct.unpack_from("<4I", blocks[skin])
    require([types[indices[i]] for i in (skin, data, partition)] ==
            ["NiSkinInstance", "NiSkinData", "NiSkinPartition"] and count == 4,
            "Pinned FSMP skin block layout differs")
    packed = blocks[partition]
    require(struct.unpack_from("<IIIQ", packed) == (1, 886 * 40, 40, 1600890815710218),
            "Pinned FP16 layout differs")
    weights = np.zeros((len(shape.verts), len(NAMES)))
    vertices = []
    for i, native in enumerate(shape.verts):
        offset = 20 + i * 40
        vertex = struct.unpack_from("<3f", packed, offset)
        require(vertex == native, "Packed/native vertex correspondence differs")
        values = struct.unpack_from("<4e4B", packed, offset + 28)
        vertices.append(vertex)
        for weight, index in zip(values[:4], values[4:], strict=True):
            require(0 <= weight <= 1 and index < count, "Invalid packed influence")
            weights[i, NAMES.index(shape.bone_names[index])] += weight
    return np.asarray(vertices), weights


def load(aim_path, peer_path, surface_path, skeleton_path, pynifly, family):
    """Validate and read the exact original file inputs before opening a game session."""
    aim = json.loads(aim_path.read_bytes())
    planned = aim["fsmpTrialAim"]
    peer = json.loads(peer_path.read_bytes())
    surface = json.loads(surface_path.read_bytes())
    target = surface["families"][family]
    require(surface["status"] == "verified-offline-surface-binding-and-source-eligibility-only"
            and hashlib.sha256(surface_path.read_bytes()).hexdigest() == planned["surfaceReportSha256"]
            and target["strictEndpointByteEquivalence"] is True
            and target["endpoints"][0]["sha256"] == target["endpoints"][1]["sha256"] == aim["nifSha256"],
            "The selected family does not match the retained collision aim and endpoints")
    points, radius, peer_sha = read_pinned_probe(peer_path)
    require(peer_sha == planned["peerReportSha256"] and peer["skinBone"] == PELVIS
            and planned["gameQualified"] is False, "Wrong retained probe or pose")
    for relative, expected in surface["files"].items():
        if relative.startswith(family + "/"):
            pinned_file(surface_path.parent, relative, expected)
    nif_path = Path(target["endpoints"][0]["path"]).resolve()
    nif_path = pinned_file(surface_path.parent, nif_path.relative_to(surface_path.parent.resolve()), aim["nifSha256"])
    tri_path = pinned_file(nif_path.parent, "malebodywerewolf.tri", target["triSha256"])
    require(hashlib.sha256(skeleton_path.read_bytes()).hexdigest() == aim["skeletonSha256"], "Skeleton input changed")
    for relative in ("pyn/pynifly.py", "NiflyDLL.dll", "tri/tripfile.py"):
        expected, = [value for name, value in peer["inputs"].items()
                     if name.replace("\\", "/").endswith("/" + relative)]
        pinned_file(pynifly, relative, expected)
    api, trip, api_path = load_pynifly(pynifly)
    require(Path(api.__file__).resolve() == (api_path / "pyn/pynifly.py").resolve(), "Wrong already loaded PyNifly")
    morphs = trip.from_filepath(str(tri_path))
    require(morphs.is_valid and morphs.shapes.get("genitals"), "The retained surface morph catalog differs")
    morph_names = tuple(sorted(morphs.shapes["genitals"]))
    require(len(morph_names) == 6, "Unexpected number of contact surface morph channels")
    nif = api.NifFile(str(nif_path))
    shape, = [shape for shape in nif.shapes if shape.name == "genitals"]
    require(set(shape.bone_names) == set(NAMES), "Actual contact bone palette differs")
    vertices, weights = packed_geometry(nif_path.read_bytes(), shape)
    local_points = np.stack([np.c_[vertices, np.ones(len(vertices))] @
                             matrix(shape.get_shape_skin_to_bone(name)).T for name in NAMES], axis=1)
    local_points *= weights[:, :, None]
    faces = np.asarray(shape.tris)
    retained = np.flatnonzero((weights[faces, 1:] > np.finfo(np.float32).eps).any(axis=(1, 2)))
    require(len(retained) == planned["providerFaceCount"], "Unexpected retained face count")
    verify_face_digest(retained, planned["providerFaceIndicesSha256"])
    probe_nif = api.NifFile(str((peer_path.parent / "payload" / peer["mesh"]).resolve()))
    probe_shape, = probe_nif.shapes
    bind = matrix(probe_shape.get_shape_skin_to_bone(PELVIS))
    require(np.array_equal(points, np.asarray(probe_shape.verts))
            and probe_shape.bone_names == [PELVIS] and np.array_equal(bind, np.eye(4)),
            "Probe geometry no longer follows its single claimed pelvis frame")
    skel = api.NifFile(str(skeleton_path))
    rest = np.stack([matrix(skel.nodes[name].global_transform) for name in NAMES])
    rest_points = np.einsum("bij,vbj->vi", rest, local_points)[:, :3]
    driver, selection = next((name, choice) for name, choice in planned["drivers"].items() if choice is not None)
    selected = selection["face"]
    near_face, = np.flatnonzero(retained == selected)
    require(faces[selected].tolist() == selection["indices"]
            and (weights[faces[selected], NAMES.index(driver)] > np.finfo(np.float32).eps).all(),
            "Planned face or dynamic owner changed")
    center, normal, inradius = face_incenter(rest_points[faces[selected]])
    sign = 1 if normal @ selection["normal"] > 0 else -1
    require(abs(inradius - selection["faceInradius"]) < .005 and
            np.linalg.norm(center + sign * normal * radius / 4 - selection["near"]) < .03,
            "Raw packed rest reconstruction disagrees with the pinned plan")
    return Geometry(faces[retained], int(near_face), local_points, np.c_[points, np.ones(len(points))],
                    radius, sign, driver, FAMILIES[family], peer["configuration"], peer["tagMismatchControl"], morph_names,
                    {"family": family, "face": selected, "retainedFaceCount": len(retained),
                     "targetNifSha256": aim["nifSha256"], "peerReportSha256": peer_sha,
                     "surfaceReportSha256": planned["surfaceReportSha256"],
                     "poseModel": "raw FP16 weights and native skin-to-bone applied to observed world nodes"})
