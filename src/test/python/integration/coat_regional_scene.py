"""Place and inspect the four regional coat pairs in an owned Skyrim SE run."""

import argparse
import json
import math
from pathlib import Path
import time
from unittest.mock import patch

from coat_regional_readback import compare_pairs, expected_paths, inspect_regions, verify_human
from coat_persistence_readback import require


PALETTE = Path(__file__).resolve().parents[2] / 'resources/inspection/regional-coats/pairs.json'
PLAYER = '0x00000014'
WOLF_RACE = '0x000CDD84'
CELL = '0x00032AE7'  # QASmoke in Skyrim.esm
WALL_X, FLOOR_Z = -2697.94482421875, 6976.4501953125
CAMERA = (-2319.94482421875, 1740., FLOOR_Z)
ROLES = ('Human', 'Wolf')


def tag(index, role):
    return f'colour{index}{role}'


def actors(pairs):
    for index, pair in enumerate(pairs):
        for side, role in enumerate(ROLES):
            # Keep spawns out of the wall row and leave at least 110 units between lanes.
            yield pair, role, tag(index, role), (350. + 110. * side, -340. + 110. * index), pair[role.lower() + 'Y']


def session_policy(config, palette):
    policy = config.get('native_session', {}).get('nativeBindings', {})
    pairs = palette['pairs']
    require(config.get('game_edition') == 'se' and not config.get('reuse_test_profile')
            and not config.get('interactive_session'), 'Use a fresh, isolated TEST SE profile')
    require(set(policy.get('fixtureActorBases', [])) == {pair['base'] for pair in pairs}
            and set(policy.get('allowedRaceForms', [])) == {WOLF_RACE, *(pair['race'] for pair in pairs)}
            and any(row.get('id') == 'morph_race' for row in policy.get('bindings', [])),
            'The SE configuration must admit the four fixture bases and the guarded morph_race binding')
    return policy


