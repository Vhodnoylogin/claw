"""Nominal sphere and capsule geometry for stock CBPC VR fixtures.

The caller still owns the overlay, actor, provider, driver and attach receipts.
Observer frames contain scene transforms, without solver or render readback.
"""

import math

from cbpc_event_readback import positive_int, require
from src.test.python.integration.fsmp_probe import OBSERVATION, numbers, transform


PLAYER = 0x14
TAIL = "TailBone01"
CONTROLS = {"head": ("uprightHmd", "UprightHmdNode"), "right": ("rightWand", "RightWandNode")}
NANOSECONDS = 1_000_000_000


def _finite_positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _form(value, expected):
    return type(value) is str and value.casefold() == f"0x{expected:08x}"


def _sphere(frame, offset, radius):
    rotation, scale = frame["rotationRowMajor"], frame["scale"]
    center = [position + scale * sum(rotation[axis * 3 + i] * value for i, value in enumerate(offset))
              for axis, position in enumerate(frame["translation"])]
    radius *= scale
    require(all(math.isfinite(value) for value in center) and _finite_positive(radius),
            "Invalid nominal sphere in world space")
    return center, radius


def _point_segment_distance(point, start, end):
    edge = [b - a for a, b in zip(start, end, strict=True)]
    length_squared = sum(value * value for value in edge)
    require(math.isfinite(length_squared), "Invalid world capsule axis")
    if length_squared == 0:
        return math.dist(point, start)
    along = sum((value - origin) * delta for value, origin, delta in zip(point, start, edge, strict=True))
    require(math.isfinite(along), "Invalid world capsule projection")
    position = max(0., min(1., along / length_squared))
    closest = [origin + position * delta for origin, delta in zip(start, edge, strict=True)]
    return math.dist(point, closest)


def _reference(raw, form, base, cell):
    rows = [row for row in raw["refs"] if _form(row["identity"].get("form"), form)]
    require(len(rows) == 1, "Expected exactly one observed reference")
    row = rows[0]
    identity = row["identity"]
    require(row.get("status") == "available" and row.get("loaded3D") is True
            and row.get("disabled") is False and row.get("deleted") is False
            and _form(row.get("baseForm"), base) and _form(row.get("cellForm"), cell)
            and type(identity.get("loadGeneration")) is int
            and identity["loadGeneration"] == raw["loadGeneration"]
            and positive_int(identity.get("runtimeHandle")),
            "Reference is unavailable, foreign or in a different cell")
    return identity, numbers(row["position"], 3), transform(row["sceneTransform"])


def _wand(picking, key, name):
    row = picking["nodes"].get(key, {})
    require(row.get("status") == "available" and row.get("name") == name,
            "Missing exact VR tracking node: " + name)
    return transform(row["world"])


def measure_frame(raw, *, actor, base, cell, pid, target_offset, target_radius, target_node=None, target_end=None):
    """Extract synchronized scene geometry and both reference incarnations."""
    require(type(actor) is int and 0xFF000000 <= actor < 0xFFFFFFFF
            and all(positive_int(value) for value in (base, cell, pid)) and _finite_positive(target_radius),
            "Explicit disposable actor, process, cell and sphere required")
    require(raw.get("ok") is True and type(raw.get("schemaVersion")) is int and raw["schemaVersion"] == 1
            and raw.get("observerVersion") == "0.2.6" and raw.get("quality") == "complete"
            and raw.get("coherence") == OBSERVATION and raw.get("phase") == "skse_main_thread_task"
            and raw.get("space") == "world" and raw.get("units") == "skyrim_engine_units"
            and type(raw.get("sessionId")) is str and raw["sessionId"].startswith(f"{pid}-")
            and all(positive_int(raw.get(k)) for k in ("sampleId", "producerFrame", "producerMonotonicNs", "loadGeneration"))
            and len(raw.get("refs", [])) == 2,
            "Complete same-task VR Observer snapshot required")
    player = _reference(raw, PLAYER, 7, cell)
    npc = _reference(raw, actor, base, cell)
    node = TAIL if target_node is None else target_node
    require(isinstance(node, str) and bool(node), "An exact target node name is required")
    targets = [row for row in raw.get("nodes", []) if row.get("name") == node]
    require(len(targets) == 1 and targets[0].get("status") == "available"
            and targets[0].get("firstPerson") is False and targets[0].get("identity") == npc[0]
            and _form(targets[0].get("form"), actor), f"Expected exact owned third-person {node}")
    picking = raw.get("vrPicking", {})
    require(picking.get("status") == "available" and picking.get("phase") == raw["phase"]
            and picking.get("space") == raw["space"] and picking.get("units") == raw["units"],
            "VR tracking scene poses are unavailable")
    left = _wand(picking, "leftWand", "LeftWandNode")
    target_pose = transform(targets[0]["world"])
    target, target_world_radius = _sphere(target_pose, numbers(target_offset, 3), target_radius)
    source, source_world_radius = _sphere(left, (0., -6., -2.), 3.)
    shape = {"target": target, "radiusSum": source_world_radius + target_world_radius}
    if target_end is None:
        shape["distance"] = math.dist(source, target)
    else:
        endpoint, _ = _sphere(target_pose, numbers(target_end, 3), target_radius)
        shape.update(segmentEnd=endpoint, distance=_point_segment_distance(source, target, endpoint))
    return {"session": raw["sessionId"], "epoch": raw["loadGeneration"], "sample": raw["sampleId"],
            "frame": raw["producerFrame"],
            "ns": raw["producerMonotonicNs"], "player": player, "actor": npc, "left": left,
            "controls": {side: _wand(picking, *node) for side, node in CONTROLS.items()},
            "source": source, **shape}


