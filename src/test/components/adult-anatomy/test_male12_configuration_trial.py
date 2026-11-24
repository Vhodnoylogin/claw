"""Synthetic transport only. No owned game, fixture, native or provider is started."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

import male12_configuration_trial as trial
import test_male12_readback as fixtures


class Clock:
    def __init__(self):
        self.now = 0.

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class Session:
    def __init__(self, directory, xml):
        self.dir = Path(directory)
        game = {'pid': 17, 'created': 100}
        self.state = {'id': 'synthetic-run', 'gameEdition': 'se', 'game': game,
                      'owned': [{'role': 'game', 'identity': game}]}
        self.world, before, after = fixtures.symbolic(xml)
        self.world['refs'][0]['identity'].update(sourcePlugin=trial.FIXTURE_PLUGIN, localFormId='0x00000900')
        self.world['refs'][0]['cellForm'] = trial.QA_SMOKE
        idle = copy.deepcopy(before)
        window = idle['sample']['objectWindow']
        window.update(status='idle', nonce=0, loadEpoch=0, pairedSteps=0, objectCount=0, objects=[],
                      minimumPairedHostTimeStep=None, summedPairedHostTimeStep=0.)
        window['incidentConstraints'].update(status='not_started', constraintCount=0, constraints=[])
        final = copy.deepcopy(after)
        sample = final['sample']
        sample.update(sampledQpc=3000)
        for side in ('pre', 'post'):
            sample[side].update(count=900, lastQpc=2999)
        sample['objectWindow'].update(status='complete', pairedSteps=900, lastPreQpc=2998, lastPostQpc=2999,
                                      summedPairedHostTimeStep=.016 * 900)
        self.snapshots = [idle, before, after, final]
        self.serial = self.arms = self.world_count = 0
        self.requests = []
        self.arm_timeout = self.change_root = False

    def tool(self, tool, args, *, timeout, deadline):
        self.requests.append((tool, args))
        if tool == 'inspect':
            assert args['kind'] == 'world_observer' and args['refs'] == [fixtures.REF]
            self.world_count += 1
            raw = copy.deepcopy(self.world)
            raw.update(sampleId=self.world_count, producerMonotonicNs=250_000_000 * self.world_count)
            if self.change_root and self.world_count == 3:
                raw['refs'][0]['rootIdentity']['sampledRootToken'] += 1
            return raw
        assert tool == 'papyrus'
        script = args['script']
        if args['action'] == 'describe':
            return {'name': script, 'globalFunctions': [
                {'name': function, 'params': [{'type': kind} for kind in params], 'native': True, 'returnType': returned}
                for function, (params, returned) in trial.SIGNATURES[script].items()]}
        call, values = args['function'], args['args']
        if call == 'GetFormFromFile':
            assert values[1] == trial.FIXTURE_PLUGIN
            reference = values[0] == trial.REFERENCE_LOCAL_ID
            return {'called': True, 'returnedType': 'Form', 'returned': {
                'formId': fixtures.REF if reference else fixtures.BASE,
                'formType': '62' if reference else '43'}}
        if call == 'QueryCurrentPhysicsFile':
            assert values == [{'form': fixtures.REF}, {'form': trial.WOLF_ADDON}, False]
            value = trial.EXPECTED_XML.replace('/', '\\')
        elif call == 'BeginWindow':
            self.arms += 1
            assert len(values) == 1 and values[0] == 71
            if self.arm_timeout:
                raise TimeoutError('Missing first arm response')
            value = json.dumps({'schema': trial.SCHEMA, 'status': 'pending' if self.arms == 1 else 'ready',
                                'nonce': 71, 'loadEpoch': 2, 'markedQpc': 10})
        else:
            assert call == 'ReadState'
            if values == [0]:
                self.serial += 1
            else:
                assert values == [self.serial]
            snapshot = copy.deepcopy(self.snapshots[min(self.serial - 1, len(self.snapshots) - 1)])
            snapshot['requestSerial'] = self.serial
            if values == [0]:
                snapshot['status'] = 'pending'
                del snapshot['sample']
            value = json.dumps(snapshot)
        return {'called': True, 'returnedType': 'String', 'returned': value}


class ConfigurationTrialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.Male12ReadbackTests.setUpClass()
        cls.xml = fixtures.Male12ReadbackTests.xml

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.session = Session(directory.name, self.xml)
        self.out = self.session.dir / 'male12-quiet-configuration'

    def run_case(self):
        return trial.run(self.session, self.xml, nonce=71, clock=Clock())

    def status(self):
        return json.loads((self.out / 'status.json').read_bytes())

    def test_configuration_requires_named_quiet_bracket_and_terminal_same_window(self):
        result = self.run_case()
        self.assertEqual(result['status'], 'configured-se-rig-observed')
        self.assertEqual(len(result['joints']), 12)
        self.assertFalse(result['runtimeQualified'])
        self.assertFalse(result['contactQualified'])
        self.assertEqual(self.session.arms, 2)  # one first call, one known pending observation
        self.assertEqual(self.status()['windowEnd'], 'complete-900')
        self.assertFalse(self.status()['motionQualified'])
        final = json.loads((self.out / 'native-complete-900.json').read_bytes())
        self.assertEqual(final['sample']['objectWindow']['pairedSteps'], 900)
        self.assertEqual(final['sample']['objectWindow']['nonce'], 71)
        self.assertEqual({a.get('function') for _, a in self.session.requests if a.get('action') == 'call'},
                         {'GetFormFromFile', 'QueryCurrentPhysicsFile', 'ReadState', 'BeginWindow'})

    def test_unknown_arm_never_polls_or_rearms(self):
        self.session.arm_timeout = True
        with self.assertRaisesRegex(TimeoutError, 'Missing first arm response'):
            self.run_case()
        self.assertEqual(self.session.arms, 1)
        self.assertEqual(self.session.serial, 1)
        self.assertEqual(self.status()['arm'], 'unknown-until-acknowledged')
        self.assertTrue(self.status()['ownedSessionTeardownRequired'])
        self.assertFalse((self.out / 'configuration-evidence.json').exists())

    def test_changed_world_root_refuses_scoring_and_drains_acknowledged_window(self):
        self.session.change_root = True
        with self.assertRaisesRegex(ValueError, 'actor/root/epoch changed'):
            self.run_case()
        self.assertEqual(self.status()['status'], 'failed')
        self.assertEqual(self.status()['windowEnd'], 'complete-900')
        self.assertTrue(self.status()['ownedSessionTeardownRequired'])
        self.assertFalse((self.out / 'configuration-evidence.json').exists())

    def test_completed_window_with_changed_joints_cannot_qualify(self):
        self.session.snapshots[-1]['sample']['objectWindow']['incidentConstraints']['constraints'][0]['spring2'][
            'stiffness'][0] += 1.
        with self.assertRaisesRegex(ValueError, 'did not preserve'):
            self.run_case()
        self.assertEqual(self.status()['status'], 'failed')
        self.assertEqual(self.status()['windowEnd'], 'complete-900')
        self.assertEqual(self.session.serial, 4)
        self.assertFalse((self.out / 'configuration-evidence.json').exists())

    def test_nonadvancing_collecting_window_cannot_qualify(self):
        self.session.snapshots[2] = copy.deepcopy(self.session.snapshots[1])
        with self.assertRaisesRegex(ValueError, 'before the required live bracket'):
            self.run_case()
        self.assertEqual(self.status()['status'], 'failed')
        self.assertEqual(self.status()['windowEnd'], 'complete-900')
        self.assertFalse((self.out / 'configuration-evidence.json').exists())


if __name__ == '__main__':
    unittest.main()
