"""Synthetic typed transport plus a separately selected exact file preflight."""

import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from fsmp_contact_pose import Geometry, NAMES, PELVIS, load, load_pynifly
from fsmp_contact_windows import PHASES, SCRIPT
from fsmp_probe import OBSERVATION
from run_fsmp_contact_trial import Subjects, Trial


SUBJECTS = Subjects("0xFF000802", "0x000A2C90", "0xFF000803", "0x01000805")
SOURCE = "SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/"
MORPHS = ("CLAWLegThighGirth", "CLAWLegThighLean")


def transform_at(position):
    return {"translation": list(position), "rotationRowMajor": [1, 0, 0, 0, 1, 0, 0, 0, 1], "scale": 1.}


def geometry():
    vertices = np.zeros((3, 4, 4))
    vertices[:, 1, :] = [(0., 0., 0., 1.), (5., 0., 0., 1.), (0., 5., 0., 1.)]
    points = np.array([(0.06, .06, .06, 1), (-.06, -.06, .06, 1),
                       (-.06, .06, -.06, 1), (.06, -.06, -.06, 1)])
    return Geometry(np.array([[0, 1, 2]]), 0, vertices, points, 1., 1, "WWD 2",
                    SOURCE + "CLAWNeutralAnatomyContact.xml", SOURCE + "CLAWAnatomyContactProbe.xml",
                    SOURCE + "CLAWAnatomyContactProbeNoContact.xml", MORPHS, {"scope": "synthetic"})