def _same_basis(first, current):
    return (math.dist(first["rotationRowMajor"], current["rotationRowMajor"]) <= .005
            and abs(first["scale"] - current["scale"]) <= .005)


def _same_pose(first, current, tolerance):
    return (_same_basis(first, current)
            and math.dist(first["translation"], current["translation"]) <= tolerance)


def admit_holds(frames, *, actor, base, cell, pid, target_offset, target_radius, qpc_frequency,
                minimum_hold_ticks, maximum_gap_ticks, minimum_surface_margin=.75, maximum_pose_drift=.35):
    """Return inward-rounded QPC ranges for positively measured nominal holds."""
    phases = ("nearBefore", "far", "nearAfter")
    if "nearDetached" in frames:
        phases += ("nearDetached",)
    require(set(frames) == set(phases) and all(len(frames[phase]) >= 2 for phase in phases),
            "Complete near/far/near holds with independent samples required")
    require(all(positive_int(value) for value in (qpc_frequency, minimum_hold_ticks, maximum_gap_ticks))
            and maximum_gap_ticks < minimum_hold_ticks
            and all(_finite_positive(value) for value in (minimum_surface_margin, maximum_pose_drift)),
            "Explicit capture clock and positive hold, cadence and geometry bounds required")
    holds, evidence = {}, {}
    baseline = previous = None
    for phase in phases:
        measured = [measure_frame(row, actor=actor, base=base, cell=cell, pid=pid,
                                  target_offset=target_offset, target_radius=target_radius)
                    for row in frames[phase]]
        if baseline is None:
            baseline = measured[0]
        first = measured[0]
        separations = []
        for current in measured:
            require(current["session"] == baseline["session"] and current["epoch"] == baseline["epoch"]
                    and (previous is None or all(current[k] > previous[k] for k in ("sample", "frame", "ns"))),
                    "Replayed or different-process Observer frame")
            for ref in ("player", "actor"):
                identity, position, pose = current[ref]
                original = baseline[ref]
                require(identity == original[0] and math.dist(position, original[1]) <= maximum_pose_drift
                        and _same_pose(pose, original[2], maximum_pose_drift), "Reference drift or incarnation change")
            require(all(_same_pose(current["controls"][side], baseline["controls"][side], maximum_pose_drift)
                        for side in CONTROLS) and _same_basis(baseline["left"], current["left"]),
                    "HMD, right controller or left controller basis changed")
            require(math.dist(current["source"], first["source"]) <= maximum_pose_drift,
                    "Left controller moved during the measured hold")
            separation = current["distance"] - current["radiusSum"]
            require(current["distance"] > 0 and (separation >= minimum_surface_margin if phase == "far"
                    else separation <= -minimum_surface_margin), "Insufficient nominal sphere separation/overlap")
            separations.append(separation)
            previous = current
        for earlier, later in zip(measured, measured[1:]):
            require((later["ns"] - earlier["ns"]) * qpc_frequency <= maximum_gap_ticks * NANOSECONDS,
                    "Observer cadence leaves an unobserved hold gap")
        require(phase in ("nearBefore", "far") or
                math.dist(first["source"], baseline["source"]) <= maximum_pose_drift,
                "Left controller did not return to the original near pose")
        require(phase != "far" or math.dist(first["source"], baseline["source"]) >= 2 * minimum_surface_margin,
                "Far hold did not move the left controller sufficiently")
        start = (first["ns"] * qpc_frequency + NANOSECONDS - 1) // NANOSECONDS
        end = measured[-1]["ns"] * qpc_frequency // NANOSECONDS
        require(end - start >= minimum_hold_ticks and (not holds or start > list(holds.values())[-1][1]),
                "Measured hold is too short or overlaps another hold")
        holds[phase] = (start, end)
        evidence[phase] = {"samples": [row["sample"] for row in measured],
                           "minSurfaceGap": min(separations), "maxSurfaceGap": max(separations)}
    return {"holds": holds, "evidence": evidence, "observation": "nominal_scene_spheres"}
