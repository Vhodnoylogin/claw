"""Take reproducible 0.11.0 reference screenshots in a disposable SE session."""

import json
import math
from pathlib import Path
import time

from coat_regional_scene import CELL, FLOOR_Z, PLAYER, ROLES, WALL_X, RegionalScene, require, tag
from coat_regional_readback import SAME_HAIR, SAME_SKIN, expected_paths, inspect_discrete_regions
from coat_scene_capture import capture_game_frame


SCENE = Path(__file__).resolve().parents[2] / 'resources/inspection/publicity-se/scene.json'
HUD = {'menu': 'HUD Menu', 'path': '_root._visible'}


def load_scene(path=SCENE, *, black_gate=False):
    scene = json.loads(path.read_bytes())
    stage, morph = scene['stage'], scene['morphComparison']
    palette = json.loads((path.parent / scene['coatPalette']).read_bytes())
    palette['pairs'] = [
        dict(pair, humanY=stage['humanY'], wolfY=stage['wolfY']) for pair in palette['pairs']
    ]
    if black_gate:
        gate = scene['blackGate']
        inputs = json.loads((path.parent / gate['controlPalette']).read_bytes())['pairs']
        deep, = (pair for pair in inputs if pair['base'] == gate['controlBase'])
        pattern = gate['permittedPattern']
        key = ','.join(map(str, deep['hair']))
        require(palette['hairCoats'][key] == pattern, 'The published black hair control changed')
        palette['hairCoats'][key] = gate['hairFallback']
        palette['pairs'].append(dict(deep, humanY=stage['humanY'], wolfY=stage['wolfY'], permittedCoat=pattern))
    for family, entry in morph['families'].items():
        for label, neutral in (('baseline', True), ('expressive', False)):
            values = {side: dict.fromkeys(entry[side], 0.) if neutral else entry[side]
                      for side in ('human', 'wolf')}
            identity = {key: entry[key] for key in ('base', 'race', 'sex', 'inventory', 'weight', 'profile')}
            palette['pairs'].append(dict(identity, name=f'{family}-{label}', humanY=stage['humanY'],
                                         wolfY=stage['wolfY'], morphs=values))
    return scene, palette


def verify_coat_controls(groups, human):
    for name in groups[0]:
        values = [group[name] for group in groups]
        same, different = (SAME_SKIN, SAME_HAIR) if name == 'body' else (SAME_HAIR, SAME_SKIN)
        if name == 'body' or len(set(values)) > 1:
            require(all(values[a] == values[b] for a, b in same)
                    and all(values[a] != values[b] for a, b in different),
                    'Coat controls differ outside the expected input on ' + name)
    require(len({group['head'] for group in groups}) == 2, 'Hair colour did not change the head texture')
    for field, same, different in (('hairRGB8', SAME_HAIR, SAME_SKIN), ('skinRGB8', SAME_SKIN, SAME_HAIR)):
        require(all(human[a][field] == human[b][field] for a, b in same)
                and all(human[a][field] != human[b][field] for a, b in different),
                'Unexpected human colour controls for ' + field)


