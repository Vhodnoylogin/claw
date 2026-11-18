"""Portable symbolic scorer controls; these fixtures are not game observations."""
from pathlib import Path
import copy
import math
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mixed_source_readback as m

SOURCES = [m.MORPH, "OtherSource"]
TARGETS = [m.TARGET, *["SymbolicTarget" + str(i) for i in range(30)]]
KEYS = m.keys_for_run("symbolic-only")


def row(value=0., keys=(), present=None):
    return {"available": True, "present": bool(keys) if present is None else present, "value": value,
            "keys": [{"key": key, "available": True, "present": True, "value": v} for key, v in keys]}


def original():
    return {name: row() for name in [*SOURCES, *TARGETS]}


def baseline():
    return {"stage": "human", "sources": {name: row() for name in SOURCES},
            "traits": {"$human.height": {"available": True, "value": 1.03}}, "weightRaw": 50.}


def prediction(value):
    # An explicitly supplied symbolic output vector, not a second matrix evaluator.
    return {"outputs": {name: value if name == m.TARGET else 0. for name in TARGETS}}


def measured(pair, value=.5):
    records = original()
    records[m.MORPH] = row(sum(pair.values()), [(KEYS[k], v) for k, v in pair.items()], present=True)
    records[m.TARGET] = row(value, [(m.OWN, value)] if value else [])
    return records


