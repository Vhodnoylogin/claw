"""Pure JSON contract checks for an offline Polygon restoring-guard response.

No transport, filesystem, clock, process, mutex or authority operations live here.
Expected bindings must come from an independently reviewed registered record and
the origin's plan, never be manufactured from the response being checked.
"""
from __future__ import annotations

import copy
import json
import math
from pathlib import PureWindowsPath
import re


SUPPORTED_PROTOCOL_COMMIT = "d9d3b72fba2f925180a3aba211cfc045f9f01d5e"
EXPECTED_KEYS = {"protocolCommit", "record", "reservedReview", "implementationPins",
                 "allowedPostimages", "freshModlistBackup", "profilePins",
                 "managedIniPath", "modlistVariants"}
RESPONSE_KEYS = {"schemaVersion", "kind", "record", "reservedReview", "implementationPins",
                 "stage", "stageProof", "nativeIdleObservation", "allowedPostimages",
                 "freshModlistBackup", "archiveVerified", "copyOnly", "callerMustOwnSessionMutex",
                 "mutexOwnershipProvedByGuard", "newCleanupGranted", "launchGranted"}
RESERVE_KEYS = {"schemaVersion", "kind", "id", "diagnosticId", "preparedRequestSha256",
                "subjectOrderSha256", "slotGrantSha256", "assessment", "installationReceipt",
                "installHelper", "installationStarted", "nativeUiReady", "ownerAuthorization",
                "noLaunchAuthority", "verifiedBy", "reason"}


def _object(value, keys):
    if type(value) is not dict or set(value) != keys:
        raise ValueError("Exact JSON object fields required")


def _json(value):
    if value is None or type(value) in (str, bool, int):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json(item)
        return
    raise ValueError("Finite JSON values and string object keys required")


def _same(left, right):
    _json(left)
    _json(right)
    encode = lambda value: json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return encode(left) == encode(right)


