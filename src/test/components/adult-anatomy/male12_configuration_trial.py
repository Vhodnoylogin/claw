"""Collect a quiet male12 configuration bracket in an admitted disposable SE session.

The launcher owns the game, VFS/module admission, fixture activation and teardown.
This callback reads an already enabled fixture and arms only the bounded diagnostic.
"""
from __future__ import annotations

import copy
import json
import os
import time

import male12_readback as readback


FIXTURE_PLUGIN = 'test_CLAW - Male Physics Probe.esp'
REFERENCE_LOCAL_ID = 0x900
BASE_LOCAL_ID = 0x800
QA_SMOKE = '0x00032AE7'
WOLF_ADDON = '0x000CDD87'
EXPECTED_XML = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotionNeutralAnatomyMale.xml'
WITNESS = 'CLAWFSMPWitness'
SCHEMA = 'claw-fsmp-step-witness/4'
SIGNATURES = {
    'Game': {'GetFormFromFile': (['int', 'string'], 'form')},
    'DynamicHDT': {'QueryCurrentPhysicsFile': (['actor', 'armoraddon', 'bool'], 'string')},
    WITNESS: {'ReadState': (['int'], 'string'), 'BeginWindow': (['int'], 'string')},
}
require = readback.require


def _write_json(path, value):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def _normal(sample):
    require(sample['mainGameActive'] is True and sample['worldRootPresent'] is True
            and all(sample[key] is False for key in ('mainFreezeTime', 'mainFreezeNextFrame', 'uiPaused'))
            and sample['timerPauseCount'] == 0 and sample['engineMultiplier'] == 1,
            'Unpaused normal-rate world required for quiet configuration')