class PublicityScene(RegionalScene):
    def __init__(self, session, appearance, scene_path=SCENE, *, black_gate=False, subjects=None):
        scene, palette = load_scene(scene_path, black_gate=black_gate)
        if subjects is not None:
            names = set(subjects)
            palette['pairs'] = [pair for pair in palette['pairs'] if pair['name'] in names]
            require(names and len(palette['pairs']) == len(names), 'Publicity subject list does not match the fixture')
        super().__init__(session, palette, appearance, 'discrete', 3, capture=True)
        self.morph = scene['morphComparison']
        stage = scene['stage']
        self.camera = (stage['cameraX'], (stage['humanY'] + stage['wolfY']) / 2., FLOOR_Z)
        self.camera_drive = dict(x=self.camera[0], y=self.camera[1], z=stage['cameraZ'], pitch=0., yaw=math.tau * .75)
        self.lighting = stage['lighting']
        self.black_gate = black_gate
        self.data.update(morphChecks={}, positions={}, coatComparisons={}, lightingComparisons={})

    def prepare_human(self, pair, actor, audit):
        if 'morphs' not in pair:
            return super().prepare_human(pair, actor, audit)
        return self.write_morph_sources(pair, actor, initial=True)

    def write_morph_sources(self, pair, actor, *, initial=False):
        require(self.guard(actor)['actor']['race'] == pair['race'], 'The input actor is not human')
        reference = {'form': self.spec(actor)['reference']}
        key = self.morph['ownerKey']
        values = {}
        for name, value in pair['morphs']['human'].items():
            args = [reference, name, key]
            if initial:
                require(self.papyrus('NiOverride', 'HasBodyMorph', args, 'bool') is False,
                        'The scene-owned source morph is already present')
            self.papyrus('NiOverride', 'SetBodyMorph', [*args, value], 'none', write=True)
            measured = self.papyrus('NiOverride', 'GetBodyMorph', args, 'float')
            require(abs(measured - value) < 1e-6, 'RaceMenu human morph readback differs: ' + name)
            values[name] = measured
        self.papyrus('NiOverride', 'UpdateModelWeight', [reference], 'none', write=True)
        measured_weight = self.guard(actor)['actor']['weight']
        require(measured_weight == pair['weight'], 'The controlled NPC weight differs')
        return {'morphs': values, 'weight': measured_weight}

    def common_coat(self, pair):
        return self.morph['coat'] if 'morphs' in pair else None

    def inspect_coat(self, audit, pair, pattern):
        if 'morphs' in pair:
            paths = expected_paths(self.appearance, self.morph['coat'])
            return inspect_discrete_regions(audit, pair, paths, paths)
        if 'permittedCoat' in pair:
            require(pattern == pair['permittedCoat'], 'The dark skin and dark hair control did not retain black')
            paths = expected_paths(self.appearance, pattern)
            return inspect_discrete_regions(audit, pair, paths, paths)
        return super().inspect_coat(audit, pair, pattern)

    def verify_morphs(self, actor, pair):
        family = self.claw(actor, 'GetMorphFamily')
        require(family == pair['profile'], 'Unexpected live morph family: ' + family)
        reference = {'form': self.spec(actor)['reference']}
        measured = {}
        for name, value in pair['morphs']['wolf'].items():
            coefficient = self.claw(actor, 'GetOwnMorph', 'float', name)
            skee = self.papyrus('NiOverride', 'GetBodyMorph', [reference, name, 'CLAW.Distribution'], 'float')
            require(abs(coefficient - value) < 1e-5 and abs(skee - value) < 1e-5,
                    f'Wolf morph {name} differs from {value}: CLAW {coefficient}, SKEE {skee}')
            measured[name] = skee
        return {'family': family, 'coefficients': measured}

    def read_hud(self):
        value = self.tool('gfx', dict(HUD, op='get')).get('value')
        require(type(value) is bool, 'Actual HUD visibility is unavailable')
        return value

    def set_hud(self, value):
        self.mutate('Set HUD visibility', lambda: self.tool('gfx', dict(HUD, op='set', value=value)))
        require(self.read_hud() is value, 'HUD visibility did not change')

    def set_camera(self, **packet):
        result = self.mutate('Set photo camera', lambda: self.tool('camera', packet))
        require(result.get('action') == packet['action'] and result.get('queued') is False,
                'Camera operation did not complete')

    def read_camera(self):
        actual = self.tool('camera', {'action': 'get'})
        keys = ('camX', 'camY', 'camZ', 'camPitch', 'camYaw')
        require(actual.get('freeCam') is True
                and all(isinstance(actual.get(key), (int, float)) for key in keys)
                and math.dist([actual[key] for key in keys], list(self.camera_drive.values())) < .05,
                'Camera moved from the fixed comparison position')
        return {key: actual[key] for key in keys}

    def frame(self, label, pair, index, heading):
        names = [tag(index, role) for role in ROLES]
        references = [self.spec(name)['reference'] for name in names]
        positions = [(WALL_X, pair[role.lower() + 'Y'], FLOOR_Z) for role in ROLES]
        for reference in references:
            self.papyrus('ObjectReference', 'SetAngle', [0., 0., heading], 'none', reference, write=True)
        require(self.guard(names[0])['actor']['race'] == pair['race'], 'Human reference is no longer human')
        before = self.audit(names[1])
        selected = self.claw(names[1], 'GetAppliedCoatPattern')
        materials = self.inspect_coat(before, pair, selected)
        # Let the engine settle the turn before restoring the capture marks.
        # An actor's movement controller can displace it during a profile turn.
        for reference, position in zip(references, positions, strict=True):
            self.papyrus('ObjectReference', 'SetPosition', list(position), 'none', reference, write=True)

        def settled(sample):
            rows = {row['identity']['form']: row for row in sample.get('refs', [])}
            return all(ref in rows and rows[ref].get('loaded3D') and rows[ref].get('cellForm') == CELL
                       and math.dist(rows[ref]['position'], pos) < 5.
                       for ref, pos in zip([PLAYER, *references], [self.camera, *positions], strict=True))

        observations = self.poll(lambda: self.view([PLAYER, *references]), settled, 8, 'Subjects left the photo marks')
        require(self.read_hud() is False, 'HUD is visible before capture')
        camera = self.read_camera()
        self.data['frames'][label] = capture_game_frame(self.native, self.game, self.session.dir / (label + '.png'))
        after_pose = self.view([PLAYER, *references])
        require(settled(after_pose), 'Subjects moved during frame capture')
        self.data['positions'][label] = {'heading': heading, 'camera': camera,
                                         'observed': observations, 'afterCapture': after_pose}
        after = self.audit(names[1])
        require(after['modelGeneration'] == before['modelGeneration'] and int(after['sample']) > int(before['sample'])
                and self.inspect_coat(after, pair, selected) == materials and self.read_hud() is False
                and self.read_camera() == camera, 'Model, HUD or camera changed during frame capture')
        self.data['rawAudits'][names[1]][label] = {'before': before, 'after': after}
        self.save()
        return materials

    def lighting_refs(self):
        refs = {local: self.papyrus('Game', 'GetFormFromFile', [local, self.lighting['plugin']], 'form')['formId']
                for local in self.lighting['references']}
        require(len(set(refs.values())) == len(refs), 'Expected distinct inspection lights')
        return refs

    def lights_disabled(self, refs):
        return [self.papyrus('ObjectReference', 'IsDisabled', [], 'bool', ref) for ref in refs.values()]

    def set_lights_disabled(self, refs, flags):
        for ref, off, was_off in zip(refs.values(), flags, self.lights_disabled(refs), strict=True):
            if off != was_off:
                action = 'DisableNoWait' if off else 'EnableNoWait'
                self.papyrus('ObjectReference', action, [False], 'none', ref, write=True)
        return self.poll(lambda: self.lights_disabled(refs), lambda observed: observed == flags, 5.,
                         'Light state did not settle')

    def compare_lighting(self, pair, index, full_fill):
        refs = self.lighting_refs()
        original = self.lights_disabled(refs)
        require(not any(original), 'The full fill setup differs from the scene')
        try:
            for mode, enabled in self.lighting['modes'].items():
                self.session.phase('Capture the same wolf with ' + mode, 55)
                flags = [local not in enabled for local in refs]
                self.set_lights_disabled(refs, flags)
                time.sleep(1.0)
                label = f'lighting-{mode}'
                require(self.frame(label, pair, index, 90.) == full_fill, 'Coat changed with room lighting')
                self.data['lightingComparisons'][label] = {
                    'lights': list(refs.values()), 'disabled': self.lights_disabled(refs), 'coat': full_fill,
                }
                self.save()
        finally:
            if not self.data['unknownMutation']:
                self.set_lights_disabled(refs, original)

    def create_pair(self, index, pair):
        for side, role in enumerate(ROLES):
            actor = tag(index, role)
            lane = (110., -220. + 440. * side)
            self.create(pair, role, actor, lane, pair[role.lower() + 'Y'])
            reference = self.spec(actor)['reference']
            self.papyrus('Actor', 'SetRestrained', [True], 'none', reference, write=True)
            self.papyrus('Actor', 'SetHeadTracking', [False], 'none', reference, write=True)
        human, wolf = (tag(index, role) for role in ROLES)
        require(self.data['humanInputs'][human] == self.data['humanInputs'][wolf],
                'The wolf source and its still-human twin differ')

    def hide_pair(self, index):
        for role in ROLES:
            self.papyrus('ObjectReference', 'DisableNoWait', [False], 'none',
                         self.spec(tag(index, role))['reference'], write=True)

    def return_to_human(self, actor, pair):
        self.guard(actor)
        self.session.state['activeSemanticCommandId'] = 'preview-return-' + actor
        self.mutate('Return the wolf to human form', lambda: self.bindings.guarded_call(self.session,
            {'bindingId': 'morph_race', 'self': self.spec(actor), 'args': [pair['race']]}, self.deadline(), self.policy))
        self.poll(lambda: self.guard(actor)['actor']['race'], lambda race: race == pair['race'], 12.,
                  'The wolf did not return to human form')
        self.poll(lambda: self.claw(actor, 'GetStatus', 'int'), lambda status: status == 5, 12.,
                  'The human retained the old wolf morph state')

    def photograph(self):
        self.session.phase('Photograph the CLAW paired colour controls in QASmoke', self.prep_seconds)
        colours = [(i, p) for i, p in enumerate(self.pairs) if 'morphs' not in p]
        for index, pair in colours:
            self.session.phase('Photograph ' + pair['name'], 90)
            self.create_pair(index, pair)
            self.transform(index, pair)
            applied = self.frame(f'coat-{index + 1:02}', pair, index, 90.)
            self.data['coatComparisons'][pair['name']] = applied
            if index == 1:
                self.compare_lighting(pair, index, applied)
            self.hide_pair(index)
            self.save()

        controls = [(i, pair) for i, pair in colours if 'permittedCoat' not in pair]
        verify_coat_controls([self.data['coatComparisons'][pair['name']] for _, pair in controls],
                             [self.data['humanInputs'][tag(i, 'Human')] for i, _ in controls])

    def photograph_morphs(self, case):
        index, pair = next((i, p) for i, p in enumerate(self.pairs) if p['name'] == case and 'morphs' in p)
        self.session.phase('Photograph morphs ' + case, 110)
        self.preselected = True
        self.create_pair(index, pair)
        self.transform(index, pair)
        self.data['morphChecks'][case] = self.verify_morphs(tag(index, 'Wolf'), pair)
        for view, heading in (('front', 90.), ('profile', 0.)):
            self.frame(f'morph-{case}-{view}', pair, index, heading)
        self.hide_pair(index)
        self.save()

    def run(self, case):
        coat_case = 'black-gate' if self.black_gate else 'coat'
        require(case == coat_case or any(case == pair['name'] and 'morphs' in pair for pair in self.pairs),
                'Unknown photo case: ' + case)
        self.data['case'] = case
        require(self.view([PLAYER]).get('ok') is True, 'QASmoke view unavailable')
        require(self.tool('camera', {'action': 'get'}).get('freeCam') is False, 'Foreign free camera is active')
        self.pose(PLAYER, self.camera, 270.)
        original_hud = self.read_hud()
        self.set_camera(action='freecam', on=True)
        try:
            self.set_camera(action='drive', **self.camera_drive)
            self.set_hud(False)
            if case == coat_case:
                self.photograph()
            else:
                self.photograph_morphs(case)
            self.release_crosshair()
        finally:
            if not self.data['unknownMutation']:
                self.set_hud(original_hud)
                self.set_camera(action='freecam', on=False)
        self.data['status'] = 'CAPTURE_COMPLETE'
        self.save()
        return self.data
