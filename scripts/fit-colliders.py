"""Create an offline XP32 collider candidate through Morphbench's documented CLI.

No installation or release integration. Inputs remain read-only; all command output
and provenance are retained in a newly created staging directory.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

import locate

ROOT = Path(__file__).resolve().parents[1]
RECIPE = ROOT / "recipes/colliders.json"
STAGING = ROOT / "work/collider-candidates"


def digest(path: Path) -> dict:
    payload = path.read_bytes()
    if payload.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise ValueError("Git LFS pointer is not an asset: " + str(path))
    return {"path": str(path), "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest()}


def inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def validate_destination(out: Path, inputs: list[Path], mods: Path | None,
                         source_root: Path = ROOT, staging_root: Path = STAGING) -> Path:
    """Resolve junctions/symlinks before checking boundaries; existing dirs refused."""
    out = out.resolve()
    if out.exists():
        raise ValueError("Output must be a NEW directory: " + str(out))
    if any(inside(out, path.resolve().parent) for path in inputs):
        raise ValueError("Output is inside an input/source directory")
    if mods and inside(out, mods.resolve().parent):
        raise ValueError("Output is inside the live MO2 instance")
    if {part.lower() for part in out.parts} & {"data", "mods", "overwrite", "downloads"}:
        raise ValueError("Output uses a live/game/archive directory name")
    allowed = inside(out, staging_root.resolve()) and out != staging_root.resolve()
    if inside(out, source_root.resolve()) and not allowed:
        raise ValueError("Repository outputs belong only in work/collider-candidates/<new-run>")
    for parent in out.parents:
        if (parent / ".git").exists() and not (parent == source_root.resolve() and allowed):
            raise ValueError("Output is inside a source checkout: " + str(parent))
    return out


def validate_recipe(recipe: dict) -> None:
    if recipe.get("schemaVersion") != 1:
        raise ValueError("Unsupported collider recipe schema")
    fit = recipe["fit"]
    pct = fit["percentile"]
    if isinstance(pct, bool) or not isinstance(pct, (int, float)) or not math.isfinite(pct) or not 0 < pct <= 100:
        raise ValueError("percentile must be finite and in (0, 100]")
    if type(fit["bundle"]) is not int or not 1 <= fit["bundle"] <= 16:
        raise ValueError("bundle must be an integer in 1..16")
    if fit["split"] not in ("axis", "kmeans"):
        raise ValueError("split must be axis or kmeans")
    if not isinstance(fit["only"], list) or not fit["only"] or any(not isinstance(name, str) or not name or "," in name for name in fit["only"]):
        raise ValueError("only must name mesh parts explicitly")
    if not isinstance(fit["sliders"], dict):
        raise ValueError("sliders must be an object")
    for name, amount in fit["sliders"].items():
        if not isinstance(name, str) or not name or "=" in name or isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(amount):
            raise ValueError("sliders must contain named finite values")


def fit_arguments(recipe: dict, output: Path) -> list[str]:
    fit = recipe["fit"]
    args = ["--only", ",".join(fit["only"]), "--percentile", str(fit["percentile"]),
            "--bundle", str(fit["bundle"]), "--split", fit["split"], "--out", str(output)]
    for name, amount in sorted(fit["sliders"].items()):
        args += ["--slider", f"{name}={amount}"]
    return args


def coverage_delta(before: list[dict], after: list[dict]) -> list[dict]:
    original = {row["bone"]: row for row in before}
    old = {row["bone"]: row.get("clearance") for row in before}
    result = []
    for row in after:
        prior = original.get(row["bone"])
        if prior and any(prior.get(key) != row.get(key) for key in ("kind", "physics", "ragdoll")):
            raise ValueError("Collision body properties/frame changed: " + row["bone"])
        previous, current = old.get(row["bone"]), row.get("clearance")
        item = {"bone": row["bone"], "before": previous, "after": current}
        if previous and current:
            if previous["points"] != current["points"]:
                raise ValueError("Coverage point count changed: " + row["bone"])
            item["outsideDelta"] = round(current["outside"] - previous["outside"], 6)
            item["worstDelta"] = round(current["worst"] - previous["worst"], 6)
        result.append(item)
    if set(old) != {row["bone"] for row in after}:
        raise ValueError("Collision body set changed")
    return result


def git_state(root: Path) -> dict:
    def run(*args):
        proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True,
                              text=True, encoding="utf-8", timeout=10)
        return proc.stdout.strip() if proc.returncode == 0 else None
    status = run("status", "--porcelain")
    return {"commit": run("rev-parse", "HEAD"), "branch": run("branch", "--show-current"),
            "dirty": None if status is None else bool(status)}


def run_cli(python: str, mb: Path, command: str, common: list[str], extra: list[str],
            out: Path, label: str, timeout: int, commands: list) -> object:
    args = [python, str(mb), command, *common, *extra, "--json"]
    record = {"label": label, "argv": args, "timeoutSeconds": timeout}
    commands.append(record)
    env = dict(os.environ, MORPHBENCH_LANG="en", PYTHONDONTWRITEBYTECODE="1")
    try:
        proc = subprocess.run(args, cwd=out, capture_output=True, text=True,
                              encoding="utf-8", env=env, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        record["timedOut"] = True
        for kind, payload in (("stdout", exc.stdout), ("stderr", exc.stderr)):
            (out / f"{label}.{kind}.txt").write_bytes(payload if isinstance(payload, bytes) else (payload or "").encode("utf-8"))
        raise ValueError("Morphbench command timed out: " + label) from exc
    record["returnCode"] = proc.returncode
    (out / f"{label}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (out / f"{label}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise ValueError(f"Morphbench {label} refused ({proc.returncode}); see stderr in staging")
    result = json.loads(proc.stdout)
    (out / f"{label}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sex", choices=("male", "female"), default="male")
    parser.add_argument("--recipe", type=Path, default=RECIPE)
    parser.add_argument("--body", type=Path)
    parser.add_argument("--tri", type=Path)
    parser.add_argument("--skeleton", type=Path)
    parser.add_argument("--hkx", type=Path)
    parser.add_argument("--morphbench", type=Path)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--out", type=Path, help="new staging directory, never a live/source path")
    parser.add_argument("--timeout", type=int, default=60, help="per command seconds, 1..60; five bounded commands")
    args = parser.parse_args(argv)
    out = None
    owned_output = False
    manifest = {"schemaVersion": 1, "status": "incomplete", "releaseReady": False,
                "requiresGamePhysicsValidation": True, "startedAt": datetime.now(timezone.utc).isoformat(),
                "commands": []}
    try:
        if not 1 <= args.timeout <= 60:
            raise ValueError("timeout must be in 1..60 seconds")
        recipe_path = args.recipe.resolve()
        recipe = json.loads(recipe_path.read_text(encoding="utf-8-sig"))
        validate_recipe(recipe)
        cfg = locate.local_config(ROOT)
        mods = Path(cfg["mods"]) if cfg.get("mods") else None
        asset = Path(recipe["assetDirectory"])
        if not mods and (not args.body or not args.skeleton or not args.hkx):
            raise ValueError("Provide --body --skeleton --hkx or configure mods in build.local.json")
        body = (args.body or mods / recipe["bodyMod"] / asset / recipe["bodies"][args.sex]).resolve()
        skeleton = (args.skeleton or mods / recipe["skeletonMod"] / asset / "skeleton.nif").resolve()
        hkx = (args.hkx or skeleton.with_suffix(".hkx")).resolve()
        tri = (args.tri or body.with_name(body.stem.removesuffix("_0").removesuffix("_1") + ".tri")).resolve()
        mb = (args.morphbench or locate.morphbench(ROOT)).resolve()
        settings_path = mb.parent / "morphbench.json"
        settings = json.loads(settings_path.read_text(encoding="utf-8-sig"))
        log_name = settings.get("logFile", "")
        if log_name and log_name != "morphbench.log":
            raise ValueError("Morphbench logFile must be empty or morphbench.log for this offline run")
        for key, value in recipe["requiredMorphbenchSettings"].items():
            if settings.get(key) != value:
                raise ValueError(f"Morphbench setting {key} must equal {value}; current {settings.get(key)!r}")
        inputs = [Path(__file__).resolve(), recipe_path, body, tri, skeleton, hkx, mb, settings_path]
        pinned = [digest(path) for path in inputs]
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        out = validate_destination(args.out or STAGING / (stamp + "-" + args.sex), inputs, mods)
        out.mkdir(parents=True, exist_ok=False)
        owned_output = True
        manifest.update(recipe=recipe, sex=args.sex, inputs=pinned,
                        claw=git_state(ROOT), morphbench=git_state(mb.parent),
                        python={"executable": args.python, "controllerVersion": sys.version},
                        coverageScope=recipe["coverageScope"])
        common = [str(body), "--tri", str(tri), "--skeleton", str(skeleton), "--hkx", str(hkx)]
        def call(command, extra, label, shared=common):
            return run_cli(args.python, mb, command, shared, extra, out, label, args.timeout, manifest["commands"])
        shapes = call("shapes", [], "shapes")
        missing = set(recipe["fit"]["only"]) - {row["name"] for row in shapes}
        if missing:
            raise ValueError("Selected mesh parts missing: " + ", ".join(sorted(missing)))
        summary = call("summary", [], "summary")
        ragdoll = summary.get("ragdoll") or {}
        if ragdoll.get("state") != "read" or ragdoll.get("unmatched"):
            raise ValueError("A fully matched readable HKX ragdoll is required")
        before = call("colliders", ["--clearance"], "before")
        candidate = out / "skeleton.nif"
        fitted = call("fit", fit_arguments(recipe, candidate), "fit")
        if not any(row.get("fitted") for row in fitted["fitted"]):
            raise ValueError("No collision body was fitted")
        after_common = [str(body), "--tri", str(tri), "--skeleton", str(candidate), "--hkx", str(hkx)]
        after = call("colliders", ["--clearance"], "after", after_common)
        manifest["coverage"] = coverage_delta(before, after)
        manifest["bodyPropertiesAndRagdollFramesPreserved"] = True
        manifest["unfittedBodies"] = [row["bone"] for row in fitted["fitted"] if not row.get("fitted")]
        for label, rows in (("before", before), ("after", after)):
            measured = [row["clearance"] for row in rows if row.get("clearance")]
            points = sum(row["points"] for row in measured)
            manifest[label + "Coverage"] = {"points": points, "outsideFractionWeighted":
                sum(row["points"] * row["outside"] for row in measured) / points if points else None,
                "unmeasuredBodies": [row["bone"] for row in rows if not row.get("clearance")]}
        if [digest(path) for path in inputs] != pinned:
            raise ValueError("Input/settings drifted during calculation; candidate is invalid")
        manifest["candidate"] = digest(candidate)
        manifest["status"] = "offline-candidate"
        print("Offline candidate (game validation pending): " + str(out))
        return 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        print("fit-colliders: " + str(exc), file=sys.stderr)
        return 2
    finally:
        if owned_output:
            manifest["finishedAt"] = datetime.now(timezone.utc).isoformat()
            (out / "collider-candidate.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