class Trial:
    def __init__(self, session, nonce, maximum_seconds, clock):
        require(type(nonce) is int and 0 < nonce <= 0x7FFFFFFF, 'Positive Papyrus nonce required')
        require(type(maximum_seconds) in (int, float) and 30 <= maximum_seconds <= 180,
                'A 30–180 second collection budget is required')
        self.session, self.nonce, self.clock = session, nonce, clock
        self.end = clock.monotonic() + maximum_seconds
        self.game, self.run_id = copy.deepcopy(session.state.get('game')), session.state.get('id')
        self.probe, self.rig, _, _ = readback.shared()
        self._remaining()
        self.output = session.dir / 'male12-quiet-configuration'
        self.output.mkdir()
        self.state = {'status': 'started', 'game': self.game, 'nonce': nonce, 'arm': 'unattempted',
                      'windowEnd': None, 'fixtureDisposal': 'outer-owned-session',
                      'runtimeQualified': False, 'motionQualified': False, 'contactQualified': False}
        self._save()
        self.read_serial = 0
        self.epoch = None
        self.baseline = None

    def _save(self):
        _write_json(self.output / 'status.json', self.state)

    def _remaining(self):
        state = self.session.state
        require(state.get('gameEdition', state.get('configuration', {}).get('game_edition')) == 'se'
                and self.run_id and state.get('id') == self.run_id and state.get('game') == self.game
                and self.game and type(self.game.get('pid')) is int and self.game['pid'] > 0
                and any(row.get('role') == 'game' and row.get('identity') == self.game for row in state.get('owned', ()))
                and not state.get('ownedFixtureQuarantine'), 'Exact owned SE session required')
        remaining = self.end - self.clock.monotonic()
        require(remaining > 0, 'Male12 configuration collection deadline exhausted')
        return remaining

    def _pause(self, seconds):
        self.clock.sleep(min(seconds, self._remaining()))

    def _call(self, tool, args):
        remaining = self._remaining()
        result = self.session.tool(tool, args, timeout=min(6, remaining), deadline=self.end)
        with (self.output / 'tool-receipts.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps({'tool': tool, 'args': args, 'result': result}, allow_nan=False) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
        self._remaining()
        require(type(result) is dict and not result.get('error') and not result.get('isError'),
                'Incomplete tool envelope: ' + tool)
        return result

    def _qualify(self):
        from skyrim_autotest.api_contract import validate_description

        for script, signatures in SIGNATURES.items():
            result = self._call('papyrus', {'action': 'describe', 'script': script})
            functions = validate_description(script, result, 'globalFunctions',
                                             {name: row[0] for name, row in signatures.items()})
            require(all(row['native'] is True and str(row['returnType']).casefold() == signatures[row['function']][1]
                        for row in functions), 'Unexpected native contract: ' + script)

    def _pap(self, script, function, *args):
        timeout_ms = max(1, min(5000, int(self._remaining() * 1000)))
        result = self._call('papyrus', {'action': 'call', 'script': script, 'function': function,
                                       'args': list(args), 'timeoutMs': timeout_ms})
        wanted = SIGNATURES[script][function][1]
        require(self.rig.cached.completed(result, wanted), 'Typed native completion unavailable: ' + function)
        return result['returned']

    def _resolve(self, local_id, form_type):
        result = self._pap('Game', 'GetFormFromFile', local_id, FIXTURE_PLUGIN)
        require(type(result) is dict and result.get('formType') == form_type, 'Fixture form type differs')
        form = self.probe.form(result['formId'])
        number = int(form, 16)
        require(0 < number >> 24 < 0xFE and number & 0xFFFFFF == local_id,
                'Unexpected authored fixture FormID')
        return form

    def _binding(self):
        raw = self._pap('DynamicHDT', 'QueryCurrentPhysicsFile',
                        {'form': self.reference}, {'form': WOLF_ADDON}, False)
        require(raw.replace('\\', '/').casefold() == EXPECTED_XML.casefold(),
                'Active male12 FSMP binding differs')
        return raw

    def _world(self):
        raw = self._call('inspect', {'kind': 'world_observer', 'refs': [self.reference], 'actors': True,
                         'nodes': [{'ref': self.reference, 'name': name, 'firstPerson': False}
                                   for name in readback.node_names()]})
        row = readback.snapshot(raw, self.reference)
        readback.expected_scales(row)
        guard, actor = row['guard'], row['guard']['actor']
        require(guard['session'].partition('-')[0] == str(self.game['pid'])
                and str(guard['identity'].get('sourcePlugin')).casefold() == FIXTURE_PLUGIN.casefold()
                and guard['identity'].get('localFormId') == f'0x{REFERENCE_LOCAL_ID:08X}'
                and raw['refs'][0].get('cellForm') == QA_SMOKE
                and actor['baseForm'] == self.base and actor['race'] == actor['baseRace'] == self.rig.WOLF_RACE
                and actor['weight']['rawNPCWeight'] == 50, 'Wrong authored male12 fixture identity')
        if self.baseline is not None:
            self._quiet(self.baseline, row)
        return raw, row

    def _quiet(self, first, second):
        delta = self.probe.max_delta
        require(first['guard'] == second['guard'] and first['sample'] < second['sample']
                and first['time'] < second['time'], 'World Observer actor/root/epoch changed or sample did not advance')
        require(delta(first['position'], second['position']) <= .025
                and delta(first['angles'], second['angles']) <= 1e-5
                and delta(first['root']['translation'], second['root']['translation']) <= .025
                and delta(first['root']['rotationRowMajor'], second['root']['rotationRowMajor']) <= 1e-5,
                'Actor/root pose did not remain quiet')
        for name in first['nodes']:
            require(all(delta(first['nodes'][name]['local'][channel], second['nodes'][name]['local'][channel]) <= floor
                        for channel, floor in self.probe.FLOORS.items()), 'Local scene pose changed: ' + name)
        for name in (*readback.anchors(), *self.probe.CONTROL, 'CME Pelvis [Pelv]'):
            a, b = (self.probe.relative(row['nodes'][name]['world'], row['root']) for row in (first, second))
            require(all(delta(a[channel], b[channel]) <= floor for channel, floor in self.probe.FLOORS.items()),
                    'Scene control pose changed: ' + name)

    def _read(self, serial):
        raw = self._pap(WITNESS, 'ReadState', serial)
        native = self.rig.witness.parse(raw, serial or None)
        require(native['schema'] == SCHEMA and native['pid'] == self.game['pid'],
                'Native witness schema or process changed')
        return native

    def _snapshot(self):
        pending = self._read(0)
        serial = pending['requestSerial']
        require(pending['status'] == 'pending' and serial > self.read_serial,
                'Fresh queued native snapshot required')
        self.read_serial = serial
        while True:
            native = self._read(serial)
            if native['status'] == 'ready':
                sample = native['sample']
                require(self.epoch is None or sample['loadEpoch'] == self.epoch, 'Native load epoch changed')
                _normal(sample)
                return native
            self._pause(.05)

    def _arm(self):
        self.state['arm'] = 'unknown-until-acknowledged'
        self._save()  # Before the one call that can queue the bounded window.
        while True:
            value = readback.json_object(self._pap(WITNESS, 'BeginWindow', self.nonce))
            require(value.get('schema') == SCHEMA and type(value.get('nonce')) is int
                    and value['nonce'] == self.nonce and type(value.get('loadEpoch')) is int
                    and value['loadEpoch'] == self.epoch and value.get('status') in ('pending', 'ready'),
                    'Exact schema-4 arm acknowledgement unavailable')
            if value['status'] == 'ready':
                require(self.rig.witness.integer(value.get('markedQpc'), 1), 'Arm boundary timestamp unavailable')
                self.marked_qpc = value['markedQpc']
                self.state['arm'] = 'acknowledged'
                self._save()
                return
            self._pause(.05)  # Only a known pending receipt permits same-nonce polling.

    def _window(self, status, after=None):
        while True:
            native = self._snapshot()
            sample = native['sample']
            window = self.rig.witness.validate_window(sample['objectWindow'], self.epoch, self.nonce, version=4)
            if window['status'] == status and not window['awaitingPost'] and window['pairedSteps'] >= 2:
                require(window['lastPostQpc'] >= self.marked_qpc, 'Native pairs predate arm completion')
                if after is None or window['pairedSteps'] > after['sample']['objectWindow']['pairedSteps']:
                    self.rig._normal_window(native, self.game['pid'], self.nonce, status)
                    return native
            require(window['status'] != 'complete', 'Window completed before the required live bracket')
            self._pause(.25 if status == 'complete' else .05)

    def _finish(self, after=None):
        final = self._window('complete', after)
        _write_json(self.output / 'native-complete-900.json', final)
        self._remaining()
        self.state['windowEnd'] = 'complete-900'
        self._save()
        if after is not None:
            previous, last = (value['sample']['objectWindow'] for value in (after, final))
            progression = self.rig.witness.compare(after, final)
            require(progression['providerCompletedStepsObserved'] and previous['firstPreQpc'] == last['firstPreQpc']
                    and previous['lastPostQpc'] < last['lastPostQpc']
                    and previous['incidentConstraints'] == last['incidentConstraints']
                    and [(x['token'], x['initialPre']) for x in previous['objects']] ==
                        [(x['token'], x['initialPre']) for x in last['objects']],
                    'Completed native boundary did not preserve the configuration bracket')

    def execute(self, xml):
        self._qualify()
        self.reference = self._resolve(REFERENCE_LOCAL_ID, '62')
        self.base = self._resolve(BASE_LOCAL_ID, '43')
        require(int(self.reference, 16) >> 24 == int(self.base, 16) >> 24,
                'Reference and base resolved from different load slots')
        initial, self.baseline = self._world()
        self._pause(.22)
        _, settled = self._world()
        require(settled['time'] - self.baseline['time'] >= 200_000_000, 'Quiet baseline shorter than .2 seconds')
        binding_before = self._binding()
        idle = self._snapshot()
        require(idle['sample']['objectWindow']['status'] == 'idle', 'Native window already consumed in this process')
        self.epoch = idle['sample']['loadEpoch']
        self._arm()
        before = self._window('collecting')
        world, row = self._world()
        self._quiet(settled, row)
        after = self._window('collecting', before)
        self._finish(after)
        binding_after = self._binding()
        final_world, final_row = self._world()
        self._quiet(row, final_row)
        proof = readback.evaluate_configuration(xml, world, before, after, reference=self.reference, base=self.base,
                                                pid=self.game['pid'], nonce=self.nonce)
        _write_json(self.output / 'configuration-evidence.json', {
            'configuration': proof, 'game': self.game, 'bindings': [binding_before, binding_after],
            'baselineWorld': initial, 'world': world, 'worldAfterWindow': final_world,
            'nativeBefore': before, 'nativeAfter': after, 'windowEnd': 'native-complete-900.json',
        })
        self._remaining()
        self.state['status'] = proof['status']
        self._save()
        return proof

    def failed(self, error):
        self.state.update(status='failed', error=repr(error))
        if self.state['arm'] == 'acknowledged' and self.state['windowEnd'] is None:
            try:
                self._finish()  # Acknowledged nonce only; no reset or guessed cancellation.
            except Exception as cleanup:
                self.state['windowEndError'] = repr(cleanup)
        self.state['ownedSessionTeardownRequired'] = True
        self._save()


def run(session, xml: bytes, *, nonce: int, maximum_seconds: float = 90, clock=time):
    """Run within an already admitted, active fixture session. Never launch or change the actor."""
    readback.source_profile(xml)
    trial = Trial(session, nonce, maximum_seconds, clock)
    try:
        return trial.execute(xml)
    except Exception as error:
        trial.failed(error)
        raise
