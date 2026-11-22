"""Map a measured CLAW contact point through the admitted VR controller route."""

from copy import deepcopy
from dataclasses import dataclass
from math import ceil, dist, isfinite
import time

import numpy as np

from prepare_tail_refit_waypoint import GAIN_MAX, point_clearance
from verify_tail_refit import DRIFT, _same_pose, require


TRANSLATION = (3, 7, 11)
PROBE_METRES = .025
HOLD_SECONDS = 5.


def public_frame(frame):
    return {key: deepcopy(value) for key, value in frame.items() if not key.startswith("_")}


def tracking_xyz(frame):
    return np.asarray([frame["left"]["matrix"][index] for index in TRANSLATION], dtype=float)


def moved_frame(frame, xyz):
    updated = public_frame(frame)
    for index, value in zip(TRANSLATION, xyz, strict=True):
        updated["left"]["matrix"][index] = float(value)
    return updated


def same_room(reference, measured):
    return (all(measured[key] == reference[key] for key in ("session", "epoch")) and
            all(measured[key][0] == reference[key][0] and dist(measured[key][1], reference[key][1]) <= DRIFT and
                _same_pose(reference[key][2], measured[key][2], DRIFT) for key in ("actor", "player")) and
            _same_pose(reference["root"], measured["root"], DRIFT) and
            all(_same_pose(reference["controls"][role], measured["controls"][role], DRIFT) for role in ("head", "right")) and
            _same_pose({**reference["left"], "translation": measured["left"]["translation"]}, measured["left"], DRIFT))


def newer(previous, current):
    return all(type(current[key]) is int and current[key] > previous[key] for key in ("sample", "frame", "ns"))


def acknowledges(status, publication, driver_instance):
    return (status.get("acknowledgedByDriver") is True and status.get("protocolVersion") == 2 and
            status.get("rolesUpdated") == 7 and status.get("errorRoles") == 0 and status.get("expired") is False and
            status.get("command") == publication["command"] and type(status.get("sequence")) is int and
            status["sequence"] >= publication["sequence"] and status.get("driverInstance") == driver_instance and
            bool(status.get("rawAcknowledgement")))


def fit_columns(reference_frame, reference, probes):
    """Three ordered acknowledged positive axis probes and their measured returns."""
    require(len(probes) == 3, "Independent X, Y and Z probes are required")
    xyz = tracking_xyz(reference_frame)
    columns, previous = [], reference
    for axis, (frame, measured, returned) in enumerate(probes):
        delta = np.eye(3)[axis] * PROBE_METRES
        require(public_frame(frame) == moved_frame(reference_frame, xyz + delta), "A calibration command changed the wrong axes")
        require(newer(previous, measured) and newer(measured, returned) and same_room(reference, measured) and
                same_room(reference, returned) and dist(reference["source"], returned["source"]) <= DRIFT,
                "Calibration moved the room basis or failed to restore the reference point")
        columns.append((np.asarray(measured["source"]) - reference["source"]) / PROBE_METRES)
        previous = returned
    result = np.stack(columns, axis=1)
    require(np.isfinite(result).all(), "Controller projection is not finite")
    maximum, minimum = np.linalg.svd(result, compute_uv=False)[[0, 2]]
    require(68. <= minimum <= maximum <= GAIN_MAX and maximum <= 1.03 * minimum and np.linalg.det(result) > 0.,
            "Expected a near-rigid measured tracking basis with the original handedness")
    return result


@dataclass(frozen=True)
class MovementLimits:
    """Controller limits reviewed for the admitted fixture, in tracking metres."""

    travel: float
    minimum_height: float
    step: float = .10

    def __post_init__(self):
        require(all(type(value) in (int, float) and isfinite(value) and value > 0.
                    for value in (self.travel, self.minimum_height, self.step)) and self.step <= self.travel,
                "The admitted movement limits must be finite and positive")