def _digest(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Lowercase SHA256 required")


def _id(value):
    if type(value) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", value):
        raise ValueError("Bounded identifier required")


def _path(value):
    if type(value) is not str or any(x in {".", ".."} for x in value.replace("\\", "/").split("/")):
        raise ValueError("Local absolute Windows path required")
    path = PureWindowsPath(value)
    if (not path.is_absolute() or not re.fullmatch(r"[A-Za-z]:", path.drive)
            or any(re.search(r'[<>:"|?*\x00-\x1f]', x) or x.endswith((".", " ")) for x in path.parts[1:])):
        raise ValueError("Local absolute Windows path required")
    return path


def _pin(value):
    _object(value, {"path", "sha256"})
    _path(value["path"])
    _digest(value["sha256"])


def _pins(value, count=None):
    if type(value) is not list or not 1 <= len(value) <= 4096 or count is not None and len(value) != count:
        raise ValueError("Bounded nonempty ordered file pins required")
    for row in value:
        _pin(row)
    if len({_path(x["path"]) for x in value}) != len(value):
        raise ValueError("Duplicate file path")


def build_guard_query(recovery_id, reserved_review_pin, stage, archive=None):
    """Build a query object only. It is not sent or written by this function."""
    _id(recovery_id)
    _pin(reserved_review_pin)
    if stage not in ("pre-archive", "partial") or (archive is not None) != (stage == "partial"):
        raise ValueError("Archive pin is required only for the partial stage")
    result = {"schemaVersion": 1, "kind": "diagnostic-preexecution-restoring-guard",
              "id": recovery_id, "reservedReviewPin": copy.deepcopy(reserved_review_pin), "stage": stage}
    if archive is not None:
        _pin(archive)
        result["archive"] = copy.deepcopy(archive)
    return result


def _identity(value):
    _object(value, {"pid", "birth", "path"})
    if any(type(value[k]) is not int or value[k] <= 0 for k in ("pid", "birth")):
        raise ValueError("Positive native process identity required")
    _path(value["path"])


def _native_observation(value):
    _object(value, {"observedAt", "processes", "checkedOwners", "runtimeStates"})
    at = value["observedAt"]
    if type(at) not in (int, float) or at <= 0 or at > 1e20 or not math.isfinite(at):
        raise ValueError("Finite producer observation time required; it does not establish freshness")
    rows = value["processes"]
    if type(rows) is not list or not 1 <= len(rows) <= 200000:
        raise ValueError("Nonempty bounded process inventory required")
    forbidden = {"skyrimse.exe", "skyrimvr.exe", "skse64_loader.exe", "sksevr_loader.exe",
                 "vrserver.exe", "vrmonitor.exe", "vrcompositor.exe", "vrstartup.exe",
                 "vrdashboard.exe", "vrwebhelper.exe", "vrprismhost.exe"}
    seen = set()
    for row in rows:
        if (type(row) is not dict or type(row.get("pid")) is not int or row["pid"] < 0
                or type(row.get("name")) is not str or not row["name"] or row["pid"] in seen
                or row["name"].casefold() in forbidden):
            raise ValueError("Malformed or contradictory native process inventory")
        seen.add(row["pid"])
    owners = value["checkedOwners"]
    if type(owners) is not list or not 1 <= len(owners) <= 4096:
        raise ValueError("Checked prior owner identities required")
    for owner in owners:
        _object(owner, {"expected", "alive", "observedReusedPid"})
        _identity(owner["expected"])
        if owner["alive"] is not False:
            raise ValueError("Prior native owner is not proven ended in the response")
        reused = owner["observedReusedPid"]
        if reused is not None:
            _identity(reused)
            if reused["pid"] != owner["expected"]["pid"] or reused["birth"] == owner["expected"]["birth"]:
                raise ValueError("Contradictory reused PID identity")
        if (owner["expected"]["pid"] in seen) != (reused is not None):
            raise ValueError("Process inventory and ended/reused owner disagree")
    states = value["runtimeStates"]
    if type(states) is not list or not 1 <= len(states) <= 4096:
        raise ValueError("Bounded historical runtime states required")
    for state in states:
        _object(state, {"state", "game", "order", "done", "restored"})
        _pin(state["state"])
        if state["game"] is not None:
            _identity(state["game"])
        if state["order"] is not None and type(state["order"]) is not dict:
            raise ValueError("Malformed historical order")
        if state["done"] is not True or state["restored"] is not True:
            raise ValueError("Unfinished historical runtime state")


def validate_guard_response(query, response, expected, exit_code=0):
    """Check saved JSON against reviewed bindings; never certify current state.

    The exit code is a supplied value, not independently observed execution.
    The producer does not echo the partial archive pin. A future trusted actor
    must bind the exact query/source/exit/stdout and own the mutex across a fresh
    invocation and its bounded action. Neither transport nor that actor is here.
    """
    _json(query)
    _json(response)
    _json(expected)
    if type(exit_code) is not int or exit_code != 0:
        raise ValueError("Successful actual-source invocation is a required future caller precondition")
    if type(query) is not dict:
        raise ValueError("Exact guard query object required")
    _object(query, {"schemaVersion", "kind", "id", "reservedReviewPin", "stage"}
            | ({"archive"} if query.get("stage") == "partial" else set()))
    rebuilt = build_guard_query(query["id"], query["reservedReviewPin"], query["stage"], query.get("archive"))
    if not _same(query, rebuilt):
        raise ValueError("Exact guard query required")
    _object(expected, EXPECTED_KEYS)
    if expected["protocolCommit"] != SUPPORTED_PROTOCOL_COMMIT:
        raise ValueError("One reviewed supported version is required for new reserve/guard/complete")
    _object(response, RESPONSE_KEYS)
    if type(response["schemaVersion"]) is not int or response["schemaVersion"] != 1 or response["kind"] != "validated-current-restoring-scope":
        raise ValueError("Validated restoring-scope response required")
    record = expected["record"]
    _object(record, {"id", "diagnosticId", "status", "requestSha256"})
    _id(record["id"])
    _id(record["diagnosticId"])
    _digest(record["requestSha256"])
    if record["status"] != "restoring" or record["id"] != query["id"]:
        raise ValueError("Known registered recovery fingerprint required")
    reserved = expected["reservedReview"]
    _object(reserved, {"pin", "review"})
    _pin(reserved["pin"])
    review = reserved["review"]
    _object(review, RESERVE_KEYS)
    if (type(review["schemaVersion"]) is not int or review["schemaVersion"] != 1
            or review.get("kind") != "diagnostic-preexecution-recovery-reserve"
            or review.get("id") != record["id"] or review.get("diagnosticId") != record["diagnosticId"]
            or review.get("noLaunchAuthority") is not True or not _same(reserved["pin"], query["reservedReviewPin"])):
        raise ValueError("Full independently reviewed reserved review binding required")
    for key in ("preparedRequestSha256", "subjectOrderSha256", "slotGrantSha256"):
        _digest(review[key])
    for key in ("assessment", "installationReceipt", "installHelper", "installationStarted", "nativeUiReady"):
        _pin(review[key])
    owner = review["ownerAuthorization"]
    if type(owner) is not dict or not {"path", "sha256", "threadId", "messageId", "quote", "verifiedBy"} <= set(owner):
        raise ValueError("Retained owner provenance shape required, without new permission")
    _pin({"path": owner["path"], "sha256": owner["sha256"]})
    for value in [review["verifiedBy"], review["reason"], *[owner[k] for k in ("threadId", "messageId", "quote", "verifiedBy")]]:
        if type(value) is not str or not value.strip():
            raise ValueError("Nonempty reviewer, reason and retained owner provenance strings required")
    for key in ("record", "reservedReview", "implementationPins", "allowedPostimages", "freshModlistBackup"):
        if not _same(response[key], expected[key]):
            raise ValueError("Response differs from reviewed " + key)
    _pins(expected["implementationPins"])
    allowed = expected["allowedPostimages"]
    _pins(allowed, 13)
    fresh = expected["freshModlistBackup"]
    _object(fresh, {"path", "backup", "sha256", "currentSha256", "currentlyByteIdentical"})
    if fresh["currentlyByteIdentical"] is not False:
        raise ValueError("Fresh modlist and installed postimage must differ")
    modlist = _path(fresh["path"])
    _path(fresh["backup"])
    _digest(fresh["sha256"])
    _digest(fresh["currentSha256"])
    managed_ini = _path(expected["managedIniPath"])
    if (modlist.name != "modlist.txt" or modlist.parent.parent != managed_ini.parent / "profiles"
            or managed_ini.name != "ModOrganizer.ini"):
        raise ValueError("Exact native instance/source profile boundary required")
    variants = expected["modlistVariants"]
    _object(variants, {"postimage", "disabled-new-mod", "preimage"})
    for digest in variants.values():
        _digest(digest)
    if variants["postimage"] != fresh["currentSha256"] or variants["preimage"] != fresh["sha256"]:
        raise ValueError("Modlist variants contradict independent fresh/postimage hashes")
    _pins(expected["profilePins"])
    if [x for x in expected["profilePins"] if _path(x["path"]) == modlist] != [{"path": fresh["path"], "sha256": fresh["currentSha256"]}]:
        raise ValueError("Reserved source modlist profile pin required")
    if response["stage"] != query["stage"]:
        raise ValueError("Stage differs from the query")
    pre_archive = query["stage"] == "pre-archive"
    for key, value in {"archiveVerified": not pre_archive, "copyOnly": pre_archive,
                       "callerMustOwnSessionMutex": True, "mutexOwnershipProvedByGuard": False,
                       "newCleanupGranted": False, "launchGranted": False}.items():
        if response[key] is not value:
            raise ValueError("Invalid stage/authority/mutex flag: " + key)
    proof = response["stageProof"]
    _object(proof, {"present", "absent", "modlistState", "profilePins", "managedIniPin"})
    present, absent = proof["present"], proof["absent"]
    if type(present) is not list or type(absent) is not list or len(present) + len(absent) != 13:
        raise ValueError("Exact owned present/absent partition required")
    if present:
        _pins(present)
    for path in absent:
        _path(path)
    all_paths = [x["path"] for x in allowed]
    present_paths = [x["path"] for x in present]
    if (len(set(present_paths + absent)) != 13 or set(present_paths + absent) != set(all_paths)
            or not _same(present, [x for x in allowed if x["path"] in present_paths])
            or absent != [x for x in all_paths if x in absent]):
        raise ValueError("Changed, extra, duplicate or reordered owned transition")
    state = proof["modlistState"]
    if type(state) is not str or state not in variants or pre_archive and (present != allowed or absent or state != "postimage"):
        raise ValueError("Unreviewed modlist state or incomplete pre-archive inventory")
    profiles = copy.deepcopy(expected["profilePins"])
    for pin in profiles:
        if _path(pin["path"]) == modlist:
            pin["sha256"] = variants[state]
    if not _same(proof["profilePins"], profiles):
        raise ValueError("Other profile inventory or source modlist variant changed")
    _pin(proof["managedIniPin"])
    if _path(proof["managedIniPin"]["path"]) != managed_ini:
        raise ValueError("Different managed INI path")
    _native_observation(response["nativeIdleObservation"])
    return {"schemaVersion": 1, "kind": "claw-offline-restoring-guard-response-review",
            "protocolCommit": SUPPORTED_PROTOCOL_COMMIT, "recoveryId": record["id"], "stage": query["stage"],
            "responseContractVerified": True, "liveStateVerified": False, "mutexOwnershipVerified": False,
            "managerIdleVerified": False, "cleanupGranted": False, "launchGranted": False,
            "executionSupported": False, "nativeIdleObservation": copy.deepcopy(response["nativeIdleObservation"])}
