"""Synthetic VR Observer controls for the stock CBPC geometry gate."""

import copy
import unittest

from cbpc_vr_geometry import admit_holds, measure_frame


ACTOR = 0xFF000899
BASE = 0x0B000800
CELL = 0x0A01A5C6
PID = 123
HZ = 10_000_000
ROTATION = [0, -1, 0, 1, 0, 0, 0, 0, 1]
FIXTURE = {"actor": ACTOR, "base": BASE, "cell": CELL, "pid": PID,
           "target_offset": [1, 0, 0], "target_radius": 2.}


def pose(position, scale=1.):
    return {"translation": list(position), "rotationRowMajor": ROTATION.copy(), "scale": scale}


def reference(form, base, position):
    return {"identity": {"form": f"0x{form:08X}", "loadGeneration": 1, "runtimeHandle": form & 0xffff},
            "baseForm": f"0x{base:08X}", "cellForm": f"0x{CELL:08X}", "status": "available", "loaded3D": True,
            "disabled": False, "deleted": False, "position": list(position), "sceneTransform": pose(position)}


def sample(sequence, ns, left_x):
    player = reference(0x14, 7, (0, 0, 0))
    npc = reference(ACTOR, BASE, (15, 0, 0))
    return {"ok": True, "schemaVersion": 1, "observerVersion": "0.2.6", "quality": "complete",
            "sessionId": f"{PID}-birth", "loadGeneration": 1, "sampleId": sequence, "producerFrame": 10 * sequence,
            "producerMonotonicNs": ns, "phase": "skse_main_thread_task", "space": "world",
            "units": "skyrim_engine_units", "refs": [player, npc],
            "coherence": {"mode": "single_main_thread_task", "physics": "not_sampled", "render": "not_synchronized"},
            "nodes": [{"name": "TailBone01", "firstPerson": False, "status": "available",
                       "identity": npc["identity"].copy(), "form": npc["identity"]["form"],
                       "world": pose((15, -2, 9), 2.)}],
            "vrPicking": {"status": "available", "space": "world", "units": "skyrim_engine_units",
                          "phase": "skse_main_thread_task",
                          "nodes": {"leftWand": {"name": "LeftWandNode", "status": "available",
                                                 "world": pose((left_x, 0, 10), .5)},
                                    "rightWand": {"name": "RightWandNode", "status": "available",
                                                  "world": pose((-10, 0, 10))},
                                    "uprightHmd": {"name": "UprightHmdNode", "status": "available",
                                                   "world": pose((0, 0, 15))}}}}


