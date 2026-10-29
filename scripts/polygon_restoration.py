"""Prepare an offline, origin-owned Polygon restoration plan.

This client never reserves a lease, archives or removes installed files, drives
MO2, queries an API, or certifies native restoration. Its output is deliberately
not an executable cleanup authorization or a valid restoration receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any

from polygon_guard_contract import SUPPORTED_PROTOCOL_COMMIT


CONFIG_KIND = "claw-origin-recovery-plan-input"
CONFIG_KEYS = {"schemaVersion", "kind", "workspaceRoot", "recoveryId", "assessment",
               "preparedRequest", "submittedOrder", "reserveReview"}
METADATA = {"claw-build.json", "readme.md", "readme.ru.md"}
REPOSITORY = Path(__file__).resolve().parents[1]


def checked_path(value: str | Path) -> Path:
    """Reject relative/dot/reparse paths before following filesystem entries."""
    if not isinstance(value, (str, Path)):
        raise ValueError("A local absolute path is required")
    raw = str(value)
    if any(x in {".", ".."} for x in raw.replace("\\", "/").split("/")):
        raise ValueError("Dot path components are outside the reviewed scope")
    path = Path(raw)
    if not path.is_absolute() or raw.startswith(("\\\\", "//")):
        raise ValueError("A local absolute path is required")
    for item in [*reversed(path.parents), path]:
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("Reparse/symlink entries are outside the reviewed scope")
    return path.resolve()


def read_pin(value: dict[str, Any]) -> bytes:
    if not isinstance(value, dict) or not {"path", "sha256"} <= set(value):
        raise ValueError("A file pin is required")
    digest = value["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("A lowercase SHA256 is required")
    path = checked_path(value["path"])
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    stamp = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns)
    if (not stat.S_ISREG(before.st_mode) or stamp(before) != stamp(after)
            or stamp(after) != stamp(path.stat())
            or hashlib.sha256(raw).hexdigest() != digest):
        raise ValueError("Pinned file bytes or identity changed")
    return raw


def document(value: dict[str, Any]) -> dict[str, Any]:
    result = json.loads(read_pin(value).decode("utf-8-sig"))
    if not isinstance(result, dict):
        raise ValueError("A pinned JSON object is required")
    return result


def short_pin(value: dict[str, Any]) -> dict[str, str]:
    return {"path": value["path"], "sha256": value["sha256"]}


def _unique(rows: list[dict[str, Any]], expected: int) -> dict[Path, dict[str, Any]]:
    if not isinstance(rows, list) or len(rows) != expected:
        raise ValueError("Unexpected owned-file/preimage count")
    result = {checked_path(x["path"]): x for x in rows}
    if len(result) != expected:
        raise ValueError("Duplicate owned-file/preimage path")
    return result


def prepare_plan(config: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(config, dict) or set(config) != CONFIG_KEYS
            or type(config["schemaVersion"]) is not int or config["schemaVersion"] != 1
            or config["kind"] != CONFIG_KIND
            or not isinstance(config["recoveryId"], str)
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", config["recoveryId"])):
        raise ValueError("Exact offline recovery-plan input required")
    workspace = checked_path(config["workspaceRoot"])
    assessment = document(config["assessment"])
    prepared = document(config["preparedRequest"])
    order = document(config["submittedOrder"])
    if assessment.get("kind") != "read-only-minimal-unstarted-preparation-restoration-assessment":
        raise ValueError("Reviewed owned-installation assessment required")
    if (prepared.get("orderId") != order.get("id")
            or any(prepared.get(k) != order.get(k) for k in ("sourceChat", "sourceThreadId"))
            or prepared.get("cycleId") != order.get("cycle", {}).get("id")
            or prepared.get("slotId") != order.get("cycle", {}).get("slotId")):
        raise ValueError("Prepared and submitted subject/origin bindings differ")
    reserve = config["reserveReview"]
    if reserve is not None:
        review = document(reserve)
        if (review.get("kind") != "diagnostic-preexecution-recovery-reserve"
                or review.get("id") != config["recoveryId"]
                or review.get("diagnosticId") != prepared.get("id")
                or review.get("noLaunchAuthority") is not True):
            raise ValueError("Recovery review does not match the offline plan")

    fresh = _unique(assessment["freshPreimages"], 11)
    managers = [x for x in fresh if x.name == "ModOrganizer.ini"]
    if len(managers) != 1:
        raise ValueError("One fresh native manager INI preimage required")
    manager_ini = managers[0]
    instance = manager_ini.parent
    profile_paths = set(fresh) - {manager_ini}
    parents = {x.parent for x in profile_paths}
    if len(parents) != 1:
        raise ValueError("Fresh profile preimages must share the exact source profile")
    profile = parents.pop()
    profile_name = order.get("profile")
    if (not isinstance(profile_name, str) or not profile_name or profile_name in {".", ".."}
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', profile_name)
            or profile_name.endswith((".", " "))):
        raise ValueError("The source profile must be one plain directory name")
    if (profile.parent != instance / "profiles" or profile.name != profile_name
            or profile / "modlist.txt" not in fresh):
        raise ValueError("Exact source instance/profile preimages required")
    root_mod = checked_path(assessment["rootMod"])
    if root_mod.parent != instance / "mods":
        raise ValueError("Owned mod must be a direct child of the reviewed instance")
    if REPOSITORY == instance or instance in REPOSITORY.parents:
        raise ValueError("An installed instance cannot contain this source checkout")

    owned_mod = _unique(assessment["modFiles"], 11)
    relative = {path: path.relative_to(root_mod) for path in owned_mod}
    if any(root_mod not in path.parents for path in owned_mod):
        raise ValueError("An owned mod file escapes its exact root")
    metadata_ini = [x for x in relative if relative[x] == Path("meta.ini")]
    payload = [x for x in relative if x not in metadata_ini]
    metadata = [x for x in payload if len(relative[x].parts) == 1
                and relative[x].name.casefold() in METADATA]
    game = [x for x in payload if x not in metadata]
    if (len(metadata_ini) != 1 or len(metadata) != 3 or len(game) != 7
            or {relative[x].name.casefold() for x in metadata} != METADATA
            or sorted(x.suffix.casefold() for x in game) != [".esp", ".nif", ".nif", ".nif", ".nif", ".tri", ".tri"]):
        raise ValueError("Exact ten-payload plus native metadata CLAW layout required")
    expected_directories = {p for x in owned_mod for p in x.parents if root_mod in p.parents}
    actual_entries = {checked_path(x) for x in root_mod.rglob("*")}
    if actual_entries != set(owned_mod) | expected_directories:
        raise ValueError("Extra or missing owned mod entries forbid this plan")

    downloads = _unique(assessment["newDownloadFiles"], 2)
    download_paths = list(downloads)
    if (any(x.parent != instance / "downloads" for x in downloads)
            or str(download_paths[1]) != str(download_paths[0]) + ".meta"
            or download_paths[0].suffix.casefold() not in {".7z", ".zip"}):
        raise ValueError("Only the exact copied archive and its metadata are owned")
    for item in [*owned_mod.values(), *downloads.values()]:
        read_pin(item)

    for path, item in fresh.items():
        backup = checked_path(item["backup"])
        if instance == backup or instance in backup.parents or path == backup:
            raise ValueError("Fresh backups must be independent of the installed instance")
        before = read_pin({"path": str(backup), "sha256": item["sha256"]})
        current = path.read_bytes()
        if path == profile / "modlist.txt":
            lines = current.splitlines(keepends=True)
            matches = [i for i, line in enumerate(lines)
                       if line.rstrip(b"\r\n") == ("+" + root_mod.name).encode("utf-8")]
            first_entry = next((i for i, line in enumerate(lines) if line.startswith((b"+", b"-"))), None)
            if (len(matches) != 1 or matches[0] != first_entry
                    or b"".join(x for i, x in enumerate(lines) if i != matches[0]) != before):
                raise ValueError("Source modlist differs beyond the one owned mod entry")
        elif current != before:
            raise ValueError("Fresh non-modlist bytes changed; a separate reviewed boundary is needed")
    profiles = sorted((instance / "profiles").iterdir())
    if len(profiles) > 256:
        raise ValueError("Profile scope exceeds the bounded review")
    for directory in profiles:
        checked_path(directory)
        if not directory.is_dir():
            raise ValueError("Unknown native profile entry")
        path = checked_path(directory / "modlist.txt")
        references = [line for line in path.read_text(encoding="utf-8-sig").splitlines()
                      if line.strip().lstrip("+-").casefold() == root_mod.name.casefold()]
        if references and (directory != profile or references != ["+" + root_mod.name]):
            raise ValueError("Another profile or ambiguous source entry references the owned mod")

    inputs = order.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError("Submitted pinned inputs are required")
    order_files = {checked_path(x["path"]): x for x in inputs}
    if len(order_files) != len(inputs):
        raise ValueError("Duplicate submitted input path")
    for path in payload:
        if path not in order_files or order_files[path]["sha256"] != owned_mod[path]["sha256"]:
            raise ValueError("Owned payload differs from the submitted subject")
    audit = document(prepared["baselineAudit"])
    audit_rows = audit.get("files")
    if not isinstance(audit_rows, list) or len(audit_rows) != 10:
        raise ValueError("Exact pinned baseline audit/readback order required")
    ordered_payload = []
    for row in audit_rows:
        name = Path(row["virtualPath"])
        if name.is_absolute() or any(x in {".", ".."} for x in str(name).replace("\\", "/").split("/")):
            raise ValueError("Unsafe baseline virtual path")
        path = checked_path(root_mod / name)
        if path not in payload or owned_mod[path]["sha256"] != row["sha256"]:
            raise ValueError("Baseline audit differs from owned payload")
        ordered_payload.append(path)
    if len(set(ordered_payload)) != 10:
        raise ValueError("Duplicate baseline virtual path")
    originals = []
    for path in [x for x in ordered_payload if x in game]:
        suffix = tuple(x.casefold() for x in relative[path].parts)
        candidates = []
        for row in inputs:
            candidate = checked_path(row["path"])
            if (instance / "mods" in candidate.parents and root_mod not in candidate.parents
                    and tuple(x.casefold() for x in candidate.parts[-len(suffix):]) == suffix):
                read_pin(row)
                candidates.append(short_pin(row))
        if not candidates:
            raise ValueError("Every original game path needs a pinned former provider")
        originals.append({"virtualPath": str(relative[path]), "originalPinnedCandidates": candidates})

    evidence_root = workspace / "local" / "skyrim-polygon" / "diagnostic-recoveries" / config["recoveryId"]
    checked_path(evidence_root)
    if (instance == evidence_root or instance in evidence_root.parents
            or REPOSITORY == evidence_root or REPOSITORY in evidence_root.parents):
        raise ValueError("Generated evidence must remain outside installed and source trees")
    owned = [*assessment["modFiles"], *assessment["newDownloadFiles"]]
    archive_rows = []
    for row in owned:
        source = checked_path(row["path"])
        rel = Path("mod") / source.relative_to(root_mod) if source in owned_mod else Path("downloads") / source.name
        archive_rows.append({"original": short_pin(row), "plannedArchivePath": str(evidence_root / "archive" / rel)})
    return {
        "schemaVersion": 1, "kind": "claw-origin-restoration-plan", "recoveryId": config["recoveryId"],
        "cleanupGranted": False, "launchGranted": False, "executionSupported": False,
        "blocker": "A supported restoring guard is published, but this client only checks offline JSON; no live actor, reservation, cleanup strategy or execution handoff is implemented.",
        "source": {"path": str(Path(__file__).resolve()), "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
        "guardAdapter": {
            "protocolCommit": SUPPORTED_PROTOCOL_COMMIT,
            "source": {"path": str(Path(__file__).with_name("polygon_guard_contract.py").resolve()),
                       "sha256": hashlib.sha256(Path(__file__).with_name("polygon_guard_contract.py").read_bytes()).hexdigest()},
            "mode": "pure-offline-json-validation", "transportImplemented": False,
            "liveExecutionApproved": False, "savedResponseGrantsCleanup": False,
            "managerIdleEvidenceRequiredSeparately": True,
        },
        "inputPins": {k: config[k] for k in ("assessment", "preparedRequest", "submittedOrder", "reserveReview")},
        "instance": str(instance), "profile": order["profile"], "evidenceRoot": str(evidence_root),
        "sameQueuedSubjectMustRemainUnchanged": order["id"], "physicalRollbackIsOptionalFallback": True,
        "ownedPostimages": [short_pin(x) for x in owned], "freshPreimages": assessment["freshPreimages"],
        "plannedArchiveMembers": archive_rows,
        "rollbackTargets": [x["path"] for x in owned] + [str(profile / "modlist.txt")],
        "gameVfsReadbacks": originals,
        "metadataVfsReadbacks": [str(relative[x]) for x in ordered_payload if x in metadata],
        "orderedNativeVfsReadbacks": [{"virtualPath": str(relative[x]),
                                       "role": "metadata" if x in metadata else "original-game-provider"}
                                      for x in ordered_payload],
        "actionsAfterSeparateReviewedHandoffOnly": [
            "Verify supported current restoring reservation, exact review/source/ACK/Q1 hold and original queued subject under the native mutex.",
            "Verify real SE manager PID/birth/path, source profile and known idle; reject every game/loader/unknown owner.",
            "Archive and hash all thirteen owned postimages externally before any removal; retain the fresh eleven independent backups.",
            "Recheck exact inventory/reparse boundaries and every profile reference immediately before native UI removal of only this named mod.",
            "Use native Downloads UI to remove only the two proven copied download records; do not touch the retained original acquisition.",
            "Verify native modlist equals the fresh backup and nine other profile files remain exact. If file restoration is needed, first close only the verified manager and confirm its full identity ended; copy only the fresh modlist, then reopen that exact instance.",
            "Never copy an INI over a live manager. Preserve an immutable post-restoration INI under the scoped evidence directory for the producer's strict GUI-only comparison.",
            "Capture actual UI/API evidence, current manager identity/known-idle/profile, absence and ordered seven original game VFS winners plus three bounded metadata observations.",
            "Independently review the actual receipt and complete through the supported recovery API. No game, test result, new order, budget reset or automatic next preparation follows."
        ],
        "receiptTemplate": {
            "schemaVersion": 1, "kind": "DRAFT-diagnostic-preexecution-native-restoration-receipt",
            "recoveryId": config["recoveryId"], "reservedReviewPin": reserve,
            "sourceChat": order["sourceChat"], "sourceThreadId": order["sourceThreadId"],
            "instance": str(instance), "profile": order["profile"], "managerIdentity": None,
            "noGameStarted": None, "archive": None,
            "rollbackTargets": [x["path"] for x in owned] + [str(profile / "modlist.txt")],
            "nativeUiActor": {"helper": None, "evidence": []}, "readback": None,
            "verifiedBy": None, "reason": "DRAFT ONLY: actual supported reservation, archived files and native UI/process/API observations do not exist here."
        }
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Read verified inputs and write one external, non-authorizing draft")
    plan.add_argument("--config", type=Path, required=True)
    plan.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    config_path = checked_path(args.config)
    if REPOSITORY == config_path or REPOSITORY in config_path.parents:
        raise ValueError("Machine configuration must remain outside Git")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    result = prepare_plan(config)
    output = checked_path(args.output)
    evidence_root = checked_path(result["evidenceRoot"])
    if evidence_root not in output.parents:
        raise ValueError("Plan output must remain inside its external scoped evidence directory")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
    print(json.dumps({"plan": str(output), "cleanupGranted": False, "launchGranted": False, "executionSupported": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
