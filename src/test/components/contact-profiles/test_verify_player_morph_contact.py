"""Synthetic ledger controls for the equipped player's three native morph banks."""

from copy import deepcopy
import json
import unittest

from test_cbpc_vr_geometry import CELL, PID
from test_pose_ack import COLLIDER_INDEX_BASE, lines, receipt
from test_verify_equipped_turnover import case as turnover_case
from test_verify_player_contact import case as static_case
from verify_equipped_turnover import ACTOR, EAR_MORPHS, TAIL_MORPHS
from verify_player_morph_contact import CONTROL, MORPH_REFIT_PHASES, NATIVE, PLAYER_BODY_CONTACT_NODES, SCHEMA, decode, verify


def morph_case(arm, *, extra_provider_write=False):
    female = arm == "tail"
    static, static_ledger, _ = static_case(female=female, arm=arm)
    turnover, turnover_ledger, _, _, profile = turnover_case(female, ears=not female, tail=female)
    field = "tail" if female else "ear"
    fields = TAIL_MORPHS if female else EAR_MORPHS
    channel = "CLAWTailFluff" if female else "CLAWHeadEarSize"
    pose_template = turnover["phases"]["equipped"][field + "Pose"]
    node = "TailBone02" if female else "NPC EarL [EarL]Bone01"
    slots = PLAYER_BODY_CONTACT_NODES[node]
    profile.update(morphs=sorted(fields), slots=[{"node": node if i in slots else "unused", "sexMask":
                                                ("both" if i in slots else "male" if female else "female")}
                                               for i in range(slots[-1] + 1)])
    ledger, acks = [], []
    manifest = {**static, "schema": SCHEMA, "phases": {}, "capture": dict(static["capture"])}

    def copy_row(rows, index, *, packet=None, args=None):
        row = deepcopy(rows[index])
        if packet is not None:
            row["result"]["returned"] = json.dumps(packet)
        if args is not None:
            row["args"]["args"] = args
        ledger.append(row)
        return len(ledger) - 1

    def typed(method, args, kind, value, script=NATIVE):
        ledger.append({"tool": "papyrus", "args": {"action": "call", "script": script, "function": method, "args": args},
                       "result": {"called": True, "returnedType": kind, "returned": value}})
        return len(ledger) - 1

    def value(rows, index):
        return decode(rows[index]["result"]["returned"])

    manifest["fixtureReads"] = {key: copy_row(static_ledger, index) for key, index in static["fixtureReads"].items()}
    generation = 57
    manifest["generationRead"] = typed("GetGeneration", [0], "int", generation, CONTROL)
    for key in ("idle", "arm", "armed"):
        manifest["capture"][key] = copy_row(static_ledger, static["capture"][key])
    frame_template = static["holds"]["nearBefore"]
    for number, name in enumerate(MORPH_REFIT_PHASES):
        token, nonce, time = 40 + number, number + 1, number * 4_000_000
        value_now = .5 if name == "morphed" else 0.
        ack = dict(receipt(token, time + 100), actor=0x14, generation=generation,
                   model=profile["modelIdentity"], female=female, weight=0.)
        ack["morphs"] = [{"name": key, "value": value_now if key == channel else 0.} for key in profile["morphs"]]
        x = 0. if name == "morphed" else 8.
        ack["capsules"] = [{"slot": slot, "node": node, "colliderIndex": COLLIDER_INDEX_BASE + slot,
                            "geometry": [x, 0., 0., x, 0., 1., 1.5]} for slot in slots]
        ack["changedSlots"] = list(slots)
        acks.append(ack)
        binding = [ACTOR, ack["generation"], token]
        if name == "morphed" and extra_provider_write:
            typed("AttachColliderCapsule", [ACTOR, node], "bool", True, "CBPCPluginScript")
        row = {"token": token, "currentBefore": typed("SnapshotCurrent", binding, "bool", True)}
        row["topology"] = {"nonce": nonce}
        for key in ("request", "capture"):
            index = static["topology"]["attached"][key]
            packet = value(static_ledger, index)
            packet["nonce"] = nonce
            packet["sample"].update(qpcBegin=time * 10 + 3_000, qpcEnd=time * 10 + 4_000)
            row["topology"][key] = copy_row(static_ledger, index, packet=packet, args=[nonce])
            if key == "capture":
                topology_sample = packet["sample"]
        row["pose"] = {"nonce": nonce}
        rotation = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        for key in ("request", "capture"):
            index = pose_template[key]
            packet = value(turnover_ledger, index)
            packet.update(pid=PID, nonce=nonce)
            if key == "capture":
                sidecar = packet["sample"]
                packet["worldGate"]["postPhaseCount"] += number
                sidecar.update(cell=CELL, handle=topology_sample["runtimeHandle"], rawWeight=0.,
                               phaseSequence=20 + number, qpcBegin=time * 10 + 5_000, qpcEnd=time * 10 + 6_000)
                sidecar[field + "EffectiveMorphs"] = {entry["name"]: entry["value"] for entry in ack["morphs"]}
                sidecar["leftWand"] = {"position": [10., 0., 10.], "scale": .5, "rotation": rotation}
                sidecar.setdefault(field + "Bones", {})[node] = {
                    "world": {"position": [14., 0., 9.], "scale": 1., "rotation": rotation}}
            row["pose"][key] = copy_row(turnover_ledger, index, packet=packet, args=[nonce])
        row["frames"] = []
        for i, index in enumerate(frame_template):
            j = copy_row(static_ledger, index)
            frame = ledger[j]["result"]
            frame.update(producerMonotonicNs=(time + 1_000_000 + i * 800_000) * 1000,
                         sampleId=number * 3 + i + 1, producerFrame=number * 3 + i + 10)
            row["frames"].append(j)
        row["currentAfter"] = typed("SnapshotCurrent", binding, "bool", True)
        manifest["phases"][name] = row
    manifest["capture"]["seal"] = copy_row(static_ledger, static["capture"]["seal"])
    old_read = static["capture"]["read"]
    window = value(static_ledger, old_read)
    window["events"] = [dict(window["events"][0], qpc=55_000_000)]
    window["lastSequence"] = 1
    manifest["capture"]["read"] = copy_row(static_ledger, old_read, packet=window)
    return manifest, ledger, acks, profile


