"""Verify the actual isolated player outfit and reject a bad sex route."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from stage_player_armor import PLUGIN, verify_record, world_ear_path
from stage_world_motion_markers import Nif, PLAYER_ARMOR_MARKERS, PLAYER_WORLD_MARKERS, motion, node_children
from vr_dispatch import LEGACY_ALIAS, ROOT, SEXES, resource_paths


@unittest.skipUnless(os.getenv('CLAW_VR_PLAYER_ARMOR_ROOT'), 'Explicit built player outfit required')
class PlayerArmorArchiveTests(unittest.TestCase):
    def test_two_local_forms_and_both_static_model_families(self):
        root = Path(os.environ['CLAW_VR_PLAYER_ARMOR_ROOT'])
        esp = root / PLUGIN
        layout = verify_record(esp)
        self.assertEqual(layout['slot'], 32)
        self.assertNotEqual(layout['declaredModels']['male'], layout['declaredModels']['female'])
        expected = {PLUGIN, *(resource_paths(sex, endpoint) for sex in SEXES for endpoint in (None, 0, 1))}
        with ZipFile(esp.with_suffix('.zip')) as archive:
            names = archive.namelist()
            self.assertCountEqual(names, expected)
            self.assertNotIn(LEGACY_ALIAS, names)
            self.assertEqual(archive.read(PLUGIN), esp.read_bytes())
            for sex in SEXES:
                low, high = (archive.read(resource_paths(sex, weight)) for weight in (0, 1))
                self.assertEqual(low, high)

    def test_wrong_world_or_first_person_sex_resource_is_refused(self):
        original = (Path(os.environ['CLAW_VR_PLAYER_ARMOR_ROOT']) / PLUGIN).read_bytes()
        route = b'\\male\\Body_1.nif'
        self.assertEqual(original.count(route), 2)
        with TemporaryDirectory() as scratch:
            changed = Path(scratch) / PLUGIN
            for index in (original.index(route), original.rindex(route)):
                updated = route.replace(b'male', b'mole')
                changed.write_bytes(original[:index] + updated + original[index + len(route):])
                with self.assertRaisesRegex(ValueError, 'both views'):
                    verify_record(changed)

    def test_markers_change_only_the_scene_root_and_append_one_empty_node(self):
        source = Path(os.environ['CLAW_VR_COMPONENT_ROOT']) / 'resources'
        trial = Path(os.environ['CLAW_VR_PLAYER_ARMOR_ROOT'])
        receipt = json.loads((trial / 'player-body32.json').read_bytes())
        self.assertEqual(receipt['markers'], PLAYER_ARMOR_MARKERS)
        with ZipFile((trial / PLUGIN).with_suffix('.zip')) as archive:
            for sex, token in PLAYER_ARMOR_MARKERS.items():
                link = resource_paths(sex)
                self.assertEqual(archive.read(link), (source / link).read_bytes())
                for endpoint in (0, 1):
                    asset = resource_paths(sex, endpoint)
                    before = Nif((source / asset).read_bytes())
                    after = Nif(archive.read(asset))
                    added = len(before.blocks)
                    self.assertEqual(after.footer, before.footer)
                    self.assertEqual(after.blocks[1:added], before.blocks[1:])
                    self.assertEqual(len(after.blocks), added + 1)
                    self.assertEqual(after.kind(added), 'NiNode')
                    self.assertEqual(after.strings, [*before.strings, ('CLAW_VR_DISPATCH_PROBE_' + token).encode()])
                    root_offset, children = node_children(before.blocks[0])
                    _, after_children = node_children(after.blocks[0])
                    self.assertEqual(after_children, [*children, added])
                    prefix, end = root_offset, root_offset + 4 + 4 * len(children)
                    self.assertEqual(after.blocks[0][:prefix], before.blocks[0][:prefix])
                    self.assertEqual(after.blocks[0][end + 4:], before.blocks[0][end:])
                    self.assertEqual(node_children(after.blocks[added])[1], [])


@unittest.skipUnless(os.getenv('CLAW_VR_PLAYER_WORLD_EAR_ROOT'), 'Explicit built world-ear outfit required')
class PlayerWorldEarArchiveTests(unittest.TestCase):
    def test_only_world_routes_get_the_optional_motion_binding(self):
        root = Path(os.environ['CLAW_VR_PLAYER_WORLD_EAR_ROOT'])
        esp = root / PLUGIN
        pack = motion.open_tools(ROOT / 'src/main/python/build-tools/package-source-build.py')
        archive = pack.read_zip(esp.with_suffix('.zip').read_bytes())
        addon = pack.read_zip((root / (esp.stem + ' - World FSMP.zip')).read_bytes())
        records = verify_record(esp, visible_ears=True)
        self.assertEqual(len(archive), 11)
        self.assertEqual(len(addon), 4)
        self.assertNotIn(LEGACY_ALIAS, archive | addon)
        for sex in SEXES:
            world = world_ear_path(sex, '.nif')
            first = resource_paths(sex, 1)
            xml = pack.MOTION_XML + sex.title() + '.xml'
            self.assertEqual(records['declaredWorldModels'][sex], world.removeprefix('Meshes/').replace('/', '\\'))
            self.assertEqual(records['declaredModels'][sex], first.removeprefix('Meshes/').replace('/', '\\'))
            self.assertEqual(set(addon) & set(archive) & {world, first}, {world})
            self.assertIn(world_ear_path(sex, '.tri'), archive)
            self.assertNotIn(world_ear_path(sex, '.tri'), addon)
            static = Nif(archive[world])
            first_view = Nif(archive[first])
            self.assertIn(('CLAW_VR_DISPATCH_PROBE_' + PLAYER_WORLD_MARKERS[sex]).encode(), static.strings)
            self.assertIn(('CLAW_VR_DISPATCH_PROBE_' + PLAYER_ARMOR_MARKERS[sex]).encode(), first_view.strings)
            self.assertNotIn(pack.FSMP_HOOK, first_view.strings)
            self.assertNotIn(pack.FSMP_HOOK, static.strings)
            self.assertEqual(motion.fsmp_motion.bind_nif(archive[world], xml)[0], addon[world])
            self.assertEqual(motion.fsmp_motion.render_xml(sex == 'female'), addon[xml])

    def test_swapped_world_path_cannot_confirm_the_compiled_armor(self):
        esp = Path(os.environ['CLAW_VR_PLAYER_WORLD_EAR_ROOT']) / PLUGIN
        payload = esp.read_bytes()
        route = b'\\male\\EarWorldTrial.nif'
        self.assertEqual(payload.count(route), 1)
        with TemporaryDirectory() as scratch:
            wrong = Path(scratch) / PLUGIN
            wrong.write_bytes(payload.replace(route, route.replace(b'male', b'mole')))
            with self.assertRaisesRegex(ValueError, 'both views'):
                verify_record(wrong, visible_ears=True)
