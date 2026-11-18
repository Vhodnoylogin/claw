"""Explicit immutable actual projections. No launcher, native CLI, live API or game writes."""
from pathlib import Path
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mixed_source_readback as m

EVIDENCE_ENV = "CLAW_MIXED_SOURCE_READBACK_EVIDENCE"
REQUIRED_ENV = "CLAW_MIXED_SOURCE_READBACK_REQUIRED"
ARCHIVED_EVIDENCE_SHA256 = "cbcb031572849c27f6b6de6b29e8ef3f829e1957854f52520df01962b61b5c74"


def read_selected_actual():
    selected = os.environ.get(EVIDENCE_ENV)
    if not selected:
        if os.environ.get(REQUIRED_ENV) == "1":
            raise AssertionError("Required actual mixed-source evidence missing: set " + EVIDENCE_ENV)
        raise unittest.SkipTest("Optional actual mixed-source evidence not selected; set " + EVIDENCE_ENV)
    payload = Path(selected).expanduser().resolve(strict=True).read_bytes()
    if hashlib.sha256(payload).hexdigest() != ARCHIVED_EVIDENCE_SHA256:
        raise AssertionError("Explicit actual mixed-source proof hash differs; new evidence requires review")
    return json.loads(payload)


class ExplicitActualMixedSourceReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.actual = read_selected_actual()

    def test_actual14_full31_captures_four_provisional_and_four_full_barriers(self):
        before = copy.deepcopy(self.actual); result = m.replay(self.actual)
        self.assertEqual(self.actual, before)
        self.assertEqual((result["fullCaptures"], result["targetsPerCapture"], result["sourceOperations"]), (14, 31, 9))
        self.assertEqual((result["provisionalMarkers"], result["mandatoryFullActorBarriers"]), (4, 4))
        self.assertFalse(result["nativeEvaluatorReexecuted"])
        self.assertFalse(result["liveRestorationReverified"])
        self.assertFalse(result["renderedVertexClaim"])

    def damaged(self): return copy.deepcopy(self.actual)

    def test_actual_wrong_target_stored_zero_and_foreign_key_refused(self):
        for kind in ("target", "zero", "foreign"):
            value = self.damaged(); capture = next(c for c in value["captures"] if c["label"] == m.TAGS[0] + "WolfChanged")
            matrix = capture["matrix"]
            if kind == "target":
                next(k for k in matrix["targets"][m.TARGET]["keys"] if k["key"] == m.OWN)["value"] = .25
            elif kind == "zero":
                name = next(n for n, row in capture["currentSourcePrediction"]["targets"].items() if row["expected"] == 0.)
                matrix["targets"][name]["keys"].append({"key": m.OWN, "available": True, "present": True, "value": 0.})
            else:
                matrix["sources"][m.MORPH]["keys"][0]["value"] = .75
            with self.subTest(kind=kind), self.assertRaises(AssertionError): m.replay(value)

    def test_actual_other_source_change_cannot_hide_in_retained_marker(self):
        value = self.damaged()
        packet = value["fullReady"]["automatic-empty"]["actors"][m.TAGS[0]]["providerObservations"][0]
        name = next(n for n in value["sources"] if n != m.MORPH)
        item = next(r for r in packet["skee"][0]["morphs"] if r["name"] == name)
        item["aggregate"]["value"] += .125
        with self.assertRaises(AssertionError): m.replay(value)

    def test_actual_provisional_cannot_claim_full_fresh_inputs_or_full_proof_flags(self):
        for kind in ("fresh", "flag", "retained"):
            value = self.damaged(); block = value["markers"]["automatic-changed"]["actors"][m.TAGS[0]]["provisionalMarker"]
            if kind == "fresh": block["fullSourceVectorFresh"] = True
            elif kind == "flag": block["symbolicOrCounterfactual"] = False
            else:
                name = block["inputs"]["retainedSourceNames"][0]; block["inputs"]["values"][name] += .25
            with self.subTest(kind=kind), self.assertRaises(AssertionError): m.replay(value)

    def test_actual_marker_stale_identity_incomplete_keys_or_missing_full_audit_refused(self):
        for kind in ("identity", "truncated", "missing-full", "clock"):
            value = self.damaged(); packet = value["markers"]["automatic-empty"]["actors"][m.TAGS[0]]["providerObservations"][0]
            if kind == "identity": packet["loadGeneration"] += 1
            elif kind == "truncated": packet["skee"][0]["morphs"][0]["keys"]["truncated"] = True
            elif kind == "missing-full": value["fullReady"]["automatic-empty"]["actors"].pop(m.TAGS[1])
            else: value["intervals"]["automatic-empty"]["deadlineMonotonic"] += 30
            with self.subTest(kind=kind), self.assertRaises(AssertionError): m.replay(value)

    def test_actual_unknown_operation_missing_clear_and_missing_load_refused(self):
        for kind in ("unknown", "clear", "load"):
            value = self.damaged()
            if kind == "unknown": value["completion"]["unknownMutation"] = True
            elif kind == "clear": value["operations"] = [o for o in value["operations"] if o["label"] != m.TAGS[0] + ":Source:clear"]
            else:
                for capture in value["captures"]:
                    if capture["label"].endswith("LoadedWolf"): capture["actor"]["identity"]["loadGeneration"] = 1
            with self.subTest(kind=kind), self.assertRaises(AssertionError): m.replay(value)

    def test_actual_case_alias_nonfinite_and_unavailable_rows_refused(self):
        for kind in ("alias", "nan", "unavailable"):
            value = self.damaged(); row = value["captures"][0]["matrix"]["sources"][m.MORPH]
            if kind == "alias":
                duplicate = copy.deepcopy(row["keys"][0]); duplicate["key"] = duplicate["key"].swapcase(); row["keys"].append(duplicate)
            elif kind == "nan": row["value"] = float("nan")
            else: row["available"] = False
            with self.subTest(kind=kind), self.assertRaises(AssertionError): m.replay(value)


class ExplicitMixedSourceSelectionContract(unittest.TestCase):
    def test_unset_optional_skips_and_required_unset_fails(self):
        for required, error in (("", unittest.SkipTest), ("1", AssertionError)):
            with self.subTest(required=required), patch.dict(os.environ, {EVIDENCE_ENV: "", REQUIRED_ENV: required}), self.assertRaises(error):
                read_selected_actual()

    def test_explicit_missing_and_changed_bytes_fail(self):
        repo = Path(__file__).resolve().parents[4]
        target = repo / "target/test-inputs/mixed-source-selection"; target.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target) as temporary:
            missing = Path(temporary) / "missing.json"
            with patch.dict(os.environ, {EVIDENCE_ENV: str(missing)}), self.assertRaises(FileNotFoundError): read_selected_actual()
            changed = Path(temporary) / "changed.json"; changed.write_text("{}", encoding="utf-8")
            with patch.dict(os.environ, {EVIDENCE_ENV: str(changed)}), self.assertRaisesRegex(AssertionError, "hash differs"): read_selected_actual()


if __name__ == "__main__": unittest.main()
