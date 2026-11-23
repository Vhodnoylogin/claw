"""Stage two isolated VR self-contact configuration arms outside the game."""

import argparse
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path
import struct
import sys


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src/test/python/physics"))
from cbpc_event_readback import PLAYER_BODY_CONTACT_NODES, require


MASTER = "CBPCMasterConfig.txt"
COLLISION = "CBPCollisionConfig.txt"
PROFILE_SHA = "b4e08b9f81dd31566e9308087639268ee97f58d6b2c8c240736dafde6a977970"
BASELINES = {
    MASTER: "f5e451e22dc3e33f066ce44a52e853d308afadf4eb66a3165d9600ca7ce43a8a",
    COLLISION: "c401c1f58b899a39f1a3841e39d31d2b61ac470118aea1f7fcc766ece7c323c8",
    "CBPCPlayerCollisionEventConfig.txt": "aa5566c1c968b9f5eac435b7f7e9d5bc372367495e6716c322e2f97892048ecc",
    "CBPConfig_CLAWCBPCBench.txt": "c2bcb9de0396f0f6003e3de6e1b87f74bb5301607e7929e9d731baf757367975",
    "CBPWeaponCollisionConfig.txt": "d2a2306a1c4ad7bdf2163c7d386cc4c270cb25a0eb78d8a9744116dd99e8c2b0",
    "CBPCollisionConfig_Yuriana.txt": "a6bfea67d8612e82d08d635511060c6c875819938923baaa8e476b67be17c33b",
    "CBPCSystem.ini": "dc97156901e3874f38e2c2c5d0fd4e88fcf1fd1a36f46c6f40eeaf01734e0cf7",
}
OLD_ROW = ("TailBone02=CLAW_CBPCBenchTail=IsRaceFormId(Skyrim.esm|0CDD84) AND IsMale() AND "
           "IsActorBase(test_CLAW - VR CBPC Contact Fixture.esp|000800)")


def pinned(path, digest):
    payload = path.read_bytes()
    require(sha256(payload).hexdigest() == digest, f"Input hash changed: {path}")
    return payload


def replace_row(payload, before, after):
    lines = payload.decode("ascii").splitlines()
    require(lines.count(before) == 1, f"Unexpected single-node CBPC row: {before}")
    lines[lines.index(before)] = after
    return ("\n".join(lines) + "\n").encode("ascii")


def neutral_capsules(profile, slots):
    neutral, = (fixture for fixture in profile["fixtures"] if fixture["name"] == "neutral" and fixture["weight"] == 0.0)
    require(neutral["values"] == {}, "Expected zero morphs in the neutral fixture")
    members = {}
    for sex in ("male", "female"):
        source = neutral["sexes"][sex]["capsules"]
        capsules = []
        for slot in slots:
            capsule = source[slot]
            shape = struct.unpack("<7f", struct.pack("<7f", *capsule["p1"], *capsule["p2"], capsule["radius"]))
            require(all(map(isfinite, shape)) and shape[-1] > 0, "Invalid neutral fixture capsule")
            capsules.append({"slot": slot, "colliderIndex": 0x434C0000 + slot, "geometry": list(shape)})
        members[sex] = capsules
    return members


def stage(baseline, profile_path, output):
    inputs = {name: pinned(baseline / name, digest) for name, digest in BASELINES.items()}
    profile = json.loads(pinned(profile_path, PROFILE_SHA))
    output = output.resolve()
    require(output != ROOT and ROOT not in output.parents and
            not {"data", "mods", "overwrite", "profiles"} & {part.casefold() for part in output.parts},
            "Choose a detached staging directory")
    stages = {}
    archives = {}
    for label, node in (("left-ear", "NPC EarL [EarL]Bone01"), ("tail", "TailBone02")):
        slots = PLAYER_BODY_CONTACT_NODES[node]
        require(tuple(i for i, row in enumerate(profile["slots"]) if row["node"] == node and row["sexMask"] == "both") == slots,
                "Equipped profile does not match both-sex single-node slots")
        master = replace_row(inputs[MASTER], OLD_ROW, f"{node}=CLAW_CBPCBenchTail=IsRaceFormId(Skyrim.esm|0CDD84) AND IsPlayer()")
        collision = replace_row(inputs[COLLISION], "TailBone02", node)
        archives[label] = members = {**inputs, MASTER: master, COLLISION: collision}
        stages[label] = {"node": node, "slots": list(slots), "capsuleTarget": "affected",
                         "capsules": neutral_capsules(profile, slots),
                         "files": {name: sha256(data).hexdigest() for name, data in members.items()}}
    receipt = {"schema": "claw-vr-player-contact-config/1", "profileSha256": PROFILE_SHA,
               "modelIdentity": profile["modelIdentity"], "actor": "0x00000014", "source": "LeftWandNode",
               "sourceSphere": [0, -6, -2, 3], "minimumEngineDuration": .3, "fixtureWeight": 0, "fixtureMorphs": "zero",
               "inputHashes": BASELINES, "arms": stages, "runtimeChecked": False}
    output.mkdir(parents=True, exist_ok=False)
    for label, members in archives.items():
        plugins = output / label / "SKSE/Plugins"
        plugins.mkdir(parents=True, exist_ok=False)
        for name, blob in members.items():
            (plugins / name).write_bytes(blob)
    (output / "RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="Pinned isolated NPC subject SKSE/Plugins directory")
    parser.add_argument("--profile", type=Path, required=True, help="Pinned equipped fitted-capsules.json")
    parser.add_argument("--out", type=Path, required=True, help="Fresh detached staging directory")
    args = parser.parse_args()
    print(json.dumps(stage(args.baseline, args.profile, args.out), indent=2))