class CalibratedWand:
    """Publish finite left-hand waypoints and independently confirm each one."""

    def __init__(self, call, state, observe, reference_frame, reference, probes, driver_instance, limits, *, clock=time):
        session_frame = state.get("hardwareFrame") or {}
        self.call, self.state, self.observe, self.clock = call, state, observe, clock
        self.reference_frame, self.reference = public_frame(reference_frame), deepcopy(reference)
        self.columns = fit_columns(reference_frame, reference, probes)
        self.reference_xyz = tracking_xyz(reference_frame)
        self.driver_instance, self.limits = driver_instance, limits
        self.owner = state.get("hardwareOwner")
        require(isinstance(self.owner, str) and len(self.owner) == 32 and isinstance(driver_instance, str) and driver_instance and
                public_frame(session_frame) == self.reference_frame, "Expected the restored owned calibration frame")
        for role in ("left", "right"):
            controls = self.reference_frame[role]["controller"]
            require(controls["pressed"] == 0 and controls["touched"] == 0 and controls["axes"] == [[0., 0.]] * 5,
                    "Contact motion requires neutral controller inputs")
        self.expected = session_frame.get("_publication")
        self.check_publication(self.expected)
        self.measured = deepcopy(probes[-1][2])
        self.xyz = self.reference_xyz.copy()
        self.pending = False

    def check_publication(self, publication):
        require(isinstance(publication, dict) and publication.get("version") == 2 and publication.get("owner") == self.owner and
                isinstance(publication.get("command"), str) and len(publication["command"]) == 32 and
                type(publication.get("sequence")) is int and publication["sequence"] > 0,
                "Expected an exact owned Protocol 2 publication")

    def driver(self, action, deadline, **args):
        remaining = deadline - self.clock.monotonic()
        require(remaining > 0 and self.state.get("hardwareOwner") == self.owner and self.state.get("inputBackend") == "driver" and
                self.state.get("driverBackend") == "file" and self.state.get("focusInputPaused") is not True,
                "Owned controller delivery is unavailable")
        result = self.call("driver", {"action": action, **args}, timeout=min(1.5, remaining), deadline=deadline)
        require(self.clock.monotonic() < deadline, "Controller operation exceeded the admitted deadline")
        return result

    def world(self, xyz):
        return np.asarray(self.reference["source"]) + self.columns @ (xyz - self.reference_xyz)

    def tracking(self, points):
        displacement = np.asarray(points, dtype=float) - self.reference["source"]
        return np.linalg.solve(self.columns, displacement.T).T + self.reference_xyz

    def reachable(self, points, frame):
        require(same_room(self.reference, frame), "The controller room basis changed")
        xyz = self.tracking(points)
        return ((np.linalg.norm(xyz - self.reference_xyz, axis=1) <= self.limits.travel) &
                (xyz[:, 1] >= self.limits.minimum_height) &
                (point_clearance(frame, points, "head") >= .30 * GAIN_MAX) &
                (point_clearance(frame, points, "right") >= .50 * GAIN_MAX))

    def confirm(self, deadline):
        for _ in range(4):
            status = self.driver("status", deadline)
            if acknowledges(status, self.expected, self.driver_instance):
                return
            self.clock.sleep(.08)
        raise ValueError("Controller command lacks a matching owned-driver acknowledgment")

    def require_owned_frame(self, xyz):
        current = self.state.get("hardwareFrame") or {}
        publication = current.get("_publication")
        self.check_publication(publication)
        require(public_frame(current) == moved_frame(self.reference_frame, xyz) and
                publication["command"] == self.expected["command"] and publication["sequence"] >= self.expected["sequence"],
                "The current driver frame is outside case custody")

    def publish(self, xyz, deadline):
        self.require_owned_frame(self.xyz)
        frame = moved_frame(self.reference_frame, xyz)
        previous = self.expected
        self.pending = True
        result = self.driver("publish", deadline, frame=frame, holdSeconds=HOLD_SECONDS)
        publication = result.get("publication")
        self.check_publication(publication)
        require(result.get("published") is True and publication["command"] != previous["command"] and
                publication["sequence"] > previous["sequence"], "Controller publication was not newly confirmed")
        self.expected = publication
        self.confirm(deadline)
        self.require_owned_frame(xyz)
        predicted = self.world(xyz)
        for _ in range(4):
            measured = self.observe(deadline)
            require(same_room(self.reference, measured) and newer(self.measured, measured), "Stale or foreign pose after publication")
            self.measured = measured
            if dist(measured["source"], predicted) <= DRIFT:
                self.xyz, self.pending = xyz, False
                return
            self.clock.sleep(.08)
        raise ValueError("The World Observer did not measure the commanded hand position")

    def __call__(self, phase, waypoint, *, deadline):
        require(not self.pending and (phase == "near" and waypoint is not None or phase == "far" and waypoint is None),
                "Controller phase is invalid or a prior move remains unresolved")
        self.require_owned_frame(self.xyz)
        self.confirm(deadline)
        measured = self.observe(deadline)
        require(newer(self.measured, measured) and same_room(self.reference, measured) and
                dist(measured["source"], self.world(self.xyz)) <= DRIFT, "The hand is outside its last confirmed position")
        self.measured = measured
        target = self.reference_xyz.copy() if phase == "far" else self.tracking(waypoint)
        require(target.shape == (3,) and np.isfinite(target).all(), "The contact waypoint must be one finite world point")
        require(bool(self.reachable(np.asarray([self.world(target)]), self.measured)[0]),
                "The full controller path exceeds reach or head/right swept clearance")
        first = self.xyz.copy()
        steps = max(1, ceil(dist(first, target) / self.limits.step))
        for i in range(1, steps + 1):
            xyz = first + (target - first) * (i / steps)
            require(bool(self.reachable(np.asarray([self.world(xyz)]), self.measured)[0]),
                    "The controller step exceeds reach or head/right swept clearance")
            self.publish(xyz, deadline)
        return True

    def restore(self, *, deadline):
        return self("far", None, deadline=deadline)
