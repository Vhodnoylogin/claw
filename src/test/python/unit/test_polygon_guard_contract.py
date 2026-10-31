"""Pure guard-protocol fixtures, never live state or cleanup authorization.

All paths are inert Windows strings. No fixtures create/read files or invoke the
producer, database, process observer, manager, native game or network.
"""
import copy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/python/build-tools'))
import polygon_guard_contract as guard


def digest(label):
    return hashlib.sha256(label.encode('utf-8')).hexdigest()


def pin(path, label=None):
    return {'path':path, 'sha256':digest(label or path)}


class GuardContractTests(unittest.TestCase):
    def setUp(self):
        self.recovery_id = 'recovery-fixture'
        self.review_pin = pin('C:/Fixture/Workspace/recovery-review.json')
        self.archive_pin = pin('C:/Fixture/Workspace/archive-manifest.json')
        self.review = {'schemaVersion':1,'kind':'diagnostic-preexecution-recovery-reserve',
                       'id':self.recovery_id,'diagnosticId':'diagnostic-fixture','noLaunchAuthority':True,
                       'verifiedBy':'synthetic fixture','reason':'protocol-only, no actual cleanup',
                       'preparedRequestSha256':digest('prepared'),'subjectOrderSha256':digest('subject'),
                       'slotGrantSha256':digest('slot-grant'),
                       'assessment':pin('C:/Fixture/assessment.json'),
                       'installationReceipt':pin('C:/Fixture/installation-receipt.json'),
                       'installHelper':pin('C:/Fixture/install-helper.py'),
                       'installationStarted':pin('C:/Fixture/installation-started.json'),
                       'nativeUiReady':pin('C:/Fixture/native-ui-ready.json'),
                       'ownerAuthorization':{**pin('C:/Fixture/owner-authorization.txt'),
                           'threadId':'thread-fixture','messageId':'message-fixture',
                           'quote':'Synthetic unit fixture; this is not actual cleanup permission.',
                           'verifiedBy':'synthetic fixture','extraBoundReviewData':{'value':1}}}
        self.modlist = 'C:/Fixture/Instance/profiles/Test/modlist.txt'
        self.post, self.disabled, self.pre = (digest(x) for x in ('postimage','disabled','preimage'))
        payload = ['claw-build.json','CLAW.esp','README.md','README.ru.md',
                   'meshes/female_0.nif','meshes/female_1.nif','meshes/male_0.nif','meshes/male_1.nif',
                   'meshes/female.tri','meshes/male.tri','meta.ini']
        self.allowed = [pin('C:/Fixture/Instance/mods/NewName/'+relative) for relative in payload]
        self.allowed += [pin('C:/Fixture/Instance/downloads/fixture.7z'),pin('C:/Fixture/Instance/downloads/fixture.7z.meta')]
        self.expected = {'protocolCommit':'d9d3b72fba2f925180a3aba211cfc045f9f01d5e',
                         'record':{'id':self.recovery_id,'diagnosticId':'diagnostic-fixture','status':'restoring','requestSha256':digest('record')},
                         'reservedReview':{'pin':copy.deepcopy(self.review_pin),'review':copy.deepcopy(self.review)},
                         'implementationPins':[pin('C:/Fixture/Tool/diagnostic_recovery.py'),pin('C:/Fixture/Tool/polygon.py')],
                         'allowedPostimages':copy.deepcopy(self.allowed),
                         'freshModlistBackup':{'path':self.modlist,'backup':'C:/Fixture/Backups/modlist.txt',
                                              'sha256':self.pre,'currentSha256':self.post,'currentlyByteIdentical':False},
                         'profilePins':[{'path':self.modlist,'sha256':self.post},pin('C:/Fixture/Instance/profiles/Other/modlist.txt')],
                         'managedIniPath':'C:/Fixture/Instance/ModOrganizer.ini',
                         'modlistVariants':{'postimage':self.post,'disabled-new-mod':self.disabled,'preimage':self.pre}}

    def query(self, stage='pre-archive'):
        return guard.build_guard_query(self.recovery_id,self.review_pin,stage,
                                       archive=self.archive_pin if stage == 'partial' else None)

    def response(self, stage='pre-archive', present=None, state='postimage'):
        if present is None:
            present = list(range(13))
        profiles = copy.deepcopy(self.expected['profilePins'])
        profiles[0]['sha256'] = self.expected['modlistVariants'][state]
        return {'schemaVersion':1,'kind':'validated-current-restoring-scope',
                'record':copy.deepcopy(self.expected['record']),
                'reservedReview':copy.deepcopy(self.expected['reservedReview']),
                'implementationPins':copy.deepcopy(self.expected['implementationPins']),
                'stage':stage,'stageProof':{'present':[copy.deepcopy(self.allowed[i]) for i in present],
                    'absent':[p['path'] for i,p in enumerate(self.allowed) if i not in present],
                    'modlistState':state,'profilePins':profiles,
                    'managedIniPin':pin(self.expected['managedIniPath'],'current GUI-only observation')},
                'nativeIdleObservation':{'observedAt':1.5,'processes':[{'pid':10,'name':'ModOrganizer.exe'}],
                    'checkedOwners':[{'expected':{'pid':11,'birth':100,'path':'C:/Fixture/worker.exe'},'alive':False,'observedReusedPid':None}],
                    'runtimeStates':[{'state':pin('C:/Fixture/state.json'),'game':None,
                                      'order':{'id':'qualification-fixture'},'done':True,'restored':True}]},
                'allowedPostimages':copy.deepcopy(self.allowed),
                'freshModlistBackup':copy.deepcopy(self.expected['freshModlistBackup']),
                'archiveVerified':stage == 'partial','copyOnly':stage == 'pre-archive',
                'callerMustOwnSessionMutex':True,'mutexOwnershipProvedByGuard':False,
                'newCleanupGranted':False,'launchGranted':False}

    def validate(self, response=None, query=None, expected=None, exit_code=0):
        return guard.validate_guard_response(query if query is not None else self.query(),
                                             response if response is not None else self.response(),
                                             expected if expected is not None else self.expected,exit_code=exit_code)

    def assert_contract_only(self, result):
        self.assertIs(result['responseContractVerified'],True)
        for key in ('liveStateVerified','cleanupGranted','launchGranted','executionSupported'):
            self.assertIs(result[key],False)

    def test_valid_prearchive_contract_never_certifies_live_state_or_mutex(self):
        self.assert_contract_only(self.validate())

    def test_valid_partial_partitions_and_each_known_modlist_state(self):
        for present in ([],[0,2,4,6,8,10,12],list(range(13))):
            for state in ('postimage','disabled-new-mod','preimage'):
                with self.subTest(present=present,state=state):
                    self.assert_contract_only(self.validate(self.response('partial',present,state),self.query('partial')))

    def test_query_uses_exact_stage_archive_and_defensive_pin_copies(self):
        review_before, archive_before = copy.deepcopy(self.review_pin),copy.deepcopy(self.archive_pin)
        query = self.query('partial')
        self.assertEqual(set(query),{'schemaVersion','kind','id','reservedReviewPin','stage','archive'})
        self.assertEqual(query['kind'],'diagnostic-preexecution-restoring-guard')
        self.assertEqual(query['reservedReviewPin'],self.review_pin)
        self.assertEqual(query['archive'],self.archive_pin)
        query['reservedReviewPin']['sha256'] = digest('mutation')
        query['archive']['sha256'] = digest('mutation')
        self.assertEqual(self.review_pin,review_before)
        self.assertEqual(self.archive_pin,archive_before)

    def test_query_refuses_unknown_stage_archive_mismatch_and_unsafe_ids(self):
        cases = [('fixture',self.review_pin,'unknown',None),
                 ('fixture',self.review_pin,'partial',None),
                 ('fixture',self.review_pin,'pre-archive',self.archive_pin),
                 ('../escape',self.review_pin,'pre-archive',None),
                 (True,self.review_pin,'pre-archive',None)]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(ValueError): guard.build_guard_query(*args)

    def test_query_refuses_relative_unc_dot_and_invalid_hash_pins(self):
        for value in (pin('relative.json'),pin('//server/share/review.json'),pin('C:/Fixture/../review.json'),
                      {'path':'C:/Fixture/review.json','sha256':'not-a-hash'}):
            with self.subTest(pin=value), self.assertRaises(ValueError):
                guard.build_guard_query(self.recovery_id,value,'pre-archive')

    def test_exit_code_and_non_object_or_error_response_refused(self):
        for code in (1,-1,False,True,'0',None):
            with self.subTest(exit_code=code), self.assertRaises(ValueError): self.validate(exit_code=code)
        for response in ('not JSON',[],{'error':'producer refused'},None):
            with self.subTest(response=response), self.assertRaises(ValueError):
                guard.validate_guard_response(self.query(),response,self.expected)

    def test_protocol_commit_and_expected_top_level_shape_bound(self):
        for mutate in (lambda d:d.__setitem__('protocolCommit','0'*40),
                       lambda d:d.pop('managedIniPath'),lambda d:d.__setitem__('surprise',True)):
            expected = copy.deepcopy(self.expected);mutate(expected)
            with self.assertRaises(ValueError): self.validate(expected=expected)

    def test_response_top_level_kind_version_and_surprise_fields_bound(self):
        for mutate in (lambda d:d.__setitem__('schemaVersion',True),
                       lambda d:d.__setitem__('kind','validated-cleanup-authorization'),
                       lambda d:d.__setitem__('unexpected',True),lambda d:d.pop('nativeIdleObservation')):
            response = self.response();mutate(response)
            with self.assertRaises(ValueError): self.validate(response)

    def test_record_id_diagnostic_status_and_request_hash_are_bound(self):
        for field in ('id','diagnosticId','status','requestSha256'):
            response = self.response();response['record'][field] = 'different'
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(response)

    def test_review_pin_full_review_and_numeric_types_are_bound(self):
        for mutate in (lambda d:d['reservedReview']['pin'].__setitem__('sha256',digest('other')),
                       lambda d:d['reservedReview']['pin'].__setitem__('path','C:/Fixture/other-review.json'),
                       lambda d:d['reservedReview']['review'].__setitem__('noLaunchAuthority',False),
                       lambda d:d['reservedReview']['review']['ownerAuthorization']['extraBoundReviewData'].__setitem__('value',True)):
            response = self.response();mutate(response)
            with self.assertRaises(ValueError): self.validate(response)

    def test_matching_but_producer_invalid_reserve_review_is_refused(self):
        required = {'schemaVersion','kind','id','diagnosticId','preparedRequestSha256','subjectOrderSha256',
                    'slotGrantSha256','assessment','installationReceipt','installHelper','installationStarted',
                    'nativeUiReady','ownerAuthorization','noLaunchAuthority','verifiedBy','reason'}
        self.assertEqual(set(self.review),required)
        cases = []
        for field in sorted(required):
            malformed = copy.deepcopy(self.review);malformed.pop(field)
            cases.append(('missing '+field,malformed))
        mutations = [
            ('extra top-level field',lambda d:d.__setitem__('extra',True)),
            ('boolean schema version',lambda d:d.__setitem__('schemaVersion',True)),
            ('wrong review kind',lambda d:d.__setitem__('kind','cleanup-grant')),
            ('launch authority elevation',lambda d:d.__setitem__('noLaunchAuthority',False)),
            ('malformed assessment pin',lambda d:d.__setitem__('assessment',None)),
            ('malformed receipt hash',lambda d:d['installationReceipt'].__setitem__('sha256','invalid')),
            ('relative helper pin',lambda d:d['installHelper'].__setitem__('path','relative.py')),
            ('malformed started pin',lambda d:d.__setitem__('installationStarted',{})),
            ('dot traversal UI pin',lambda d:d['nativeUiReady'].__setitem__('path','C:/Fixture/../native-ui.json')),
            ('malformed owner hash',lambda d:d['ownerAuthorization'].__setitem__('sha256','invalid')),
            ('missing owner message',lambda d:d['ownerAuthorization'].pop('messageId')),
            ('blank owner quote',lambda d:d['ownerAuthorization'].__setitem__('quote','  ')),
            ('blank owner reviewer',lambda d:d['ownerAuthorization'].__setitem__('verifiedBy','')),
            ('blank reviewer',lambda d:d.__setitem__('verifiedBy','  ')),
            ('blank reason',lambda d:d.__setitem__('reason','')),
        ]
        mutations += [('malformed '+field,lambda d,field=field:d.__setitem__(field,'invalid'))
                      for field in ('preparedRequestSha256','subjectOrderSha256','slotGrantSha256')]
        for label,mutate in mutations:
            malformed = copy.deepcopy(self.review);mutate(malformed);cases.append((label,malformed))
        for label,malformed in cases:
            expected = copy.deepcopy(self.expected)
            expected['reservedReview']['review'] = copy.deepcopy(malformed)
            response = self.response()
            response['reservedReview']['review'] = copy.deepcopy(malformed)
            # Matching malformed expected/response JSON must not bypass the
            # independent producer schema and minimum owner-evidence contract.
            with self.subTest(review=label), self.assertRaises(ValueError):
                self.validate(response,expected=expected)

    def test_query_must_match_reserved_id_pin_and_response_stage(self):
        for mutate in (lambda d:d.__setitem__('id','other-recovery'),
                       lambda d:d['reservedReviewPin'].__setitem__('sha256',digest('other')),
                       lambda d:d.__setitem__('stage','partial'),lambda d:d.__setitem__('extra',True)):
            query = self.query();mutate(query)
            with self.assertRaises(ValueError): self.validate(query=query)

    def test_implementation_and_allowed_postimage_exact_order_pins(self):
        for field in ('implementationPins','allowedPostimages'):
            for mutate in (lambda rows:rows.reverse(),lambda rows:rows[0].__setitem__('sha256',digest('changed')),
                           lambda rows:rows.append(pin('C:/Fixture/extra')),lambda rows:rows.pop()):
                response = self.response();mutate(response[field])
                with self.subTest(field=field), self.assertRaises(ValueError): self.validate(response)

    def test_prearchive_requires_all_thirteen_present_and_exact_postimage(self):
        for response in (self.response(present=[0,1]),self.response(state='disabled-new-mod'),self.response(state='preimage')):
            with self.assertRaises(ValueError): self.validate(response)

    def test_partial_partition_overlap_missing_unknown_and_non_path_absent_refused(self):
        query = self.query('partial')
        cases = []
        response = self.response('partial',list(range(6)));response['stageProof']['absent'][0] = self.allowed[0]['path'];cases.append(response)
        response = self.response('partial',list(range(6)));response['stageProof']['absent'].pop();cases.append(response)
        response = self.response('partial',list(range(6)));response['stageProof']['absent'][0] = 'C:/Fixture/unowned';cases.append(response)
        response = self.response('partial',list(range(6)));response['stageProof']['absent'][0] = copy.deepcopy(self.allowed[6]);cases.append(response)
        for response in cases:
            with self.assertRaises(ValueError): self.validate(response,query)

    def test_partial_partition_present_and_absent_order_are_bound(self):
        for field in ('present','absent'):
            response = self.response('partial',list(range(6)));response['stageProof'][field].reverse()
            with self.subTest(field=field), self.assertRaises(ValueError): self.validate(response,self.query('partial'))

    def test_partial_only_source_modlist_changes_to_selected_variant(self):
        for mutate in (lambda d:d['stageProof'].__setitem__('modlistState','unknown'),
                       lambda d:d['stageProof']['profilePins'][0].__setitem__('sha256',digest('unreviewed')),
                       lambda d:d['stageProof']['profilePins'][1].__setitem__('sha256',digest('other profile changed')),
                       lambda d:d['stageProof']['profilePins'].reverse()):
            response = self.response('partial',[0,1],'disabled-new-mod');mutate(response)
            with self.assertRaises(ValueError): self.validate(response,self.query('partial'))

    def test_managed_ini_path_and_fresh_backup_record_bound(self):
        for mutate in (lambda d:d['stageProof']['managedIniPin'].__setitem__('path','C:/Unrelated/ModOrganizer.ini'),
                       lambda d:d['stageProof']['managedIniPin'].__setitem__('sha256','invalid'),
                       lambda d:d['freshModlistBackup'].__setitem__('backup','C:/Fixture/other-backup'),
                       lambda d:d['freshModlistBackup'].__setitem__('currentlyByteIdentical',0)):
            response = self.response();mutate(response)
            with self.assertRaises(ValueError): self.validate(response)

    def test_mandatory_flags_cannot_be_elevated_or_replaced_by_zero_one(self):
        flags = {'copyOnly':True,'archiveVerified':False,'callerMustOwnSessionMutex':True,
                 'mutexOwnershipProvedByGuard':False,'newCleanupGranted':False,'launchGranted':False}
        for key,valid in flags.items():
            for invalid in (not valid,int(valid)):
                response = self.response();response[key] = invalid
                with self.subTest(flag=key,value=invalid), self.assertRaises(ValueError): self.validate(response)

    def test_partial_archive_and_copy_flags_bound(self):
        for key,value in (('archiveVerified',False),('copyOnly',True)):
            response = self.response('partial',[1,2]);response[key] = value
            with self.assertRaises(ValueError): self.validate(response,self.query('partial'))
        for bad in (None,{'path':'relative','sha256':digest('archive')},pin('C:/Fixture/../archive.json')):
            query = self.query('partial');query['archive'] = bad
            with self.assertRaises(ValueError): self.validate(self.response('partial'),query)

    def test_native_observation_rejects_failed_or_contradictory_syntax(self):
        for mutate in (lambda d:d['nativeIdleObservation'].__setitem__('observedAt',float('nan')),
                       lambda d:d['nativeIdleObservation'].__setitem__('processes',[]),
                       lambda d:d['nativeIdleObservation']['processes'][0].__setitem__('pid',True),
                       lambda d:d['nativeIdleObservation']['processes'][0].__setitem__('name','SkyrimSE.exe'),
                       lambda d:d['nativeIdleObservation']['checkedOwners'][0].__setitem__('alive',True),
                       lambda d:d['nativeIdleObservation']['checkedOwners'][0].__setitem__('alive',0),
                       lambda d:d['nativeIdleObservation']['runtimeStates'][0].__setitem__('done',False),
                       lambda d:d['nativeIdleObservation']['runtimeStates'][0].__setitem__('restored',1)):
            response = self.response();mutate(response)
            with self.assertRaises(ValueError): self.validate(response)

    def test_native_pid_reuse_requires_inventory_and_different_birth(self):
        response = self.response()
        native = response['nativeIdleObservation']
        native['processes'].append({'pid':11,'name':'other.exe'})
        native['checkedOwners'][0]['observedReusedPid'] = {'pid':11,'birth':101,'path':'C:/Fixture/other.exe'}
        self.assert_contract_only(self.validate(response))
        for mutate in (lambda d:d['nativeIdleObservation']['checkedOwners'][0].__setitem__('observedReusedPid',None),
                       lambda d:d['nativeIdleObservation']['processes'].pop(),
                       lambda d:d['nativeIdleObservation']['checkedOwners'][0]['observedReusedPid'].__setitem__('birth',100),
                       lambda d:d['nativeIdleObservation']['checkedOwners'][0]['observedReusedPid'].__setitem__('pid',12)):
            changed = copy.deepcopy(response);mutate(changed)
            with self.assertRaises(ValueError): self.validate(changed)

    def test_duplicate_scope_paths_in_expected_cannot_be_smuggled_as_valid(self):
        expected = copy.deepcopy(self.expected);expected['allowedPostimages'][-1] = copy.deepcopy(expected['allowedPostimages'][0])
        response = self.response();response['allowedPostimages'] = copy.deepcopy(expected['allowedPostimages'])
        response['stageProof']['present'] = copy.deepcopy(expected['allowedPostimages'])
        with self.assertRaises(ValueError): self.validate(response,expected=expected)

    def test_functions_do_not_mutate_query_response_or_expected(self):
        query,response,expected = self.query(),self.response(),copy.deepcopy(self.expected)
        before = copy.deepcopy((query,response,expected))
        self.assert_contract_only(self.validate(response,query,expected))
        self.assertEqual((query,response,expected),before)


if __name__ == '__main__':
    unittest.main()
