"""Offline contracts for the isolated male VR CBPC host template."""
import unittest

from stage_pose_contact_host import ALIAS, COLLISION, CONDITION, FIXTURE, MASTER, full_host_configs, male_layout


NODES = (
    "NPC Pelvis [Pelv]", "NPC Spine [Spn0]", "NPC Spine1 [Spn1]", "NPC Spine2 [Spn2]", "NPC Head [Head]",
    "NPC L UpperArm [RUar]", "NPC L Forearm [RLar]", "NPC L Hand [RHnd]",
    "NPC R UpperArm [RUar]", "NPC R Forearm [RLar]", "NPC R Hand [RHnd]",
    "NPC L Thigh [LThg]", "NPC L Calf [LClf]", "NPC L Foot [Lft ]",
    "NPC R Thigh [LThg]", "NPC R Calf [LClf]", "NPC R Foot [Lft ]",
    "NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02", "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
    "TailBone01", "TailBone02", "TailBone03", "TailBone05",
)
TAIL_ROW = f"TailBone02={ALIAS}={CONDITION}".encode("ascii")
MASTER_TEMPLATE = b"# Fixture scope\n[Settings]\nTuningMode = 0\nMalePhysics=0\n\n[ConfigMap]\n" + TAIL_ROW + b"\n"
COLLISION_TEMPLATE = (
    b"# Exactly one static sphere\n[ExtraOptions]\nBellyBulge=1.0\n\n[PlayerNodes]\nLeftWandNode\n\n"
    b"[AffectedNodes]\nTailBone02\n\n[ColliderNodes]\n\n[LeftWandNode]\n0,-6.0,-2.0,3.0\n"
)


def profile(override=None):
    nodes = [override if node == NODES[0] and override is not None else node for node in NODES * 4 + NODES[:20]]
    slots = [{"node": name, "male": {}} for name in nodes]
    female = [{"node": name, "male": None} for name in ("BreastLeft", "BreastRight") for _ in range(4)]
    return {"slots": slots[:13] + female + slots[13:]}


def sections(payload):
    result = {}
    for line in payload.decode("ascii").splitlines():
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if line in result:
                raise AssertionError(f"Duplicate generated section {line}")
            result[line] = []
        else:
            result[next(reversed(result))].append(line)
    return result


class StagePoseContactHostTests(unittest.TestCase):
    def test_male_layout_keeps_active_indices_and_interior_brackets(self):
        active, nodes = male_layout(profile())
        self.assertEqual(nodes, NODES)
        self.assertEqual([slot for slot, _ in active], [*range(13), *range(21, 128)])
        self.assertEqual([node for _, node in active], [*NODES * 4, *NODES[:20]])
        self.assertIn((5, "NPC L UpperArm [RUar]"), active)
        self.assertIn((21, "NPC L Foot [Lft ]"), active)

    def test_overlay_has_only_independent_fixture_groups_and_one_wand_sphere(self):
        _, nodes = male_layout(profile())
        config = full_host_configs(MASTER_TEMPLATE, COLLISION_TEMPLATE, nodes)
        self.assertEqual(set(config), {MASTER, COLLISION})
        master = sections(config[MASTER])
        condition = f"IsRaceFormId(Skyrim.esm|0CDD84) AND IsMale() AND IsActorBase({FIXTURE}|000800)"
        self.assertEqual(master, {
            "[Settings]": ["TuningMode = 0", "MalePhysics=1"],
            "[ConfigMap]": [f"{node}={ALIAS}={condition}" for node in NODES],
        })
        self.assertEqual(sections(config[COLLISION]), {
            "[ExtraOptions]": ["BellyBulge=1.0"], "[PlayerNodes]": ["LeftWandNode"],
            "[AffectedNodes]": list(NODES), "[ColliderNodes]": [],
            "[LeftWandNode]": ["0,-6.0,-2.0,3.0"],
        })

    def test_each_template_anchor_must_appear_once(self):
        for master_anchor, collision_anchor in ((b"MalePhysics=0", None), (TAIL_ROW, None), (None, b"TailBone02")):
            for duplicate in (False, True):
                with self.subTest(anchor=master_anchor or collision_anchor, duplicate=duplicate):
                    master, collision = MASTER_TEMPLATE, COLLISION_TEMPLATE
                    if master_anchor:
                        master = master.replace(master_anchor + b"\n",
                                                (master_anchor + b"\n") * (2 if duplicate else 0))
                    else:
                        collision = collision.replace(collision_anchor + b"\n",
                                                      (collision_anchor + b"\n") * (2 if duplicate else 0))
                    with self.assertRaisesRegex(ValueError, "Unexpected pinned template line"):
                        full_host_configs(master, collision, NODES)

    def test_layout_rejects_wrong_slot_node_and_sex_counts(self):
        fewer_slots = profile()
        fewer_slots["slots"].pop()
        fewer_male = profile()
        fewer_male["slots"][0]["male"] = None
        duplicate_group = profile(override=NODES[1])
        for bad in (fewer_slots, fewer_male, duplicate_group):
            with self.subTest(bad=bad["slots"][0]):
                with self.assertRaisesRegex(ValueError, "120 male slots on 25 nodes"):
                    male_layout(bad)

    def test_layout_rejects_node_syntax_that_changes_provider_parsing(self):
        for malformed in ("", " TailBone02", "TailBone02 ", "[PlayerNodes]", "TailBone02#comment",
                          "TailBone02=Alias", "TailBone02<chain", "TailBone02>chain",
                          "TailBone02\r\nextra", "TailBone02\0", "TailBone02,OtherNode",
                          "TailBone02(@)", []):
            with self.subTest(node=malformed):
                with self.assertRaisesRegex(ValueError, "Invalid single-node CBPC group name"):
                    male_layout(profile(override=malformed))

    def test_crlf_template_renders_same_ascii_overlay(self):
        crlf = (payload.replace(b"\n", b"\r\n") for payload in (MASTER_TEMPLATE, COLLISION_TEMPLATE))
        self.assertEqual(full_host_configs(*crlf, NODES), full_host_configs(MASTER_TEMPLATE, COLLISION_TEMPLATE, NODES))


if __name__ == "__main__":
    unittest.main()
