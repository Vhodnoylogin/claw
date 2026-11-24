"""Photograph matched human skin and hair references in the QASmoke bay."""

import math
import time

from coat_regional_readback import luma, verify_human
from coat_regional_scene import CELL, FLOOR_Z, PLAYER, WALL_X, require, tag
from coat_scene_capture import capture_game_frame
from publicity_se_scene import SCENE, PublicityScene, load_scene


HUMAN_SCENE = SCENE.with_name('human-scene.json')


def human_palette():
    _, palette = load_scene(HUMAN_SCENE)
    subjects = {pair['id']: pair for pair in palette['pairs']}
    require(len(subjects) == len(palette['pairs']) == 9, 'Expected nine distinct portrait subjects')
    skin = [subjects[identifier] for identifier in palette['groups']['skin']]
    brightness = [luma(pair['skinRecordRGB8']) for pair in skin]
    require(len(skin) == 5 and len({tuple(pair['hair']) for pair in skin}) == 1
            and all(left > right for left, right in zip(brightness, brightness[1:])), 'Skin controls differ')
    for group, size in (('hairMediumSkin', 3), ('hairLightSkin', 2)):
        hair = [subjects[identifier] for identifier in palette['groups'][group]]
        require(len(hair) == size and len({tuple(pair['hair']) for pair in hair}) == size
                and len({tuple(pair['skinRecordRGB8']) for pair in hair}) == 1, 'Hair controls differ: ' + group)
    return palette


class PublicityHumanPalette(PublicityScene):
    def __init__(self, session, appearance, *, mode='single-fill'):
        palette = human_palette()
        super().__init__(session, appearance, HUMAN_SCENE)
        self.path = session.dir / 'claw-human-palette.json'
        require(not self.path.exists() and mode in self.lighting['modes'], 'Expected a fresh portrait scene and known lighting')
        self.mode = mode
        self.data.update(groups=palette['groups'], portraits={})

    def lights_disabled(self):
        return [self.papyrus('ObjectReference', 'IsDisabled', [], 'bool', ref) for ref in self.fill_refs]

    def set_lights(self, flags):
        for ref, off, was_off in zip(self.fill_refs, flags, self.lights_disabled(), strict=True):
            if off != was_off:
                action = 'DisableNoWait' if off else 'EnableNoWait'
                self.papyrus('ObjectReference', action, [False], 'none', ref, write=True)
        self.poll(self.lights_disabled, lambda current: current == flags, 5., 'The portrait lighting did not settle')

    def photograph_human(self, index, pair, light_flags):
        self.session.phase('Photograph human input colours: ' + pair['name'], 70)
        actor = tag(index, 'Human')
        self.create(pair, 'Human', actor, (110., -220.), pair['humanY'])
        reference = self.spec(actor)['reference']
        self.papyrus('Actor', 'SetRestrained', [True], 'none', reference, write=True)
        self.papyrus('Actor', 'SetHeadTracking', [False], 'none', reference, write=True)
        position = (WALL_X, pair['humanY'], FLOOR_Z)
        heading = 75.
        self.papyrus('ObjectReference', 'SetAngle', [0., 0., heading], 'none', reference, write=True)

        def settled(sample):
            rows = {row['identity']['form']: row for row in sample.get('refs', [])}
            return all(ref in rows and rows[ref].get('loaded3D') and rows[ref].get('cellForm') == CELL
                       and math.dist(rows[ref]['position'], mark) < 5.
                       for ref, mark in ((PLAYER, self.camera), (reference, position)))

        require(self.guard(actor)['actor']['race'] == pair['race'], 'Portrait subject is no longer human')
        camera = self.read_camera()
        label = f'human-{index + 1:02}-{pair["id"]}'
        for attempt in range(1, 4):
            before = self.audit(actor)
            colours = verify_human(before, pair)
            # The animation controller can still move the actor after a turn.
            # Reapply the standing mark immediately before capture.
            self.papyrus('ObjectReference', 'SetPosition', list(position), 'none', reference, write=True)
            observations = self.poll(lambda: self.view([PLAYER, reference]), settled, 8., 'Portrait subject left the mark')
            require(self.lights_disabled() == light_flags and not self.read_hud(), 'Portrait lighting or HUD changed')
            path = self.session.dir / f'{label}-attempt-{attempt}.png'
            frame = capture_game_frame(self.native, self.game, path)
            after_pose = self.view([PLAYER, reference])
            after = self.audit(actor)
            require(int(after['sample']) > int(before['sample']) and verify_human(after, pair) == colours,
                    'Human portrait material sample or colour changed during capture')
            require(self.read_camera() == camera and self.lights_disabled() == light_flags and not self.read_hud(),
                    'Portrait camera, lighting or HUD changed during capture')
            if settled(after_pose) and after['modelGeneration'] == before['modelGeneration']:
                final = self.session.dir / (label + '.png')
                path.rename(final)
                self.data['frames'][label] = dict(frame, path=str(final), markAttempt=attempt)
                break
            self.data.setdefault('rejectedPortraits', {}).setdefault(label, []).append({
                'frame': frame, 'position': after_pose, 'generationBefore': before['modelGeneration'],
                'generationAfter': after['modelGeneration'],
            })
            self.save()
        else:
            raise RuntimeError(f'Portrait {label} did not keep the same mark and model across three frames')
        self.data['portraits'][label] = {'id': pair['id'], 'name': pair['name'], 'base': pair['base'],
                                         'reference': reference, 'skinLabel': pair['skinLabel'],
                                         'hairLabel': pair['hairLabel'], **colours, 'lighting': self.mode}
        self.data['positions'][label] = {'heading': heading, 'camera': camera, 'observed': observations,
                                         'afterCapture': after_pose}
        self.data['rawAudits'][actor][label] = {'before': before, 'after': after}
        self.papyrus('ObjectReference', 'DisableNoWait', [False], 'none', reference, write=True)
        self.save()

    def run(self):
        self.session.phase('Prepare fixed human portrait camera and lighting', 60)
        light_ids = self.lighting['references']
        self.fill_refs = [self.papyrus('Game', 'GetFormFromFile', [local, self.lighting['plugin']], 'form')['formId']
                          for local in light_ids]
        require(len(set(self.fill_refs)) == len(light_ids), 'Expected distinct inspection fills')
        original_lights = self.lights_disabled()
        flags = [local not in self.lighting['modes'][self.mode] for local in light_ids]
        require(self.view([PLAYER]).get('ok') is True, 'QASmoke view unavailable')
        require(self.tool('camera', {'action': 'get'}).get('freeCam') is False, 'Foreign free camera is active')
        self.pose(PLAYER, self.camera, 270.)
        original_hud = self.read_hud()
        self.set_camera(action='freecam', on=True)
        try:
            self.set_camera(action='drive', **self.camera_drive)
            self.set_hud(False)
            self.set_lights(flags)
            self.data['lighting'] = {'mode': self.mode, 'fills': dict(zip(self.fill_refs, flags, strict=True))}
            self.save()
            time.sleep(1.)
            for index, pair in enumerate(self.pairs):
                self.photograph_human(index, pair, flags)
            self.release_crosshair()
        finally:
            if not self.data['unknownMutation']:
                self.set_lights(original_lights)
                self.set_hud(original_hud)
                self.set_camera(action='freecam', on=False)
        self.data['status'] = 'CAPTURE_COMPLETE'
        self.save()
        return self.data
