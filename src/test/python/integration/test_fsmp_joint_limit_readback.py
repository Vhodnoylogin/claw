"""Portable symbolic discrimination, never actual runtime/physics qualification.

Fixtures contain independent forward transforms and invented typed envelopes.
No mandatory case reads a game capture, Build directory, DLL, NIF or vendor asset.
"""
from pathlib import Path
import copy
import math
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fsmp_joint_limit_readback as joint

IDENTITY = [1., 0., 0., 0., 1., 0., 0., 0., 1.]
YAW90 = [0., -1., 0., 1., 0., 0., 0., 0., 1.]
REFERENCE = "0xFF001234"
BASE = "0x01000801"


def transform(xyz=(0., 0., 0.), rotation=IDENTITY, scale=1.):
    return {"translation": list(xyz), "rotationRowMajor": list(rotation), "scale": scale}


def compose(parent, child):
    """Independent forward fixture, not the checked inverse implementation."""
    a, b = parent["rotationRowMajor"], child["rotationRowMajor"]
    xyz = [parent["translation"][i] + parent["scale"] * sum(a[i*3+j]*child["translation"][j] for j in range(3)) for i in range(3)]
    rotation = [sum(a[i*3+k]*b[k*3+j] for k in range(3)) for i in range(3) for j in range(3)]
    return transform(xyz, rotation, parent["scale"]*child["scale"])


def object_row(token, frame, inverse_mass, flags):
    pose = {"world": frame["rotationRowMajor"] + frame["translation"], "rigidBody": True,
            "inverseMass": inverse_mass, "flags": flags}
    return {"token": token, "initialPre": copy.deepcopy(pose), "lastPre": copy.deepcopy(pose), "lastPost": copy.deepcopy(pose),
            "minimumPostWorld": pose["world"][:], "maximumPostWorld": pose["world"][:],
            "maximumPairedDifference": 0., "firstNonzeroStep": 0,
            "firstNonzeroPreQpc": 0, "firstNonzeroPostQpc": 0, "firstNonzeroPair": None}


def symbolic_fixture(left=.05, right=0.):
    """Synthetic already-settled state; its acceptance proves scorer logic only."""
    probe = joint.probe
    names = probe.node_names("female")
    anchors = tuple(dict.fromkeys(probe.anchors("female").values()))
    frames = {name: transform((100.*(i+1), 0., 0.)) for i, name in enumerate(anchors)}
    rest = {name: transform((0., 1., 0.)) for name in joint.DRIVERS}
    for i, name in enumerate(probe.drivers("female")):
        anchor = frames[probe.anchors("female")[name]]
        if name in joint.DRIVERS:
            q = left if name == joint.DRIVERS[0] else right
            frames[name] = compose(compose(anchor, transform((q, 0., 0.))), rest[name])
        else:
            frames[name] = compose(anchor, transform((10.*(i+1), 5., 0.)))
    for i, name in enumerate(names):
        if name not in frames:
            frames[name] = transform((0., 0., float(i)))
    identity = {"form": REFERENCE, "runtimeHandle": 12, "loadGeneration": 7}
    root = {"firstPerson": False, "sampledRootToken": 9,
            "identityBasis": "sampled_pointer_and_handle_changes_no_object_retention"}
    actor = {"status": "available", "raceStatus": "available", "sex": 1, "baseForm": BASE,
             "race": "0x000CDD84", "baseRace": "0x000CDD84",
             "weight": {"status": "available", "rawNPCWeight": 50., "normalizedNPCWeight": .5}}
    world = {"schemaVersion": 1, "observerVersion": "symbolic-test-observer", "ok": True, "quality": "complete",
             "sessionId": "symbolic-not-game-evidence", "loadGeneration": 7, "sampleId": 1,
             "producerMonotonicNs": 1_000_000_000, "phase": "skse_main_thread_task", "units": "skyrim_engine_units",
             "space": "world", "coherence": copy.deepcopy(probe.OBSERVATION), "producerFrame": None,
             "refs": [{"identity": identity, "rootIdentity": root, "baseForm": BASE, "status": "available",
                       "loaded3D": True, "deleted": False, "disabled": False, "position": [0., 0., 0.],
                       "anglesRadians": [0., 0., 0.], "scale": 1., "sceneTransform": transform(), "actor": actor}],
             "nodes": [{"form": REFERENCE, "identity": identity, "rootIdentity": root, "status": "available",
                        "firstPerson": False, "name": name, "world": frames[name],
                        "local": rest.get(name, transform())} for name in names]}
    catalog = list(anchors) + list(probe.drivers("female"))
    objects = [object_row(i+1, frames[name], 0. if name in anchors else 20., 2 if name in anchors else 0) for i, name in enumerate(catalog)]
    window = {"status": "collecting", "nonce": 71, "loadEpoch": 7, "coherent": True, "objectCapacity": 128,
              "pairedStepLimit": 900, "objectCount": len(objects), "pairedSteps": 41, "failureCode": 0,
              "callbackDrops": 0, "firstPreQpc": 1, "lastPreQpc": 2999, "lastPostQpc": 3000,
              "lastPreThreadId": 7, "lastPostThreadId": 7, "lastTimeStep": .016, "awaitingPost": False, "objects": objects}
    counter = {"count": 1000, "lastQpc": 3000, "lastThreadId": 7, "lastTimeStep": .016,
               "coherent": True, "invalidEvents": 0, "droppedEvents": 0}
    native = {"status": "ready", "pid": 17, "qpcFrequency": 1000, "requestSerial": 1,
              "sample": {"loadEpoch": 7, "sampledQpc": 4000, "mainFreezeTime": True, "uiPaused": False,
                         "pre": copy.deepcopy(counter), "post": copy.deepcopy(counter), "objectWindow": window}}
    world_b, native_b = copy.deepcopy(world), copy.deepcopy(native)
    world_b.update(sampleId=2, producerMonotonicNs=1_300_000_000)
    native_b["requestSerial"] = 2
    native_b["sample"]["sampledQpc"] = 4300
    final = copy.deepcopy(native_b)
    final["requestSerial"] = 3
    final["sample"].update(sampledQpc=10_000, mainFreezeTime=False)
    final["sample"]["objectWindow"].update(status="complete", pairedSteps=900, lastPreQpc=8999, lastPostQpc=9000)
    return {"worldA": world, "worldB": world_b, "witnessA": native, "witnessB": native_b,
            "restLocal": rest, "finalWitness": final}


