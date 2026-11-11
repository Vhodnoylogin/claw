"""One manually dispatched CLAW 0.9 upload of an already accepted public asset.

Without --apply this only validates authored pins and publication text. Generated
acceptance/proposal/raw dependency snapshots belong in RUNNER_TEMP, never Git.
"""
from pathlib import Path
from urllib import request
from urllib.parse import urlparse
import argparse
import hashlib
import json
import os
import re
import sys

import nexus_upload_once as upload


ROOT = Path(__file__).resolve().parents[4]


def checked_pin(path, reviewed_sha=None):
    if reviewed_sha is not None:
        upload.require(upload.digest(path) == reviewed_sha, "Reviewed package pin changed")
    pin = upload.read(path)
    upload.require(pin["schemaVersion"] == 1 and pin["game"] == upload.GAME and
                   pin["globalModId"] == upload.GLOBAL_MOD and pin["activeFileId"] == upload.ACTIVE_FILE and
                   pin["previousVersionId"] == upload.PREVIOUS_VERSION and
                   pin["scopedPreviousVersionId"] == upload.SCOPED_PREVIOUS and pin["version"] == upload.VERSION,
                   "Unexpected fixed CLAW release target")
    upload.require(pin["sourceCommit"] == "b6f65b5160efbd373ac35bd286810f8b3f805965" and
                   pin["archive"]["sha256"] == "f7ae8b52877680eafd3ef9c5c1f3bf1cdf94605e9a69d6d3acabaf2093adcbf8" and
                   pin["archive"]["bytes"] == 14420086 and pin["releaseDll"]["sha256"] ==
                   "51841ddca157cd6917433fc6d4c0dbc1c0362023cb7def0386f9aa47cadf6182", "Accepted package/DLL/source identity changed")
    upload.require(pin["requirements"]["groups"] == 8 and pin["requirements"]["dlcGroups"] == 0 and
                   re.fullmatch(r"[a-f0-9]{64}", pin["requirements"]["meaningSha256"]), "Reviewed requirement fingerprint absent")
    evidence = pin["acceptedEvidence"]
    upload.require(evidence["fullReleaseAccepted"] is True and [row["id"] for row in evidence["runs"]] ==
                   ["20261111-170411-6e5863", "20261111-170720-f10b97"] and
                   all(row["result"] == "passed" and row["restored"] is True for row in evidence["runs"]),
                   "Previous installed-game acceptance unavailable")
    for key in ("description", "changelog"):
        relative = Path(pin[key]["path"])
        source = (ROOT / relative).resolve()
        upload.require(not relative.is_absolute() and source.is_relative_to(ROOT), "Publication source escapes repository")
        payload = source.read_bytes()
        if key == "changelog":
            normalized = payload.replace(b"\r\n", b"\n")
            upload.require(hashlib.sha256(normalized).hexdigest() == pin[key]["sourceLfSha256"] and
                           hashlib.sha256(normalized.replace(b"\n", b"\r\n")).hexdigest() == pin[key]["sha256"] and
                           pin[key]["mode"] == "edit-existing-in-ui", "Approved changelog text changed")
        else:
            upload.require(hashlib.sha256(payload).hexdigest() == pin[key]["sha256"], "Approved description changed")
    return pin


def workflow_environment(env):
    upload.require(env.get("GITHUB_REPOSITORY") == "Vhodnoylogin/claw" and
                   env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and env.get("GITHUB_REF") == "refs/heads/main" and
                   env.get("GITHUB_RUN_ATTEMPT") == "1" and env.get("GITHUB_RUN_NUMBER") == "1" and
                   re.fullmatch(r"\d+", env.get("GITHUB_RUN_ID", "")) and env.get("RUNNER_TEMP"),
                   "Only the first manual main-branch workflow attempt is admitted")
    return Path(env["RUNNER_TEMP"]).resolve() / ("claw-nexus-090-" + env["GITHUB_RUN_ID"])


class PublicAssetRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        upload.require(parsed.scheme == "https" and parsed.username is None and parsed.password is None and
                       type(parsed.hostname) is str and
                       (parsed.hostname == "github.com" or parsed.hostname.endswith(".githubusercontent.com")),
                       "Public asset redirected outside reviewed GitHub hosts")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(pin, directory):
    asset = pin["archive"]
    upload.require(asset["url"] == "https://github.com/Vhodnoylogin/claw/releases/download/claw/0.9.0-r3/CLAW.-.Customizable.Lycanthrope.Appearance.and.Weight.zip",
                   "Unexpected public release asset URL")
    filename = asset["filename"]
    upload.require(type(filename) is str and Path(filename).name == filename and
                   re.fullmatch(r"[a-zA-Z0-9 _'().-]+\.zip", filename) and not filename.startswith("."),
                   "Unsafe release archive basename")
    archive = directory / filename
    opener = request.build_opener(PublicAssetRedirect())
    with opener.open(asset["url"], timeout=60) as response, archive.open("xb") as stream:
        count = 0
        while chunk := response.read(1024 * 1024):
            count += len(chunk)
            upload.require(count <= asset["bytes"], "Public asset exceeds accepted byte count")
            stream.write(chunk)
    upload.require(count == asset["bytes"] and upload.digest(archive) == asset["sha256"], "Downloaded release asset hash/size mismatch")
    return archive