class PortableMixedSourceReadback(unittest.TestCase):
    def test_fresh_inputs_do_not_change_retained_baseline(self):
        base = baseline(); before = copy.deepcopy(base)
        fresh = {name: row() for name in SOURCES}; fresh[m.MORPH] = row(.4375)
        result = m.current_inputs(fresh, base, SOURCES)
        self.assertEqual(result["values"][m.MORPH], .4375)
        self.assertEqual(result["weightRaw"], 50.)
        self.assertEqual(result["values"]["$human.height"], 1.03)
        self.assertEqual(base, before)

    def test_provisional_marker_retains_other_sources_and_has_no_full_score_flag(self):
        base = baseline(); pair = {"Source": .375, "Foreign": .0625}
        all_rows = measured(pair)
        inputs = m.marker_inputs(all_rows[m.MORPH], base, SOURCES)
        marker = m.marker_score({n: all_rows[n] for n in [m.MORPH, *TARGETS]}, original(), KEYS,
                                pair, prediction(.5), inputs, TARGETS, "beast")
        self.assertTrue(marker["matches"])
        self.assertFalse(marker["fullSourceVectorFresh"])
        self.assertEqual(inputs["freshSourceNames"], [m.MORPH])
        self.assertEqual(inputs["retainedSourceNames"], ["OtherSource"])
        self.assertNotIn("symbolicOrCounterfactual", marker)

    def test_provisional_pass_cannot_replace_full_source_preservation(self):
        pair = {"Source": .125, "Foreign": .0625}; records = measured(pair)
        records["OtherSource"] = row(.25)
        inputs = m.marker_inputs(records[m.MORPH], baseline(), SOURCES)
        self.assertEqual(inputs["values"]["OtherSource"], 0.)
        self.assertTrue(m.marker_score({n: records[n] for n in [m.MORPH, *TARGETS]}, original(), KEYS,
                                       pair, prediction(.5), inputs, TARGETS, "beast")["matches"])
        with self.assertRaisesRegex(AssertionError, "aggregate"):
            m.preserve(records, original(), KEYS, pair, SOURCES, TARGETS)

    def test_present_empty_bucket_after_final_clear_is_valid(self):
        records = measured({}, 0.)
        self.assertTrue(records[m.MORPH]["present"])
        self.assertTrue(m.preserve(records, original(), KEYS, {}, SOURCES, TARGETS))
        self.assertTrue(m.score(records, prediction(0.), {"basis": "symbolic"}, TARGETS, "beast")["matches"])

    def test_intermediate_clear_preserves_the_independent_remaining_key(self):
        records = measured({"Foreign": .0625})
        self.assertTrue(m.preserve_pair(records[m.MORPH], original()[m.MORPH], KEYS, {"Foreign": .0625}))
        records[m.MORPH]["keys"][0]["value"] = .125
        with self.assertRaisesRegex(AssertionError, "Owned pair"):
            m.preserve_pair(records[m.MORPH], original()[m.MORPH], KEYS, {"Foreign": .0625})

    def test_stale_or_wrong_float32_target_is_not_accepted(self):
        result = m.score(measured({}, .25), prediction(.5), {"basis": "symbolic"}, TARGETS, "beast")
        self.assertFalse(result["matches"]); self.assertEqual(result["mismatchCount"], 1)

    def test_stored_zero_owned_key_is_not_absence(self):
        records = measured({}, 0.); records[TARGETS[-1]] = row(0., [(m.OWN, 0.)])
        result = m.score(records, prediction(0.), {"basis": "symbolic"}, TARGETS, "beast")
        self.assertFalse(result["matches"]); self.assertFalse(result["targets"][TARGETS[-1]]["zeroKeyAbsent"])

    def test_human_requires_owned_target_absence_even_with_nonzero_prediction(self):
        self.assertTrue(m.score(measured({}, 0.), prediction(.5), {"basis": "symbolic"}, TARGETS, "human")["matches"])
        self.assertFalse(m.score(measured({}, .5), prediction(.5), {"basis": "symbolic"}, TARGETS, "human")["matches"])

    def test_foreign_target_key_cannot_change(self):
        before = original(); before[TARGETS[-1]] = row(.125, [("External.Provider", .125)])
        after = copy.deepcopy(before); after[TARGETS[-1]]["keys"][0]["value"] = .25
        with self.assertRaisesRegex(AssertionError, "Foreign key"):
            m.preserve(after, before, KEYS, {}, SOURCES, TARGETS)

    def test_owned_pair_cannot_escape_breasts(self):
        after = original(); after["OtherSource"] = row(.125, [(KEYS["Source"], .125)])
        with self.assertRaisesRegex(AssertionError, "Owned pair"):
            m.preserve(after, original(), KEYS, {}, SOURCES, TARGETS)

    def test_case_alias_keys_and_preexisting_run_key_are_refused(self):
        with self.assertRaisesRegex(AssertionError, "collision"):
            m.rows(row(.25, [("Key", .125), ("key", .125)]))
        before = original(); before[TARGETS[0]] = row(.25, [(KEYS["Source"].upper(), .25)])
        with self.assertRaisesRegex(AssertionError, "already exists"):
            m.collision_check(before, KEYS)

    def test_unavailable_absent_with_keys_nonfinite_and_boolean_are_refused(self):
        candidates = [row(), row(.1, [("key", .1)], present=False), row(math.nan), row(True)]
        candidates[0]["available"] = False
        for bad in candidates:
            with self.subTest(record=bad), self.assertRaises(AssertionError): m.rows(bad)
        with self.assertRaises(AssertionError): m.bits(1e100)

    def test_missing_catalog_target_or_source_is_refused(self):
        for name in (TARGETS[-1], SOURCES[-1]):
            records = original(); del records[name]
            with self.subTest(name=name), self.assertRaisesRegex(AssertionError, "catalog"):
                m.preserve(records, original(), KEYS, {}, SOURCES, TARGETS)
        with self.assertRaises(AssertionError): m.target_comparison(original(), {"outputs": {}}, TARGETS, "beast")

    def test_vector_change_gate_covers_all31(self):
        m.compare_vectors(prediction(.25), prediction(.5), TARGETS, equal=False)
        bad = prediction(.5); bad["outputs"][TARGETS[-1]] = .125
        with self.assertRaises(AssertionError): m.compare_vectors(prediction(.25), bad, TARGETS, equal=False)


if __name__ == "__main__": unittest.main()