def associate(value):
    return joint.pair(value["worldA"], value["worldB"], value["witnessA"], value["witnessB"],
                      reference=REFERENCE, base=BASE, rest_local=value["restLocal"],
                      expected_inverse_mass=dict.fromkeys(joint.DRIVERS, 20.))


def move_final_joint(value, associated, driver, coordinate):
    """Independent forward final-pose mutation inside nominal endpoint ranges."""
    objects = {row["token"]: row for row in value["finalWitness"]["sample"]["objectWindow"]["objects"]}
    parent = joint.PARENTS[joint.DRIVERS.index(driver)]
    p = objects[associated["A"]["tokens"][parent]]["lastPost"]["world"]
    frame = compose(compose(transform(p[9:], p[:9]), transform(coordinate)), value["restLocal"][driver])
    obj = objects[associated["A"]["tokens"][driver]]
    for stage in ("lastPre", "lastPost"):
        obj[stage]["world"] = frame["rotationRowMajor"] + frame["translation"]
    poses = [obj[stage]["world"] for stage in joint.STAGES]
    obj["minimumPostWorld"] = [min(p[i] for p in poses) for i in range(12)]
    obj["maximumPostWorld"] = [max(p[i] for p in poses) for i in range(12)]


class PortableJointMath(unittest.TestCase):
    def test_rotated_anchor_not_raw_world_x(self):
        parent = transform((10., 20., 30.), YAW90)
        actual = joint.joint_frame(parent, compose(compose(parent, transform((.05, 0., 0.))), transform((0., 1., 0.))), transform((0., 1., 0.)))
        self.assertAlmostEqual(actual["translation"][0], .05)
        self.assertAlmostEqual(actual["translation"][1], 0.)
    def test_pivot_lever_arm_rotation_is_removed(self):
        parent = transform((100., 200., 300.))
        driver = transform((99.05, 200., 300.), YAW90)
        actual = joint.joint_frame(parent, driver, transform((0., 1., 0.)))
        self.assertAlmostEqual(actual["translation"][0], .05)
        self.assertNotAlmostEqual(driver["translation"][0]-parent["translation"][0], .05)
    def test_nonunit_and_nonfinite_frames_refused(self):
        for frame in (transform(scale=2.), transform((float("nan"), 0., 0.))):
            with self.subTest(frame=frame), self.assertRaises(ValueError):joint.joint_frame(frame, transform(), transform())
    def test_frozen_thresholds_and_sole_witness_validator(self):
        self.assertEqual((joint.LOWER_LEFT, joint.UPPER_LEFT, joint.JOINT_TOLERANCE), (.05, .15, .005))
        expected = Path(__file__).resolve().parents[4]/"src/test/cpp/fsmp_step_witness/validate_snapshot.py"
        self.assertEqual(Path(joint.witness.__file__).resolve(), expected.resolve())


