"""Exercise calibrated left-wand movement through an admitted driver adapter."""

from copy import deepcopy
from hashlib import sha256
import json
from math import dist
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from pose_contact_driver import (
    CalibratedWand, FIXED_HOLD_SECONDS, HOLD_SECONDS, MovementLimits, PROBE_METRES, TRANSLATION, fit_columns,
    moved_frame, public_frame, tracking_xyz,
)
from run_pose_contact import PoseContactCapture
from test_run_pose_contact import AdmittedExecutor, EVIDENCE, FAR, NONCE
from test_tail_refit import ACTOR, BASE, CELL, NODE, PID, point
from verify_tail_refit import Subject


OWNER = "1" * 32
INSTANCE = "43984-134396856007491964"
START = np.array([-.3, 1.2, -.35])
TRACKING_TO_WORLD = np.array([[-65.78125, 0., -23.9453125], [-23.984375, 0., 65.78125], [0., 70., 0.]])
WAND_ORIGIN = np.array([5606.43359375, -17439.626953125, 4594.609375])
WAND_ROTATION = np.array([[-.9396926, .3420202, 0.], [-.3420202, -.9396926, 0.], [0., 0., 1.]])


def reference_frame():
    frame = {"seq": 1, "tMs": 0, "originCode": 1}
    for name, xyz in (("hmd", [0., 1.65, 0.]), ("left", START), ("right", [.3, 1.2, -.35])):
        x, y, z = xyz
        frame[name] = {"matrix": [0., -1., 0., x, 1., 0., 0., y, 0., 0., 1., z],
                       "controller": {"pressed": 0, "touched": 0, "axes": [[0., 0.]] * 5}}
    return frame


