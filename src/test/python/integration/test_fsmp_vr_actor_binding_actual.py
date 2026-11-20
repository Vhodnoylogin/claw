"""Optional replay of the separately retained VR61 actor/provider evidence."""
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_vr_actor_binding as binding


INPUT_SHA = "be5a43be5c82607b4ec6b5a3497f2eb1e7eee1839dac61039145e40f29cc73f2"
XML_SHA = "b42bfa436a4e53baa48ff2249d4659718603798dabdb1e6b9427dc37efa0ea34"
EVIDENCE_ENV = "CLAW_FSMP_VR61_EVIDENCE"
XML_ENV = "CLAW_FSMP_VR61_XML"


class VR61ActualReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [os.environ.get(name) for name in (EVIDENCE_ENV, XML_ENV)]
        if paths == [None, None]:
            raise unittest.SkipTest("Optional pinned VR61 replay not selected")
        if not all(paths):
            raise AssertionError(f"Set both {EVIDENCE_ENV} and {XML_ENV}")
        inputs, cls.xml = [Path(path).read_bytes() for path in paths]
        if (hashlib.sha256(inputs).hexdigest(), hashlib.sha256(cls.xml).hexdigest()) != (INPUT_SHA, XML_SHA):
            raise AssertionError("Explicit VR61 evidence or effective authored XML differs")
        cls.data = json.loads(inputs)
        cls.raw = cls.data["rawReadState5"]
        cls.poses = cls.data["rawNativePoseReplies"]
        cls.args = {"serial": 5, "actor": 0xFF000844, "pose_nonce": 461663627,
                    "window_nonce": 1867481519, "arm_qpc": 649226113276}

    def test_actual_association_and_relative_last_pair(self):
        result = binding.evaluate(self.raw, self.poses, self.xml, **self.args)
        self.assertEqual(result["pairedSteps"], 28)
        self.assertEqual(len(result["tokens"]), 11)
        self.assertEqual(result["tokens"][binding.HEAD], 3)
        self.assertEqual(result["tokens"][binding.TAIL], 4)
        self.assertTrue(result["localSolverMovementObserved"])
        self.assertTrue(all(.006 < row["localTranslationDelta"] < .047 for row in result["roles"].values()))
        self.assertFalse(result["directProviderOwnerAvailable"])
        self.assertFalse(result["renderedMotionQualified"])
        self.assertFalse(result["contactQualified"])

    def test_cross_owner_changed_epoch_and_reversed_window_refused(self):
        for name, value in (("actor", 0xFF000845), ("pose_nonce", 1), ("window_nonce", 1),
                            ("arm_qpc", self.args["arm_qpc"] + 1_000_000)):
            with self.subTest(changed=name), self.assertRaises(ValueError):
                binding.evaluate(self.raw, self.poses, self.xml, **{**self.args, name: value})
        pose = json.loads(self.poses[1])
        pose["sample"]["loadEpoch"] += 1
        with self.assertRaisesRegex(ValueError, "identity"):
            binding.evaluate(self.raw, [self.poses[0], json.dumps(pose)], self.xml, **self.args)

    def test_swapped_ear_landmarks_and_wrong_configured_damping_refused(self):
        poses = []
        for raw in self.poses:
            pose = json.loads(raw)
            role = {row["name"]: row for row in pose["sample"]["nodes"]}
            left, right = (role[name] for name in binding.probe.MALE[:4:2])
            left["world"], right["world"] = right["world"], left["world"]
            poses.append(json.dumps(pose))
        with self.assertRaisesRegex(ValueError, "ear-side"):
            binding.evaluate(self.raw, poses, self.xml, **self.args)
        frame = copy.deepcopy(self.data["providerFrame"])
        frame["sample"]["objectWindow"]["incidentConstraints"]["constraints"][0]["spring2"]["damping"][0] = .2
        with self.assertRaisesRegex(ValueError, "damping"):
            binding.evaluate(json.dumps(frame), self.poses, self.xml, **self.args)

    def test_serialized_queue_can_report_two_positive_os_threads(self):
        pose = json.loads(self.poses[1])
        pose["sample"]["threadID"] += 1
        result = binding.evaluate(self.raw, [self.poses[0], json.dumps(pose)], self.xml, **self.args)
        self.assertNotEqual(*result["poseThreadIDs"])
        pose["sample"]["threadID"] = 0
        with self.assertRaisesRegex(ValueError, "scoped male wolf pose"):
            binding.evaluate(self.raw, [self.poses[0], json.dumps(pose)], self.xml, **self.args)
