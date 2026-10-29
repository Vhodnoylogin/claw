"""Synthetic temporary fixtures for the read-only recovery PLAN client.

These tests never restore a real installation or certify a native cleanup.
"""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import polygon_restoration as recovery


def pin(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class RecoveryPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / 'workspace'
        self.documents = self.workspace / 'inputs'
        self.instance = self.root / 'instance'
        self.profile = self.instance / 'profiles' / 'Test'
        self.mod = self.instance / 'mods' / 'NewName'
        self.backups = self.root / 'fresh-backups'
        for directory in (self.documents, self.profile, self.mod, self.backups, self.instance / 'downloads'):
            directory.mkdir(parents=True, exist_ok=True)
        self.ids = {'id': 'fixture-preparation', 'orderId': 'fixture-order', 'slotId': 'fixture-slot',
                    'cycleId': 'fixture-cycle', 'sourceChat': 'skyrimvr-claw',
                    'sourceThreadId': '00000000-0000-4000-8000-000000000001'}
        self.payload = [
            'claw-build.json', 'CLAW.esp',
            'meshes/actors/WerewolfBeast/Character Assets/femalebodywerewolf.tri',
            'meshes/actors/WerewolfBeast/Character Assets/femalebodywerewolf_0.nif',
            'meshes/actors/WerewolfBeast/Character Assets/femalebodywerewolf_1.nif',
            'meshes/actors/WerewolfBeast/Character Assets/malebodywerewolf.tri',
            'meshes/actors/WerewolfBeast/Character Assets/malebodywerewolf_0.nif',
            'meshes/actors/WerewolfBeast/Character Assets/malebodywerewolf_1.nif',
            'README.md', 'README.ru.md']
        self.game_paths = [name for name in self.payload if Path(name).suffix in ('.esp', '.nif', '.tri')]
        for relative in self.payload:
            self.write(self.mod / relative, ('new fixture ' + relative).encode())
        self.write(self.mod / 'meta.ini', b'[General]\ninstallationFile=fixture.7z\n')
        archive = self.instance / 'downloads' / 'fixture.7z'
        self.write(archive, b'fixture archive bytes, not an installable package')
        self.write(Path(str(archive) + '.meta'), b'[General]\ninstalled=true\n')
        fresh = []
        profile_names = ['modlist.txt', 'archives.txt', 'initweaks.ini', 'loadorder.txt', 'lockedorder.txt',
                         'plugins.txt', 'settings.ini', 'Skyrim.ini', 'SkyrimCustom.ini', 'SkyrimPrefs.ini']
        current = [self.instance / 'ModOrganizer.ini', *[self.profile / name for name in profile_names]]
        for index, path in enumerate(current):
            before = (b'# native modlist\n+OldCLAW\n+SourceHost\n' if path.name == 'modlist.txt'
                      else ('fixture before ' + path.name + '\n').encode())
            self.write(path, before)
            backup = self.backups / str(index)
            self.write(backup, before)
            fresh.append({'path': str(path), 'backup': str(backup), 'sha256': pin(backup)['sha256']})
        self.write(self.profile / 'modlist.txt', b'# native modlist\n+NewName\n+OldCLAW\n+SourceHost\n')
        self.other = self.instance / 'profiles' / 'Other'
        self.write(self.other / 'modlist.txt', b'# another profile\n+OldCLAW\n')
        old_inputs = []
        for relative in self.game_paths:
            path = self.instance / 'mods' / 'OldCLAW' / relative
            self.write(path, ('old fixture ' + relative).encode())
            old_inputs.append({**pin(path), 'role': 'subject'})
        provider = self.instance / 'mods' / 'SourceHost' / 'SKSE' / 'Plugins' / 'fixture.dll'
        self.write(provider, b'fixture provider; never loaded')
        self.order = {'id': self.ids['orderId'], 'profile': 'Test', 'sourceChat': self.ids['sourceChat'],
                      'sourceThreadId': self.ids['sourceThreadId'],
                      'cycle': {'id': self.ids['cycleId'], 'slotId': self.ids['slotId']},
                      'inputs': [*old_inputs, {**pin(provider), 'role': 'dependency'},
                                 *[{**pin(self.mod / name), 'role': 'subject'} for name in self.payload]]}
        self.audit = {'files': [{'virtualPath': name, 'sha256': pin(self.mod / name)['sha256']} for name in self.payload]}
        self.prepared = {**self.ids, 'baselineAudit': self.save('baseline-audit.json', self.audit)}
        # Physical inventory order is not the authoritative native VFS query order.
        self.assessment = {'kind': 'read-only-minimal-unstarted-preparation-restoration-assessment',
                           'rootMod': str(self.mod),
                           'modFiles': [pin(self.mod / 'meta.ini'), *[pin(self.mod / name) for name in reversed(self.payload)]],
                           'newDownloadFiles': [pin(archive), pin(Path(str(archive) + '.meta'))],
                           'freshPreimages': fresh}
        self.config = {'schemaVersion': 1, 'kind': 'claw-origin-recovery-plan-input',
                       'workspaceRoot': str(self.workspace), 'recoveryId': 'fixture-recovery',
                       'assessment': self.save('assessment.json', self.assessment),
                       'preparedRequest': self.save('prepared.json', self.prepared),
                       'submittedOrder': self.save('order.json', self.order), 'reserveReview': None}
        self.config_path = self.documents / 'config.json'

    @staticmethod
    def write(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def save(self, name, value):
        path = self.documents / name
        path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        return pin(path)

    def resave_assessment(self):
        self.config['assessment'] = self.save('assessment.json', self.assessment)

    def resave_prepared(self):
        self.config['preparedRequest'] = self.save('prepared.json', self.prepared)

    def resave_order(self):
        self.config['submittedOrder'] = self.save('order.json', self.order)

    def tree(self):
        return {str(path.relative_to(self.root)): pin(path)['sha256'] if path.is_file() else '<directory>'
                for path in self.root.rglob('*')}

    def prepare(self):
        return recovery.prepare_plan(copy.deepcopy(self.config))

    def assert_refused(self):
        before = self.tree()
        with self.assertRaises((ValueError, KeyError, OSError)):
            self.prepare()
        self.assertEqual(before, self.tree())

    def test_valid_plan_is_read_only_and_never_a_restoration_receipt(self):
        before, config_before = self.tree(), copy.deepcopy(self.config)
        plan = recovery.prepare_plan(self.config)
        self.assertEqual(before, self.tree())
        self.assertEqual(self.config, config_before)
        self.assertEqual(plan['schemaVersion'], 1)
        for flag in ('cleanupGranted', 'launchGranted', 'executionSupported'):
            self.assertIs(plan[flag], False)
        receipt = plan['receiptTemplate']
        self.assertTrue(receipt['kind'].startswith('DRAFT-'))
        self.assertNotEqual(receipt['kind'], 'diagnostic-preexecution-native-restoration-receipt')
        for field in ('managerIdentity', 'readback', 'noGameStarted', 'archive', 'verifiedBy'):
            self.assertIsNone(receipt[field])
        self.assertEqual(receipt['nativeUiActor'], {'helper': None, 'evidence': []})
        self.assertEqual(len(plan['plannedArchiveMembers']), 13)
        self.assertTrue(all(not Path(member['plannedArchivePath']).exists() for member in plan['plannedArchiveMembers']))
        self.assertEqual(plan['sameQueuedSubjectMustRemainUnchanged'], self.ids['orderId'])

    def test_all_thirteen_changed_postimages_are_refused(self):
        for row in self.assessment['modFiles'] + self.assessment['newDownloadFiles']:
            path = Path(row['path']); original = path.read_bytes()
            with self.subTest(file=path.name):
                try:
                    path.write_bytes(original + b'changed')
                    self.assert_refused()
                finally:
                    path.write_bytes(original)

    def test_all_eleven_changed_backups_are_refused(self):
        for row in self.assessment['freshPreimages']:
            path = Path(row['backup']); original = path.read_bytes()
            with self.subTest(backup=path.name):
                try:
                    path.write_bytes(original + b'changed')
                    self.assert_refused()
                finally:
                    path.write_bytes(original)

    def test_extra_owned_file_and_empty_directory_are_refused(self):
        path = self.mod / 'unexpected.txt'
        path.write_bytes(b'not admitted')
        self.assert_refused()
        path.unlink()
        (self.mod / 'unexpected-empty').mkdir()
        self.assert_refused()

    def test_reparse_attribute_on_owned_file_backup_or_parent_is_refused(self):
        real_lstat = Path.lstat
        class ReparseInfo:
            def __init__(self, original): self.original = original
            def __getattr__(self, key): return getattr(self.original, key)
            @property
            def st_file_attributes(self): return getattr(self.original, 'st_file_attributes', 0) | 0x400
        targets = [self.mod / 'CLAW.esp', Path(self.assessment['freshPreimages'][0]['backup']), self.mod.parent]
        for target in targets:
            def observed(path, *args, **kwargs):
                original = real_lstat(path, *args, **kwargs)
                return ReparseInfo(original) if os.path.normcase(os.fspath(path)) == os.path.normcase(str(target)) else original
            with self.subTest(target=target.name), mock.patch.object(Path, 'lstat', observed):
                with self.assertRaisesRegex(ValueError, 'Reparse|symlink'):
                    self.prepare()

    def test_owned_file_outside_root_is_refused(self):
        path = self.root / 'unrelated' / 'CLAW.esp'
        self.write(path, b'not owned')
        self.assessment['modFiles'][0] = pin(path)
        self.resave_assessment()
        self.assert_refused()

    def test_download_pair_outside_exact_directory_is_refused(self):
        path = self.instance / 'other-downloads' / 'fixture.7z'
        self.write(path, b'wrong directory')
        self.assessment['newDownloadFiles'][0] = pin(path)
        self.resave_assessment()
        self.assert_refused()

    def test_backup_inside_instance_is_refused(self):
        row = self.assessment['freshPreimages'][0]
        path = self.instance / 'backup-copy'
        self.write(path, Path(row['backup']).read_bytes())
        row['backup'] = str(path)
        self.resave_assessment()
        self.assert_refused()

    def test_other_profile_preimage_or_reference_is_refused(self):
        row = self.assessment['freshPreimages'][1]
        original_path = row['path']
        row['path'] = str(self.other / 'modlist.txt')
        self.resave_assessment()
        self.assert_refused()
        row['path'] = original_path
        self.resave_assessment()
        for entry in ('+NewName', '-NewName'):
            self.write(self.other / 'modlist.txt', (entry + '\n').encode())
            with self.subTest(reference=entry): self.assert_refused()

    def test_absolute_profile_cannot_rebind_ten_fresh_preimages_outside_instance(self):
        external = self.root / 'forged-external-profile'
        for row in self.assessment['freshPreimages']:
            source = Path(row['path'])
            if source.name == 'ModOrganizer.ini':
                continue
            destination = external / source.name
            self.write(destination, source.read_bytes())
            row['path'] = str(destination)
        # Remove every genuine-instance reference, so the old profile-reference
        # scan cannot accidentally reject this otherwise coherent forged scope.
        before_modlist = next(Path(row['backup']).read_bytes() for row in self.assessment['freshPreimages']
                              if Path(row['path']).name == 'modlist.txt')
        (self.profile / 'modlist.txt').write_bytes(before_modlist)
        self.assertFalse(any('NewName' in (directory / 'modlist.txt').read_text()
                             for directory in (self.profile, self.other)))
        self.resave_assessment()
        for name in (str(external), 'Test/../Other', 'Test\\Other', '.', '..', 'Test.', 'Test '):
            self.order['profile'] = name
            self.resave_order()
            before = self.tree()
            with self.subTest(profile=name), self.assertRaisesRegex(ValueError, 'profile'):
                self.prepare()
            self.assertEqual(before, self.tree())

    def test_non_modlist_profile_drift_is_refused(self):
        (self.profile / 'plugins.txt').write_bytes(b'unreviewed plugin change')
        self.assert_refused()

    def test_owned_mod_entry_must_be_unique_and_highest(self):
        for value in (b'# native modlist\n+NewName\n+NewName\n+OldCLAW\n+SourceHost\n',
                      b'# native modlist\n+OldCLAW\n+SourceHost\n+NewName\n'):
            (self.profile / 'modlist.txt').write_bytes(value)
            with self.subTest(modlist=value): self.assert_refused()

    def test_origin_cycle_and_order_mismatch_are_refused(self):
        for field in ('orderId', 'slotId', 'cycleId', 'sourceChat', 'sourceThreadId'):
            original = self.prepared[field]
            self.prepared[field] = 'unrelated'
            self.resave_prepared()
            with self.subTest(field=field): self.assert_refused()
            self.prepared[field] = original
            self.resave_prepared()

    def test_original_vfs_provider_must_remain_pinned_and_in_instance(self):
        original = copy.deepcopy(self.order['inputs'][0])
        self.order['inputs'][0]['sha256'] = '0' * 64
        self.resave_order()
        self.assert_refused()
        external = self.root / 'unrelated-originals' / self.game_paths[0]
        self.write(external, b'external source is not an installed former provider')
        self.order['inputs'][0] = {**pin(external), 'role': 'subject'}
        self.resave_order()
        self.assert_refused()
        self.order['inputs'][0] = original

    def test_new_payload_must_match_submitted_pins(self):
        self.order['inputs'][-1]['sha256'] = '0' * 64
        self.resave_order()
        self.assert_refused()

    def test_baseline_audit_controls_game_vfs_order(self):
        plan = self.prepare()
        self.assertEqual([Path(row['virtualPath']).as_posix() for row in plan['gameVfsReadbacks']], self.game_paths)

    def test_baseline_audit_changed_hash_extra_or_traversal_is_refused(self):
        original = copy.deepcopy(self.audit)
        for mutate in (lambda d:d['files'][0].__setitem__('sha256', '0' * 64),
                       lambda d:d['files'].append({'virtualPath':'meta.ini','sha256':pin(self.mod / 'meta.ini')['sha256']}),
                       lambda d:d['files'][0].__setitem__('virtualPath', '../claw-build.json')):
            self.audit = copy.deepcopy(original); mutate(self.audit)
            self.prepared['baselineAudit'] = self.save('baseline-audit.json', self.audit)
            self.resave_prepared()
            self.assert_refused()

    def test_config_unknown_execution_flags_types_and_relative_roots_refused(self):
        cases = [dict(self.config, execute=True), dict(self.config, schemaVersion=True),
                 dict(self.config, schemaVersion=2), dict(self.config, kind='execute-recovery'),
                 dict(self.config, workspaceRoot='relative'), dict(self.config, recoveryId='../escape')]
        for config in cases:
            before = self.tree()
            with self.subTest(config=config), self.assertRaises(ValueError): recovery.prepare_plan(config)
            self.assertEqual(before, self.tree())

    def test_optional_reserve_review_remains_non_authorizing(self):
        review = {'kind':'diagnostic-preexecution-recovery-reserve', 'id':self.config['recoveryId'],
                  'diagnosticId':self.ids['id'], 'noLaunchAuthority':True}
        self.config['reserveReview'] = self.save('reserve.json', review)
        self.assertIs(self.prepare()['cleanupGranted'], False)
        review['noLaunchAuthority'] = False
        self.config['reserveReview'] = self.save('reserve.json', review)
        self.assert_refused()

    def run_main(self, argv):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return recovery.main(argv)

    def test_cli_writes_only_explicit_scoped_plan_and_never_overwrites(self):
        output = self.workspace / 'local/skyrim-polygon/diagnostic-recoveries' / self.config['recoveryId'] / 'plan.json'
        output.parent.mkdir(parents=True)
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')
        before = self.tree()
        self.assertEqual(self.run_main(['plan','--config',str(self.config_path),'--output',str(output)]), 0)
        after = self.tree()
        self.assertEqual(set(after) - set(before), {str(output.relative_to(self.root))})
        self.assertTrue(all(after[key] == value for key,value in before.items()))
        original = output.read_bytes()
        with self.assertRaises(FileExistsError):
            self.run_main(['plan','--config',str(self.config_path),'--output',str(output)])
        self.assertEqual(output.read_bytes(), original)

    def test_cli_execute_and_output_scope_escape_refused_without_writes(self):
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')
        for command in ('execute','archive','remove'):
            before = self.tree()
            with self.subTest(command=command), self.assertRaises(SystemExit): self.run_main([command])
            self.assertEqual(before, self.tree())
        for output in (self.root / 'outside-plan.json', self.instance / 'plan.json'):
            before = self.tree()
            with self.subTest(output=output.name), self.assertRaises(ValueError):
                self.run_main(['plan','--config',str(self.config_path),'--output',str(output)])
            self.assertEqual(before, self.tree())


if __name__ == '__main__':
    unittest.main()
