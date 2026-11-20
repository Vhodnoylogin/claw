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


def selected_inputs(evidence_env, xml_env, input_sha, xml_sha):
    paths = [os.environ.get(name) for name in (evidence_env, xml_env)]
    if paths == [None, None]:
        raise unittest.SkipTest("Optional pinned actor replay not selected")
    if not all(paths):
        raise AssertionError(f"Set both {evidence_env} and {xml_env}")
    inputs, xml = [Path(path).read_bytes() for path in paths]
    if (hashlib.sha256(inputs).hexdigest(), hashlib.sha256(xml).hexdigest()) != (input_sha, xml_sha):
        raise AssertionError("Explicit actor evidence or effective authored XML differs")
    return json.loads(inputs), xml


class VR61ActualReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.xml = selected_inputs(EVIDENCE_ENV, XML_ENV, INPUT_SHA, XML_SHA)
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


class VR69ActualReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.xml = selected_inputs(
            "CLAW_FSMP_VR69_EVIDENCE", "CLAW_FSMP_VR69_XML",
            "da20816197738faf93ee3a92a93c1e3d2ac24af7cef0d02b39fbd8044e65f19d",
            "8d3a1fd08901e0ef2a9a2defe34548ba0cf4112f352778c27832a4f85a697a35",
        )
        cls.pose = cls.data["pose"]["rawNativePoseReplies"]
        cls.catalogue = cls.data["catalogue"]
        cls.args = {"serial": 5, "actor": 0xFF00087C, "pose_nonce": 1495847292,
                    "window_nonce": 359439051, "arm_qpc": 692272301588, "sex": "female"}

    def test_actual_female_graph_and_both_p1_anchors(self):
        result = binding.evaluate(self.catalogue["rawReadState5"], self.pose, self.xml, **self.args)
        self.assertEqual(result["pairedSteps"], 29)
        self.assertEqual(len(result["tokens"]), 15)
        for anchor, driver, pair in (("NPC L PreBreast P1", "NPC L Breast P1", (11, 14)),
                                     ("NPC R PreBreast P1", "NPC R Breast P1", (4, 15))):
            self.assertEqual((result["tokens"][anchor], result["tokens"][driver]), pair)
            self.assertEqual(result["roles"][driver]["parent"], anchor)
            self.assertEqual(result["roles"][driver]["observedInverseMass"], 20.)
        self.assertFalse(result["renderedMotionQualified"])

    def test_wrong_joint_frame_or_stiffness_refused(self):
        malformed = self.xml.replace(b"<frameInA />", b"<frameInB />", 1)
        with self.assertRaisesRegex(ValueError, "identity joint frame"):
            binding.evaluate(self.catalogue["rawReadState5"], self.pose, malformed, **self.args)
        frame = copy.deepcopy(self.catalogue["frame"])
        frame["sample"]["objectWindow"]["incidentConstraints"]["constraints"][0]["spring2"]["stiffness"][0] += .1
        with self.assertRaisesRegex(ValueError, "stiffness"):
            binding.evaluate(json.dumps(frame), self.pose, self.xml, **self.args)