class Session:
    def __init__(self, directory, geom):
        self.dir, self.geom = Path(directory), geom
        self.state = {"game": {"pid": 4321}, "gameEdition": "se"}
        self.path = geom.probe_path
        self.position = [0., -10., 0.]
        self.ticks = 100
        self.arm_count = 0
        self.calls = []
        self.fail_move = False
        self.foreign_observer = False
        self.outside_qpc = False
        self.morph = 0.

    def papyrus(self, packet):
        script, function = packet["script"], packet.get("function")
        args = packet.get("args", [])
        if packet["action"] == "describe":
            return {"name": script}
        if function == "GetFormFromFile":
            assert args == [0x800, "test_CLAW - FSMP Contact Peer.esp"]
            kind, value = "form", {"formId": "0x08000800"}
        elif function == "QueryCurrentPhysicsFile":
            kind, value = "string", self.geom.target_path if args[0]["form"] == SUBJECTS.surface_ref else self.path
        elif function == "ReloadPhysicsFile":
            assert args[0]["form"] == SUBJECTS.probe_ref and args[3:] == [False, False]
            self.path = args[2]
            kind, value = "bool", True
        elif function == "SetPosition":
            assert packet["self"]["form"] == SUBJECTS.probe_ref and all(type(a) is float for a in args)
            self.position = args
            if self.fail_move:
                raise TimeoutError("Move completion unknown")
            kind, value = "none", None
        elif function == "Arm" and script == SCRIPT:
            assert args[:4] == [{"form": v} for v in (SUBJECTS.surface_ref, "0x000CDD87", SUBJECTS.probe_ref, "0x08000800")]
            self.arm_count += 1
            self.contact = self.arm_count == 3
            self.head = {"schema": "claw-fsmp-pair-contact/1", "status": "complete", "pid": 4321,
                         "surfaceRef": 0xFF000802, "surfaceAddon": 0xCDD87, "probeRef": 0xFF000803,
                         "probeAddon": 0x08000800, "callerEpoch": args[5], "nonce": args[4],
                         "mode": "tag_control" if self.path == self.geom.control_path else "reciprocal",
                         "measure": "pre-solve accepted contact point", "frames": args[6], "requiredFrames": args[6],
                         "qpcFrequency": 10000000, "firstQpc": self.ticks - (1000 if self.outside_qpc else 0),
                         "lastQpc": self.ticks + 1, "contactRows": int(self.contact)}
            kind, value = "bool", True
        elif function == "Describe" and script == SCRIPT:
            kind, value = "string", json.dumps(self.head)
        elif function == "Read" and script == SCRIPT:
            rows = [{"step": 1, "qpc": self.head["firstQpc"], "surfaceDriver": "WWD 2", "signedDepth": -0.5,
                     "surfaceLocal": [0, 0, 0], "probeLocal": [0, 0, 0],
                     "normalToSurface": [1, 0, 0]}] if self.contact else []
            kind, value = "string", json.dumps({"status": "complete", "nonce": args[0], "offset": args[1],
                                              "total": len(rows), "rows": rows})
        else:
            raise AssertionError(packet)
        return {"called": True, "returnedType": kind, "returned": value}

    def tool(self, tool, args, *, timeout, deadline):
        self.calls.append((tool, args))
        self.ticks += 40
        if tool == "papyrus":
            return self.papyrus(args)
        assert tool == "inspect" and args["skee"] == {"refs": [SUBJECTS.surface_ref], "morphs": list(self.geom.morphs)}
        refs, nodes = [], []
        positions = ([0., 0., 0.], self.position)
        for i, (actor, race, names, position) in enumerate(zip(
                SUBJECTS.specs(), ("0x000CDD84", "0x00013746"), (NAMES, (PELVIS,)), positions, strict=True), 1):
            identity = {"form": actor["reference"], "runtimeHandle": 100 + i, "loadGeneration": 7}
            root = {"sampledRootToken": i, "firstPerson": False,
                    "identityBasis": "sampled_pointer_and_handle_changes_no_object_retention"}
            frame = transform_at(position)
            refs.append({"identity": identity, "status": "available", "loaded3D": True, "deleted": False,
                         "disabled": False, "baseForm": actor["base"], "cellForm": "0x0001A20A", "position": position,
                         "sceneTransform": frame, "rootIdentity": root,
                         "actor": {"status": "available", "raceStatus": "available", "race": race,
                                   "baseForm": actor["base"], "sex": 0}})
            nodes.extend({"name": name, "status": "available", "firstPerson": False, "form": actor["reference"],
                          "identity": identity, "rootIdentity": root, "world": frame} for name in names)
        return {"schemaVersion": 1, "ok": True, "quality": "complete", "phase": "skse_main_thread_task",
                "units": "skyrim_engine_units", "space": "world", "coherence": OBSERVATION,
                "sessionId": "foreign" if self.foreign_observer else "fake-world", "loadGeneration": 7,
                "sampleId": self.ticks, "producerMonotonicNs": self.ticks * 100, "refs": refs, "nodes": nodes,
                "skee": [{"status": "available", "identity": refs[0]["identity"],
                          "provider": {"status": "available", "interfaceVersion": 5, "interfaceEpoch": 1},
                          "morphs": [{"name": name, "status": "available",
                                      "aggregate": {"status": "available", "value": self.morph}} for name in self.geom.morphs]}]}


