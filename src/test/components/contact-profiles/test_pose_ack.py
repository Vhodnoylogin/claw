"""Offline controls for the Distribution pose ACK reader."""
from copy import deepcopy
import json
import struct
import unittest

from verify_pose_ack import COLLIDER_INDEX_BASE, PREFIX, SCHEMA, verify


ACTOR = 0xFF000868
GENERATION = 3
MORPH = "CLAWHeadEarSize"
MODEL = "CLAW.Physics.CurrentVector.exact"
PROFILE = {"modelIdentity": MODEL, "morphs": [MORPH], "slots": [
    {"node": "Head", "sexMask": "both"}, {"node": "NPC Breast", "sexMask": "female"},
    {"node": "TailBone02", "sexMask": "male"}, {"node": "TailBone03", "sexMask": "both"},
]}
MALE = {0: "Head", 2: "TailBone02", 3: "TailBone03"}


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bank(slots, offset=0.):
    return [{"slot": slot, "node": MALE[slot], "colliderIndex": COLLIDER_INDEX_BASE + slot,
             "geometry": [float(slot + offset), 0., 1., 0., 1., 2., 1.25]}
            for slot in slots]


def receipt(token, start, *, previous=0, application="full"):
    changed = [2] if previous else list(MALE)
    capsules = bank(MALE if application == "full" else changed)
    if previous:
        next(item for item in capsules if item["slot"] == 2)["geometry"][0] += 1.
    x = float(token - 40)
    return {"schema": SCHEMA, "actor": ACTOR, "generation": GENERATION, "token": token, "previousToken": previous,
            "world": 1, "registration": 7, "model": MODEL, "female": False, "application": application,
            "capturedUs": start, "computedUs": start + 1, "publishedUs": start + 2, "acknowledgedUs": start + 3,
            "weight": f32(.4), "morphs": [{"name": MORPH, "value": f32(.3)}],
            "bones": [{"name": "TailBone02", "world": [0, -2, 0, x, 2, 0, 0, 2, 0, 0, 2, 3],
                       "worldToBone": [0, .5, 0, -1, -.5, 0, 0, .5 * x, 0, 0, .5, -1.5]}],
            "changedSlots": changed, "capsules": capsules}


def lines(*receipts):
    return ["[info] ignored unrelated message\n",
            *(f"[2026-11-22 22:13:00] [info] {PREFIX}{json.dumps(item)}\n" for item in receipts)]


