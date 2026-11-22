"""Build a detached SE contact test composition and read its installed baseline."""

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct
import subprocess

from build_contact_peer import verify_plugin as verify_peer_plugin
from fsmp_contact_pose import FAMILIES, MIN_MARGIN, load, pinned_file
from fsmp_contact_windows import require


ROOT = Path(__file__).resolve().parents[4]
ACTORS = "test_CLAW - FSMP Contact Actors.esp"
PEER = "test_CLAW - FSMP Contact Peer.esp"
AUTHORING = ROOT / "src/test/resources/physics/fsmp-contact-peer/actors"
BODY = "Meshes/Actors/WerewolfBeast/Character Assets/"
MORPH_XML = "SKSE/Plugins/CLAW/MorphLinks.xml"
BODY_FAMILY = "SKSE/Plugins/CLAW/BodyFamilyBindings.xml"
DIAGNOSTIC_DLL = "provider/src/hdtsmp64.dll"
DIAGNOSTIC_PEX = "papyrus/CLAWFSMPPairContact.pex"
TRANSLATOR_SHA = "a7b4d65e0916e0f11d1530458e7e973d9bb4df887b486177275185199c9532f8"
STOCK_PROVIDER_SHA = "5290e2a8c3ddc4c13fecfd08234ff455f50c6a9ca42dcd381cde158631446672"

spec = importlib.util.spec_from_file_location(
    "claw_contact_fixture_reader", ROOT / "src/test/resources/physics/human-origin-lifecycle/build_fixture.py")
records = importlib.util.module_from_spec(spec)
spec.loader.exec_module(records)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text(data):
    require(data.endswith(b"\0") and b"\0" not in data[:-1], "Invalid ESP string")
    return data[:-1].decode("ascii")


def fields(row):
    return records.inputs.subrecords(row[3])


def check_actors(data):
    entities = list(records.binary.records(data))
    require(Counter(row[0] for row in entities) == {b"TES4": 1, b"NPC_": 2, b"OTFT": 1}
            and all(row[2] == 0 for row in entities), "Unexpected actor fixture records or flags")
    by_id = {row[1]: row for row in entities}
    require(set(by_id) == {0, 0x02000800, 0x02000801, 0x02000802}, "Fixture records must be new full-plugin forms")
    require([text(value) for value in fields(by_id[0])["MAST"]] == ["Skyrim.esm", PEER], "Fixture masters differ")
    for local, name, race in ((0x800, "CLAWTestFSMPContactSurface", 0xCDD84), (0x801, "CLAWTestFSMPContactPeerActor", 0x13746)):
        npc = fields(by_id[0x02000000 | local])
        common = {"EDID", "OBND", "ACBS", "VTCK", "RNAM", "AIDT", "CNAM", "FULL", "DATA",
                  "NAM5", "NAM6", "NAM7", "NAM8", "QNAM"}
        require(set(npc) == common | ({"DOFT"} if local == 0x801 else {"CSCR"}), "Fixture actor has extra behavior or state")
        require(text(records.single(npc, "EDID")) == name
                and struct.unpack_from("<I", records.single(npc, "ACBS"))[0] == 0x12
                and records.single(npc, "RNAM") == struct.pack("<I", race)
                and records.single(npc, "NAM6") == struct.pack("<f", 1.)
                and records.single(npc, "NAM7") == struct.pack("<f", 50.),
                "Fixture sex, race, essential state, weight or height differs")
        if local == 0x801:
            require(records.single(npc, "DOFT") == struct.pack("<I", 0x02000802), "Peer's default outfit differs")
    outfit = fields(by_id[0x02000802])
    require(set(outfit) == {"EDID", "INAM"} and text(records.single(outfit, "EDID")) == "CLAWTestFSMPContactOutfit"
            and records.single(outfit, "INAM") == struct.pack("<I", 0x01000801),
            "The peer outfit must contain only the reviewed probe accessory")
    return {"actors": 2, "newOutfits": 1, "placedReferences": 0, "overrides": 0, "maleActorWeight": 50.,
            "targetNpcLocal": "000800", "probeNpcLocal": "000801", "probeOutfitLocal": "000802", "probeArmorLocal": "000801"}


def active_baseline(mo2):
    settings = mo2 / "ModOrganizer.ini"
    selected, = re.findall(rb"(?m)^selected_profile=@ByteArray\(([^\r\n()]+)\)\r?$", settings.read_bytes())
    profile = mo2 / "profiles" / selected.decode("utf-8")
    require(profile.is_dir() and profile.resolve().parent == (mo2 / "profiles").resolve(), "Invalid selected test profile")
    profile_files = [profile / name for name in ("modlist.txt", "plugins.txt", "loadorder.txt")]
    modlist, plugins, _ = [path.read_text(encoding="utf-8-sig").splitlines() for path in profile_files]
    require("*CLAW.esp" in plugins and all("*" + name not in plugins for name in (ACTORS, PEER)),
            "Expected current CLAW base and detached contact fixture")
    active = [row[1:] for row in modlist if row.startswith("+")]
    require(len(active) == len(set(active)) and all(Path(name).name == name for name in active), "Invalid test mod list")
    return profile, [settings, *profile_files], [mo2 / "overwrite", *(mo2 / "mods" / name for name in active)]


