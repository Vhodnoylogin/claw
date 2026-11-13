"""One-use CLAW upload using the official Nexus v3 multipart/version API.

Default: local review only, no credential read or network access.
--apply requires an exact reviewed proposal hash and a fully accepted artifact.
No mutation is retried; any existing attempt directory forbids replay.
"""
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET
import argparse
import datetime
import hashlib
import json
import math
import os
import re
import sys
import time
import zipfile
from urllib import request as http, error as http_error

API_BASE = "https://api.nexusmods.com/v3"
GAME = "skyrimspecialedition"
GLOBAL_MOD = "7318624467182"
ACTIVE_FILE = "8342508"
PREVIOUS_VERSION = "7318625109219"
SCOPED_PREVIOUS = "836835"
VERSION = "0.10.0"
DUPLICATE_VERSIONS = {VERSION, "0.10"}
DISPLAY_NAME = "CLAW - Custom Lycanthrope Appearance and Weight"
OLD_UPLOAD_ID = "289d7120-fb73-478e-8486-08932b656a55"
SOURCE_COMMIT = "1e7513b8c4e439ed93fec6d0856642b7cf90e75d"



class SafeStop(Exception):
    """Only fixed, non-secret diagnostic text may reach the operator."""


def require(condition, message):
    if not condition:
        raise SafeStop(message)


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def dependency_meaning(value):
    """Ignore newly allocated definition IDs; retain every AND/OR boundary."""
    ranges = []
    for definition in value["dependency_definitions"]:
        group = [(row["target_mod_file"]["id"], row["min_version"]["id"], row["max_version"]["id"] if row["max_version"] else None) for row in definition["ranges"]]
        ranges.append(sorted(group, key=canonical))
    dlc = [sorted(row["dlc_id"] for row in definition["dlc_targets"]) for definition in value["dlc_dependency_definitions"]]
    return {"ranges": sorted(ranges, key=canonical), "dlc": sorted(dlc, key=canonical)}


def ensure_current(previous, file, versions):
    require(str(previous["id"]) == PREVIOUS_VERSION and str(previous["file"]["id"]) == ACTIVE_FILE, "Previous version/update chain changed")
    require(previous["version"] == "0.9.0" and previous["category"] == "main" and previous["is_primary"] is True
            and previous["security_scan_status"] == "cleared", "Previous0.9.0 is no longer cleared/Main/primary")
    require(str(file["id"]) == ACTIVE_FILE and file["is_active"] is True and file["name"] == DISPLAY_NAME, "Expected active file identity changed")
    require(not any(row["version"] in DUPLICATE_VERSIONS for row in versions["versions"]), "0.10 already exists; do not create a duplicate")
    require(any(str(row["id"]) == PREVIOUS_VERSION for row in versions["versions"]), "Rollback version is absent from active chain")