class PoseAckTests(unittest.TestCase):
    def setUp(self):
        self.full = receipt(40, 100)
        self.delta = receipt(44, 200, previous=40, application="delta")
        self.fallback = receipt(44, 200, previous=40, application="full")

    def verify(self, *receipts, **kwargs):
        return verify(lines(*receipts), actor=ACTOR, generation=GENERATION, **kwargs)

    def test_exact_binding_and_host_delta_of_two_receipts(self):
        foreign = dict(receipt(42, 150), actor=ACTOR + 1)
        result = self.verify(self.full, foreign, self.delta, profile=PROFILE, expected_tokens=[40, 44],
                             require_delta=True)
        for key, value in {"lastToken": 44, "nativeFull": 1, "pose": 1, "hostFull": 1, "hostDelta": 1,
                           "enabledSlots": 3, "profileBindingsVerified": True,
                           "solverGeometryVerified": False, "contactVerified": False}.items():
            self.assertEqual(result[key], value, key)

    def test_native_token_order_survives_delayed_log_flush(self):
        result = self.verify(self.delta, self.full, require_delta=True)
        self.assertEqual(result["lastToken"], self.delta["token"])

    def test_host_full_fallback_uses_complete_bank_without_claiming_delta(self):
        result = self.verify(self.full, self.fallback, profile=PROFILE)
        self.assertEqual((result["pose"], result["hostFull"], result["hostDelta"]), (1, 2, 0))
        self.assertRaisesRegex(ValueError, "No successful Host delta",
                               self.verify, self.full, self.fallback, require_delta=True)

    def test_pose_ack_accepts_42_changed_slots_and_rejects_43(self):
        slots = list(range(43))
        node = "TailBone02"
        profile = {**PROFILE, "slots": [{"node": node, "sexMask": "both"} for _ in slots]}
        initial = [{"slot": slot, "node": node, "colliderIndex": COLLIDER_INDEX_BASE + slot,
                    "geometry": [0., 0., 0., 0., 0., 1., 1.]} for slot in slots]
        full = dict(self.full, changedSlots=slots, capsules=initial)
        updated = [dict(item, geometry=[0., 0., 0., 0., 0., 1., 1.5]) for item in initial]
        delta = dict(self.delta, changedSlots=slots[:42], capsules=updated[:42])
        fallback = dict(delta, application="full", capsules=[*updated[:42], initial[-1]])

        for receipt, expected in ((delta, (1, 1)), (fallback, (2, 0))):
            with self.subTest(application=receipt["application"]):
                result = self.verify(full, receipt, profile=profile)
                self.assertEqual((result["hostFull"], result["hostDelta"]), expected)
                self.assertEqual((result["enabledSlots"], result["pose"]), (43, 1))
                oversized = dict(receipt, changedSlots=slots, capsules=updated)
                self.assertRaisesRegex(ValueError, "within the pose budget", self.verify, full, oversized,
                                       profile=profile)

    def test_morph_vector_retains_32_entry_limit(self):
        morphs = [{"name": f"Morph{index}", "value": .5} for index in range(33)]
        self.assertEqual(self.verify(dict(self.full, morphs=morphs[:32]))["nativeFull"], 1)
        self.assertRaisesRegex(ValueError, "Invalid effective morph vector", self.verify,
                               dict(self.full, morphs=morphs))

    def test_full_native_refits_may_change_morphs_and_omit_prior_token(self):
        refit = receipt(44, 200)
        refit["morphs"][0]["value"] = .75
        result = self.verify(self.full, refit)
        self.assertEqual(result["nativeFull"], 2)
        self.assertFalse(result["profileBindingsVerified"])

    def test_female_profile_has_its_own_slots(self):
        female = deepcopy(self.full)
        female["female"] = True
        female["changedSlots"] = [0, 1, 3]
        female["capsules"][1] = {"slot": 1, "node": "NPC Breast", "colliderIndex": COLLIDER_INDEX_BASE + 1,
                                "geometry": [1, 2, 3, 4, 5, 6, .5]}
        self.assertEqual(self.verify(female, profile=PROFILE)["enabledSlots"], 3)

    def test_missing_duplicate_wrong_binding_and_stale_tokens_fail(self):
        for rows, pattern in (
            ([], "No ACK"),
            ([dict(self.full, generation=GENERATION + 1)], "No ACK"),
            ([self.delta], "Initial full ACK"),
            ([self.full, self.full], "Duplicate ACK token"),
            ([self.full, dict(self.delta, previousToken=42)], "Previous ACK token"),
            ([self.full, receipt(44, 80)], "regressed"),
            ([self.full, dict(self.delta, registration=8)], "binding changed"),
            ([self.full, dict(self.delta, world=2)], "binding changed"),
            ([self.full, dict(self.delta, model="other")], "binding changed"),
        ):
            with self.subTest(pattern=pattern):
                self.assertRaisesRegex(ValueError, pattern, self.verify, *rows)
        self.assertRaisesRegex(ValueError, "Expected ACK token", self.verify, self.full, expected_tokens=[44])

    def test_malformed_json_schema_and_wrong_stage_order_fail_with_line(self):
        self.assertRaisesRegex(ValueError, "Log line 1:", verify, [PREFIX + "{"], actor=ACTOR, generation=GENERATION)
        duplicate = PREFIX + json.dumps(self.full).replace('"actor":', '"actor": 2, "actor":')
        self.assertRaisesRegex(ValueError, "Repeated JSON key", verify, [duplicate], actor=ACTOR,
                               generation=GENERATION)
        self.assertRaisesRegex(ValueError, "Log line 2: Invalid ACK schema", self.verify,
                               dict(self.full, schema="other"))
        self.assertRaisesRegex(ValueError, "stage order", self.verify, dict(self.full, computedUs=122))
        self.assertRaisesRegex(ValueError, "previous accepted inputs", self.verify, self.full,
                               receipt(44, 102, previous=40, application="delta"))
        self.assertRaisesRegex(ValueError, "previous accepted inputs", self.verify, self.full,
                               dict(self.delta, weight=.5))

    def test_numeric_domains_enforce_types_finiteness_and_exact_unit_float32(self):
        for field, value, pattern in (
            ("actor", True, "actor"), ("generation", 0, "generation"), ("token", 0x1000000, "token"),
            ("world", -1, "world"), ("registration", 0, "registration"), ("capturedUs", True, "capturedUs"),
            ("acknowledgedUs", 2**64, "acknowledgedUs"), ("weight", 1.1, "weight"),
            ("weight", float("nan"), "weight"), ("weight", .4, "weight"),
            ("morphs", [{"name": MORPH, "value": False}], "morph"),
            ("morphs", [{"name": MORPH, "value": .3}], "morph"), ("morphs", [], "morph"),
        ):
            with self.subTest(field=field, value=value):
                self.assertRaisesRegex(ValueError, pattern, self.verify, dict(self.full, **{field: value}))

    def test_affine_and_geometry_controls(self):
        for path, value, pattern in (
            (("bones", "world", 3), 7., "not inverses"),
            (("bones", "worldToBone", 11), float("inf"), "Invalid worldToBone"),
            (("bones", "world", 0), 10**500, "Invalid world transform"),
            (("capsules", "geometry", 6), -1., "radius"),
            (("capsules", "geometry", 1), 1.e40, "Float32"),
            (("capsules", "geometry", 6), 1.e-50, "radius"),
        ):
            with self.subTest(path=path, value=value):
                bad = deepcopy(self.full)
                group, field, index = path
                bad[group][0][field][index] = value
                self.assertRaisesRegex(ValueError, pattern, self.verify, bad)

    def test_profile_coverage_changes_and_unchanged_capsules(self):
        incomplete = dict(self.full, changedSlots=[0, 2], capsules=self.full["capsules"][:2])
        self.assertRaisesRegex(ValueError, "omits enabled slots", self.verify, incomplete, profile=PROFILE)
        self.assertRaisesRegex(ValueError, "sorted", self.verify, dict(self.full, changedSlots=[2, 0, 3]))
        self.assertRaisesRegex(ValueError, "unique", self.verify, dict(self.full, changedSlots=[0, 2, 2]))
        bad_index = deepcopy(self.delta)
        bad_index["capsules"][0]["colliderIndex"] += 1
        self.assertRaisesRegex(ValueError, "owned slot", self.verify, self.full, bad_index)
        wrong_node = deepcopy(self.delta)
        wrong_node["capsules"][0]["node"] = "TailBone03"
        self.assertRaisesRegex(ValueError, "attachment node", self.verify, self.full, wrong_node)
        self.assertRaisesRegex(ValueError, "declared changed slots", self.verify,
                               self.full, dict(self.delta, changedSlots=[0, 2]))
        self.assertRaisesRegex(ValueError, "contradicts", self.verify,
                               self.full, dict(self.delta, capsules=bank([2])))
        stale_fallback = deepcopy(self.fallback)
        stale_fallback["capsules"][0]["geometry"][-1] = 2.
        self.assertRaisesRegex(ValueError, "contradicts", self.verify, self.full, stale_fallback)

    def test_endpoint_reversal_alone_is_no_geometry_change(self):
        reversed_only = deepcopy(self.delta)
        old = self.full["capsules"][1]["geometry"]
        reversed_only["capsules"][0]["geometry"] = old[3:6] + old[:3] + old[6:]
        self.assertRaisesRegex(ValueError, "contradicts", self.verify, self.full, reversed_only)


if __name__ == "__main__":
    unittest.main()
