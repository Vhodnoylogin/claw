"""Compose both private VR player-contact arms for offline installation review."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZipFile

from stage_player_contact import pinned, require
from player_contact_custody import (
    BODY_DIR, BODY_MEMBERS, BODY_PLUGIN, BODY_SHA, CONFIG_SHA, INHERITED_CONFIGS, ISOLATED_ABSENCES, MODULES, PLUGINS, SCRIPTS,
    SKELETON_PATH, SKELETON_SHA, resources,
)
from retarget_player_contact import CUE_SHA


OBSERVERS_SHA = "0f8c3a6b9caa423a7bf2ee7ba883175df7a4616928dd1b52aa1df6821cb43380"
ARM_SHA = {
    "left-ear": "04e0633a0599fd7ef079453a53a0323724f10f29d68d0bdeb3b6a4d9c280c16d",
    "tail": "baf570b4fc354464a3e51a07ca82befeb461f148efa0b56ef599ea75a561e50b",
}
TOPOLOGY = "CLAWVRModelTopology"
EVENTS = "CLAWVRPlayerCBPCEvents"


def binary_paths(module):
    return (PLUGINS + module + ".dll", "Scripts/" + module + ".pex")


def extract(blob, expected):
    with ZipFile(BytesIO(blob)) as archive:
        names = archive.namelist()
        require(set(names) == expected and len(names) == len(expected), "Unexpected or duplicate ZIP members")
        return {name: archive.read(name) for name in names}


def pin_bytes(data):
    return {"sha256": sha256(data).hexdigest(), "bytes": len(data)}


def external_dependencies(root, skeleton):
    refs = {
        PLUGINS + "cbp.dll": (root / PLUGINS / "cbp.dll", MODULES["cbp.dll"]),
        "Scripts/CBPCPluginScript.pex": (root / "Scripts/CBPCPluginScript.pex", SCRIPTS["Scripts/CBPCPluginScript.pex"]),
        SKELETON_PATH: (skeleton, SKELETON_SHA),
    }
    return {name: {"origin": str(path.resolve()), **pin_bytes(pinned(path, digest))} for name, (path, digest) in refs.items()}


def stage_inputs(args):
    config = json.loads(pinned(args.config, CONFIG_SHA))
    body = pinned(args.body, BODY_SHA)
    body_members = {BODY_PLUGIN, *(f"{BODY_DIR}/{sex}/{name}" for sex in ("male", "female") for name in BODY_MEMBERS)}
    common = extract(body, body_members)
    observers = extract(pinned(args.observers, OBSERVERS_SHA),
                        {*binary_paths(TOPOLOGY), *binary_paths("CLAWVREquippedEarPose")})
    common.update((path, observers[path]) for path in binary_paths(TOPOLOGY))
    for name, digest in INHERITED_CONFIGS.items():
        common[PLUGINS + name] = pinned(args.provider_reference / PLUGINS / name, digest)
    inherited = external_dependencies(args.provider_reference, args.skeleton)
    all_arms = {}
    for arm, path in (("left-ear", args.left_ear), ("tail", args.tail)):
        arm_files = {PLUGINS + name for name in config["arms"][arm]["files"]} | set(binary_paths(EVENTS))
        arm_entries = extract(pinned(path, ARM_SHA[arm]), arm_files)
        require(not arm_entries.keys() & common.keys(), "Contact arm would replace a shared member")
        members = common | arm_entries
        member_pins = {name: pin_bytes(data) for name, data in members.items()}
        inventory = {name.casefold(): pin["sha256"] for name, pin in (member_pins | inherited).items()}
        for sex in ("male", "female"):
            expected, configs = resources(config, body, arm, sex)
            observation = (PLUGINS + "SkyrimWorldObserver.dll").casefold()
            require(all(inventory.get(name) == digest for name, digest in expected.items() if name != observation),
                    "Staged fixture and actual replay requirements differ")
            require({Path(name).name.casefold() for name in members if name.startswith(PLUGINS + "CBP") and name.endswith(".txt")} == configs,
                    "Staged CBP configuration inventory differs from replay expectations")
        all_arms[arm] = members, member_pins
    return config, inherited, all_arms


def compose(args):
    out = args.out.resolve()
    require(not {"data", "mods", "overwrite", "profiles"} & {part.casefold() for part in out.parts},
            "Choose a detached staging directory")
    config, dependencies, arms = stage_inputs(args)
    cues = pinned(args.cues, CUE_SHA)
    out.mkdir(parents=True, exist_ok=False)
    (out / "REFERENCE-MOVEMENT.json").write_bytes(cues)
    report = {"schema": "claw-vr-player-contact-detached-subject/1", "installed": False, "gameValidated": False,
              "target": "Skyrim VR", "condition": "Equipped wolf player; neutral reference capsules; actor weight zero",
              "fixture": {"plugin": BODY_PLUGIN, "actor": "0x00000014", "race": "Skyrim.esm|0CDD84",
                          "fixtureArmorLocalId": "000801", "fixtureArmorAddonLocalId": "000800", "weight": 0},
              "independentDependencies": dependencies, "mustBeAbsent": list(ISOLATED_ABSENCES),
              "movementReference": {"file": "REFERENCE-MOVEMENT.json", **pin_bytes(cues)}, "arms": {}}
    for arm, (members, pins) in arms.items():
        data = out / arm / "subject" / "Data"
        for name, payload in members.items():
            target = data / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            require(pin_bytes(target.read_bytes()) == pins[name], "Detached fixture readback differs")
        report["arms"][arm] = {"data": str(data), "members": pins, "slots": config["arms"][arm]["slots"],
                               "receiver": config["arms"][arm]["node"], "source": config["source"]}
    target = out / "SUBJECT-STAGING.json"
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return target


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("config", "body", "observers", "left-ear", "tail", "provider-reference", "skeleton", "cues", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    print(compose(parser.parse_args()))