def proposal(path):
    value = read(path)
    require(type(value["schemaVersion"]) is int and value["schemaVersion"] == 1 and value["game"] == GAME and value["globalModId"] == GLOBAL_MOD, "Unexpected target mod")
    require(value["activeFileId"] == ACTIVE_FILE and value["previousVersionId"] == PREVIOUS_VERSION and value["scopedPreviousVersionId"] == SCOPED_PREVIOUS, "Unexpected current update chain")
    require(value["version"] == VERSION and value["name"] == DISPLAY_NAME and value["sourceCommit"] == SOURCE_COMMIT, "Fixed accepted release identity changed")
    require(value["helperSha256"] == digest(__file__), "Proposal does not bind reviewed portable publisher")
    require(value["changelog"]["mode"] == "append-once", "Only one new changelog append allowed")
    for key in ("archive", "description", "modDescription", "baselineModDescription", "changelog", "requirementsSnapshot", "acceptance"):
        item = value[key]
        require(Path(item["path"]).is_absolute() and digest(item["path"]) == item["sha256"], "Pinned local input differs")
    archive = Path(value["archive"]["path"])
    require(archive.name == "CLAW - Customizable Lycanthrope Appearance and Weight.zip" and archive.stat().st_size == value["archive"]["bytes"], "Version-neutral archive identity differs")
    with zipfile.ZipFile(archive) as package:
        require(package.testzip() is None, "Archive CRC failure")
        require(not any(n.lower().endswith((".dds", ".zip", ".pdb", ".cpp", ".py", ".psc", ".exe", ".wasm")) for n in package.namelist()), "Forbidden runtime payload")
        dlls = [n for n in package.namelist() if n.endswith("CLAWDistribution.dll")]
        require(len(dlls) == 1, "Exactly one CLAW DLL required")
        dll_sha = hashlib.sha256(package.read(dlls[0])).hexdigest()
    accepted = read(value["acceptance"]["path"])
    require(accepted["sourceCommit"] == SOURCE_COMMIT and accepted["releaseArchive"]["sha256"] == value["archive"]["sha256"] and accepted["releaseDll"]["sha256"] == dll_sha, "Accepted archive/DLL/source binding differs")
    require(value["allowedStorageHosts"] and all(re.fullmatch(r"[a-z0-9.-]+", h) for h in value["allowedStorageHosts"]), "Invalid storage host admission")
    receipt = Path(value["receiptDirectory"])
    require(receipt.is_absolute() and receipt.parent == Path(path).resolve().parent and receipt.name == "attempt", "Receipt directory must be the one reviewed runner attempt")
    require(not receipt.exists() and not list(receipt.parent.glob("attempt*/*.intent.json")), "Existing remote mutation ledger forbids replay")
    value["_texts"] = {key: Path(value[key]["path"]).read_text(encoding="utf-8-sig").strip() for key in ("description", "modDescription", "baselineModDescription", "changelog")}
    dependency_meaning(read(value["requirementsSnapshot"]["path"]))
    return value, accepted


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def durable(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


class Ledger:
    def __init__(self, directory, reviewed_path):
        self.directory = Path(directory)
        self.directory.mkdir(exist_ok=False)
        durable(self.directory / "upload-intent.json", {"atUtc": utc(), "proposalSha256": digest(reviewed_path), "helperSha256": digest(__file__), "policy": "One request per mutating stage; never replay an ambiguous attempt"})

    def stage(self, name, action, summarize):
        durable(self.directory / (name + ".intent.json"), {"atUtc": utc(), "stage": name})
        value = action()
        durable(self.directory / (name + ".receipt.json"), {"atUtc": utc(), "stage": name, **summarize(value)})
        print(json.dumps({"stage": name, "completed": True}), flush=True)
        return value


class NoRedirect(http.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Response:
    def __init__(self, status, headers, content):
        self.status_code, self.headers, self.content = status, headers, content

    def json(self):
        return json.loads(self.content)


def transport(method, url, payload, headers, timeout):
    """No redirects, retries, request dumps or third-party HTTP dependency."""
    opener = http.build_opener(NoRedirect())
    try:
        with opener.open(http.Request(url, data=payload, headers=headers, method=method), timeout=timeout) as response:
            return Response(response.status, response.headers, response.read())
    except http_error.HTTPError as error:
        with error:
            return Response(error.code, error.headers, error.read())
    except (OSError, http_error.URLError):
        raise SafeStop("Network transport failed; do not retry the mutation") from None


class Api:
    def __init__(self):
        key = os.environ.get("NEXUS_API_KEY", "").strip()
        require(key and all(32 <= ord(c) < 127 for c in key), "Private NEXUS_API_KEY environment credential required")
        self.headers = {"apikey": key, "Accept": "application/json", "Content-Type": "application/json",
                        "User-Agent": "Nexus-Mods/upload-action (reviewed CLAW one-use invocation)"}

    def call(self, method, route, body=None):
        payload = json.dumps(body).encode() if body is not None else None
        response = transport(method, API_BASE + route, payload, self.headers, 60)
        require(200 <= response.status_code < 300, f"Nexus {method} {route} HTTP{response.status_code}; do not retry")
        if response.status_code == 204:
            return None
        value = response.json()
        return value if route.endswith("/dependencies") else value["data"]

    def changelogs(self):
        response = transport("GET", "https://api.nexusmods.com/v1/games/skyrimspecialedition/mods/194798/changelogs.json", None, self.headers, 60)
        require(response.status_code == 200, "Read-only changelog request failed")
        result = response.json()
        require(type(result) is dict, "Malformed changelog readback")
        return result


def storage_request(method, url, body, content_type, allowed_hosts):
    parsed = urlparse(url)
    require(parsed.scheme == "https" and parsed.hostname in allowed_hosts and parsed.username is None and
            parsed.password is None and not parsed.fragment and parsed.port in (None, 443),
            "Unreviewed signed-storage host/layout; stop without replay")
    response = transport(method, url, body, {"Content-Type": content_type, "Content-Length": str(len(body))}, 180)
    require(200 <= response.status_code < 300, f"Signed-storage HTTP{response.status_code}; do not retry")
    return response


def complete_xml(parts):
    root = ET.Element("CompleteMultipartUpload")
    for number, tag in parts:
        node = ET.SubElement(root, "Part")
        ET.SubElement(node, "PartNumber").text = str(number)
        ET.SubElement(node, "ETag").text = tag
    return ET.tostring(root)


def ensure_completion(response):
    root = ET.fromstring(response.content)
    require(root.tag.rsplit("}", 1)[-1] == "CompleteMultipartUploadResult", "Storage completion response did not confirm success")
    return response


def upload_part(url, payload, allowed_hosts):
    response = storage_request("PUT", url, payload, "application/octet-stream", allowed_hosts)
    tag = response.headers.get("ETag", "").strip('"')
    require(bool(re.fullmatch(r"[a-zA-Z0-9-]{1,128}", tag)), "Missing or unexpected storage ETag; do not retry")
    return tag


def publish(value, acceptance, reviewed_path):
    require(value["publicationReady"] is True and acceptance.get("fullReleaseAccepted") is True, "Release remains blocked; final acceptance required")
    require(not Path(value["receiptDirectory"]).exists(), "Attempt directory already exists; inspect receipts instead of replaying")
    api = Api()

    def current():
        previous = api.call("GET", "/games/" + GAME + "/mod-file-versions/" + SCOPED_PREVIOUS)
        file = api.call("GET", "/mod-files/" + ACTIVE_FILE)
        versions = api.call("GET", "/mod-files/" + ACTIVE_FILE + "/versions")
        ensure_current(previous, file, versions)
        old_upload = api.call("GET", "/uploads/" + OLD_UPLOAD_ID)
        require(old_upload["id"] == OLD_UPLOAD_ID and old_upload["state"] == "created", "Old local upload is no longer unfinalised; recovery requires fresh review")
        for row in api.call("GET", "/mods/" + GLOBAL_MOD + "/files")["mod_files"]:
            other = api.call("GET", "/mod-files/" + str(row["id"]) + "/versions")
            require(not any(v["version"] in DUPLICATE_VERSIONS for v in other["versions"]), "0.10 already exists in this mod; do not duplicate")
        require(not DUPLICATE_VERSIONS.intersection(api.changelogs()), "0.10 changelog already exists; never append twice")
        mod = api.call("GET", "/mods/" + GLOBAL_MOD)
        require(str(mod["id"]) == GLOBAL_MOD and mod["description"].strip() == value["_texts"]["baselineModDescription"], "Live description differs from reviewed preimage")

    current()
    dependencies = api.call("GET", "/mod-file-versions/" + PREVIOUS_VERSION + "/dependencies")
    expected_dependencies = dependency_meaning(read(value["requirementsSnapshot"]["path"]))
    require(dependency_meaning(dependencies) == expected_dependencies, "Existing requirements changed since review")
    ledger = Ledger(value["receiptDirectory"], reviewed_path)
    try:
        durable(ledger.directory / "previous-dependencies.json", dependencies)
        durable(ledger.directory / "old-local-upload-guard.json", {"id": OLD_UPLOAD_ID, "state": "created", "claimedFieldAvailable": False, "basis": "Fresh created-state plus no0.10 versions/changelog; old local ledger retained separately and never replayed"})
        archive = Path(value["archive"]["path"])
        created = ledger.stage("01-create-multipart", lambda: api.call("POST", "/uploads/multipart", {"filename": archive.name, "size_bytes": str(archive.stat().st_size)}), lambda row: {"uploadId": row["id"], "partCount": len(row["part_presigned_urls"]), "partSizeBytes": row["part_size_bytes"]})
        upload_id = created["id"]
        urls, size = created["part_presigned_urls"], created["part_size_bytes"]
        require(type(size) is int and size > 0 and len(urls) == math.ceil(archive.stat().st_size / size), "Unexpected multipart layout")
        parts = []
        with archive.open("rb") as stream:
            for number, url in enumerate(urls, 1):
                payload = stream.read(size)
                tag = ledger.stage(f"02-part-{number:03d}", lambda: upload_part(url, payload, value["allowedStorageHosts"]), lambda row: {"partNumber": number, "bytes": len(payload), "etag": row})
                parts.append((number, tag))
            require(not stream.read(1), "Archive byte count changed during upload")
        require(digest(archive) == value["archive"]["sha256"], "Archive changed during upload")
        ledger.stage("03-complete-multipart", lambda: ensure_completion(storage_request("POST", created["complete_presigned_url"], complete_xml(parts), "application/xml", value["allowedStorageHosts"])), lambda _: {"uploadId": upload_id})
        ledger.stage("04-finalise", lambda: api.call("POST", "/uploads/" + upload_id + "/finalise"), lambda row: {"uploadId": row["id"], "state": row["state"]})
        available = False
        for attempt in range(60):
            state = api.call("GET", "/uploads/" + upload_id)
            durable(ledger.directory / f"processing-{attempt:03d}.json", {"atUtc": utc(), "uploadId": upload_id, "state": state["state"]})
            if state["state"] == "available":
                available = True
                break
            time.sleep(2)
        require(available, "Processing deadline reached; inspect existing upload, never recreate automatically")
        current()
        require(dependency_meaning(api.call("GET", "/mod-file-versions/" + PREVIOUS_VERSION + "/dependencies")) == expected_dependencies, "Existing requirements changed during upload; stop before creating version")
        require(digest(archive) == value["archive"]["sha256"], "Archive changed before version creation")
        body = {"upload_id": upload_id, "name": value["name"], "description": value["_texts"]["description"], "version": VERSION, "file_category": "main", "archive_existing_file": True, "previous_version_id": PREVIOUS_VERSION, "primary_mod_manager_download": True, "allow_mod_manager_download": True, "show_requirements_pop_up": True, "update_mod_version": True}
        created_version = ledger.stage("05-create-version", lambda: api.call("POST", "/mod-files/" + ACTIVE_FILE + "/versions", body), lambda row: {"fileId": ACTIVE_FILE, "versionId": row["version"]["id"]})
        new_id = str(created_version["version"]["id"])
        versions = api.call("GET", "/mod-files/" + ACTIVE_FILE + "/versions")["versions"]
        new = next(row for row in versions if str(row["id"]) == new_id)
        old = next(row for row in versions if str(row["id"]) == PREVIOUS_VERSION)
        durable(ledger.directory / "version-readback.json", {"new": new, "previous": old})
        require(new["version"] == VERSION and new["category"] == "main" and new["is_primary"] is True and new["supports_mod_managers"] is True, "Version readback does not confirm Main/primary/manager downloads")
        require(old["version"] == "0.9.0" and old["category"] == "archived", "Previous0.9.0 not preserved as archived rollback")
        inherited = api.call("GET", "/mod-file-versions/" + new_id + "/dependencies")
        durable(ledger.directory / "new-dependencies.json", inherited)
        require(dependency_meaning(inherited) == expected_dependencies, "New requirements were not inherited identically; correct explicitly before announcing release")
        require(not DUPLICATE_VERSIONS.intersection(api.changelogs()), "A changelog appeared before the one permitted append")
        changelog = ledger.stage("06-add-changelog", lambda: api.call("POST", "/mods/" + GLOBAL_MOD + "/changelogs", {"version": VERSION, "changelog": value["_texts"]["changelog"]}),
            lambda row: {"version": row["version"], "changelogSha256": hashlib.sha256(row["changelog"].encode()).hexdigest()})
        require(changelog["version"] == VERSION and changelog["changelog"].strip() == value["_texts"]["changelog"], "Changelog append receipt differs")
        mod = api.call("GET", "/mods/" + GLOBAL_MOD)
        require(mod["description"].strip() == value["_texts"]["baselineModDescription"], "Description preimage changed before patch")
        ledger.stage("07-patch-description", lambda: api.call("PATCH", "/mods/" + GLOBAL_MOD, {"description": value["_texts"]["modDescription"]}), lambda _: {"descriptionSha256": value["modDescription"]["sha256"], "onlyDescriptionFieldSent": True})
        mod = api.call("GET", "/mods/" + GLOBAL_MOD)
        require(mod["description"].strip() == value["_texts"]["modDescription"] and mod["version"] == VERSION, "Description/version readback differs")
        actual_lines = [line.strip() for entry in api.changelogs().get(VERSION, []) for line in entry.splitlines() if line.strip()]
        expected_lines = [line.strip() for line in value["_texts"]["changelog"].splitlines() if line.strip()]
        require(actual_lines == expected_lines, "Changelog readback differs; never append again")
        require(dependency_meaning(api.call("GET", "/mod-file-versions/" + new_id + "/dependencies")) == expected_dependencies, "Requirements changed during publication")
        durable(ledger.directory / "publication-readback.json", {"descriptionSha256": hashlib.sha256(mod["description"].strip().encode()).hexdigest(), "changelogLines": actual_lines, "requirementsPreserved": True, "descriptionMatches": True})
        durable(ledger.directory / "upload-result.json", {"atUtc": utc(), "uploaded": True, "fileId": ACTIVE_FILE, "versionId": new_id, "gameScopedVersionId": new["game_scoped_id"], "archiveSha256": value["archive"]["sha256"], "sourceCommit": value["sourceCommit"], "requirementsPreserved": True, "rollbackArchived": True, "securityScanStatus": new.get("security_scan_status"), "publicDownloadReady": new.get("security_scan_status") == "cleared", "changelogAppendedOnce": True, "descriptionReadbackMatched": True})
    except BaseException as error:
        durable(ledger.directory / "uncertain-stop.json", {"atUtc": utc(), "complete": False, "errorType": type(error).__name__, "reason": str(error) if isinstance(error, SafeStop) else "Details omitted to protect credential/signed URLs", "doNotReplay": True})
        raise SafeStop("One-use attempt stopped; inspect durable receipts. Do not replay.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reviewed-proposal-sha256")
    args = parser.parse_args()
    value, acceptance = proposal(args.proposal)
    if args.apply:
        require(args.reviewed_proposal_sha256 == digest(args.proposal), "Exact reviewed proposal hash required")
        publish(value, acceptance, args.proposal)
    else:
        print(json.dumps({"networkUsed": False, "publicationReady": value["publicationReady"], "fullReleaseAccepted": acceptance.get("fullReleaseAccepted", False), "proposalSha256": digest(args.proposal), "activeFileId": ACTIVE_FILE, "previousVersionId": PREVIOUS_VERSION, "archiveSha256": value["archive"]["sha256"], "receiptDirectory": value["receiptDirectory"], "changelogMode": value["changelog"]["mode"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        if isinstance(error, (SystemExit, KeyboardInterrupt)):
            raise
        print(json.dumps({"stopped": True, "errorType": type(error).__name__, "reason": str(error) if isinstance(error, SafeStop) else "Details omitted to protect credential/signed URLs"}), file=sys.stderr)
        raise SystemExit(1) from None
