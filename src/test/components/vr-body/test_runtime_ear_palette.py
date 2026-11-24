import unittest

from verify_runtime_ear_palette import EARS, EXPECTED, HEAD, TRI, verify_runtime_ear_palette


def stock_summary(*, ear_bound=False):
    meshes = {}
    for name, vertices, triangles in ((HEAD, 6980, 12733), (EARS, 1354, 2394)):
        slots = []
        for slot, bone in EXPECTED.items():
            coupled = slot == 3 or ear_bound
            matrices = name == EARS
            lookup = {"found": True, "sameBone": coupled, "sameTransform": coupled and matrices}
            slots.append({"slot": slot, "expected": bone, "bone": bone if coupled else "",
                          "boneMembership": {"worldActor": coupled}, "worldTransformPresent": matrices,
                          "worldActor": lookup.copy(), "skinRoot": lookup.copy()})
        meshes[name] = {"bodyTri": TRI, "partitionVertices": vertices, "partitionTriangles": triangles,
                        "runtimePalette": {"boneCount": 17, "matrixCount": 17 if name == EARS else 0,
                                           "rootMembership": {"worldActor": True}, "reviewedSlots": slots}}
    capture = {"view": "thirdPerson", "sex": 0, "meshSource": {"measured": meshes},
               "observations": [{"view": "thirdPerson", "bank": "active", "item": 0xCDD86,
                                 "addon": 0xCDD87, "clone": 4, "actorRoot": 1}]}
    return {"pending": None, "stockMorphState": {"status": 2}, "captures": {"stock": capture}}


def palette(summary, name):
    return summary["captures"]["stock"]["meshSource"]["measured"][name]["runtimePalette"]


class RuntimeEarPaletteTests(unittest.TestCase):
    def test_matrix_is_present_with_unresolved_ear_bones(self):
        report = verify_runtime_ear_palette(stock_summary())
        self.assertEqual(list(report["leftEarBoundToWorld"].values()), [False, False])
        self.assertEqual(report["adjacentHeadMatrices"], 0)

    def test_complete_world_binding_for_only_one_ear_driver(self):
        summary = stock_summary(ear_bound=True)
        row = palette(summary, EARS)["reviewedSlots"][2]
        row["firstActor"] = row["worldActor"].copy()
        row["worldActor"]["sameTransform"] = False
        report = verify_runtime_ear_palette(summary)
        self.assertEqual(list(report["leftEarBoundToWorld"].values()), [True, False])

    def test_wrong_slot_number_rejected_even_with_three_rows(self):
        summary = stock_summary(ear_bound=True)
        palette(summary, EARS)["reviewedSlots"][2]["slot"] = 17
        with self.assertRaisesRegex(ValueError, "palette slots"):
            verify_runtime_ear_palette(summary)

    def test_live_world_head_control_and_both_meshes_required(self):
        summary = stock_summary(ear_bound=True)
        palette(summary, EARS)["reviewedSlots"][0]["worldActor"]["sameBone"] = False
        with self.assertRaisesRegex(ValueError, "head control"):
            verify_runtime_ear_palette(summary)
        del summary["captures"]["stock"]["meshSource"]["measured"][HEAD]
        with self.assertRaisesRegex(ValueError, "adjacent head"):
            verify_runtime_ear_palette(summary)
