"""Check explicit offline physics resource bindings; never qualify or install.

The model identity intentionally excludes sourceInputs (a proven input-only
rebase can preserve the numeric model). Resource pins therefore need their own
byte comparison. This tool does not invent roles from basenames or matching
hashes, and a completed receipt never authorizes provider calls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import types

import build

ROOT = Path(__file__).resolve().parent
SOURCE_BYTES = Path(__file__).read_bytes()
if compile(SOURCE_BYTES, sys._getframe().f_code.co_filename, "exec", dont_inherit=True,
           optimize=sys.flags.optimize) != sys._getframe().f_code:
    raise ValueError("Preflight source bytes do not match the loaded code")
ROLES = ("maleNif", "maleWeight1Nif", "maleTri", "femaleNif",
         "femaleWeight1Nif", "femaleTri", "skeleton")
RUNTIME_GATES = [
    "Confirm actual actor race/armor model bindings and effective process VFS, including archives and NIF-selected XML.",
    "Qualify the loaded provider/API and exclusive simulation ownership, including inherited motion and reserved native indices.",
    "Bind the compiled Distribution DLL and compiled host PEX to these exact generated sources; source agreement alone does not prove binary provenance.",
    "Exercise effective aggregate/model-update ordering, independent NPC weight, animation/scale limits, lifecycle cleanup and provider reset behavior.",
    "Measure node transforms and visible ear/tail/P1 motion/contact with negative controls, both sexes, morph/weight extremes and return to neutral.",
]


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


class Inputs:
    def __init__(self):
        self.payloads = {}

    def read(self, path):
        path = Path(path).resolve()
        if path not in self.payloads:
            self.payloads[path] = path.read_bytes()
        return self.payloads[path]

    def rows(self):
        return [{"path":str(path), "bytes":len(payload), "sha256":digest(payload)}
                for path, payload in self.payloads.items()]

    def verify(self):
        for path, payload in self.payloads.items():
            if path.read_bytes() != payload:
                raise ValueError("Input changed during preflight: " + str(path))


def json_input(inputs, path):
    return json.loads(inputs.read(path))


def resource_checks(model, binding, binding_path, inputs):
    """Resolve explicit roles against exact source paths, never a first match."""
    if binding.get("schemaVersion") != 1 or not isinstance(binding.get("resources"), dict):
        raise ValueError("Resource bindings require schemaVersion 1 and a resources object")
    resources = binding["resources"]
    if set(resources) != set(ROLES):
        raise ValueError("Resource roles must be exactly: " + ", ".join(ROLES))
    pins = {}
    for pin in model.get("sourceInputs", []):
        if (not isinstance(pin, dict) or not isinstance(pin.get("path"), str)
                or type(pin.get("bytes")) is not int or pin["bytes"] <= 0
                or not isinstance(pin.get("sha256"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", pin["sha256"])):
            raise ValueError("Invalid declared model source pin")
        if pin["path"] in pins:
            raise ValueError("Ambiguous duplicate model source path: " + pin["path"])
        pins[pin["path"]] = pin
    rows, source_paths, actual_paths = [], set(), set()
    for role in ROLES:
        row = resources[role]
        if (not isinstance(row, dict) or set(row) != {"modelSourcePath", "actualPath"}
                or not all(isinstance(value, str) and value.strip() for value in row.values())):
            raise ValueError("Each resource role requires explicit modelSourcePath and actualPath: " + role)
        source = row["modelSourcePath"]
        if source not in pins:
            raise ValueError("Resource role has no exact model source pin: " + role)
        if source in source_paths:
            raise ValueError("One model source path cannot stand for two resource roles: " + role)
        source_paths.add(source)
        path = Path(row["actualPath"])
        if not path.is_absolute(): path = binding_path.parent / path
        path = path.resolve()
        if path in actual_paths:
            raise ValueError("Each deployed resource role needs its own explicit path: " + role)
        actual_paths.add(path)
        expected = pins[source]
        record = {"role":role, "modelSourcePath":source, "actualPath":str(path),
                  "expectedBytes":expected["bytes"], "expectedSha256":expected["sha256"]}
        try:
            payload = inputs.read(path)
            record.update(actualBytes=len(payload), actualSha256=digest(payload))
            record["matched"] = len(payload) == expected["bytes"] and digest(payload) == expected["sha256"]
        except OSError as error:
            record.update(matched=False, error=str(error))
        rows.append(record)
    return rows


def text_matches(payload, expected):
    # Both generators write text using the platform's newline convention.
    return payload.decode("utf-8").replace("\r\n", "\n") == expected.replace("\r\n", "\n")


def run_preflight(model_path, binding_path, native_header, host_data, provider_snapshot, out):
    out = build.destination(out)
    explicit = [model_path, binding_path, native_header, host_data, provider_snapshot]
    if any(path is not None and (Path(path).resolve() == out or Path(path).resolve() in out.parents)
           for path in explicit):
        raise ValueError("Preflight output cannot be inside an input path")
    out.mkdir(parents=True, exist_ok=False)
    marker = out / "FAILED-unverified-do-not-install"
    marker.write_text("Offline preflight is incomplete or has mismatched inputs. Do not install.\n", encoding="utf-8")
    inputs = Inputs()
    report = {"schemaVersion":1, "status":"incomplete", "staticInputsMatched":False,
              "runtimeQualified":False, "gameValidated":False, "releaseReady":False,
              "scope":"Declared offline resource pins and generated source agreement; no independent geometric reconstruction, loaded provider or process VFS proof",
              "runtimeGates":RUNTIME_GATES, "checks":{}, "errors":[]}
    try:
        # The renderer's captured code is the one already loaded by build.py.
        if inputs.read(ROOT / "build.py") != build.BUILDER_BYTES:
            raise ValueError("Loaded builder differs from current source bytes")
        if inputs.read(ROOT / "current_model.py") != build._settings_module.SOURCE_BYTES:
            raise ValueError("Loaded evaluator differs from current source bytes")
        if inputs.read(Path(__file__)) != SOURCE_BYTES:
            raise ValueError("Loaded preflight differs from current source bytes")
        recipe = json_input(inputs, ROOT / "recipe.json")
        capsules = json_input(inputs, ROOT / "capsules.json")
        build.validate(recipe, capsules)
        model = json_input(inputs, model_path)
        build.validate_fitted_model(model)
        if model["schemaVersion"] != 3 or model.get("weightDependent") is not True:
            raise ValueError("Preflight requires the current-vector independent-weight model")
        report["model"] = {"identity":model["modelIdentity"], "morphs":model["morphs"],
                           "slots":len(model["slots"]), "weightDependent":True,
                           "sourcePinsAreIdentityBound":False}
        if binding_path is None:
            report["errors"].append("Explicit resource bindings were not supplied")
        else:
            binding = json_input(inputs, binding_path)
            report["resources"] = resource_checks(model, binding, Path(binding_path).resolve(), inputs)
            report["checks"]["resourceBytes"] = all(row["matched"] for row in report["resources"])

        # Execute captured own emitter bytes, avoiding stale import bytecode.
        emitter_path = ROOT / "fit-capsules.py"
        emitter = types.ModuleType("claw_preflight_emitter")
        emitter.__file__ = str(emitter_path)
        exec(compile(inputs.read(emitter_path), str(emitter_path), "exec"), emitter.__dict__)
        expected_header = out / "expected-physics-fit-model.h"
        emitter.write_cpp_model(model, expected_header)
        expected_data = build.render_data(recipe, capsules, model)
        (out / "expected-CLAWPhysicsData.psc").write_text(expected_data, encoding="utf-8")
        for name, path, expected in (("nativeHeader", native_header, expected_header.read_text(encoding="utf-8")),
                                     ("hostData", host_data, expected_data)):
            if path is None:
                report["checks"][name] = False
                report["errors"].append("Explicit " + name + " source was not supplied")
            else:
                report["checks"][name] = text_matches(inputs.read(path), expected)

        if provider_snapshot is None:
            report["checks"]["providerBaseline"] = False
            report["errors"].append("Explicit baseline provider snapshot was not supplied")
        else:
            audit = build.audit_provider(Path(provider_snapshot))
            report["providerAudit"] = audit
            report["checks"]["providerBaseline"] = not (audit["earTailConflicts"] or audit["breastConflicts"] or audit["uncertainties"])
            # An empty/missing DLL cannot qualify even the declared offline inputs.
            report["checks"]["providerDllPresent"] = any(row["path"].lower() == "cbp.dll" and row["bytes"] > 0 for row in audit["files"])
            build.verify_provider_unchanged(audit)
        inputs.verify()
        if provider_snapshot is not None:
            build.verify_provider_unchanged(report["providerAudit"])
        report["staticInputsMatched"] = not report["errors"] and all(report["checks"].values())
        report["status"] = "offline-inputs-matched-runtime-pending" if report["staticInputsMatched"] else "blocked-input-mismatch-or-missing"
    except (OSError, ValueError, TypeError, KeyError, IndexError, ImportError) as error:
        report["status"] = "blocked-input-mismatch-or-missing"
        report["errors"].append(str(error))
    finally:
        report["inputs"] = inputs.rows()
        (out / "physics-preflight.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if report["staticInputsMatched"]: marker.unlink()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fitted-capsules", type=Path, required=True)
    parser.add_argument("--resources", type=Path, help="explicit seven-role bindings JSON; paths relative to this file are allowed")
    parser.add_argument("--native-header", type=Path, help="actual generated header selected for the Distribution build")
    parser.add_argument("--host-data", type=Path, help="actual CLAWPhysicsData.psc selected for host compilation")
    parser.add_argument("--provider-snapshot", type=Path, help="explicit SKSE/Plugins baseline snapshot before CLAW motion configs")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run_preflight(args.fitted_capsules, args.resources, args.native_header,
                               args.host_data, args.provider_snapshot, args.out)
    except (OSError, ValueError) as error:
        parser.exit(2, "CLAW physics preflight: " + str(error) + "\n")
    print(json.dumps({"status":report["status"], "staticInputsMatched":report["staticInputsMatched"],
                      "runtimeQualified":False, "report":str(args.out.resolve() / "physics-preflight.json")}))
    return 0 if report["staticInputsMatched"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