def run(frames):
    return admit_holds(frames, **FIXTURE, qpc_frequency=HZ,
                       minimum_hold_ticks=HZ - 1, maximum_gap_ticks=HZ // 2)


class CbpcVrGeometryControls(unittest.TestCase):
    def setUp(self):
        self.frames = {phase: [sample(3 * group + i + 1, (1 + 2 * group) * 10**9 + i * 500_000_000 + 99, left_x)
                               for i in range(3)]
                       for group, (phase, left_x) in enumerate(
                           (("nearBefore", 10), ("far", -4), ("nearAfter", 10), ("nearDetached", 10)))}

    def test_rotates_and_scales_both_world_spheres(self):
        result = measure_frame(self.frames["nearBefore"][0], **FIXTURE)
        self.assertEqual(result["source"], [13., 0., 9.])
        self.assertEqual(result["target"], [15., 0., 9.])
        self.assertEqual(result["distance"], 2.)
        self.assertEqual(result["radiusSum"], 5.5)

    def test_measures_the_nearest_point_on_a_rotated_named_capsule(self):
        raw = self.frames["nearBefore"][0]
        raw["nodes"][0]["name"] = "EarR"
        raw["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][1] = 1
        result = measure_frame(raw, **FIXTURE, target_node="EarR", target_end=[1, 2, 0])
        self.assertEqual(result["target"], [15., 0., 9.])
        self.assertEqual(result["segmentEnd"], [11., 0., 9.])
        self.assertEqual(result["distance"], 1.)
        self.assertEqual(result["radiusSum"], 5.5)
        with self.assertRaisesRegex(ValueError, "Expected exact owned third-person TailBone01"):
            measure_frame(raw, **FIXTURE)

    def test_capsule_distance_clamps_to_endpoints_and_accepts_a_point_capsule(self):
        raw = self.frames["nearBefore"][0]
        result = measure_frame(raw, **FIXTURE, target_end=[1, .5, 0])
        self.assertEqual(result["segmentEnd"], [14., 0., 9.])
        self.assertEqual(result["distance"], 1.)
        point = measure_frame(raw, **FIXTURE, target_end=FIXTURE["target_offset"])
        self.assertEqual(point["distance"], 2.)

    def test_measured_holds_bound_event_clock_inward(self):
        result = run(self.frames)
        self.assertEqual(result["holds"], {"nearBefore": (10_000_001, 20_000_000), "far": (30_000_001, 40_000_000),
                                          "nearAfter": (50_000_001, 60_000_000), "nearDetached": (70_000_001, 80_000_000)})
        self.assertEqual(result["evidence"]["nearBefore"]["maxSurfaceGap"], -3.5)
        self.assertEqual(result["evidence"]["far"]["minSurfaceGap"], 10.5)
        self.assertEqual(result["observation"], "nominal_scene_spheres")

    def test_far_must_be_separated_and_near_must_overlap(self):
        for phase, x in (("far", 8), ("nearAfter", 3)):
            with self.subTest(phase=phase), self.assertRaisesRegex(ValueError, "separation/overlap"):
                frames = copy.deepcopy(self.frames)
                for raw in frames[phase]:
                    raw["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][0] = x
                run(frames)

    def test_missing_or_wrong_owner_geometry_does_not_qualify(self):
        mutations = (
            lambda raw: raw["nodes"].append(copy.deepcopy(raw["nodes"][0])),
            lambda raw: raw["nodes"][0].update(firstPerson=True),
            lambda raw: raw["nodes"][0]["identity"].update(runtimeHandle=1),
            lambda raw: raw["refs"][1].update(cellForm="0x02000001"),
            lambda raw: raw["refs"][1].update(loaded3D=False),
            lambda raw: raw["vrPicking"].update(phase="wrong"),
            lambda raw: raw["vrPicking"]["nodes"]["leftWand"].update(name="RightWandNode"),
            lambda raw: raw["nodes"][0]["world"].update(scale=float("nan")),
        )
        for change in mutations:
            with self.subTest(change=change), self.assertRaises(ValueError):
                frames = copy.deepcopy(self.frames)
                change(frames["nearBefore"][1])
                run(frames)

    def test_reference_controls_and_stable_wand_must_hold(self):
        changes = (
            (lambda raw: raw["refs"][1]["position"].__setitem__(0, 18), "Reference drift"),
            (lambda raw: raw["vrPicking"]["nodes"]["uprightHmd"]["world"]["translation"].__setitem__(1, 1),
             "HMD, right controller"),
            (lambda raw: raw["vrPicking"]["nodes"]["leftWand"]["world"]["translation"].__setitem__(0, 9),
             "Left controller moved"),
        )
        for change, reason in changes:
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                frames = copy.deepcopy(self.frames)
                change(frames["nearBefore"][1])
                run(frames)
        for raw in self.frames["nearAfter"]:
            raw["vrPicking"]["nodes"]["leftWand"]["world"]["translation"][0] = 9
        with self.assertRaisesRegex(ValueError, "original near pose"):
            run(self.frames)

    def test_replayed_and_sparse_clock_intervals_refused(self):
        for key in ("sampleId", "producerFrame", "producerMonotonicNs", "sessionId"):
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "Replayed or different-process"):
                frames = copy.deepcopy(self.frames)
                first, second = frames["far"][:2]
                second[key] = f"{PID}-other" if key == "sessionId" else first[key]
                run(frames)
        del self.frames["far"][1]
        with self.assertRaisesRegex(ValueError, "hold gap"):
            run(self.frames)

    def test_phase_presence_and_hold_duration_are_independent(self):
        del self.frames["nearDetached"]
        self.assertNotIn("nearDetached", run(self.frames)["holds"])
        del self.frames["far"][-1]
        with self.assertRaisesRegex(ValueError, "hold is too short"):
            run(self.frames)
        del self.frames["far"]
        with self.assertRaisesRegex(ValueError, "Complete near/far/near"):
            run(self.frames)
