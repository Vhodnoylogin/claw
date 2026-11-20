"""Associate anonymous VR FSMP observations with a scoped actor pose.

The caller supplies the pinned source XML and externally observed process,
window and actor lease. This reader neither opens a game nor asserts ownership
through a provider API that does not supply one.
"""
import math
import xml.etree.ElementTree as ET

if __package__:
    from . import fsmp_probe as probe, fsmp_joint_limit_readback as joint
    from .fsmp_uniform_scale_readback import MASS_TOLERANCE
else:
    import fsmp_probe as probe
    import fsmp_joint_limit_readback as joint
    from fsmp_uniform_scale_readback import MASS_TOLERANCE


HEAD, TAIL = "NPC Head [Head]", "Tails"
POSE_IDENTITY = ("actor", "base", "runtimeHandle", "race", "cell", "bodyItem", "bodyAddon",
                 "sex", "loadEpoch", "rootToken", "weight")
FIELDS = ("linearLowerLimit", "angularLowerLimit", "linearUpperLimit", "angularUpperLimit",
          "linearDamping", "angularDamping", "linearStiffness", "angularStiffness")
require = probe.require


def anchor_roles(sex):
    return tuple(dict.fromkeys(probe.anchors(sex).values()))


def driver_chains(sex):
    shared = ((probe.MALE[0], probe.MALE[1:2]), (probe.MALE[2], probe.MALE[3:4]), (TAIL, probe.MALE[4:]))
    anchors = probe.anchors(sex)
    extra = probe.drivers(sex)[len(probe.MALE):]
    return shared + tuple((anchors[driver], (driver,)) for driver in extra)


def xml_xyz(row, name):
    element = row.find(name)
    require(element is not None, "Missing authored vector: " + name)
    values = tuple(float(element.attrib[axis]) for axis in "xyz")
    require(all(math.isfinite(value) for value in values), "Finite authored vector required: " + name)
    return values


def source_profile(xml, sex):
    """Read the motion-only XML subset with identity COM and joint frame."""
    root = ET.fromstring(xml)
    require(root.tag == "system" and all(row.tag in ("bone", "generic-constraint") for row in root),
            "Motion-only profile required")
    bones = root.findall("bone")
    masses = {row.attrib["name"]: float(row.findtext("mass")) for row in bones}
    anchors, drivers = anchor_roles(sex), probe.drivers(sex)
    require(len(bones) == len(masses) and set(masses) == {*anchors, *drivers}
            and all(masses[name] == 0 for name in anchors)
            and all(math.isfinite(masses[name]) and masses[name] > 0 for name in drivers)
            and all(row.find("centerOfMassTransform") is None for row in bones),
            "Exact authored roles with implicit identity COM required")
    inertia = {row.attrib["name"]: xml_xyz(row, "inertia") for row in bones if row.attrib["name"] in drivers}
    require(all(value > 0 for axis in inertia.values() for value in axis), "Positive dynamic inertia required")
    edges = root.findall("generic-constraint")
    expected = {(HEAD, probe.MALE[0]), (HEAD, probe.MALE[2])}
    for parent, chain in driver_chains(sex):
        expected.update(zip((parent, *chain[:-1]), chain))
    found = {(row.attrib["bodyA"], row.attrib["bodyB"]): row for row in edges}
    require(len(edges) == len(found) and set(found) == expected,
            "Exact authored anchor and driver graph required")
    parameters = {}
    for edge, row in found.items():
        frame_name = "frameInA" if edge[1] in probe.FEMALE[len(probe.MALE):] else "frameInB"
        frame = row.find(frame_name)
        require(frame is not None and not frame.attrib and not len(frame)
                and not any(child.tag.startswith("frame") and child is not frame for child in row),
                "Authored identity joint frame required")
        parameters[edge] = {key: xml_xyz(row, key) for key in FIELDS}
    return masses, inertia, parameters