def winner(relative, roots):
    providers = [base / relative for base in roots if (base / relative).is_file()]
    require(providers, "Installed baseline has no file for " + relative)
    return providers[0]


def run_tool(out, label, argv):
    result = subprocess.run([str(arg) for arg in argv], input=b"", capture_output=True, timeout=60)
    (out / (label + ".stdout")).write_bytes(result.stdout)
    (out / (label + ".stderr")).write_bytes(result.stderr)
    require(result.returncode == 0, "Offline tool failed: " + label)
    return result.stdout


def emit(out, destination, files):
    for relative, path in files.items():
        target = out / destination / relative
        require(target.resolve().is_relative_to((out / destination).resolve()) and not target.exists(),
                "Duplicate or unsafe output path")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())


def build(pose_inputs, diagnostic, mo2, game, translator, matrix, family, out):
    require(not out.exists() and not out.is_relative_to(mo2.resolve()) and not out.is_relative_to(game.resolve())
            and not out.is_relative_to(ROOT), "Create a fresh external composition outside game and MO2")
    require(sha(translator.read_bytes()) == TRANSLATOR_SHA, "Expected the retained offline Spriggit translator shim")
    configured = json.loads(pose_inputs.read_bytes())
    peer_dir, surface = Path(configured["peer"]), Path(configured["surface"])
    peer_path, aim_path = peer_dir / "peer-report.json", peer_dir / (family + "-aim.json")
    geometry = load(aim_path, peer_path, surface, Path(configured["skeleton"]), Path(configured["pynifly"]), family)
    source = json.loads(surface.read_bytes())
    target_files = {name.split("/", 1)[1]: pinned_file(surface.parent, name, digest)
                    for name, digest in source["files"].items() if name.startswith(family + "/")}
    require(set(target_files) == {FAMILIES[family], *(BODY + "malebodywerewolf" + suffix for suffix in ("_0.nif", "_1.nif", ".tri"))},
            "Unsupported subject payload")
    peer = json.loads(peer_path.read_bytes())
    fixture_files = {name: pinned_file(peer_dir / "payload", name, value) for name, value in peer["files"].items()}
    verify_peer_plugin(fixture_files[PEER].read_bytes())
    native = json.loads(diagnostic.read_bytes())
    require(native["status"] == "offline-collector-built-exact-pinned-framework" and native["nativeBuildExit"] == 0
            and native["papyrusBuildExit"] == 0 and native["compiledWithOptionOn"] is True,
            "Exact FSMP contact diagnostic build evidence required")
    platform_overlay = {"SKSE/Plugins/hdtsmp64.dll": pinned_file(diagnostic.parent, DIAGNOSTIC_DLL, native["artifactSha256"][DIAGNOSTIC_DLL]),
                        "Scripts/CLAWFSMPPairContact.pex": pinned_file(diagnostic.parent, DIAGNOSTIC_PEX, native["artifactSha256"][DIAGNOSTIC_PEX])}

    profile, profile_files, roots = active_baseline(mo2)
    baseline = {name: winner(name, roots) for name in (
        "CLAW.esp", "SKSE/Plugins/CLAWDistribution.dll", MORPH_XML, BODY_FAMILY, BODY + "skeleton.nif",
        BODY + "malebodywerewolf.tri", "Meshes/Actors/Character/Character Assets/skeleton.nif",
        "SKSE/Plugins/hdtsmp64.dll", "SKSE/Plugins/skee64.dll")}
    require(sha(baseline[BODY + "skeleton.nif"].read_bytes()) == sha(Path(configured["skeleton"]).read_bytes())
            and sha(baseline[BODY + "malebodywerewolf.tri"].read_bytes()) == source["families"][family]["triSha256"]
            and sha(baseline["SKSE/Plugins/hdtsmp64.dll"].read_bytes()) == STOCK_PROVIDER_SHA,
            "The selected installed skeleton/TRI/provider baseline differs")
    arma, = [row for row in records.binary.records(baseline["CLAW.esp"].read_bytes())
             if row[0] == b"ARMA" and row[1] == 0xCDD87]
    expect_path = (BODY + "malebodywerewolf_1.nif").removeprefix("Meshes/")
    require(text(records.single(fields(arma), "MOD2")).replace("\\", "/").casefold() == expect_path.casefold()
            and records.single(fields(arma), "RNAM") == struct.pack("<I", 0xCDD84),
            "Active CLAW plugin does not author the intended stock male werewolf armor addon")

    inputs = [pose_inputs, peer_path, aim_path, surface, diagnostic, translator, matrix,
              game / "SkyrimSE.exe", game / "Data/Skyrim.esm",
              *profile_files, *baseline.values(), *target_files.values(), *fixture_files.values(), *platform_overlay.values(),
              *[path for path in AUTHORING.rglob("*") if path.is_file()], Path(__file__)]
    pins = {str(path.resolve()): sha(path.read_bytes()) for path in inputs}
    out.mkdir()
    actor_build = out / "actor-build"
    actor_build.mkdir()
    esp = actor_build / ACTORS
    run_tool(actor_build, "compile", [translator, "deserialize", "-i", AUTHORING, "-o", esp, "-t", 1])
    composition_actors = check_actors(esp.read_bytes())
    readback = actor_build / "readback"
    flags = ["-p", "Spriggit.Yaml", "-v", "0.41.0", "-t", 1]
    run_tool(actor_build, "readback", [translator, "serialize", "-i", esp, "-o", readback, "-g", "SkyrimSE", *flags])
    rebuilt = actor_build / "roundtrip" / ACTORS
    rebuilt.parent.mkdir()
    run_tool(actor_build, "rebuild", [translator, "deserialize", "-i", readback, "-o", rebuilt, *flags])
    require(esp.read_bytes() == rebuilt.read_bytes(), "Spriggit actor round trip changed bytes")
    fixture_files[ACTORS] = esp

    family_proof = json.loads(run_tool(out, "default-family", [matrix, "body-family", baseline[MORPH_XML],
                                                              baseline[BODY_FAMILY], "male", "--source-unobserved"]))
    require(family_proof["sourceObserved"] is False and family_proof["blocked"] is False and family_proof["reason"] == "default",
            "No eligible default installed matrix for the originally-beast actor")
    values = json.loads(run_tool(out, "neutral-six-targets", [matrix, "matrix", baseline[MORPH_XML],
                                                             family_proof["profile"], "--actor-weight-raw", 50]))
    require(all(type(values.get(name)) in (int, float) and values[name] == 0 for name in geometry.morphs),
            "Installed default matrix does not keep the six test channels neutral")

    groups = {"subject/Data": target_files, "fixture/Data": fixture_files, "platform-review/Data": platform_overlay}
    manifests = {}
    for group, files in groups.items():
        emit(out, group, files)
        manifests[group] = {name: sha((out / group / name).read_bytes()) for name in files}
    require(all(sha(Path(path).read_bytes()) == digest for path, digest in pins.items()), "Inputs changed during composition")

    subject_only = {
        "family": family, "testCell": "QASmoke", "geometry": geometry.identity, "poseBracketMinimumGapGU": MIN_MARGIN,
        "fixture": {"plugin": ACTORS, **composition_actors, "peerAccessoryPlugin": PEER, "targetRace": "000CDD84",
                    "peerRace": "00013746", "surfaceArmorAddon": "000CDD87", "peerAddonLocal": "000800",
                    "placementOffsetsGU": {"surface": {"forward": 120, "right": -45}, "peer": {"forward": 120, "right": 45}}},
        "defaultProfile": family_proof["profile"], "neutralTargets": {name: values[name] for name in geometry.morphs},
        "nativeMatrixInputs": {"originallyBeastNoObservedHumanMorphs": True, "weight": 50., "profileChanged": False},
        "requiredResults": ["separated-start", "tag-mismatch-overlap", "reciprocal-overlap", "separated-return", "owned-cleanup"],
        "testStart": "first completed separated contact-trial measurement, after fixture/model/provider admission",
        "paths": {k: manifests[k] for k in ("subject/Data", "fixture/Data")},
    }
    (out / "subject-and-fixture.json").write_text(json.dumps(subject_only, indent=2) + "\n", encoding="utf-8")
    report = {
        "status": "offline-composition-and-installed-baseline-readback-verified", "installed": False, "gameStarted": False,
        "liveEquipmentVerified": False, "liveNeutralAggregatesVerified": False, "contactQualified": False,
        "gameInstall": str(game), "selectedSourceProfile": str(profile),
        "baselineMethod": "Offline active MO2 priority/readback, no live VFS claims",
        "baselineFilePins": {name: {"path": str(path.resolve()), "sha256": pins[str(path.resolve())]}
                             for name, path in baseline.items()},
        "incomingOverlay": manifests, "actorRoundtripByteEqual": True, "inputPins": pins,
        "platformReview": {"digestMatchesInstalledStock": True, "installedDiagnostic": False,
                           "qualifiedThisComposition": False, "mustStayOutOfSubjectOrder": True},
        "unfinished": ["Platform admission", "Live VFS identity and two owned actor witnesses",
                       "Effective default outfit/registered probe shell and six live SKEE aggregates",
                       "Four contact windows and original states/physical restoration"],
    }
    (out / "composition-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("pose-inputs", "diagnostic", "mo2", "game", "translator", "matrix", "out"):
        parser.add_argument("--" + key, type=lambda arg: Path(arg).resolve(), required=True)
    parser.add_argument("--family", choices=tuple(FAMILIES), default="anatomy3")
    args = parser.parse_args()
    result = build(**vars(args))
    print(result["status"])