class AdmittedDriver:
    def __init__(self, *, columns=TRACKING_TO_WORLD, right_offset=(0., 125., 5.)):
        self.clock = 1.
        self.sample = 0
        self.sequence = 100
        self.inputs = []
        self.publications = []
        self.last_status = None
        self.ref_frame = reference_frame()
        self.state = {"hardwareOwner": OWNER, "inputBackend": "driver", "driverBackend": "file",
                      "focusInputPaused": False, "hardwareFrame": self.leased_frame(self.ref_frame)}
        self.columns = columns
        self.actual = START.copy()
        self.motion_consumed = True
        self.driver_instance = INSTANCE
        self.room_epoch = 4
        self.delay_ack = 0
        self.fixed_reported_seconds = FIXED_HOLD_SECONDS
        self.fixed_position_error = 0.
        self.observed_tick_offset = 0
        self.reference = self.scene(START)
        self.reference["controls"]["right"]["translation"] = (np.asarray(self.reference["source"]) + right_offset).tolist()
        self.probes = []
        for axis in np.eye(3):
            xyz = START + PROBE_METRES * axis
            self.probes.append((moved_frame(self.ref_frame, xyz), self.scene(xyz), self.scene(START)))

    def leased_frame(self, frame):
        publication = {"version": 2, "owner": OWNER, "command": f"{self.sequence:032x}",
                       "sequence": self.sequence, "publishedTickMs": self.tick_ms(),
                       "expiresTickMs": self.tick_ms() + 5000}
        return {**deepcopy(frame), "_owner": OWNER, "_command": publication["command"], "_publication": publication}

    def tick_ms(self):
        return round(self.clock * 1000) + 100_000

    def monotonic(self):
        return self.clock

    def sleep(self, seconds):
        self.clock += seconds

    def scene(self, xyz):
        self.sample += 1
        wand_position = WAND_ORIGIN + self.columns @ (xyz - START)
        source = wand_position + WAND_ROTATION @ np.array([0., -6., -2.])
        if hasattr(self, "reference"):
            controls = deepcopy(self.reference["controls"])
        else:
            controls = {"head": point(*(source + [0., 0., 140.])), "right": point()}
        return {"session": "10420-owned", "epoch": self.room_epoch, "sample": self.sample, "frame": self.sample * 2,
                "ns": self.sample * 120_000_000, "actor": ({"runtimeHandle": 123}, [4., 5., 6.], point(4., 5., 6.)),
                "player": ({"runtimeHandle": 456}, [7., 8., 9.], point(7., 8., 9.)),
                "root": point(4., 5., 6.), "controls": controls,
                "left": {**point(*wand_position), "rotationRowMajor": WAND_ROTATION.ravel().tolist()},
                "source": source.tolist()}

    def observe(self, deadline):
        if self.clock >= deadline:
            raise AssertionError("Observer used outside the admitted deadline")
        self.sleep(.02)
        return self.scene(self.actual)

    def call(self, name, request, *, timeout, deadline):
        if name != "driver" or not 0 < timeout <= min(deadline - self.clock, 1.5):
            raise AssertionError("Driver request left the admitted boundary")
        started = self.clock
        self.sleep(.02)
        if request["action"] == "publish":
            duration = request["holdSeconds"]
            if set(request) != {"action", "frame", "holdSeconds"} or duration not in (HOLD_SECONDS, FIXED_HOLD_SECONDS):
                raise AssertionError("Inexact Protocol 2 publication")
            frame = deepcopy(request["frame"])
            self.inputs.append(frame)
            self.sequence += 10
            self.state["hardwareFrame"] = self.leased_frame(frame)
            self.state["hardwareHoldUntilTickMs"] = self.tick_ms() + int(duration * 1000)
            publication = deepcopy(self.state["hardwareFrame"]["_publication"])
            self.publications.append((started, duration, publication))
            self.delay_ack = 1
            if self.motion_consumed:
                self.actual = tracking_xyz(frame)
                if duration == FIXED_HOLD_SECONDS:
                    self.actual[0] += self.fixed_position_error
            return {"published": True, "holdSeconds": self.fixed_reported_seconds if duration == FIXED_HOLD_SECONDS else duration,
                    "publication": publication}
        if request != {"action": "status"}:
            raise AssertionError("Unexpected driver request outside publish/status")
        frame = self.state["hardwareFrame"]
        active = frame["_publication"]
        if self.delay_ack:
            self.delay_ack -= 1
            return {"acknowledgedByDriver": False, "protocolVersion": 2}
        # Simulate the executor heartbeat renewing the same command at a later sequence.
        active["sequence"] = self.sequence + 1
        raw = f"SKYRIM_AUTOTEST_ACK 2 {self.driver_instance} {OWNER} {active['sequence']} {active['command']} 100 5099 7 0 0\n"
        self.last_status = {"acknowledgedByDriver": True, "protocolVersion": 2, "rolesUpdated": 7, "errorRoles": 0,
                            "expired": False, "command": active["command"], "sequence": active["sequence"],
                            "driverInstance": self.driver_instance, "rawAcknowledgement": raw,
                            "observedTickMs": self.tick_ms() + self.observed_tick_offset}
        return self.last_status

    def binding(self, limits=MovementLimits(.45, .8, .10)):
        return CalibratedWand(self.call, self.state, self.observe, self.ref_frame, self.reference,
                              self.probes, INSTANCE, limits, clock=self)

    def center(self, xyz):
        return np.asarray(self.reference["source"]) + self.columns @ (xyz - START)


