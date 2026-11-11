"""Loaded-root stock role admission; no provider or game process is started."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_cbpc_owned_case import Session
from test_fsmp_probe import fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
try:
    import cbpc_owned_case
    import cbpc_stock_role as role
finally:
    sys.path.pop(0)

EXPECTED = json.loads((Path(__file__).resolve().parents[2] /
                      "resources/physics/cbpc-stock-role-xp32.json").read_bytes())


class StockRoleTests(unittest.TestCase):
    def setUp(self):
        self.admitted = fixture("female", effect=False)["baseline"]

    def sample(self):
        raw = copy.deepcopy(self.admitted)
        raw["sampleId"] += 1
        raw["producerMonotonicNs"] += 100_000_000
        template, raw["nodes"] = raw["nodes"][0], []
        for name in sorted(set(EXPECTED["protectedNames"]) | set(EXPECTED["writeTargets"])):
            row = copy.deepcopy(template)
            row["name"] = name
            if name in ("VaginaB1", "Clitoral1"):
                row.update(status="unavailable", reason="Node not found")
                row.pop("world")
                row.pop("local")
            raw["nodes"].append(row)
        raw["quality"] = "partial"
        return raw

    def test_either_missing_prerequisite_qualifies_without_rewriting_partial_quality(self):
        for absent in (("VaginaB1", "Clitoral1"), ("VaginaB1",), ("Clitoral1",)):
            with self.subTest(absent=absent):
                raw = self.sample()
                for row in raw["nodes"]:
                    if row["name"] in ("VaginaB1", "Clitoral1") and row["name"] not in absent:
                        row["status"] = "available"
                        row.pop("reason")
                result = role.qualify(raw, self.admitted, EXPECTED)
                self.assertTrue(result["qualifiedConditionalNoop"])
                self.assertEqual(result["qualityPreserved"], "partial")
                self.assertFalse(result["runtimeGenericParentageQualified"])

    def test_unknown_absence_stale_identity_or_unavailable_graph_never_qualifies(self):
        kinds = ("all-present", "wrong-reason", "wrong-root", "wrong-identity", "replayed",
                 "epoch", "missing-driver", "duplicate", "tree-unloaded", "read-error", "observer-version")
        for kind in kinds:
            with self.subTest(kind=kind):
                raw = self.sample()
                if kind == "all-present":
                    for row in raw["nodes"]:
                        row["status"] = "available"
                        row.pop("reason", None)
                elif kind == "wrong-reason":
                    for row in raw["nodes"]:
                        if row["status"] == "unavailable":
                            row["reason"] = "Requested 3D tree not loaded"
                elif kind == "wrong-root":
                    raw["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
                elif kind == "wrong-identity":
                    raw["nodes"][0]["identity"]["runtimeHandle"] += 1
                elif kind == "replayed":
                    raw["sampleId"] = self.admitted["sampleId"]
                elif kind == "epoch":
                    raw["loadGeneration"] += 1
                elif kind == "missing-driver":
                    next(row for row in raw["nodes"] if row["name"] == EXPECTED["requiredProbeNames"][0]).update(
                        status="unavailable", reason="Node not found")
                elif kind == "duplicate":
                    raw["nodes"][-1] = raw["nodes"][0]
                elif kind == "tree-unloaded":
                    raw["refs"][0]["loaded3D"] = False
                elif kind == "read-error":
                    raw["ok"] = False
                else:
                    raw["observerVersion"] = "unknown"
                with self.assertRaises(AssertionError):
                    role.qualify(raw, self.admitted, EXPECTED)

    def test_changed_callback_baseline_is_rejected_before_any_provider_mutation(self):
        for changed in ("root", "epoch", "identity"):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                session = Session(directory)
                qualified = copy.deepcopy(session.sample)
                if changed == "root":
                    session.sample["refs"][0]["rootIdentity"]["sampledRootToken"] += 1
                elif changed == "epoch":
                    session.sample["loadGeneration"] += 1
                else:
                    session.sample["refs"][0]["identity"]["runtimeHandle"] += 1
                original = session.tool

                def rooted(tool, args, **kwargs):
                    result = original(tool, args, **kwargs)
                    if tool == "inspect":
                        role.require_same_root(result, qualified)
                    return result

                with patch.object(session, "tool", rooted), self.assertRaises(AssertionError):
                    cbpc_owned_case.run(session, "0xFF001234", "female", sleep=lambda _: None)
                self.assertFalse(any(args.get("script") == "CBPCPluginScript" for _, args in session.calls))


if __name__ == "__main__":
    unittest.main()
