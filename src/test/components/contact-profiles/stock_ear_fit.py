"""Fit the admitted stock VR player's split-ear contact slot in live bone space."""

from pathlib import Path
import struct
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vr-body"))
from avatar_ear_stereo import ADDON, BASE, CELL, EAR_SHAPE, ITEM, PLAYER, RACE, ear_frames, normalized
from avatar_torso import observation_plan
from posed_contact import Skin, breast_rig, contact_fit, offsets, pinned_asset, require


SCHEMA = "claw-vr-stock-ear-contact-pose/1"
TRI = r"actors\werewolfbeast\claw\firstperson\male\earworldtrial.tri"
MODEL = r"actors\werewolfbeast\character assets\malebodywerewolf_1.nif"
NODE = "NPC EarL [EarL]Bone01"
SLOT = 91


def fit_stock_ear(model, reply, *, pid, nonce, handle, pynifly=None):
    """Use the pinned split mesh, exact TRI records and the co-sampled effective morphs."""
    sample, gate = reply["sample"], reply["worldGate"]
    require(reply["schema"] == SCHEMA and reply["status"] == "ready" and reply["pid"] == pid
            and reply["nonce"] == nonce and gate["generation"] == reply["epoch"] and gate["loading"] is False
            and sample["phase"] == "PostVrikPostHiggs" and sample["handle"] == handle
            and (sample["player"], sample["base"], sample["race"], sample["cell"], sample["sex"])
            == (PLAYER, BASE, RACE, CELL, 0), "Expected the current stock male wolf player")
    begin, end, frequency = (sample[name] for name in ("qpcBegin", "qpcEnd", "qpcFrequency"))
    require(all(type(value) is int for value in (begin, end, frequency)) and frequency > 0
            and 0 < begin < end <= begin + 3 * frequency
            and gate["postPhaseCount"] >= sample["phaseSequence"] > gate["armedAfterPhase"],
            "Expected a bounded current post-VRIK/HIGGS pose interval")
    weight = sample["rawWeight"]
    biped = sample["biped"]
    require(type(weight) in (int, float) and 0 <= weight <= 100 and normalized(sample["earBodyTri"]) == TRI
            and (biped["slot"], biped["item"], biped["addon"]) == (32, ITEM, ADDON)
            and normalized(biped["modelPath"]) == MODEL, "Expected the stock Body32 and its split-ear TRI")
    slot = model["slots"][SLOT]
    region = model["regions"]["male/" + NODE]
    source, = region["sources"]
    part = slot["partition"]
    partition, triangles = slot["male"]["partitionIndices"], slot["male"]["triangleIndices"]
    require(slot["node"] == NODE and source["shape"] == EAR_SHAPE
            and partition == region["partitions"][part] and triangles == region["triangleGroups"][part],
            "The selected ear slot differs from its authored split-ear region")
    mesh, _ = pinned_asset(model, "male.nif")
    _, tri = pinned_asset(model, "male.tri")
    api, _, _ = breast_rig.load_pynifly(pynifly)
    shape = api.NifFile(str(mesh)).shape_dict[EAR_SHAPE]
    records = {key: value for key, value in offsets(tri).items() if key[0] == EAR_SHAPE}
    plan = observation_plan(shape, records)
    require((plan["vertices"], plan["triangles"]) == (1354, 2394)
            and (sample["earVerticesObserved"], sample["earTrianglesObserved"]) == (1354, 2394),
            "Wrong split-ear topology")
    skin = Skin(shape, records, sample["earEffectiveMorphs"])
    vertices = np.asarray(source["vertices"], dtype=int)
    faces = np.asarray(region["faces"], dtype=int)[triangles]
    exact_faces = np.asarray(source["sourceTriangleIndices"], dtype=int)[triangles]
    require(np.array_equal(vertices[faces], skin.faces[exact_faces]), "Ear slot no longer maps to the authored triangles")
    selected_vertices = vertices[partition]
    influential = np.any(skin.weights[selected_vertices] > 0, axis=0)
    selected_bones = [name for name, active in zip(skin.names, influential, strict=True) if active]
    frames = ear_frames({**plan, "bones": selected_bones}, sample)
    support = skin.support(selected_vertices, frames, NODE)
    capsule = contact_fit.capsule(support, region["padding"])
    provider_geometry = struct.unpack("<7f", struct.pack("<7f", *capsule["p1"], *capsule["p2"], capsule["radius"]))
    return {"slot": SLOT, "node": NODE, "geometry": provider_geometry, "vertices": len(partition),
            "triangles": len(triangles), "actorWeight": weight, "morphs": sample["earEffectiveMorphs"]}
