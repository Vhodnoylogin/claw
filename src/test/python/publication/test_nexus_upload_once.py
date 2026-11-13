"""Offline fault-injection checks. All API/storage calls are fakes."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json
import hashlib
import zipfile
import tempfile
import unittest

import sys
PUBLICATION=Path(__file__).resolve().parents[3]/'main/python/publication'
sys.path.insert(0,str(PUBLICATION))
import nexus_upload_once as helper
import run_nexus_upload_once as runner

DEPENDENCIES = {"dependency_definitions": [{"id": "definition-old", "ranges": [{"id": "range-old", "target_mod_file": {"id": "requirement-file"}, "min_version": {"id": "minimum-version"}, "max_version": None}]}], "dlc_dependency_definitions": []}
PREVIOUS = {"id": helper.PREVIOUS_VERSION, "file": {"id": helper.ACTIVE_FILE}, "version": "0.9.0", "category": "main", "is_primary": True, "security_scan_status": "cleared"}
SECRET = "SIGNED-URL-SHOULD-NEVER-BE-RECORDED"


class FakeApi:
    def __init__(self, mismatch=False):
        self.requests = []
        self.created = False
        self.mismatch = mismatch
        self.changelog = None
        self.description = 'baseline public description'

    def changelogs(self):
        return {helper.VERSION: self.changelog.splitlines()} if self.changelog is not None else {}

    def call(self, method, route, body=None):
        self.requests.append((method, route, body))
        if method == "GET":
            if route.startswith("/games/"):
                return deepcopy(PREVIOUS)
            if route == "/mod-files/" + helper.ACTIVE_FILE:
                return {"id": helper.ACTIVE_FILE, "name": helper.DISPLAY_NAME, "is_active": True}
            if route == '/mods/'+helper.GLOBAL_MOD+'/files':
                return {'mod_files':[{'id':helper.ACTIVE_FILE}]}
            if route == '/mods/'+helper.GLOBAL_MOD:
                return {'id':helper.GLOBAL_MOD,'version':helper.VERSION if self.created else '0.9.0','description':self.description}
            if route.endswith("/versions"):
                old = deepcopy(PREVIOUS)
                if self.created:
                    old["category"] = "archived"
                    return {"versions": [old, {"id": "new-version", "game_scoped_id": "new-scoped", "version": helper.VERSION, "category": "main", "is_primary": True, "supports_mod_managers": True, "security_scan_status": "pending"}]}
                return {"versions": [old]}
            if route.endswith("/dependencies"):
                if self.mismatch and "new-version" in route:
                    return {"dependency_definitions": [], "dlc_dependency_definitions": []}
                return deepcopy(DEPENDENCIES)
            if route == "/uploads/" + helper.OLD_UPLOAD_ID:
                return {"id":helper.OLD_UPLOAD_ID,"state":"created"}
            if route.startswith("/uploads/"):
                return {"id": "upload-id", "state": "available"}
        if method == "POST":
            if route == '/mods/'+helper.GLOBAL_MOD+'/changelogs':
                assert self.changelog is None
                self.changelog = body['changelog']
                return {'version':helper.VERSION,'changelog':self.changelog}
            if route == "/uploads/multipart":
                return {"id": "upload-id", "part_presigned_urls": ["https://reviewed.example/part?signature=" + SECRET], "complete_presigned_url": "https://reviewed.example/complete?signature=" + SECRET, "part_size_bytes": 50_000_000}
            if route.endswith("/finalise"):
                return {"id": "upload-id", "state": "available"}
            if route == "/mod-files/" + helper.ACTIVE_FILE + "/versions":
                assert body["archive_existing_file"] and body["previous_version_id"] == helper.PREVIOUS_VERSION
                assert body["primary_mod_manager_download"] and body["allow_mod_manager_download"]
                self.created = True
                return {"file": {"id": helper.ACTIVE_FILE}, "version": {"id": "new-version"}}
        if method == 'PATCH' and route == '/mods/'+helper.GLOBAL_MOD:
            assert set(body)=={'description'}
            self.description=body['description']
            return None
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
        self.value = {"publicationReady": True, "receiptDirectory": str(self.root / "attempt"), "archive": {"path": str(self.archive), "sha256": helper.digest(self.archive)}, "requirementsSnapshot": {"path": str(self.requirements)}, "description": {"path": str(self.description)}, "modDescription": {'sha256':'reviewed-source-hash'}, "name": helper.DISPLAY_NAME, "sourceCommit":"a"*40, "allowedStorageHosts": ["reviewed.example"], '_texts':{'description':'Runtime file description','baselineModDescription':'baseline public description','modDescription':'new reviewed public description','changelog':'One change\nSecond change'}}

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
            helper.ensure_current(PREVIOUS, {"id": helper.ACTIVE_FILE, 'name':helper.DISPLAY_NAME, "is_active": True}, {"versions": [PREVIOUS, {"version": helper.VERSION}]})

    def test_http200_storage_error_body_is_not_success(self):
        with self.assertRaises(helper.SafeStop):
            helper.ensure_completion(SimpleNamespace(content=b"<Error><Code>InvalidPart</Code></Error>"))

    def test_unreviewed_storage_host_never_requests_network(self):
        with patch.object(helper,"transport", side_effect=AssertionError("network must not be called")):
            with self.assertRaises(helper.SafeStop):
                helper.storage_request("PUT", "https://unreviewed.example/part", b"a", "application/octet-stream", ["reviewed.example"])

    def test_blocked_acceptance_never_reads_credentials(self):
        self.value["publicationReady"] = False
        with patch.object(helper, "Api", side_effect=AssertionError("credential read forbidden")):
            with self.assertRaises(helper.SafeStop):
                helper.publish(self.value, {"fullReleaseAccepted": False}, self.proposal)

    def test_success_uses_current_chain_once_preserves_dependencies_and_publishes_text_once(self):
        api = FakeApi()
        with patch.object(helper, "Api", return_value=api), patch.object(helper, "storage_request", side_effect=self.fake_storage):
            helper.publish(self.value, {"fullReleaseAccepted": True}, self.proposal)
        posts = [r[1] for r in api.requests if r[0] == "POST"]
        self.assertEqual(posts, ["/uploads/multipart", "/uploads/upload-id/finalise", "/mod-files/8342508/versions", '/mods/'+helper.GLOBAL_MOD+'/changelogs'])
        self.assertEqual([(m,r) for m,r,b in api.requests if m=='PATCH'], [('PATCH','/mods/'+helper.GLOBAL_MOD)])
        self.assertFalse(any(m!='GET' and r.endswith('/dependencies') for m,r,b in api.requests))
        result = helper.read(Path(self.value["receiptDirectory"]) / "upload-result.json")
        self.assertTrue(result["requirementsPreserved"])
        self.assertFalse(result["publicDownloadReady"])
        self.assertTrue(result["changelogAppendedOnce"])
        self.assertTrue(result['descriptionReadbackMatched'])
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

    def test_existing_changelog_refuses_before_any_mutation(self):
        api=FakeApi();api.changelog='existing entry'
        with patch.object(helper,'Api',return_value=api), self.assertRaises(helper.SafeStop):
            helper.publish(self.value,{'fullReleaseAccepted':True},self.proposal)
        self.assertFalse(any(m!='GET' for m,r,b in api.requests))
        self.assertFalse(Path(self.value['receiptDirectory']).exists())

    def test_unknown_description_patch_preserves_intent_and_never_replays(self):
        api=FakeApi();original=api.call
        def fail(method,route,body=None):
            if method=='PATCH':
                api.requests.append((method,route,body));raise RuntimeError(SECRET)
            return original(method,route,body)
        with patch.object(helper,'Api',return_value=api),patch.object(api,'call',side_effect=fail),patch.object(helper,'storage_request',side_effect=self.fake_storage):
            with self.assertRaises(helper.SafeStop):helper.publish(self.value,{'fullReleaseAccepted':True},self.proposal)
        receipts=Path(self.value['receiptDirectory'])
        self.assertTrue((receipts/'07-patch-description.intent.json').exists())
        self.assertFalse((receipts/'07-patch-description.receipt.json').exists())
        self.assertEqual(sum(m=='PATCH' for m,r,b in api.requests),1)
        self.assertNotIn(SECRET,''.join(p.read_text() for p in receipts.glob('*.json')))
        with patch.object(helper,'Api',side_effect=AssertionError('no replay')):
            with self.assertRaises(helper.SafeStop):helper.publish(self.value,{'fullReleaseAccepted':True},self.proposal)

    def test_description_patch204_does_not_try_json(self):
        api=helper.Api.__new__(helper.Api)
        api.headers={}
        response=SimpleNamespace(status_code=204,json=lambda:(_ for _ in ()).throw(AssertionError('no JSON body')))
        with patch.object(helper,'transport',return_value=response):
            self.assertIsNone(api.call('PATCH','/mods/'+helper.GLOBAL_MOD,{'description':'reviewed'}))


    def test_old_available_upload_refuses_before_mutation(self):
        api=FakeApi(); original=api.call
        def changed(method,route,body=None):
            if route=='/uploads/'+helper.OLD_UPLOAD_ID:return {'id':helper.OLD_UPLOAD_ID,'state':'available'}
            return original(method,route,body)
        with patch.object(helper,'Api',return_value=api),patch.object(api,'call',side_effect=changed),self.assertRaises(helper.SafeStop):
            helper.publish(self.value,{'fullReleaseAccepted':True},self.proposal)
        self.assertFalse(any(m!='GET' for m,r,b in api.requests))
        self.assertFalse(Path(self.value['receiptDirectory']).exists())

    def test_storage_has_no_nexus_credential_header(self):
        captured=[]
        def fake(method,url,body,headers,timeout):
            captured.append(headers);return helper.Response(200,{},b'')
        with patch.object(helper,'transport',side_effect=fake):
            helper.storage_request('PUT','https://reviewed.example/part?signature='+SECRET,b'a','application/octet-stream',['reviewed.example'])
        self.assertEqual(captured,[{'Content-Type':'application/octet-stream','Content-Length':'1'}])

    def test_portable_proposal_binds_actual_local_bytes_and_refuses_tampered_acceptance_or_ledger(self):
        archive=self.root/'CLAW - Customizable Lycanthrope Appearance and Weight.zip'
        dll=b'MZoffline exact-byte identity fixture'
        with zipfile.ZipFile(archive,'w') as package:package.writestr('10 Native/SKSE/Plugins/CLAWDistribution.dll',dll)
        def pinned(path):return {'path':str(path),'sha256':helper.digest(path)}
        acceptance=self.root/'acceptance.json'
        acceptance.write_text(json.dumps({'fullReleaseAccepted':True,'sourceCommit':helper.SOURCE_COMMIT,'releaseArchive':{'sha256':helper.digest(archive)},'releaseDll':{'sha256':hashlib.sha256(dll).hexdigest()}}))
        value={'schemaVersion':1,'game':helper.GAME,'globalModId':helper.GLOBAL_MOD,'activeFileId':helper.ACTIVE_FILE,'previousVersionId':helper.PREVIOUS_VERSION,'scopedPreviousVersionId':helper.SCOPED_PREVIOUS,'version':helper.VERSION,'name':helper.DISPLAY_NAME,'sourceCommit':helper.SOURCE_COMMIT,'helperSha256':helper.digest(helper.__file__),'archive':{**pinned(archive),'bytes':archive.stat().st_size},'acceptance':pinned(acceptance),'description':pinned(self.description),'modDescription':pinned(self.description),'baselineModDescription':pinned(self.description),'changelog':{**pinned(self.description),'mode':'append-once'},'requirementsSnapshot':pinned(self.requirements),'receiptDirectory':str(self.root/'attempt'),'allowedStorageHosts':['reviewed.example']}
        self.proposal.write_text(json.dumps(value))
        with patch.object(helper,'Api',side_effect=AssertionError('offline only')):
            self.assertEqual(helper.proposal(self.proposal)[0]['archive']['sha256'],helper.digest(archive))
            value['acceptance']['sha256']='0'*64;self.proposal.write_text(json.dumps(value))
            with self.assertRaises(helper.SafeStop):helper.proposal(self.proposal)
            value['acceptance']=pinned(acceptance);self.proposal.write_text(json.dumps(value));(self.root/'attempt').mkdir()
            with self.assertRaises(helper.SafeStop):helper.proposal(self.proposal)

class RunnerTests(unittest.TestCase):
    PIN=runner.ROOT/'src/main/resources/publication/nexus/0.10.0/verified-package.json'

    def test_real_authored_pin_is_validated_offline_with_explicit_admission(self):
        with patch.object(helper,'Api',side_effect=AssertionError('no credentials')),patch.object(helper,'transport',side_effect=AssertionError('no network')):
            pin=runner.checked_pin(self.PIN,helper.digest(self.PIN))
        self.assertIs(type(pin['remoteRecoveryReady']), bool)

    def test_disabled_apply_stops_before_environment_git_download_or_credential(self):
        with tempfile.TemporaryDirectory() as temporary:
            disabled = helper.read(self.PIN)
            disabled['remoteRecoveryReady'] = False
            fixture = Path(temporary) / 'disabled-pin.json'
            fixture.write_text(json.dumps(disabled), encoding='utf-8')
            with patch.object(runner,'workflow_environment',side_effect=AssertionError('no environment')),patch.object(runner,'verify_committed_source',side_effect=AssertionError('no git')),patch.object(runner,'download',side_effect=AssertionError('no network')),patch.object(helper,'Api',side_effect=AssertionError('no credential')):
                with self.assertRaisesRegex(helper.SafeStop,'remains disabled'):
                    runner.run(fixture, helper.digest(fixture))

    def test_only_first_manual_trusted_main_workflow_admitted(self):
        env={'GITHUB_REPOSITORY':'Vhodnoylogin/claw','GITHUB_EVENT_NAME':'workflow_dispatch','GITHUB_REF':'refs/heads/main','GITHUB_RUN_ATTEMPT':'1','GITHUB_RUN_NUMBER':'1','GITHUB_RUN_ID':'123','RUNNER_TEMP':str(Path.cwd())}
        self.assertEqual(runner.workflow_environment(env).name,'claw-nexus-010-recovery-123')
        for key,value in [('GITHUB_REPOSITORY','elsewhere/claw'),('GITHUB_EVENT_NAME','push'),('GITHUB_REF','refs/heads/feature'),('GITHUB_RUN_ATTEMPT','2'),('GITHUB_RUN_NUMBER','2'),('GITHUB_RUN_ID','../evil')]:
            with self.subTest(key=key),self.assertRaises(helper.SafeStop):runner.workflow_environment({**env,key:value})

    def test_reviewed_pin_and_runner_source_hashes_are_not_optional(self):
        with self.assertRaises(helper.SafeStop):runner.checked_pin(self.PIN,'0'*64)
        with patch.object(helper,'digest',return_value='0'*64),self.assertRaises(helper.SafeStop):runner.checked_pin(self.PIN)

    def test_public_redirect_rejects_signed_storage_and_http(self):
        handler=runner.PublicAssetRedirect()
        for target in ['http://github.com/file','https://unreviewed.example/file','https://user@github.com/file']:
            with self.assertRaises(helper.SafeStop):handler.redirect_request(None,None,302,'',{},target)

if __name__=='__main__':unittest.main()
