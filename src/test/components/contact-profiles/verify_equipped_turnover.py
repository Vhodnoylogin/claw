"""Verify a stock -> equipped -> stock wolf-player collider handoff offline."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from verify_pose_ack import selected_receipts, unique_object, unit, verify as verify_ack
from verify_pose_contact_window import CLOCK, CONTROL, TICKS_PER_US
from verify_tail_refit import NATIVE, QPC, ordered, positive_int, require, typed

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "vr-body"))
from verify_dispatch_markers import ADDON, BODY, ITEM, SCHEMA as TOPOLOGY_SCHEMA, verify_dispatch_markers


SCHEMA = "claw-vr-equipped-contact-turnover/1"
TOPOLOGY = "CLAWVRModelTopology"
EAR_POSE = "CLAWVREquippedEarPose"
EAR_SCHEMA = "claw-vr-vrik-ear-stereo/2"
EAR_MORPHS = {"CLAWHeadEarSize", "CLAWHeadEarTilt", "CLAWHeadMuzzleLong", "CLAWHeadMuzzleWide", "CLAWHeadSize"}
FIXTURE_PLUGIN = "test_CLAW - VR Player Body32.esp"
ACTOR_ID = 0x14
ACTOR = {"form": "0x00000014"}
PHASES = ("stock", "equipped", "restored")
TRANSITIONS = {"stock": "EquipItem", "equipped": "UnequipItem"}
OBSERVATION_KEYS = ("generationRead", "currentBefore", "request", "capture", "currentAfter", "count")
DETACHMENT_KEYS = ("count", "snapshotCurrent")


def capture_pair(ledger, observation, script, method, schema, pid, nonce):
    request = json.loads(typed(ledger, observation["request"], script, method, "string", [nonce]),
                         object_pairs_hook=unique_object)
    require((request.get("schema"), request.get("pid"), request.get("nonce")) == (schema, pid, nonce) and
            request.get("status") in ("pending", "ready"), f"Missing matching {script} capture request")
    raw = json.loads(typed(ledger, observation["capture"], script, "Read", "string", [nonce]),
                     object_pairs_hook=unique_object)
    require((raw.get("schema"), raw.get("pid"), raw.get("nonce"), raw.get("status")) == (schema, pid, nonce, "ready") and
            (request["status"] == "pending" or request == raw), f"Missing ready {script} reply for the same nonce")
    return request, raw


def route(raw, subject, nonce, fixture, equipped):
    pid, epoch, base, cell, handle, sex = subject
    marker = ("W_F" if sex else "W_M") if equipped else None
    result = verify_dispatch_markers(raw, view="thirdPerson", pid=pid, nonce=nonce, epoch=epoch,
                                     expect=marker, fixture_forms=fixture)
    sample = raw["sample"]
    require((sample["base"], sample["cell"], result["actorRuntimeHandle"], result["sex"]) ==
            (base, cell, handle, sex), "Wolf player's identity, cell or sex changed")
    active, buffered = result["observations"][:2]
    require(result["captureClock"]["qpcFrequency"] == QPC, "Clock does not match the pinned ACK build")
    if equipped:
        require(result["modelOriginVerified"] and buffered["classification"] == "unloaded" and
                not (buffered["item"] or buffered["addon"] or buffered["reportedModelPath"]) and
                all(row.get("partHandlePresent") is False for row in sample["views"]["thirdPerson"]["buffered"]
                    if row["slot"] == BODY),
                "Expected exact equipped world clone with no competing buffered Body32")
    else:
        family = "female" if sex else "male"
        model = active["reportedModelPath"].replace("/", "\\").casefold().removeprefix("meshes\\")
        require(result["status"] == "unmarked" and (active["item"], active["addon"]) == (ITEM, ADDON) and
                active["clone"] != active["actorRoot"] and
                model == rf"actors\werewolfbeast\character assets\{family}bodywerewolf_1.nif",
                "Expected the exact active stock wolf body and addon")
        require(all(row["item"] != fixture[0] and row["addon"] != fixture[1] for row in result["observations"]),
                "Equipped fixture remains in a stock Body32 observation")
    return result


def phase_ack(lines, generation, token, profile, sex, clock):
    summary = verify_ack(lines, actor=ACTOR_ID, generation=generation, profile=profile, expected_tokens=[token])
    chain = [row[2] for row in selected_receipts(lines, ACTOR_ID, generation)]
    first = chain[0]
    selected = chain[-1]
    require(summary["nativeFull"] == 1 and first["application"] == "full" and selected["female"] == bool(sex),
            "Registration requires one initial full ACK for the recorded sex")
    require(selected["token"] == token and (selected["acknowledgedUs"] + 1) * TICKS_PER_US <= clock["qpcBegin"],
            "Expected a topology sample after the final ACK for this generation")
    return first, selected, summary["enabledSlots"]


def linked_ear_pose(ledger, observation, topology, route_result, ack):
    nonce = observation["nonce"]
    require(positive_int(nonce), "Invalid ear pose nonce")
    request, raw = capture_pair(ledger, observation, EAR_POSE, "Capture", EAR_SCHEMA, topology["pid"], nonce)
    pose, body = raw["sample"], topology["sample"]
    biped, active = pose["biped"], route_result["observations"][0]
    require((pose["player"], pose["base"], pose["race"], pose["cell"], pose["handle"], pose["sex"], pose["rawWeight"]) ==
            (body["actor"], body["base"], body["race"], body["cell"], body["runtimeHandle"], body["sex"], body["weight"]) and
            (biped["slot"], biped["item"], biped["addon"]) == (32, active["item"], active["addon"]) and
            biped["modelPath"].replace('/', '\\').casefold() == active["reportedModelPath"].replace('/', '\\').casefold() and
            "CLAW_VR_DISPATCH_PROBE_" + raw["body32"]["worldDispatchMarker"] == route_result["observedMarker"],
            "Ear pose does not match the equipped actor and Body32 route")
    armed, observed = request["worldGate"], raw["worldGate"]
    phase = pose["phaseSequence"]
    require(request["status"] == "pending" and pose["phase"] == "PostVrikPostHiggs" and
            armed["loading"] is observed["loading"] is False and positive_int(raw["epoch"]) and
            armed["generation"] == observed["generation"] == raw["epoch"] and
            positive_int(pose["higgsBuild"]) and armed["higgsBuild"] == observed["higgsBuild"] == pose["higgsBuild"] and
            type(phase) is int and 0 <= armed["postPhaseCount"] < phase <= observed["postPhaseCount"],
            "Ear pose does not come from a new post-VRIK/HIGGS sample in the same observer world")
    begin, end = pose["qpcBegin"], pose["qpcEnd"]
    require(pose["qpcFrequency"] == QPC and positive_int(begin) and positive_int(end) and
            route_result["captureClock"]["qpcEnd"] < begin < end and end - begin <= QPC * 4 // 1000,
            "Ear sample is outside the ordered 10 MHz capture bracket")
    morphs = pose["earEffectiveMorphs"]
    expected = {row["name"]: row["value"] for row in ack["morphs"] if row["name"] in EAR_MORPHS}
    require(set(morphs) == set(expected) == EAR_MORPHS and all(unit(value) for value in morphs.values()) and morphs == expected,
            "Ear morph values do not match the acknowledged fitter inputs")
    return {"nonce": nonce, "phase": phase, "qpcBegin": begin, "qpcEnd": end, "token": ack["token"],
            "earPoseLinked": True}


def check_detachment(ledger, indices, generation, token):
    count = typed(ledger, indices["count"], CONTROL, "GetLedgerCount", "int", [0])
    require(type(count) is int and count == 0 and
            typed(ledger, indices["snapshotCurrent"], NATIVE, "SnapshotCurrent", "bool", [ACTOR, generation, token]) is False,
            "Host ledger retirement or previous token expiry is unproven")


def fixture_forms(ledger, indices):
    forms = [typed(ledger, indices[key], "Game", "GetFormFromFile", "form", [local, FIXTURE_PLUGIN])
             for key, local in (("item", 0x801), ("addon", 0x800))]
    item, addon = (int(record["formId"], 16) for record in forms)
    require(0 < item >> 24 < 0xFE and item & 0xFFFFFF == 0x801 and addon == item - 1,
            "Expected the independently resolved exact Body32 fixture forms")
    return item, addon


def verify(manifest, ledger, ack_lines, stock, equipped):
    require(manifest["schema"] == SCHEMA and manifest["clock"] == CLOCK and set(manifest["phases"]) == set(PHASES),
            "Expected the three-phase wolf player handoff and pinned clock")
    fixture = fixture_forms(ledger, manifest["fixtureReads"])
    require(stock["modelIdentity"] != equipped["modelIdentity"], "Stock and equipped profiles must have distinct identities")
    require(typed(ledger, manifest["hostModel"], NATIVE, "GetModelIdentity", "string", []) == stock["modelIdentity"],
            "Loaded host ABI does not match the stock profile")
    indices = [manifest["fixtureReads"]["item"], manifest["fixtureReads"]["addon"], manifest["hostModel"]]
    for phase in PHASES:
        row = manifest["phases"][phase]
        indices.extend(row[key] for key in OBSERVATION_KEYS[:4])
        if "earPose" in row:
            require(phase == "equipped", "Ear sidecar accepts only the equipped phase")
            indices.extend(row["earPose"][key] for key in ("request", "capture"))
        indices.extend(row[key] for key in OBSERVATION_KEYS[4:])
        if phase in TRANSITIONS:
            indices.append(row["equipmentAction"])
            indices.extend(row["onModelChange"][key] for key in DETACHMENT_KEYS)
        indices.extend(row["retirement"][key] for key in ("release", *DETACHMENT_KEYS, "actorCurrent"))
    ordered(indices, "Reused or out-of-order turnover receipts")

    subject, preceding, output = None, None, {}
    for phase in PHASES:
        row = manifest["phases"][phase]
        generation = typed(ledger, row["generationRead"], CONTROL, "GetGeneration", "int", [0])
        token, nonce = row["token"], row["nonce"]
        require(positive_int(generation) and positive_int(token) and positive_int(nonce), "Invalid generation, token or nonce")
        _, raw = capture_pair(ledger, row, TOPOLOGY, "CaptureDispatch", TOPOLOGY_SCHEMA, manifest["pid"], nonce)
        sample = raw["sample"]
        subject = subject or (manifest["pid"], raw["epoch"], sample["base"], sample["cell"], sample["runtimeHandle"], sample["sex"])
        observed = route(raw, subject, nonce, fixture, phase == "equipped")
        clock = observed["captureClock"]
        first, selected, enabled = phase_ack(ack_lines, generation, token,
                                             equipped if phase == "equipped" else stock, subject[-1], clock)
        require(all(typed(ledger, row[key], NATIVE, "SnapshotCurrent", "bool", [ACTOR, generation, token]) is True
                    for key in ("currentBefore", "currentAfter")), "Exact ACK token was not current around the topology sample")
        count = typed(ledger, row["count"], CONTROL, "GetLedgerCount", "int", [0])
        require(type(count) is int and count == enabled, "Host ledger does not cover the fitted profile")
        if phase in TRANSITIONS:
            item = {"form": f"0x{fixture[0]:08X}"}
            require(typed(ledger, row["equipmentAction"], "Actor", TRANSITIONS[phase], "none", [item, False, True],
                          self_form=ACTOR) is None, "Unexpected equipment action result")
            check_detachment(ledger, row["onModelChange"], generation, token)
        released = typed(ledger, row["retirement"]["release"], CONTROL, "ReleaseActor", "int", [0])
        require(type(released) is int and released == 0, "Explicit host release failed")
        check_detachment(ledger, row["retirement"], generation, token)
        require(typed(ledger, row["retirement"]["actorCurrent"], NATIVE, "ActorCurrent", "bool", [ACTOR]) is False,
                "Explicitly released actor can still own a native cleanup lease")
        if preceding:
            old, old_nonce, old_end = preceding
            require(nonce > old_nonce and old_end < first["capturedUs"] * TICKS_PER_US and
                    old["world"] == first["world"] and old["generation"] < generation and
                    old["registration"] < first["registration"] and old["token"] < first["token"] and
                    old["acknowledgedUs"] <= first["capturedUs"],
                    "Expected a fresh binding after retiring the previous generation in the same world")
        end = clock["qpcEnd"]
        output[phase] = {"generation": generation, "registration": selected["registration"], "token": token,
                         "model": selected["model"], "ledgerCount": count, "topology": observed}
        if "earPose" in row:
            ear = linked_ear_pose(ledger, row["earPose"], raw, observed, selected)
            output[phase]["earPose"] = ear
            end = ear["qpcEnd"]
        preceding = selected, nonce, end
    return {"schema": SCHEMA, "actor": ACTOR_ID, "pid": subject[0], "phases": output,
            "routeTurnoverVerified": True, "hostLedgerRetirementVerified": True,
            "solverGeometryVerified": False, "controllerContactVerified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "ledger", "ack", "stock", "equipped"):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    try:
        files = {name: path.read_bytes() for name, path in vars(args).items()}
        manifest, stock, equipped = (json.loads(files[key], object_pairs_hook=unique_object)
                                     for key in ("manifest", "stock", "equipped"))
        ledger = [json.loads(line, object_pairs_hook=unique_object) for line in files["ledger"].splitlines() if line]
        result = verify(manifest, ledger, files["ack"].decode("utf-8-sig").splitlines(), stock, equipped)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        parser.error(str(error))
    result["inputSha256"] = {key: sha256(value).hexdigest() for key, value in files.items()}
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