class CalibratedExecutor(AdmittedExecutor):
    def __init__(self, directory):
        super().__init__(directory)
        self.driver = AdmittedDriver()
        controls = self.scene["vrPicking"]["nodes"]
        controls["rightWand"]["world"]["translation"] = [0., 140., 0.]
        controls["uprightHmd"]["world"]["translation"] = [0., 0., 140.]
        self.driver_rows = []

    def tool(self, name, args, *, timeout, deadline):
        if name != "driver":
            return super().tool(name, args, timeout=timeout, deadline=deadline)
        self.driver.clock = self.now
        reply = self.driver.call(name, args, timeout=timeout, deadline=deadline)
        self.now = self.driver.clock
        action = args["action"]
        frame = None
        if action == "publish":
            self.current_center = tuple((FAR + TRACKING_TO_WORLD @ (self.driver.actual - START)).tolist())
            self.position_frame = 0
            frame = self.driver.state["hardwareFrame"]
        row = deepcopy({"kind": "driver", "action": action, "result": reply, "frame": frame})
        self.driver_rows.append(row)
        self.append(row)
        return reply

    def observe(self):
        attached = self.attached
        self.attached = False
        try:
            result = super().observe()
        finally:
            self.attached = attached
        # The calibrated driver measures arrival before the hold's first sample.
        if attached and self.position_frame == 3 and dist(self.current_center, (6., 0., .5)) < 4.:
            self.callbacks.append({"sequence": len(self.callbacks) + 1, "qpc": self.tick(),
                                   "eventName": "CBPCPlayerCollisionWithMaleEvent", "strArg": NODE,
                                   "senderFormId": ACTOR, "numArg": .45})
        return result

    def acquired_probes(self, capture):
        def measure(frame):
            self.tool("driver", {"action": "publish", "frame": frame, "holdSeconds": HOLD_SECONDS},
                      timeout=1.5, deadline=capture.deadline)
            self.tool("driver", {"action": "status"}, timeout=1.5, deadline=capture.deadline)
            ack = self.tool("driver", {"action": "status"}, timeout=1.5, deadline=capture.deadline)
            if ack["acknowledgedByDriver"] is not True:
                raise AssertionError("The admitted calibration frame was not acknowledged")
            return capture.observe()[1]

        origin = capture.observe()[1]
        probes = []
        for axis in np.eye(3):
            frame = moved_frame(self.driver.ref_frame, START + PROBE_METRES * axis)
            probes.append((frame, measure(frame), measure(self.driver.ref_frame)))
        return origin, probes