class RegionalScene:
    def __init__(self, session, palette, appearance, coat_mode, dwell):
        from skyrim_autotest import fixture_actors, interactive_bindings, native

        self.session = session
        self.fixture, self.bindings = fixture_actors, interactive_bindings
        self.native = native
        self.policy = session_policy(session.state['configuration'], palette)
        self.game = session.state['game']
        require(any(row['role'] == 'game' and row['identity'] == self.game for row in session.state['owned'])
                and native.identity(self.game['pid']) == self.game, 'Expected exact owned Skyrim process')
        self.pairs = palette['pairs']
        self.fixed = palette['fixedCoat'] if coat_mode == 'fixed' else None
        self.appearance = appearance
        self.dwell = dwell
        self.end = time.monotonic() + 307 + dwell
        self.path = session.dir / 'claw-regional-scene.json'
        require(not self.path.exists() and not session.state.get('interactiveActorFixtures'),
                'Scene may only create actors once in a fresh run')
        self.data = {'run': session.state['id'], 'game': self.game, 'palette': palette,
                     'coatMode': coat_mode, 'dwellSeconds': dwell, 'actors': {}, 'pairs': {}, 'rawAudits': {},
                     'status': 'PREPARING', 'intent': None, 'unknownMutation': False}

    def save(self):
        pending = self.path.with_suffix('.tmp')
        pending.write_text(json.dumps(self.data, indent=2) + '\n', encoding='utf-8')
        pending.replace(self.path)

    def mutate(self, label, call):
        require(not self.data['unknownMutation'], 'Previous scene write uncertain')
        self.data['intent'] = label
        self.save()
        try:
            result = call()
        except BaseException:
            self.data['unknownMutation'] = True
            self.save()
            raise
        self.data['intent'] = None
        self.save()
        return result

    def deadline(self):
        now = time.monotonic()
        require(self.end > now, 'Scene preparation timed out')
        return min(self.end, now + 20)

    def tool(self, name, args):
        deadline = self.deadline()
        return self.session.tool(name, args, timeout=min(8, deadline - time.monotonic()), deadline=deadline)

    def papyrus(self, script, function, args, return_type, target=None, *, write=False):
        packet = {'action': 'call', 'script': script, 'function': function, 'args': args, 'timeoutMs': 6000}
        if target is not None:
            packet['self'] = {'form': target}

        def call():
            raw = self.tool('papyrus', packet)
            require(raw.get('called') is True and 'returned' in raw
                    and str(raw.get('returnedType', '')).casefold() == return_type,
                    f'Typed completion differs for {script}.{function}')
            return raw['returned']

        return self.mutate(function, call) if write else call()

    def spec(self, actor):
        row = self.session.state['interactiveActorFixtures'][actor]
        return {'reference': row['reference'], 'base': row['base']}

    def guard(self, actor):
        return self.fixture.guard(self.session, self.spec(actor), self.deadline(), self.policy)

    def claw(self, actor, function, return_type='string', *args, write=False):
        self.guard(actor)
        return self.papyrus('CLAWDistributionNative', function, [{'form': self.spec(actor)['reference']}, *args],
                            return_type, write=write)

    def poll(self, query, accept, seconds, message):
        deadline = min(self.end, time.monotonic() + seconds)
        while time.monotonic() < deadline:
            value = query()
            if accept(value):
                return value
            time.sleep(.12)
        raise RuntimeError(message)

    def audit(self, actor):
        self.guard(actor)
        args = [{'form': self.spec(actor)['reference']}]
        require(self.papyrus('CLAWDistributionNative', 'RequestCoatSurfaceAudit', args, 'bool') is True,
                'Material audit was refused')
        chunks = self.poll(lambda: self.papyrus('CLAWDistributionNative', 'GetCoatSurfaceAuditChunks', args, 'string[]'),
                           bool, 2, 'Fresh material audit unavailable')
        return json.loads(''.join(chunks))

    def pose(self, reference, position, heading):
        self.papyrus('ObjectReference', 'SetPosition', list(position), 'none', reference, write=True)
        self.papyrus('ObjectReference', 'SetAngle', [0., 0., heading], 'none', reference, write=True)

    def place(self, actor, y, *, pin=False):
        self.guard(actor)
        reference = self.spec(actor)['reference']
        self.pose(reference, (WALL_X, y, FLOOR_Z), 90.)
        if pin:
            self.guard(actor)
            self.papyrus('Actor', 'SetDontMove', [True], 'none', reference, write=True)

    def unequip(self, actor, inventory, *, remove):
        self.guard(actor)
        reference = self.spec(actor)['reference']
        for form in inventory:
            item = {'form': form}
            count = self.papyrus('ObjectReference', 'GetItemCount', [item], 'int', reference)
            if remove and count:
                self.papyrus('ObjectReference', 'RemoveItem', [item, count, True, None], 'none', reference, write=True)
                count = self.papyrus('ObjectReference', 'GetItemCount', [item], 'int', reference)
            require(count == 0, 'Source equipment remains on ' + actor)

    def create(self, pair, role, actor, lane, y):
        self.session.state['activeSemanticCommandId'] = 'preview-create-' + actor
        request = {'tag': actor, 'base': pair['base'], 'forwardGameUnits': lane[0],
                   'rightGameUnits': lane[1], 'persistentForOwnedSave': False}
        self.data['actors'][actor] = self.mutate('create ' + actor, lambda: self.fixture.create(
            self.session, request, self.deadline(), self.policy))
        observed = self.guard(actor)['actor']
        require(observed['race'] == pair['race'] and observed['sex'] == 'female', 'Human identity differs: ' + actor)
        self.poll(lambda: self.claw(actor, 'GetAppearanceStatus'), lambda value: value == 'human colours captured',
                  12, 'Human colour source was not captured: ' + actor)
        self.place(actor, y, pin=True)
        reference = self.spec(actor)['reference']
        measured = [self.papyrus('ObjectReference', 'GetPosition' + axis, [], 'float', reference) for axis in 'XYZ']
        require(math.dist((WALL_X, y, FLOOR_Z), measured) <= 4., 'Actor did not clear the spawn lane: ' + actor)
        self.data['actors'][actor]['wallPlacement'] = {'requested': [WALL_X, y, FLOOR_Z], 'observed': measured}
        self.papyrus('Actor', 'UnequipAll', [], 'none', reference, write=True)
        audit = self.audit(actor)
        self.data['rawAudits'][actor] = {'human': audit}
        self.save()
        verify_human(audit, pair)
        if role == 'Wolf':
            self.unequip(actor, pair['inventory'], remove=True)

    def transform(self, index, pair):
        human, wolf = (tag(index, role) for role in ROLES)
        self.session.state['activeSemanticCommandId'] = 'preview-transform-' + wolf
        self.mutate('transform ' + wolf, lambda: self.bindings.guarded_call(self.session,
            {'bindingId': 'morph_race', 'self': self.spec(wolf), 'args': [WOLF_RACE]}, self.deadline(), self.policy))
        self.unequip(wolf, pair['inventory'], remove=False)
        self.poll(lambda: self.claw(wolf, 'GetStatus', 'int'), lambda value: value == 2, 10, 'No live CLAW body')
        automatic = self.poll(lambda: self.claw(wolf, 'GetAppliedCoatPattern'), bool, 12, 'No automatic coat bound')
        require(self.claw(wolf, 'GetCoatPattern') == '', 'Unexpected manual coat on ' + wolf)
        audit = self.audit(wolf)
        self.data['rawAudits'][wolf]['automatic'] = audit
        self.data['pairs'][pair['name']] = {'tags': [human, wolf], 'human': self.spec(human), 'wolf': self.spec(wolf),
            'automaticPattern': automatic, 'automaticStatus': self.claw(wolf, 'GetCoatPatternStatus')}
        self.save()
        inspect_regions(audit, pair, expected_paths(self.appearance, automatic))
        if self.fixed is not None:
            require(self.claw(wolf, 'SetCoatPattern', 'bool', self.fixed, write=True) is True, 'Fixed coat refused')
            self.poll(lambda: self.claw(wolf, 'GetAppliedCoatPattern'), lambda value: value == self.fixed,
                      12, 'Fixed coat did not bind')
            self.poll(lambda: self.claw(wolf, 'GetCoatPattern'), lambda value: value == self.fixed,
                      4, 'Fixed override was not acknowledged')
        for role in ROLES:
            self.place(tag(index, role), pair[role.lower() + 'Y'], pin=True)

    def view(self, references):
        return self.tool('inspect', {'kind': 'world_observer', 'refs': list(references), 'actors': True})

    def layout(self):
        self.pose(PLAYER, CAMERA, 270.)
        row = [self.spec(actor)['reference'] for _, _, actor, _, _ in actors(self.pairs)]
        refs = [PLAYER, *row]
        previous = {}

        def stable(sample):
            nonlocal previous
            observed = {entry['identity']['form']: entry['position'] for entry in sample.get('refs', [])
                        if entry.get('loaded3D') is True and entry.get('status') == 'available'
                        and entry.get('cellForm') == CELL}
            prior, previous = previous, observed
            if not sample.get('ok') or set(observed) != set(refs) or observed.keys() != prior.keys():
                return False
            y = [observed[ref][1] for ref in row]
            return (math.dist(observed[PLAYER], CAMERA) <= 4. and 1488. <= y[0] < y[-1] <= 2000.
                    and all(b - a >= 55. for a, b in zip(y, y[1:]))
                    and all(-2775. <= observed[ref][0] <= -2600. and abs(observed[ref][2] - FLOOR_Z) <= 4. for ref in row)
                    and all(math.dist(prior[ref], observed[ref]) <= 2. for ref in refs))

        return self.poll(lambda: self.view(refs), stable, 10, 'Actors and camera did not settle in QASmoke')

    def sample(self, label):
        groups = []
        for index, pair in enumerate(self.pairs):
            wolf = tag(index, 'Wolf')
            selected = self.fixed or self.data['pairs'][pair['name']]['automaticPattern']
            earlier = self.data['rawAudits'][wolf]
            audit = self.audit(wolf)
            earlier_audits = [earlier[key] for key in ('automatic', 'first') if key in earlier]
            if earlier_audits:
                require(int(audit['sample']) > int(earlier_audits[-1]['sample']), 'Replayed material sample: ' + wolf)
            earlier[label] = audit
            self.save()
            groups.append(inspect_regions(audit, pair, expected_paths(self.appearance, selected)))
        self.data[label] = compare_pairs(groups, self.pairs) if self.fixed else groups
        self.save()

    def release_crosshair(self):
        def target():
            raw = self.tool('papyrus', {'action': 'call', 'script': 'Game', 'function': 'GetCurrentCrosshairRef', 'args': []})
            require(raw.get('called') is True and 'returned' in raw
                    and raw.get('returnedType', '').casefold() in ('none', 'objectreference'), 'Crosshair read unavailable')
            return raw['returned']

        if target() is not None:
            self.papyrus('ObjectReference', 'SetAngle', [-75., 0., 90.], 'none', PLAYER, write=True)
        consecutive = 0

        def released(value):
            nonlocal consecutive
            consecutive = consecutive + 1 if value is None else 0
            return consecutive == 2

        self.poll(target, released, 5, 'Crosshair retained its target before shutdown')

    def run(self, *, preview):
        self.session.phase('Prepare four regional coat pairs', 317 + self.dwell)
        player = self.view([PLAYER])
        require(player.get('ok') is True and any(row.get('identity', {}).get('form') == PLAYER
                and row.get('cellForm') == CELL for row in player.get('refs', [])), 'QASmoke bootstrap required')
        for entry in actors(self.pairs):
            self.create(*entry)
        for index, pair in enumerate(self.pairs):
            self.transform(index, pair)
        for _, _, actor, _, y in actors(self.pairs):
            self.place(actor, y)
        self.data['layout'] = self.layout()
        self.sample('first')
        if self.dwell > 3:
            # Refresh the inherited runner phase during longer, passive observation waits.
            stop = time.monotonic() + self.dwell
            while (remaining := stop - time.monotonic()) > 0:
                self.session.phase('Wait for regional coat material follow-up', 40)
                time.sleep(min(remaining, 4.))
        else:
            time.sleep(self.dwell)
        self.sample('afterDwell')
        if not preview:
            self.release_crosshair()
        self.data['status'] = 'READY_FOR_MANUAL_INSPECTION' if preview else 'MATERIAL_CHECK_COMPLETE'
        self.save()
        while preview and self.native.alive(self.game):
            self.session.phase('CLAW regional coat scene is ready for review', 100)
            time.sleep(4.)
        return self.data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'preview', 'check'))
    parser.add_argument('--config', required=True, type=Path, help='Prepared isolated TEST SE Autotest configuration')
    parser.add_argument('--profile', required=True, help='Prepared source profile for the disposable clone')
    parser.add_argument('--scenario', required=True, type=Path, help='Read-only QASmoke bootstrap with the qualified save pins')
    parser.add_argument('--appearance', required=True, type=Path, help='Effective candidate CoatMapping.xml / CoatLibrary.xml directory')
    parser.add_argument('--coat-mode', choices=('fixed', 'automatic'), default='fixed')
    parser.add_argument('--dwell', type=int, choices=range(3, 121), metavar='SECONDS', default=3,
                        help='Passive wait (3–120 seconds) between the two material audits')
    args = parser.parse_args()

    from skyrim_autotest import cli, scenarios

    palette = json.loads(PALETTE.read_bytes())
    session_policy(json.loads(args.config.read_bytes()), palette)
    expected_paths(args.appearance, palette['fixedCoat'])
    scenario = json.loads(args.scenario.read_bytes())
    scenarios.validate(scenario)
    require(scenario.get('cell') == 'QASmoke' and scenario.get('fixture') and len(scenario['steps']) == 1
            and scenario['steps'][0].get('tool') == 'platform'
            and scenario['steps'][0].get('args') == {'operation': 'state.read'}
            and scenario['steps'][0].get('assert') == [{'path': 'world.ready', 'equals': True}],
            'Expected the read-only QASmoke bootstrap scenario')
    config_arg, profile_arg = ['--config', str(args.config)], ['--profile', args.profile]
    if args.mode == 'preflight':
        return cli.main([*config_arg, 'preflight', *profile_arg])

    original_execute = scenarios.execute

    def execute(session, admitted_scenario):
        require(admitted_scenario == scenario, 'Bootstrap changed after admission')
        original_execute(session, admitted_scenario)
        RegionalScene(session, palette, args.appearance, args.coat_mode, args.dwell).run(preview=args.mode == 'preview')

    # The runner imports execute at the point of use. Keep the adapter local to this invocation.
    with patch.object(scenarios, 'execute', execute):
        return cli.main([*config_arg, 'run', *profile_arg, '--scenario', str(args.scenario)])


if __name__ == '__main__':
    raise SystemExit(main())