def run(pin_path, reviewed_sha):
    pin = checked_pin(pin_path, reviewed_sha)
    directory = workflow_environment(os.environ)
    directory.mkdir(exist_ok=False)  # A second attempt never reuses a mutation ledger.
    upload.durable(directory / "run-intent.json", {"pinSha256": reviewed_sha, "policy": "One manual job; no mutation replay"})
    try:
        archive = download(pin, directory)
        # Preserve the approved CRLF digest independently of checkout line endings.
        changelog = directory / "approved-changelog.txt"
        changelog.write_bytes((ROOT / pin["changelog"]["path"]).read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
        acceptance = {"schemaVersion": 1, "fullReleaseAccepted": True, "sourceCommit": pin["sourceCommit"],
                      "releaseArchive": pin["archive"], "releaseDll": pin["releaseDll"],
                      "runs": pin["acceptedEvidence"]["runs"], "scope": pin["acceptedEvidence"]["scope"]}
        acceptance_path = directory / "accepted-package.json"
        upload.durable(acceptance_path, acceptance)
        # Read the key only after the exact public artifact and authored text pins
        # pass. API credentials are never sent by the public/storage transports.
        api = upload.Api()
        dependencies = api.call("GET", "/mod-file-versions/" + upload.PREVIOUS_VERSION + "/dependencies")
        meaning = upload.dependency_meaning(dependencies)
        upload.require(len(meaning["ranges"]) == pin["requirements"]["groups"] and
                       len(meaning["dlc"]) == pin["requirements"]["dlcGroups"] and
                       hashlib.sha256(upload.canonical(meaning).encode()).hexdigest() == pin["requirements"]["meaningSha256"],
                       "Eight reviewed requirement groups changed; no upload permitted")
        requirements_path = directory / "previous-dependencies.json"
        upload.durable(requirements_path, dependencies)
        value = {key: pin[key] for key in ("schemaVersion", "game", "globalModId", "activeFileId", "previousVersionId",
                                          "scopedPreviousVersionId", "version", "name", "sourceCommit", "allowedStorageHosts")}
        value.update(publicationReady=True, receiptDirectory=str(directory / "attempt"),
                     archive={**pin["archive"], "path": str(archive)},
                     description={**pin["description"], "path": str(ROOT / pin["description"]["path"])},
                     changelog={**pin["changelog"], "path": str(changelog)},
                     acceptance={"path": str(acceptance_path), "sha256": upload.digest(acceptance_path)},
                     requirementsSnapshot={"path": str(requirements_path), "sha256": upload.digest(requirements_path)})
        proposal_path = directory / "proposal.json"
        upload.durable(proposal_path, value)
        value, acceptance = upload.proposal(proposal_path)
        upload.publish(value, acceptance, proposal_path)
        result = upload.read(directory / "attempt/upload-result.json")
        upload.durable(directory / "run-summary.json", {"uploaded": True, "fileId": result["fileId"],
            "versionId": result["versionId"], "archiveSha256": result["archiveSha256"],
            "requirementsPreserved": result["requirementsPreserved"], "publicDownloadReady": result["publicDownloadReady"],
            "changelogAppended": False, "temporarySecretRemovalRequired": True})
    except BaseException as error:
        upload.durable(directory / "run-summary.json", {"uploaded": False, "doNotReplay": True,
            "errorType": type(error).__name__, "reason": str(error) if isinstance(error, upload.SafeStop) else "Sensitive transport details omitted",
            "temporarySecretRemovalRequired": True})
        raise upload.SafeStop("One-use remote attempt stopped; inspect sanitized receipts without replay") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--reviewed-pin-sha256")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.apply:
        upload.require(args.reviewed_pin_sha256 is not None, "Explicit reviewed pin hash required")
        run(args.pin, args.reviewed_pin_sha256)
    else:
        pin = checked_pin(args.pin)
        print(json.dumps({"networkUsed": False, "credentialRead": False, "archiveSha256": pin["archive"]["sha256"],
                          "pinSha256": upload.digest(args.pin), "requirementGroups": pin["requirements"]["groups"]}, indent=2))


if __name__ == "__main__":
    try:
        main()
    except upload.SafeStop as error:
        print(json.dumps({"stopped": True, "reason": str(error)}), file=sys.stderr)
        raise SystemExit(1) from None