class PlayerMorphContactTests(unittest.TestCase):
    def check(self, inputs):
        manifest, ledger, acks, model = inputs
        return verify(manifest, ledger, lines(*acks), model)

    def test_fixed_wand_observes_contact_only_in_the_morphed_bank(self):
        for arm in ("left-ear", "tail"):
            with self.subTest(arm=arm):
                result = self.check(morph_case(arm))
                self.assertEqual(result["status"], "qualified-emission-contrast")
                self.assertEqual(result["qualifiedHeldEventCounts"], {"baseline": 0, "morphed": 1, "returned": 0})
                self.assertFalse(result["providerShapeInventoryVerified"])

    def test_rejects_wand_drift_and_stale_token(self):
        for drift in (True, False):
            with self.subTest(drift=drift):
                inputs = morph_case("tail")
                row = inputs[0]["phases"]["returned"]
                if drift:
                    frame = inputs[1][row["frames"][1]]["result"]
                    frame["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][0] += 1.
                else:
                    inputs[1][row["currentAfter"]]["result"]["returned"] = False
                with self.assertRaisesRegex(ValueError, "drifted" if drift else "not current"):
                    self.check(inputs)

    def test_a_pose_delta_ends_the_full_bank_window(self):
        inputs = morph_case("tail")
        packet = deepcopy(inputs[2][-1])
        packet.update(token=43, previousToken=42, application="delta", capturedUs=10_000_000,
                      computedUs=10_000_001, publishedUs=10_000_002, acknowledgedUs=10_000_003)
        packet["capsules"] = packet["capsules"][:1]
        packet["capsules"][0]["geometry"][-1] += .25
        packet["changedSlots"] = packet["changedSlots"][:1]
        inputs[2].append(packet)
        with self.assertRaisesRegex(ValueError, "outside the same current ACK"):
            self.check(inputs)

    def test_callbacks_in_the_clear_bank_fail_contact_qualification(self):
        inputs = morph_case("left-ear")
        result = inputs[1][inputs[0]["capture"]["read"]]["result"]
        packet = decode(result["returned"])
        packet["events"][0]["qpc"] = 15_000_000
        result["returned"] = json.dumps(packet)
        self.assertEqual(self.check(inputs)["status"], "insufficient-emission-contrast")

    def test_unrecorded_provider_write_or_disagreeing_native_wand_fails(self):
        inputs = morph_case("tail")
        row = inputs[0]["phases"]["morphed"]
        payload = inputs[1][row["pose"]["capture"]]["result"]
        pose = decode(payload["returned"])
        pose["sample"]["leftWand"]["position"][0] += 3.
        payload["returned"] = json.dumps(pose)
        with self.assertRaisesRegex(ValueError, "World Observer disagree"):
            self.check(inputs)

        with self.assertRaisesRegex(ValueError, "Unaccounted Papyrus operation"):
            self.check(morph_case("tail", extra_provider_write=True))


if __name__ == "__main__":
    unittest.main()
