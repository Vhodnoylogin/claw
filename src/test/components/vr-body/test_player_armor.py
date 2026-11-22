"""Verify the actual isolated player outfit and reject a bad sex route."""
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from stage_player_armor import PLUGIN, verify_record
from stage_world_motion_markers import Nif, PLAYER_ARMOR_MARKERS, node_children
from vr_dispatch import LEGACY_ALIAS, SEXES, resource_paths


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
