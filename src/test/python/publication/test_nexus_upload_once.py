"""Offline fault-injection checks. All API/storage calls are fakes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import tempfile
import unittest
import hashlib
import shutil
import zipfile

import sys
PUBLICATION = Path(__file__).resolve().parents[4] / "src/main/python/publication"
sys.path.insert(0, str(PUBLICATION))
try:
    import nexus_upload_once as helper
    import run_nexus_upload_once as runner
finally:
    sys.path.remove(str(PUBLICATION))

DEPENDENCIES = {"dependency_definitions": [{"id": "definition-old", "ranges": [{"id": "range-old", "target_mod_file": {"id": "requirement-file"}, "min_version": {"id": "minimum-version"}, "max_version": None}]}], "dlc_dependency_definitions": []}
PREVIOUS = {"id": helper.PREVIOUS_VERSION, "file": {"id": helper.ACTIVE_FILE}, "version": "0.8.0", "category": "main"}
SECRET = "SIGNED-URL-SHOULD-NEVER-BE-RECORDED"


class FakeApi:
    def __init__(self, mismatch=False):
        self.requests = []
        self.created = False
        self.mismatch = mismatch

    def call(self, method, route, body=None):
        self.requests.append((method, route, body))
        if method == "GET":
            if route.startswith("/games/"):
                return deepcopy(PREVIOUS)
            if route == "/mod-files/" + helper.ACTIVE_FILE:
                return {"id": helper.ACTIVE_FILE, "is_active": True}
            if route.endswith("/versions"):
                old = deepcopy(PREVIOUS)
                if self.created:
                    old["category"] = "archived"
                    return {"versions": [old, {"id": "new-version", "game_scoped_id": "new-scoped", "version": "0.9.0", "category": "main", "is_primary": True, "supports_mod_managers": True, "security_scan_status": "pending"}]}
                return {"versions": [old]}
            if route.endswith("/dependencies"):
                if self.mismatch and "new-version" in route:
                    return {"dependency_definitions": [], "dlc_dependency_definitions": []}
                return deepcopy(DEPENDENCIES)
            if route.startswith("/uploads/"):
                return {"id": "upload-id", "state": "available"}
        if method == "POST":
            if route == "/uploads/multipart":
                return {"id": "upload-id", "part_presigned_urls": ["https://reviewed.example/part?signature=" + SECRET], "complete_presigned_url": "https://reviewed.example/complete?signature=" + SECRET, "part_size_bytes": 50_000_000}
            if route.endswith("/finalise"):
                return {"id": "upload-id", "state": "available"}
            if route == "/mod-files/" + helper.ACTIVE_FILE + "/versions":
                assert body["archive_existing_file"] and body["previous_version_id"] == helper.PREVIOUS_VERSION
                assert body["primary_mod_manager_download"] and body["allow_mod_manager_download"]
                self.created = True
                return {"file": {"id": helper.ACTIVE_FILE}, "version": {"id": "new-version"}}
        raise AssertionError((method, route))


class OfflineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = self.root / "runtime.zip"
        self.archive.write_bytes(b"exact reviewed fake archive")
        self.requirements = self.root / "requirements.json"
        self.requirements.write_text(json.dumps(DEPENDENCIES))
        self.description = self.root / "description.txt"
        self.description.write_text("Runtime file description")
        self.proposal = self.root / "proposal.json"
        self.proposal.write_text("{}")
        self.value = {"publicationReady": True, "receiptDirectory": str(self.root / "attempt"), "archive": {"path": str(self.archive), "sha256": helper.digest(self.archive)}, "requirementsSnapshot": {"path": str(self.requirements)}, "description": {"path": str(self.description)}, "name": "CLAW", "allowedStorageHosts": ["reviewed.example"]}

    def tearDown(self):
        self.temp.cleanup()

    def fake_storage(self, method, url, payload, content_type, hosts):
        return SimpleNamespace(headers={"ETag": '"ABC123"'}, content=b"<CompleteMultipartUploadResult/>")

    def test_requirement_ids_can_change_without_changing_meaning(self):
        other = deepcopy(DEPENDENCIES)
        other["dependency_definitions"][0]["id"] = "new-definition"
        other["dependency_definitions"][0]["ranges"][0]["id"] = "new-range"
        self.assertEqual(helper.dependency_meaning(other), helper.dependency_meaning(DEPENDENCIES))

    def test_requirement_bounds_are_not_ignored(self):
        other = deepcopy(DEPENDENCIES)
        other["dependency_definitions"][0]["ranges"][0]["min_version"]["id"] = "different-version"
        self.assertNotEqual(helper.dependency_meaning(other), helper.dependency_meaning(DEPENDENCIES))

    def test_old_inactive_chain_rejected(self):
        file = {"id": "8126004", "is_active": False}
        with self.assertRaises(helper.SafeStop):
            helper.ensure_current(PREVIOUS, file, {"versions": [PREVIOUS]})

    def test_duplicate_version_rejected(self):
        with self.assertRaises(helper.SafeStop):
            helper.ensure_current(PREVIOUS, {"id": helper.ACTIVE_FILE, "is_active": True}, {"versions": [PREVIOUS, {"version": "0.9.0"}]})

    def test_http200_storage_error_body_is_not_success(self):
        with self.assertRaises(helper.SafeStop):
            helper.ensure_completion(SimpleNamespace(content=b"<Error><Code>InvalidPart</Code></Error>"))

    def test_unreviewed_storage_host_never_requests_network(self):
        with patch.object(helper, "transport", side_effect=AssertionError("network must not be called")):
            with self.assertRaises(helper.SafeStop):
                helper.storage_request("PUT", "https://unreviewed.example/part", b"a", "application/octet-stream", ["reviewed.example"])

    def test_blocked_acceptance_never_reads_credentials(self):
        self.value["publicationReady"] = False
        with patch.object(helper, "Api", side_effect=AssertionError("credential read forbidden")):
            with self.assertRaises(helper.SafeStop):
                helper.publish(self.value, {"fullReleaseAccepted": False}, self.proposal)

    def test_success_uses_active_chain_once_preserves_dependencies_skips_changelog(self):
        api = FakeApi()
        with patch.object(helper, "Api", return_value=api), patch.object(helper, "storage_request", side_effect=self.fake_storage):
            helper.publish(self.value, {"fullReleaseAccepted": True}, self.proposal)
        posts = [r[1] for r in api.requests if r[0] == "POST"]
        self.assertEqual(posts, ["/uploads/multipart", "/uploads/upload-id/finalise", "/mod-files/8342508/versions"])
        result = helper.read(Path(self.value["receiptDirectory"]) / "upload-result.json")
        self.assertTrue(result["requirementsPreserved"])
        self.assertFalse(result["publicDownloadReady"])
        self.assertFalse(result["changelogAppended"])
        text = "".join(path.read_text() for path in Path(self.value["receiptDirectory"]).glob("*.json"))
        self.assertNotIn(SECRET, text)

    def test_ambiguous_part_failure_is_never_retried_or_logged(self):
        api = FakeApi()
        calls = []
        def fail(*args):
            calls.append(args)
            raise RuntimeError(SECRET)
        with patch.object(helper, "Api", return_value=api), patch.object(helper, "storage_request", side_effect=fail):
            with self.assertRaises(helper.SafeStop):
                helper.publish(self.value, {"fullReleaseAccepted": True}, self.proposal)
        self.assertEqual(len(calls), 1)
        self.assertEqual([r[1] for r in api.requests if r[0] == "POST"], ["/uploads/multipart"])
        receipts = Path(self.value["receiptDirectory"])
        self.assertTrue((receipts / "02-part-001.intent.json").exists())
        self.assertFalse((receipts / "02-part-001.receipt.json").exists())
        self.assertNotIn(SECRET, "".join(p.read_text() for p in receipts.glob("*.json")))
        with patch.object(helper, "Api", side_effect=AssertionError("must not replay")):
            with self.assertRaises(helper.SafeStop):
                helper.publish(self.value, {"fullReleaseAccepted": True}, self.proposal)

    def test_requirement_inheritance_mismatch_stops_after_single_version_creation(self):
        api = FakeApi(mismatch=True)
        with patch.object(helper, "Api", return_value=api), patch.object(helper, "storage_request", side_effect=self.fake_storage):
            with self.assertRaises(helper.SafeStop):
                helper.publish(self.value, {"fullReleaseAccepted": True}, self.proposal)
        self.assertEqual(sum(method == "POST" and route.endswith("/versions") for method, route, body in api.requests), 1)
        receipts = Path(self.value["receiptDirectory"])
        self.assertTrue((receipts / "05-create-version.receipt.json").exists())
        self.assertTrue((receipts / "uncertain-stop.json").exists())
        self.assertFalse((receipts / "upload-result.json").exists())

    def test_another_version_in_the_reviewed_chain_requires_new_review(self):
        with self.assertRaises(helper.SafeStop):
            helper.ensure_current(PREVIOUS, {"id": helper.ACTIVE_FILE, "is_active": True},
                                  {"versions": [PREVIOUS, {"id": "other", "version": "0.8.1"}]})

    def test_and_or_requirement_boundaries_are_not_flattened(self):
        alternatives = deepcopy(DEPENDENCIES)
        alternatives["dependency_definitions"][0]["ranges"] *= 2
        separate = deepcopy(DEPENDENCIES)
        separate["dependency_definitions"] *= 2
        self.assertNotEqual(helper.dependency_meaning(alternatives), helper.dependency_meaning(separate))

    def test_only_first_manual_main_workflow_can_apply(self):
        env = {"GITHUB_REPOSITORY": "Vhodnoylogin/claw", "GITHUB_EVENT_NAME": "workflow_dispatch",
               "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": "1",
               "GITHUB_RUN_ID": "123", "RUNNER_TEMP": str(self.root)}
        self.assertEqual(runner.workflow_environment(env), self.root / "claw-nexus-090-123")
        for key, value in (("GITHUB_REPOSITORY", "foreign/repo"), ("GITHUB_REF", "refs/heads/feature"),
                           ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_RUN_NUMBER", "2")):
            with self.subTest(key=key), self.assertRaises(helper.SafeStop):
                runner.workflow_environment({**env, key: value})

    def test_api_key_is_not_forwarded_to_signed_storage(self):
        calls = []
        def transport(method, url, payload, headers, timeout):
            calls.append((method, url, headers))
            return helper.Response(200, {}, b'{"data":{"id":"file"}}')
        with patch.dict("os.environ", {"NEXUS_API_KEY": SECRET}), patch.object(helper, "transport", side_effect=transport):
            helper.Api().call("GET", "/mod-files/8342508")
            helper.storage_request("PUT", "https://reviewed.example/object?signature=fake", b"a", "application/octet-stream", ["reviewed.example"])
        self.assertEqual(calls[0][2]["apikey"], SECRET)
        self.assertNotIn("apikey", calls[1][2])
        self.assertIsNone(helper.NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://foreign.example"))

    def test_authored_pin_review_uses_no_credentials_or_network(self):
        pin = runner.ROOT / "src/main/resources/publication/nexus/0.9.0/verified-package.json"
        with patch.object(helper, "Api", side_effect=AssertionError("credential read forbidden")):
            value = runner.checked_pin(pin)
        self.assertEqual(value["requirements"]["groups"], 8)
        self.assertEqual(value["archive"]["bytes"], 14420086)

    def test_signed_storage_rejects_user_info_and_plain_http_before_transport(self):
        urls = ["https://:@reviewed.example/part", "https://:password@reviewed.example/part",
                "http://reviewed.example/part", "https://reviewed.example:80/part"]
        with patch.object(helper, "transport", side_effect=AssertionError("transport forbidden")):
            for url in urls:
                with self.subTest(url=url), self.assertRaises(helper.SafeStop):
                    helper.storage_request("PUT", url, b"a", "application/octet-stream", ["reviewed.example"])

    def test_fake_remote_runner_binds_zip_and_temporary_proposal_without_credentials(self):
        dependencies = deepcopy(DEPENDENCIES)
        dependencies["dependency_definitions"] *= 8
        class EightGroupApi(FakeApi):
            def call(self, method, route, body=None):
                if method == "GET" and route.endswith("/dependencies"):
                    self.requests.append((method, route, body))
                    return deepcopy(dependencies)
                return super().call(method, route, body)
        dll = b"synthetic runtime DLL for offline protocol test only"
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("SKSE/Plugins/CLAWDistribution.dll", dll)
        pin = helper.read(runner.ROOT / "src/main/resources/publication/nexus/0.9.0/verified-package.json")
        pin["archive"].update(sha256=helper.digest(self.archive), bytes=self.archive.stat().st_size)
        pin["releaseDll"].update(sha256=hashlib.sha256(dll).hexdigest(), bytes=len(dll))
        pin["requirements"]["meaningSha256"] = hashlib.sha256(helper.canonical(helper.dependency_meaning(dependencies)).encode()).hexdigest()
        env = {"GITHUB_REPOSITORY": "Vhodnoylogin/claw", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main",
               "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_NUMBER": "1", "GITHUB_RUN_ID": "123", "RUNNER_TEMP": str(self.root)}
        def download(value, directory):
            destination = directory / value["archive"]["filename"]
            shutil.copyfile(self.archive, destination)
            return destination
        with patch.dict("os.environ", env), patch.object(runner, "checked_pin", return_value=pin), \
             patch.object(runner, "download", side_effect=download), patch.object(helper, "Api", return_value=EightGroupApi()), \
             patch.object(helper, "storage_request", side_effect=self.fake_storage):
            runner.run(self.proposal, "synthetic-reviewed-pin")
        directory = self.root / "claw-nexus-090-123"
        proposal = helper.read(directory / "proposal.json")
        self.assertEqual(Path(proposal["archive"]["path"]).name, "CLAW - Customizable Lycanthrope Appearance and Weight.zip")
        self.assertEqual(Path(proposal["receiptDirectory"]).parent, directory)
        self.assertEqual(len(helper.read(directory / "previous-dependencies.json")["dependency_definitions"]), 8)
        self.assertTrue(helper.read(directory / "run-summary.json")["uploaded"])


if __name__ == "__main__":
    unittest.main()