class TransportTest(unittest.TestCase):
    def start(self, directory):
        data = geometry()
        session = Session(directory, data)
        guards = []

        def guard(s, actor, deadline):
            self.assertIs(s, session)
            remaining = deadline - time.monotonic()
            self.assertGreater(remaining, 0.)
            self.assertLessEqual(remaining, 30.)
            guards.append(actor)

        trial = Trial(session, SUBJECTS, data, guard, 70, 21, 4, lambda _: None, lambda: False)
        return session, trial, guards

    def test_complete_four_windows_and_restore(self):
        with tempfile.TemporaryDirectory() as directory, patch("run_fsmp_contact_trial.qualifier"):
            session, trial, guards = self.start(directory)
            result = trial.execute()
            self.assertTrue(trial.cleanup())
            self.assertEqual(tuple(result["windows"]), PHASES)
            self.assertEqual([row["pointCount"] for row in result["windows"].values()], [0, 0, 1, 0])
            self.assertFalse(result["impulseVerified"])
            self.assertEqual(session.position, [0., -10., 0.])
            self.assertEqual(session.path, trial.geometry.probe_path)
            self.assertGreaterEqual(len(guards), 20)
            index = json.loads((trial.output / "contact-index.json").read_bytes())
            self.assertEqual(set(index["windows"]), set(PHASES))

    def test_foreign_qpc_keeps_failure_and_restores(self):
        with tempfile.TemporaryDirectory() as directory, patch("run_fsmp_contact_trial.qualifier"):
            session, trial, _ = self.start(directory)
            session.outside_qpc = True
            with self.assertRaisesRegex(ValueError, "bracket the provider"):
                trial.execute()
            self.assertTrue(trial.cleanup())
            self.assertEqual(session.position, [0., -10., 0.])

    def test_uncertain_move_never_replays_or_restores_by_guess(self):
        with tempfile.TemporaryDirectory() as directory, patch("run_fsmp_contact_trial.qualifier"):
            session, trial, _ = self.start(directory)
            session.fail_move = True
            with self.assertRaises(TimeoutError):
                trial.execute()
            self.assertFalse(trial.cleanup())
            self.assertTrue(session.state["ownedFixtureQuarantine"]["ownedSessionTeardownRequired"])
            writes = [args["function"] for _, args in session.calls if args.get("function") == "SetPosition"]
            self.assertEqual(writes, ["SetPosition"])
            self.assertEqual(json.loads((trial.output / "journal.json").read_bytes())["intent"]["function"],
                             "SetPosition")

    def test_non_neutral_target_is_read_only_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch("run_fsmp_contact_trial.qualifier"):
            session, trial, _ = self.start(directory)
            session.morph = 0.1
            with self.assertRaisesRegex(ValueError, "neutral surface morphs"):
                trial.execute()
            self.assertTrue(trial.cleanup())
            self.assertFalse(any(args.get("function") == "SetPosition" for _, args in session.calls))

    def test_vr_without_equivalent_observer_refuses_before_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            data = geometry()
            session = Session(directory, data)
            session.state["gameEdition"] = "vr"
            with self.assertRaisesRegex(ValueError, "SE World Observer"):
                Trial(session, SUBJECTS, data, None, 70, 21, 4, lambda _: None, lambda: False)
            self.assertEqual(session.calls, [])


@unittest.skipUnless(os.environ.get("CLAW_CONTACT_POSE_INPUTS"), "Select the retained peer/target pose files")
class RealPreflightTest(unittest.TestCase):
    def test_both_actual_rigs_retain_face_and_input_morph_catalog(self):
        supplied = json.loads(Path(os.environ["CLAW_CONTACT_POSE_INPUTS"]).read_bytes())
        peer = Path(supplied["peer"])
        for family in ("anatomy3", "combined12"):
            with self.subTest(family=family):
                candidate = load(peer / (family + "-aim.json"), peer / "peer-report.json", Path(supplied["surface"]),
                                 Path(supplied["skeleton"]), Path(supplied["pynifly"]), family)
                self.assertEqual(candidate.identity["face"], 201)
                self.assertEqual(candidate.identity["retainedFaceCount"], 1620)
                self.assertEqual(len(candidate.morphs), 6)
                api, _, _ = load_pynifly(Path(supplied["pynifly"]))
                skeleton = api.NifFile(supplied["skeleton"])
                poses = {}
                for name in NAMES:
                    frame = skeleton.nodes[name].global_transform
                    poses[name] = {"translation": list(frame.translation), "scale": float(frame.scale),
                                   "rotationRowMajor": [float(value) for row in frame.rotation for value in row]}
                near, far = candidate.aims(poses, transform_at([0, 0, 0]))
                self.assertTrue(candidate.bracket(poses, transform_at(near.tolist()), True)["valid"])
                self.assertTrue(candidate.bracket(poses, transform_at(far.tolist()), False)["valid"])


if __name__ == "__main__":
    unittest.main()