class PoseContactDriverTest(unittest.TestCase):
    def test_capture_runs_calibrated_driver_and_keeps_raw_evidence_through_neutral_return(self):
        with TemporaryDirectory() as root:
            executor = CalibratedExecutor(Path(root))
            capture = PoseContactCapture(executor.tool, executor.path, executor.ack_log,
                                         Subject(PID, ACTOR, BASE, CELL, 0), executor.profile,
                                         deadline=28., clock=executor)
            capture.node = NODE
            reference, probes = executor.acquired_probes(capture)
            first_contact_driver_row = len(executor.driver_rows)

            manifest, raw, verdict = capture.run_calibrated(
                NODE, NONCE, EVIDENCE, state=executor.driver.state, reference_frame=executor.driver.ref_frame,
                reference=reference, probes=probes, driver_instance=INSTANCE, limits=MovementLimits(.45, .8, .06),
            )

            self.assertEqual(verdict["status"], "qualified-emission-contrast")
            self.assertEqual(verdict["preAppendPosition"], "unattachedFar")
            self.assertEqual(verdict["qualifiedHeldEventCounts"],
                             {"nearBefore": 1, "far": 0, "nearAfter": 1, "nearDetached": 0})
            np.testing.assert_allclose(executor.current_center, FAR, atol=1e-9)
            self.assertEqual(public_frame(executor.driver.state["hardwareFrame"]), executor.driver.ref_frame)
            self.assertFalse(executor.attached)
            self.assertTrue(executor.ended)
            self.assertEqual(raw["steps"], executor.path.read_bytes())
            self.assertEqual(manifest["sha256"]["steps"], sha256(raw["steps"]).hexdigest())

            ledger = [json.loads(line) for line in raw["steps"].splitlines()]
            self.assertEqual([row for row in ledger if row["kind"] == "driver"], executor.driver_rows)
            contact_rows = executor.driver_rows[first_contact_driver_row:]
            publications = [row for row in contact_rows if row["action"] == "publish"]
            self.assertGreater(len(publications), 4)
            self.assertEqual(public_frame(publications[-1]["frame"]), executor.driver.ref_frame)
            self.assertTrue(contact_rows[-1]["result"]["acknowledgedByDriver"])
            self.assertEqual(contact_rows[-1]["result"]["command"], publications[-1]["result"]["publication"]["command"])
            self.assertIn(publications[-1], ledger[manifest["capture"]["read"] + 1:])

    def test_three_axis_fit_and_confirmed_multistep_round_trip_preserve_full_frame(self):
        executor = AdmittedDriver()
        driver = executor.binding()
        np.testing.assert_allclose(driver.columns, TRACKING_TO_WORLD, atol=1e-9)
        xyz = START + [.25, -.08, .06]
        center = executor.center(xyz)
        np.testing.assert_allclose(driver.tracking([center]), [xyz], atol=1e-9)
        np.testing.assert_allclose(driver.world(xyz), center, atol=1e-9)

        self.assertTrue(driver("far", None, deadline=20.))
        before_near = len(executor.inputs)
        self.assertTrue(driver("near", center, deadline=20.))
        near_frames = executor.inputs[before_near:]
        self.assertGreater(len(near_frames), 1)
        np.testing.assert_allclose(executor.actual, xyz, atol=1e-9)
        self.assertTrue(driver("far", None, deadline=20.))
        self.assertTrue(driver("near", center, deadline=20.))
        self.assertTrue(driver.restore(deadline=20.))
        np.testing.assert_allclose(executor.actual, START, atol=1e-9)
        self.assertFalse(driver.pending)

        previous = START
        for frame in executor.inputs:
            current = tracking_xyz(frame)
            self.assertLessEqual(dist(previous, current), .10 + 1e-9)
            previous = current
            template = deepcopy(executor.ref_frame)
            for index in TRANSLATION:
                template["left"]["matrix"][index] = frame["left"]["matrix"][index]
            self.assertEqual(frame, template)
        self.assertEqual(public_frame(executor.state["hardwareFrame"]), executor.ref_frame)
        self.assertTrue(all(duration == HOLD_SECONDS for _, duration, _ in executor.publications))

    def test_fixed_hold_republishes_the_settled_pose_once_and_returns_exact_status(self):
        executor = AdmittedDriver()
        driver = executor.binding()
        xyz = START + [.25, -.08, .06]
        hold = driver.hold_fixed(executor.center(xyz), deadline=20.)
        issued, duration, expected = executor.publications[-1]
        self.assertEqual(duration, FIXED_HOLD_SECONDS)
        self.assertEqual(hold.expires, issued + FIXED_HOLD_SECONDS)
        self.assertEqual(hold.publication, expected)
        self.assertEqual(hold.publication["owner"], OWNER)
        self.assertTrue(all(duration == HOLD_SECONDS for _, duration, _ in executor.publications[:-1]))
        self.assertEqual(executor.inputs[-2], executor.inputs[-1])
        np.testing.assert_allclose(executor.actual, xyz, atol=1e-9)

        before = len(executor.inputs)
        self.assertIs(hold.confirm(deadline=20.), executor.last_status)
        self.assertGreater(executor.last_status["sequence"], hold.publication["sequence"])
        self.assertEqual(executor.last_status["driverInstance"], INSTANCE)
        hold.publication["command"] = "poisoned copy"
        self.assertEqual(hold.publication, expected)
        self.assertEqual(len(executor.inputs), before)
        self.assertTrue(driver.restore(deadline=20.))
        self.assertEqual(executor.publications[-1][1], HOLD_SECONDS)
        with self.assertRaisesRegex(ValueError, "custody|hold changed"):
            hold.confirm(deadline=20.)

    def test_fixed_hold_refuses_expired_shifted_or_unacknowledged_commands(self):
        for reason in ("local expiry", "boot expiry", "retimed", "new instance", "pending ack", "foreign frame"):
            with self.subTest(reason=reason):
                executor = AdmittedDriver()
                driver = executor.binding()
                hold = driver.hold_fixed(executor.center(START + [.15, 0., 0.]), deadline=20.)
                if reason == "local expiry":
                    executor.clock = hold.expires
                elif reason == "boot expiry":
                    executor.observed_tick_offset = 30_000
                elif reason == "retimed":
                    executor.state["hardwareHoldUntilTickMs"] += 1000
                elif reason == "new instance":
                    executor.driver_instance = "43984-134396856009999999"
                elif reason == "pending ack":
                    executor.delay_ack = 1
                elif reason == "foreign frame":
                    executor.state["hardwareFrame"]["_publication"]["command"] = "3" * 32
                before = len(executor.inputs)
                with self.assertRaises(ValueError):
                    hold.confirm(deadline=hold.expires + 2.)
                self.assertEqual(len(executor.inputs), before)

    def test_fixed_hold_requires_its_exact_duration_receipt_and_fresh_geometry(self):
        for changed in ("duration", "geometry"):
            with self.subTest(changed=changed):
                executor = AdmittedDriver()
                driver = executor.binding()
                if changed == "duration":
                    executor.fixed_reported_seconds = 29.
                else:
                    executor.fixed_position_error = .02
                with self.assertRaisesRegex(ValueError, "not newly confirmed|World Observer did not measure"):
                    driver.hold_fixed(executor.center(START + [.12, 0., 0.]), deadline=20.)
                self.assertTrue(driver.pending)
                self.assertEqual([duration for _, duration, _ in executor.publications].count(FIXED_HOLD_SECONDS), 1)

    def test_matching_ack_cannot_substitute_for_actual_motion(self):
        executor = AdmittedDriver()
        driver = executor.binding()
        executor.motion_consumed = False
        with self.assertRaisesRegex(ValueError, "World Observer did not measure"):
            driver("near", executor.center(START + [.25, 0., 0.]), deadline=20.)
        self.assertTrue(driver.pending)
        self.assertEqual(len(executor.inputs), 1)
        np.testing.assert_allclose(executor.actual, START)
        with self.assertRaisesRegex(ValueError, "prior move remains unresolved"):
            driver.restore(deadline=20.)
        self.assertEqual(len(executor.inputs), 1)

    def test_changed_owner_room_or_driver_instance_refuses_before_any_publication(self):
        for changed, message in (
            ("owner", "Owned controller delivery is unavailable"),
            ("room", "outside its last confirmed position"),
            ("instance", "matching owned-driver acknowledgment"),
        ):
            with self.subTest(changed=changed):
                executor = AdmittedDriver()
                driver = executor.binding()
                if changed == "owner":
                    executor.state["hardwareOwner"] = "2" * 32
                elif changed == "room":
                    executor.room_epoch += 1
                else:
                    executor.driver_instance = "43984-134396856009999999"
                with self.assertRaisesRegex(ValueError, message):
                    driver("near", executor.center(START + [.18, 0., 0.]), deadline=20.)
                self.assertFalse(executor.inputs)

    def test_sweep_refuses_clear_endpoints_when_segment_crosses_right_controller(self):
        halfway = TRACKING_TO_WORLD @ [.70, 0., 0.]
        executor = AdmittedDriver(right_offset=halfway)
        driver = executor.binding(MovementLimits(1.5, .8, 1.5))
        target = executor.center(START + [1.4, 0., 0.])
        right = executor.reference["controls"]["right"]["translation"]
        for endpoint in (executor.reference["source"], target):
            self.assertGreater(dist(endpoint, right) - 3. - .35, .50 * 72.)
        with self.assertRaisesRegex(ValueError, "full controller path exceeds"):
            driver("near", target, deadline=20.)
        self.assertFalse(executor.inputs)

    def test_calibration_refuses_reflection_wrong_axis_and_wrong_return(self):
        reflected = TRACKING_TO_WORLD.copy()
        reflected[:, 2] *= -1
        reflected_executor = AdmittedDriver(columns=reflected)
        with self.assertRaisesRegex(ValueError, "original handedness"):
            reflected_executor.binding()

        executor = AdmittedDriver()
        wrong_axis = list(executor.probes)
        _, sample, returned = wrong_axis[0]
        wrong_axis[0] = (moved_frame(executor.ref_frame, START + [0., PROBE_METRES, 0.]), sample, returned)
        with self.assertRaisesRegex(ValueError, "wrong axes"):
            fit_columns(executor.ref_frame, executor.reference, wrong_axis)

        wrong_return = deepcopy(executor.probes)
        wrong_return[2][2]["source"][0] += 2.
        with self.assertRaisesRegex(ValueError, "failed to restore"):
            fit_columns(executor.ref_frame, executor.reference, wrong_return)


if __name__ == "__main__":
    unittest.main()
