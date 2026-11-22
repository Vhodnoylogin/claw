"""Verify the actual isolated player outfit and reject a bad sex route."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from stage_player_armor import PLUGIN, verify_record
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
