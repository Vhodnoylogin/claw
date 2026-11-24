"""Place and inspect the regional coat pairs in an owned Skyrim SE run."""

import argparse
import json
import math
from pathlib import Path
import time
from unittest.mock import patch

from coat_regional_readback import (
    compare_pairs, expected_paths, inspect_discrete_regions, inspect_regions, verify_human, verify_skin_only,
)
from coat_persistence_readback import require
from coat_scene_capture import capture_game_frame


PALETTE = Path(__file__).resolve().parents[2] / 'resources/inspection/regional-coats/pairs.json'
SKIN_PALETTE = PALETTE.with_name('skin-pairs.json')
PLAYER = '0x00000014'
WOLF_RACE = '0x000CDD84'
CELL = '0x00032AE7'  # QASmoke in Skyrim.esm
WALL_X, FLOOR_Z = -2697.94482421875, 6976.4501953125
CAMERA = (-2279.94482421875, 1740., FLOOR_Z)
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
            'The SE configuration must admit the fixture bases and the guarded morph_race binding')
    return policy


class RegionalScene:
    def __init__(self, session, palette, appearance, coat_mode, dwell, *, capture=False):
        from skyrim_autotest import fixture_actors, interactive_bindings, native
        from skyrim_autotest.runner import atomic_json

        self.session = session
        self.fixture, self.bindings = fixture_actors, interactive_bindings
        self.native = native
        self.atomic_json = atomic_json
        self.policy = session_policy(session.state['configuration'], palette)
        self.game = session.state['game']
        require(any(row['role'] == 'game' and row['identity'] == self.game for row in session.state['owned'])
                and native.identity(self.game['pid']) == self.game, 'Expected exact owned Skyrim process')
        self.pairs = palette['pairs']
        self.camera = palette.get('camera', CAMERA)
        self.review_views = palette.get('reviewViews', {}) if capture else {}
        self.skin_only = palette.get('comparison') == 'skin-only'
        self.coat_mode = coat_mode
        self.fixed = palette['fixedCoat'] if coat_mode == 'fixed' else None
        self.skin_coats = palette.get('skinCoats', {})
        self.hair_coats = palette.get('hairCoats', {})
        self.generated_coats = palette.get('generatedCoats', {})
        self.preselected = coat_mode in ('skin-pairs', 'harmonized')
        if coat_mode == 'harmonized':
            require(set(self.generated_coats) == {pair['base'] for pair in self.pairs}
                    and len(set(self.generated_coats.values())) == len(self.pairs),
                    'Expected one locally generated coat per fixture base')
        require(not self.skin_only or (coat_mode == 'harmonized' and len(self.pairs) == 5),
                'The five skin controls use locally generated harmonized coats')
        self.appearance = appearance
        self.dwell = dwell
        self.capture = capture
        self.prep_seconds = 307 + dwell + 25 * len(self.review_views)
        self.end = time.monotonic() + self.prep_seconds
        self.path = session.dir / 'claw-regional-scene.json'
        require(not self.path.exists() and not session.state.get('interactiveActorFixtures'),
                'Scene may only create actors once in a fresh run')
        self.data = {'run': session.state['id'], 'game': self.game, 'palette': palette,
                     'coatMode': coat_mode, 'dwellSeconds': dwell, 'actors': {}, 'pairs': {}, 'rawAudits': {},
                     'humanInputs': {},
                     'frames': {}, 'status': 'PREPARING', 'intent': None, 'unknownMutation': False}

    def save(self):
        self.atomic_json(self.path, self.data)

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

    def common_coat(self, pair):
        if self.coat_mode == 'skin-pairs':
            return self.skin_coats[rgb_key(pair['skinRecordRGB8'])]
        if self.coat_mode == 'harmonized':
            return self.generated_coats[pair['base']]
        return self.fixed

    def inspect_coat(self, audit, pair, pattern):
        skin_paths = expected_paths(self.appearance, pattern)
        if self.coat_mode == 'discrete':
            require(pattern == self.skin_coats[rgb_key(pair['skinRecordRGB8'])], 'Automatic skin coat differs from the fixture')
            hair_paths = expected_paths(self.appearance, self.hair_coats[rgb_key(pair['hair'])])
            return inspect_discrete_regions(audit, pair, skin_paths, hair_paths)
        if self.coat_mode == 'harmonized':
            return inspect_discrete_regions(audit, pair, skin_paths, skin_paths)
        return inspect_regions(audit, pair, skin_paths)

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
        self.data['humanInputs'][actor] = verify_human(audit, pair)
        if role == 'Wolf':
            self.unequip(actor, pair['inventory'], remove=True)

    def transform(self, index, pair):
        human, wolf = (tag(index, role) for role in ROLES)
        self.session.state['activeSemanticCommandId'] = 'preview-transform-' + wolf
        common = self.common_coat(pair)
        if self.preselected:
            require(self.claw(wolf, 'SetCoatPattern', 'bool', common, write=True) is True,
                    'Scene coat was refused before transformation')
        self.mutate('transform ' + wolf, lambda: self.bindings.guarded_call(self.session,
            {'bindingId': 'morph_race', 'self': self.spec(wolf), 'args': [WOLF_RACE]}, self.deadline(), self.policy))
        self.unequip(wolf, pair['inventory'], remove=False)
        self.poll(lambda: self.claw(wolf, 'GetStatus', 'int'), lambda value: value == 2, 10, 'No live CLAW body')
        row = self.data['pairs'][pair['name']] = {'tags': [human, wolf], 'human': self.spec(human), 'wolf': self.spec(wolf)}
        if not self.preselected:
            automatic = self.poll(lambda: self.claw(wolf, 'GetAppliedCoatPattern'), bool, 12, 'No automatic coat bound')
            require(self.claw(wolf, 'GetCoatPattern') == '', 'Unexpected manual coat on ' + wolf)
            audit = self.audit(wolf)
            self.data['rawAudits'][wolf]['automatic'] = audit
            row.update(automaticPattern=automatic, automaticStatus=self.claw(wolf, 'GetCoatPatternStatus'))
            self.inspect_coat(audit, pair, automatic)
        self.save()
        if common is not None:
            if not self.preselected:
                require(self.claw(wolf, 'SetCoatPattern', 'bool', common, write=True) is True, 'Fixed coat refused')
            self.poll(lambda: self.claw(wolf, 'GetAppliedCoatPattern'), lambda value: value == common,
                      12, 'Fixed coat did not bind')
            self.poll(lambda: self.claw(wolf, 'GetCoatPattern'), lambda value: value == common,
                      4, 'Fixed override was not acknowledged')
            row['commonCoat'] = common
        for role in ROLES:
            self.place(tag(index, role), pair[role.lower() + 'Y'], pin=True)

    def view(self, references):
        return self.tool('inspect', {'kind': 'world_observer', 'refs': list(references), 'actors': True})

    def layout(self, camera=None):
        camera = self.camera if camera is None else camera
        self.pose(PLAYER, camera, 270.)
        wall_row = sorted(actors(self.pairs), key=lambda entry: entry[-1])
        row = [self.spec(actor)['reference'] for _, _, actor, _, _ in wall_row]
        y_min, y_max = wall_row[0][-1] - 7., wall_row[-1][-1] + 15.
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
            return (math.dist(observed[PLAYER], camera) <= 4. and y_min <= y[0] < y[-1] <= y_max
                    and all(b - a >= 55. for a, b in zip(y, y[1:]))
                    and all(-2775. <= observed[ref][0] <= -2600. and abs(observed[ref][2] - FLOOR_Z) <= 4. for ref in row)
                    and all(math.dist(prior[ref], observed[ref]) <= 2. for ref in refs))

        return self.poll(lambda: self.view(refs), stable, 10, 'Actors and camera did not settle in QASmoke')

    def sample_materials(self, label):
        groups = []
        for index, pair in enumerate(self.pairs):
            wolf = tag(index, 'Wolf')
            selected = self.common_coat(pair) or self.data['pairs'][pair['name']]['automaticPattern']
            earlier = self.data['rawAudits'][wolf]
            audit = self.audit(wolf)
            prior = max(int(row['sample']) for row in earlier.values())
            require(int(audit['sample']) > prior, 'Replayed material sample: ' + wolf)
            earlier[label] = audit
            self.save()
            groups.append(self.inspect_coat(audit, pair, selected))
        self.data[label] = compare_pairs(groups, self.pairs) if self.coat_mode in ('fixed', 'skin-pairs') else groups
        self.save()

    def sample(self, label):
        if self.capture:
            bracket = label + 'BeforeFrame'
            self.sample_materials(bracket)
            self.data['frames'][label] = capture_game_frame(self.native, self.game, self.session.dir / (label + '.png'))
            self.save()
        self.sample_materials(label)
        if self.capture:
            for index, _ in enumerate(self.pairs):
                audits = self.data['rawAudits'][tag(index, 'Wolf')]
                require(audits[bracket]['modelGeneration'] == audits[label]['modelGeneration'],
                        'Wolf model changed during frame capture')

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
        self.session.phase(f'Prepare {len(self.pairs)} regional coat pairs', self.prep_seconds + 10)
        player = self.view([PLAYER])
        require(player.get('ok') is True and any(row.get('identity', {}).get('form') == PLAYER
                and row.get('cellForm') == CELL for row in player.get('refs', [])), 'QASmoke bootstrap required')
        for entry in actors(self.pairs):
            self.create(*entry)
        if self.skin_only:
            inputs = self.data['humanInputs']
            self.data['skinComparison'] = verify_skin_only([
                (inputs[tag(index, 'Human')], inputs[tag(index, 'Wolf')]) for index, _ in enumerate(self.pairs)
            ])
            self.save()
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
        if self.review_views:
            self.data['reviewLayouts'] = {}
            for label, camera in self.review_views.items():
                self.session.phase('Capture regional coat detail: ' + label, 40)
                self.data['reviewLayouts'][label] = self.layout(camera)
                self.sample(label)
            self.data['panoramaRestored'] = self.layout()
        if not preview:
            self.release_crosshair()
        self.data['status'] = 'READY_FOR_MANUAL_INSPECTION' if preview else 'MATERIAL_CHECK_COMPLETE'
        self.save()
        while preview and self.native.alive(self.game):
            self.session.phase('CLAW regional coat scene is ready for review', 100)
            time.sleep(4.)
        return self.data