def actor_poses(replies, native, actor, pose_nonce, sex):
    poses, nodes = [], []
    require(len(replies) == 2, "Exactly two native actor poses required")
    for index, raw in enumerate(replies):
        reply = joint.witness.read_json(raw)
        require(reply["schema"] == "claw-vr-npc-pose/1" and reply["status"] == "ready"
                and type(reply["sequence"]) is int and reply["sequence"] == index and reply["nonce"] == pose_nonce
                and reply["pid"] == native["pid"] and reply["qpcFrequency"] == native["qpcFrequency"],
                "Native actor lease/process/clock changed")
        sample = reply["sample"]
        require(all(joint.witness.integer(sample[key], 1) for key in POSE_IDENTITY if key not in ("sex", "weight"))
                and joint.witness.integer(sample["threadID"], 1)
                and type(actor) is int and 0xFF000000 <= actor < 0xFFFFFFFF and sample["actor"] == actor
                and type(sample["sex"]) is int and sample["sex"] == (1 if sex == "female" else 0)
                and joint.witness.number(sample["weight"]) and 0 <= sample["weight"] <= 100
                and sample["race"] == 0xCDD84 and sample["bodyItem"] == 0xCDD86
                and sample["bodyAddon"] == 0xCDD87 and sample["rootToken"] == pose_nonce
                and sample["view"] == "third_person" and sample["phase"] == "skse_main_thread_task"
                and joint.witness.integer(sample["qpcBegin"], 1)
                and joint.witness.integer(sample["qpcEnd"], sample["qpcBegin"]),
                "Expected exact scoped " + sex + " wolf pose")
        by_name = {row["name"]: probe.transform(row["world"]) for row in sample["nodes"]}
        require(len(sample["nodes"]) == len(by_name) and
                {*anchor_roles(sex), *probe.drivers(sex)} <= by_name.keys(),
                "Unique native role transforms required")
        poses.append(sample)
        nodes.append(by_name)
    require(all(poses[0][key] == poses[1][key] for key in POSE_IDENTITY), "Native actor identity changed")
    return poses, nodes


def native_pose(row, stage, scale):
    pose = joint.pose_transform(row[stage])
    return {**pose, "scale": scale}


def compare_anchor(nodes, candidates, role):
    def matches(row):
        for stage, sample in zip(("initialPre", "lastPost"), nodes):
            pose, observed = native_pose(row, stage, 1), sample[role]
            if (pose["translation"] != observed["translation"] or
                    probe.max_delta(pose["rotationRowMajor"], observed["rotationRowMajor"]) > joint.ROTATION_MATCH):
                return False
        return True

    found = [token for token, row in candidates.items()
             if row["initialPre"]["flags"] & 3 == 2 and matches(row)]
    require(len(found) == 1, "Unique two-endpoint kinematic anchor unavailable: " + role)
    return found[0]


def assign_roles(nodes, objects, edges, sex):
    """Exact anchor tracks, then stable head-local side and chain topology."""
    tokens = {role: compare_anchor(nodes, objects, role) for role in anchor_roles(sex)}
    children = {token: sorted(b for a, b in edges if a == token) for token in objects}
    head = objects[tokens[HEAD]]
    ear_roots = children[tokens[HEAD]]
    require(len(ear_roots) == 2, "Expected one branch per ear")
    for role, sign in zip(probe.MALE[:4:2], (-1, 1)):
        def side(pose, parent):
            return probe.relative(pose, parent)["translation"][0] * sign > 1

        require(all(side(sample[role], sample[HEAD]) for sample in nodes), "Native ear-side landmark is ambiguous")
        eligible = [token for token in ear_roots if all(
            side(native_pose(objects[token], stage, 1), native_pose(head, stage, 1))
            for stage in ("initialPre", "lastPost"))]
        require(len(eligible) == 1, "Solver ear side is ambiguous")
        tokens[role] = eligible[0]
    for parent, chain in driver_chains(sex):
        for role in chain:
            options = children[tokens[parent]]
            require(len(options) == 1, "Unique directed chain step required: " + role)
            tokens[role] = options[0]
            parent = role
    require(set(tokens.values()) == objects.keys(), "Role mapping is not bijective")
    return tokens