class PortableReadbackDiscrimination(unittest.TestCase):
    def test_symbolic_complete_positive_is_not_runtime_evidence(self):
        value = symbolic_fixture()
        result = joint.score_case(associate(value), value["finalWitness"], value["restLocal"])
        self.assertEqual(result["status"], "left-positive-lower-limit-functional-correspondence-observed")
        self.assertIn("no exact live limit getter", result["scope"])
    def test_original_zero_wrong_sign_and_right_control_refused(self):
        for left, right in ((0., 0.), (-.05, 0.), (.05, .05)):
            value = symbolic_fixture(left, right)
            with self.subTest(left=left, right=right), self.assertRaises(ValueError):joint.score_limit(associate(value))
    def test_right_x_drift_inside_endpoint_bounds_refused(self):
        value = symbolic_fixture(right=-.004);a = associate(value)
        move_final_joint(value, a, joint.DRIVERS[1], (.004, 0., 0.))
        with self.assertRaisesRegex(ValueError, "stay settled.*NPC R"):joint.score_case(a, value["finalWitness"], value["restLocal"])
    def test_right_y_drift_inside_unchanged_interval_refused(self):
        value = symbolic_fixture();a = associate(value)
        move_final_joint(value, a, joint.DRIVERS[1], (0., .01, 0.))
        with self.assertRaisesRegex(ValueError, "stay settled.*NPC R"):joint.score_case(a, value["finalWitness"], value["restLocal"])
    def test_incomplete_window_foreign_process_and_nonce_refused(self):
        for kind in ("incomplete", "process", "nonce"):
            value = symbolic_fixture();a = associate(value);final = value["finalWitness"]
            if kind == "incomplete":final["sample"]["objectWindow"].update(status="collecting", pairedSteps=899)
            elif kind == "process":final["pid"] += 1
            else:final["sample"]["objectWindow"]["nonce"] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):joint.score_case(a, final, value["restLocal"])
    def test_wrong_original_mass_and_kinematic_metadata_refused(self):
        for kind in ("mass", "parent"):
            value = symbolic_fixture();a = associate(value)
            name = joint.DRIVERS[0] if kind == "mass" else joint.PARENTS[0]
            token = a["A"]["tokens"][name]
            for native in (value["witnessA"], value["witnessB"]):
                obj = next(row for row in native["sample"]["objectWindow"]["objects"] if row["token"] == token)
                for stage in joint.STAGES:obj[stage]["inverseMass"] = 10. if kind == "mass" else 20.
            with self.subTest(kind=kind), self.assertRaises(ValueError):associate(value)
    def test_parent_missing_or_ambiguous_refused(self):
        for kind in ("missing", "ambiguous"):
            value = symbolic_fixture();a = associate(value);token = a["A"]["tokens"][joint.PARENTS[0]]
            for native in (value["witnessA"], value["witnessB"]):
                window = native["sample"]["objectWindow"]
                if kind == "missing":
                    obj = next(row for row in window["objects"] if row["token"] == token)
                    for stage in joint.STAGES:obj[stage]["flags"] = 0
                else:
                    obj = copy.deepcopy(next(row for row in window["objects"] if row["token"] == token))
                    obj["token"] = len(window["objects"])+1;window["objects"].append(obj);window["objectCount"] += 1
            with self.subTest(kind=kind), self.assertRaises(ValueError):associate(value)
    def test_one_dynamic_object_cannot_supply_two_roles(self):
        value = symbolic_fixture()
        for raw in (value["worldA"], value["worldB"]):
            left = next(row for row in raw["nodes"] if row["name"] == joint.DRIVERS[0])
            next(row for row in raw["nodes"] if row["name"] == joint.DRIVERS[1])["world"] = copy.deepcopy(left["world"])
        with self.assertRaises(ValueError):associate(value)
    def test_unit_actor_root_local_world_and_rest_required(self):
        for kind in ("actor", "root", "local", "world", "rest"):
            value = symbolic_fixture();raw = value["worldB"]
            if kind == "actor":raw["refs"][0]["scale"] = 1.01
            elif kind == "root":raw["refs"][0]["sceneTransform"]["scale"] = 1.01
            elif kind == "rest":value["restLocal"][joint.DRIVERS[0]]["translation"][0] += .05
            else:raw["nodes"][0][kind]["scale"] = 1.01
            with self.subTest(kind=kind), self.assertRaises(ValueError):associate(value)
    def test_stale_main_task_or_changed_paused_solver_refused(self):
        for kind in ("sample", "time", "root", "solver", "request"):
            value = symbolic_fixture()
            if kind == "sample":value["worldB"]["sampleId"] = value["worldA"]["sampleId"]
            elif kind == "time":value["worldB"]["producerMonotonicNs"] = value["worldA"]["producerMonotonicNs"]
            elif kind == "root":value["worldB"]["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
            elif kind == "solver":value["witnessB"]["sample"]["objectWindow"]["lastPostQpc"] += 1
            else:value["witnessB"]["requestSerial"] = value["witnessA"]["requestSerial"]
            with self.subTest(kind=kind), self.assertRaises(ValueError):associate(value)
    def test_no_input_mutation_or_historical_module_admission(self):
        value = symbolic_fixture();before = copy.deepcopy(value)
        with patch.object(joint.cached, "module_admission", side_effect=AssertionError("Historical module pins must not be used")):
            joint.score_case(associate(value), value["finalWitness"], value["restLocal"])
        self.assertEqual(value, before)


if __name__ == "__main__":unittest.main()