def rgb_key(rgb):
    return ','.join(str(channel) for channel in rgb)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('preflight', 'preview', 'check'))
    parser.add_argument('--config', required=True, type=Path, help='Prepared isolated TEST SE Autotest configuration')
    parser.add_argument('--profile', required=True, help='Prepared source profile for the disposable clone')
    parser.add_argument('--scenario', required=True, type=Path, help='Read-only QASmoke bootstrap with the qualified save pins')
    parser.add_argument('--appearance', required=True, type=Path, help='Effective candidate CoatMapping.xml / CoatLibrary.xml directory')
    parser.add_argument('--palette', type=Path, default=PALETTE, help='Reusable scene palette and actor pairs')
    parser.add_argument('--coat-mode', choices=('fixed', 'skin-pairs', 'automatic', 'discrete', 'harmonized'), default='fixed')
    parser.add_argument('--generated-coats', type=Path, help='Local manifest of coat IDs keyed by fixture base')
    parser.add_argument('--capture', action='store_true', help='Capture an owned FHD game frame between material audits')
    parser.add_argument('--dwell', type=int, choices=range(3, 121), metavar='SECONDS', default=3,
                        help='Passive wait (3–120 seconds) between the two material audits')
    args = parser.parse_args()

    from skyrim_autotest import cli, scenarios

    palette = json.loads(args.palette.read_bytes())
    require(palette.get('comparison') != 'skin-only' or args.coat_mode == 'harmonized',
            'The skin-only palette requires harmonized coats')
    if args.coat_mode == 'harmonized':
        require(args.generated_coats is not None, 'The harmonized scene needs a generated coat manifest')
        coats = json.loads(args.generated_coats.read_bytes())
        require(isinstance(coats, dict) and set(coats) == {pair['base'] for pair in palette['pairs']}
                and all(isinstance(coat, str) and coat for coat in coats.values()),
                'Generated coat manifest does not match the scene')
        palette['generatedCoats'] = coats
        for coat in coats.values():
            expected_paths(args.appearance, coat)
    session_policy(json.loads(args.config.read_bytes()), palette)
    expected_paths(args.appearance, palette['fixedCoat'])
    groups = {'skinCoats': 'skinRecordRGB8', 'hairCoats': 'hair'}
    for palette_name, input_name in groups.items():
        if args.coat_mode == 'discrete' or (args.coat_mode == 'skin-pairs' and palette_name == 'skinCoats'):
            coats = palette[palette_name]
            require(set(coats) == {rgb_key(pair[input_name]) for pair in palette['pairs']} and len(set(coats.values())) == 2,
                    'Expected two distinct coats in ' + palette_name)
            for coat in coats.values():
                expected_paths(args.appearance, coat)
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
        RegionalScene(session, palette, args.appearance, args.coat_mode, args.dwell, capture=args.capture).run(
            preview=args.mode == 'preview')

    # The runner imports execute at the point of use. Keep the adapter local to this invocation.
    with patch.object(scenarios, 'execute', execute):
        return cli.main([*config_arg, 'run', *profile_arg, '--scenario', str(args.scenario)])


if __name__ == '__main__':
    raise SystemExit(main())