def evaluate(raw_provider, raw_poses, xml, *, serial, actor, pose_nonce, window_nonce, arm_qpc, sex="male"):
    native = joint.witness.parse(raw_provider, serial)
    require(native["schema"] == joint.witness.VR_SCHEMA and native["status"] == "ready",
            "Ready VR provider frame required")
    sample = native["sample"]
    window = joint.witness.validate_window(sample["objectWindow"], sample["loadEpoch"], window_nonce, version=4)
    poses, nodes = actor_poses(raw_poses, native, actor, pose_nonce, sex)
    require(joint.witness.integer(pose_nonce, 1) and joint.witness.integer(window_nonce, 1)
            and joint.witness.integer(arm_qpc, 1)
            and window["pairedSteps"] >= 2 and not window["awaitingPost"]
            and window["lastPreThreadId"] == window["lastPostThreadId"]
            and poses[0]["loadEpoch"] == sample["loadEpoch"]
            and poses[0]["qpcEnd"] <= arm_qpc <= window["firstPreQpc"] < window["lastPreQpc"]
            < window["lastPostQpc"] <= sample["sampledQpc"] <= poses[1]["qpcBegin"],
            "Complete provider pairs must be inside the same actor bracket")
    masses, inertia, profile = source_profile(xml, sex)
    objects = {row["token"]: row for row in window["objects"]}
    edges = {(row["bodyAToken"], row["bodyBToken"]): row for row in window["incidentConstraints"]["constraints"]}
    require(len(objects) == len(masses) and window["incidentConstraints"]["constraintCount"] == len(edges) == len(profile)
            and all(row["enabled"] and row["status"] == "spring2" for row in edges.values()),
            "Exact, enabled Spring2 catalogue required")
    tokens = assign_roles(nodes, objects, edges, sex)
    require({(tokens[a], tokens[b]) for a, b in profile} == edges.keys(), "Authored directed edges differ")

    results = {}
    for (parent, role), configured in profile.items():
        scale = nodes[0][role]["scale"]
        require(all(abs(scale - frame[name]["scale"]) <= 1e-5 for frame in nodes for name in (parent, role)),
                "Common uniform scale required for both ends of the edge")
        driver, anchor = objects[tokens[role]], objects[tokens[parent]]
        expected_mass = 1 / (masses[role] * scale**3)
        expected_inertia = [1 / (value * scale**5) for value in inertia[role]]
        for stage in joint.STAGES:
            body = driver[stage]
            require(body["flags"] & 3 == 0 and abs(body["inverseMass"] - expected_mass) <= MASS_TOLERANCE,
                    "Scaled inverse mass or dynamic flags differ: " + role)
            require(probe.max_delta(body["inverseLocalInertia"], expected_inertia) <= MASS_TOLERANCE,
                    "Scaled inverse local inertia differs: " + role)
        actual = edges[tokens[parent], tokens[role]]["spring2"]
        for key, linear, angular, linear_scale, angular_scale in (
                ("lowerLimit", *FIELDS[:2], scale, 1), ("upperLimit", *FIELDS[2:4], scale, 1),
                ("damping", *FIELDS[4:6], 1, 1), ("stiffness", *FIELDS[6:], scale**3, scale**5)):
            values = tuple(x * linear_scale for x in configured[linear]) + tuple(x * angular_scale for x in configured[angular])
            require(probe.max_delta(actual[key], values) <= 1e-6,
                    "Configured Spring2 field differs: " + role + " " + key)
        require(all(actual["springEnabled"]), "Spring axes are disabled: " + role)
        before, after = (probe.relative(native_pose(driver, stage, scale), native_pose(anchor, stage, scale))
                         for stage in ("lastPre", "lastPost"))
        results[role] = {
            "parent": parent, "expectedInverseMass": expected_mass, "observedInverseMass": driver["initialPre"]["inverseMass"],
            "expectedInverseInertia": expected_inertia, "observedInverseInertia": driver["initialPre"]["inverseLocalInertia"],
            "localTranslationDelta": math.dist(before["translation"], after["translation"]),
            "localRotationMatrixDelta": math.dist(before["rotationRowMajor"], after["rotationRowMajor"]),
        }
    require(all(objects[tokens[role]][stage]["inverseMass"] == 0 and objects[tokens[role]][stage]["flags"] & 3 == 2
                for role in anchor_roles(sex) for stage in joint.STAGES), "Kinematic anchor flags or inverse mass changed")
    return {
        "status": "scoped-actor-graph-and-last-pair-associated", "tokens": tokens, "roles": results,
        "pid": native["pid"], "pairedSteps": window["pairedSteps"], "sampledPairQpc": [window["lastPreQpc"], window["lastPostQpc"]],
        "poseThreadIDs": [row["threadID"] for row in poses],
        "localSolverMovementObserved": any(row["localTranslationDelta"] > 1e-3 for row in results.values()),
        "directProviderOwnerAvailable": False, "renderedMotionQualified": False, "contactQualified": False,
    }
