from copy import deepcopy
import unittest

from tail_refit_morph import FUNCTIONS, MORPH_SCRIPT, TEST_KEY, UnconfirmedMutation, run_states


def describe(script):
    return {"name": script, "globalFunctions": [
        {"name": name, "native": True, "returnType": result, "params": [{"type": param} for param in params]}
        for name, (result, params) in FUNCTIONS.items()]}


class TailMorphTest(unittest.TestCase):
    def setUp(self):
        self.actor = 0xFF000802
        self.writes = []
        self.values = {"CLAWDistribution": .25}
        self.states = []
        self.refuse = None

    def call(self, script, method, args, kind):
        self.assertEqual(script, MORPH_SCRIPT)
        self.assertEqual(args[0], {"form": "0xFF000802"})
        self.assertEqual(kind, FUNCTIONS[method][0])
        if method != "UpdateModelWeight":
            self.assertEqual(args[1:3], ["CLAWTailLength", TEST_KEY])
        if method == "HasBodyMorph":
            return TEST_KEY in self.values
        if method == "GetBodyMorph":
            return self.values.get(TEST_KEY, 0.)
        self.writes.append(method)
        if method == "SetBodyMorph":
            self.values[TEST_KEY] = args[3]
        if method == "ClearBodyMorph":
            del self.values[TEST_KEY]
        if method == self.refuse:
            raise RuntimeError("unconfirmed test transport")
        return None

    def collect(self, stage):
        self.states.append((stage, self.values.get(TEST_KEY, 0.)))

    def test_restores_absence_and_preserves_other_keys(self):
        run_states(self.call, describe, lambda: None, self.collect, self.actor)
        self.assertEqual(self.states, [("neutral", 0.), ("morphed", 1.), ("returned", 0.)])
        self.assertEqual(self.writes, ["SetBodyMorph", "UpdateModelWeight", "ClearBodyMorph", "UpdateModelWeight"])
        self.assertEqual(self.values, {"CLAWDistribution": .25})

    def test_refuses_existing_zero_and_wrong_registry_before_first_mutation(self):
        incompatible = deepcopy(describe(MORPH_SCRIPT))
        incompatible["globalFunctions"][0]["params"][0]["type"] = "form"
        with self.assertRaisesRegex(ValueError, "Typed RaceMenu contract"):
            run_states(self.call, lambda _: incompatible, lambda: None, self.collect, self.actor)
        self.values[TEST_KEY] = 0.
        with self.assertRaisesRegex(ValueError, "Unexpected stored tail test key"):
            run_states(self.call, describe, lambda: None, self.collect, self.actor)
        self.assertEqual(self.writes, [])

    def test_measurement_failure_restores_but_uncertain_write_is_not_replayed(self):
        def observe(phase):
            if phase == "morphed":
                raise ValueError("missing world sample")
        with self.assertRaisesRegex(ValueError, "missing world sample"):
            run_states(self.call, describe, lambda: None, observe, self.actor)
        self.assertNotIn(TEST_KEY, self.values)
        self.writes.clear()
        self.refuse = "SetBodyMorph"
        with self.assertRaises(UnconfirmedMutation):
            run_states(self.call, describe, lambda: None, self.collect, self.actor)
        self.assertEqual(self.writes, ["SetBodyMorph"])


if __name__ == "__main__":
    unittest.main()
