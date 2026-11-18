"""Optional explicit immutable actual-game replay; synthetic tests stay separate.

Set CLAW_FSMP_JOINT_LIMIT_READBACK_EVIDENCE to the reviewed replay bundle.
Unset optional input skips visibly. REQUIRED=1, a selected missing file or a changed
selected digest fails. Raw game captures remain external to source and releases.
"""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_joint_limit_readback as joint
from test_fsmp_joint_limit_readback import compose, transform

EVIDENCE_ENV = "CLAW_FSMP_JOINT_LIMIT_READBACK_EVIDENCE"
REQUIRED_ENV = "CLAW_FSMP_JOINT_LIMIT_READBACK_REQUIRED"
ARCHIVED_EVIDENCE_SHA256 = "9c2ce14b958ca5ecf848a9bb80db48df577fcec7854b76e78499200eed852dd1"


def read_selected_actual():
    selected = os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV) == "1":
            raise AssertionError("Required actual joint-limit evidence missing: set " + EVIDENCE_ENV)
        raise unittest.SkipTest("Optional actual-game joint-limit proof not selected; set " + EVIDENCE_ENV + " (and REQUIRED=1 to enforce it)")
    path = Path(selected).expanduser().resolve(strict=True)
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVED_EVIDENCE_SHA256:
        raise AssertionError("Explicit actual joint-limit proof hash differs; new evidence requires its own reviewed contract")
    actual = json.loads(payload)
    if actual.get("schema") != "claw-actual-joint-limit-replay/1" or not {
            "rawPair", "finalWitness", "restLocal", "reference", "base", "sourceRun"} <= set(actual):
        raise AssertionError("Complete reviewed actual joint-limit bundle required")
    if not {"worldA", "worldB", "witnessA", "witnessB", "matches", "limitResult"} <= set(actual["rawPair"]):
        raise AssertionError("Complete actual paused pair required")
    return actual


class ExplicitActualJointLimitReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = read_selected_actual()
    def associate(self, actual=None, base=None):
        value = self.actual if actual is None else actual
        raw = value["rawPair"]
        return joint.pair(raw["worldA"], raw["worldB"], raw["witnessA"], raw["witnessB"],
                          reference=value["reference"], base=value["base"] if base is None else base,
                          rest_local=value["restLocal"], expected_inverse_mass=dict.fromkeys(joint.DRIVERS, 20.))
    def test_actual_paused_and_completed_window_replay(self):
        with patch.object(joint.cached, "module_admission", side_effect=AssertionError("Historical module admission must not be used")):
            associated = self.associate()
            self.assertEqual(associated, self.actual["rawPair"]["matches"])
            self.assertEqual(joint.score_limit(associated), self.actual["rawPair"]["limitResult"])
            result = joint.score_case(associated, self.actual["finalWitness"], self.actual["restLocal"])
        self.assertEqual(result["status"], "left-positive-lower-limit-functional-correspondence-observed")
        self.assertEqual(len(set(associated["A"]["tokens"].values())), 4)
        for stage in joint.STAGES:
            coordinates = result["completed900JointCoordinates"][stage]
            self.assertAlmostEqual(coordinates[joint.DRIVERS[0]][0], .05, delta=.005)
            self.assertAlmostEqual(coordinates[joint.DRIVERS[1]][0], 0., delta=.005)
        self.assertEqual(self.actual["finalWitness"]["sample"]["objectWindow"]["pairedSteps"], 900)
    def test_wrong_declared_actor_base_refused(self):
        with self.assertRaises(ValueError):self.associate(base="0x0D000803")
    def test_mass_edit_cannot_replace_original20_20(self):
        value = copy.deepcopy(self.actual)
        token = value["rawPair"]["matches"]["A"]["tokens"][joint.DRIVERS[0]]
        for native in (value["rawPair"]["witnessA"], value["rawPair"]["witnessB"]):
            obj = next(row for row in native["sample"]["objectWindow"]["objects"] if row["token"] == token)
            for stage in joint.STAGES:obj[stage]["inverseMass"] = 10.
        with self.assertRaises(ValueError):self.associate(value)
    def test_parent_world_association_is_not_guessed(self):
        value = copy.deepcopy(self.actual)
        token = value["rawPair"]["matches"]["A"]["tokens"][joint.PARENTS[0]]
        for native in (value["rawPair"]["witnessA"], value["rawPair"]["witnessB"]):
            obj = next(row for row in native["sample"]["objectWindow"]["objects"] if row["token"] == token)
            for stage in joint.STAGES:obj[stage]["world"][9] += 1.
            obj["minimumPostWorld"][9] += 1.;obj["maximumPostWorld"][9] += 1.
        with self.assertRaises(ValueError):self.associate(value)
    def test_root_scale_or_replayed_observation_refused(self):
        for kind in ("root", "scale", "sample", "pid"):
            value = copy.deepcopy(self.actual)
            if kind == "root":value["rawPair"]["worldB"]["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
            elif kind == "scale":value["rawPair"]["worldB"]["nodes"][0]["world"]["scale"] = 1.01
            elif kind == "sample":value["rawPair"]["worldB"]["sampleId"] = value["rawPair"]["worldA"]["sampleId"]
            else:value["rawPair"]["witnessB"]["pid"] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):self.associate(value)
    def test_final_right_drift_within_endpoint_interval_refused(self):
        value = copy.deepcopy(self.actual);associated = self.associate(value)
        window = value["finalWitness"]["sample"]["objectWindow"]
        objects = {row["token"]: row for row in window["objects"]}
        parent = objects[associated["A"]["tokens"][joint.PARENTS[1]]]["lastPost"]["world"]
        desired = compose(compose(transform(parent[9:], parent[:9]), transform((0., .01, 0.))), value["restLocal"][joint.DRIVERS[1]])
        obj = objects[associated["A"]["tokens"][joint.DRIVERS[1]]]
        for stage in ("lastPre", "lastPost"):obj[stage]["world"] = desired["rotationRowMajor"] + desired["translation"]
        poses = [obj[stage]["world"] for stage in joint.STAGES]
        obj["minimumPostWorld"] = [min(row[i] for row in poses) for i in range(12)]
        obj["maximumPostWorld"] = [max(row[i] for row in poses) for i in range(12)]
        with self.assertRaisesRegex(ValueError, "stay settled.*NPC R"):
            joint.score_case(associated, value["finalWitness"], value["restLocal"])


class ExplicitSelectionContract(unittest.TestCase):
    def test_unset_optional_skips_and_required_unset_fails(self):
        for required, error in (("", unittest.SkipTest), ("1", AssertionError)):
            with self.subTest(required=required), patch.dict(os.environ, {EVIDENCE_ENV: "", REQUIRED_ENV: required}), self.assertRaises(error):
                read_selected_actual()
    def test_selected_missing_or_wrong_digest_fails(self):
        repo = Path(__file__).resolve().parents[4]
        target = (repo/"target/test-inputs/fsmp-joint-limit").resolve()
        self.assertTrue(target.is_relative_to((repo/"target").resolve()))
        target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="selection-", dir=target) as temporary:
            selected = Path(temporary).resolve()
            self.assertTrue(selected.is_relative_to(target))
            missing = selected/"missing.json"
            with patch.dict(os.environ, {EVIDENCE_ENV: str(missing)}), self.assertRaises(FileNotFoundError):read_selected_actual()
            damaged = selected/"damaged.json";damaged.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {EVIDENCE_ENV: str(damaged)}), self.assertRaisesRegex(AssertionError, "hash differs"):read_selected_actual()


if __name__ == "__main__":unittest.main()
