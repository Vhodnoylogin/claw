"""Prepared real-artifact PlayerOnly checks; no installation or game execution.

Required environment inputs: CLAW_PLAYERONLY_PACKAGE, CLAW_PLAYERONLY_BASELINE,
CLAW_PLAYERONLY_ELEGANT_ARCHIVE, CLAW_PLAYERONLY_PYNIFLY and
CLAW_PLAYERONLY_NATIVE_DLL. Missing real inputs
fail rather than using synthetic geometry. The positive resource selection is
Default/Timber/Yellow; an inventory of other upstream FOMOD choices is separate.
"""
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def required_path(name):
    path = Path(os.environ[name]).resolve(strict=True)
    if not path.exists():
        raise ValueError('Missing prepared resource: ' + name)
    return path


class PlayerOnlyResourceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package_path = required_path('CLAW_PLAYERONLY_PACKAGE')
        cls.baseline_path = required_path('CLAW_PLAYERONLY_BASELINE')
        cls.elegant_path = required_path('CLAW_PLAYERONLY_ELEGANT_ARCHIVE')
        cls.native_data = required_path('CLAW_PLAYERONLY_NATIVE_DLL').read_bytes()
        addon = required_path('CLAW_PLAYERONLY_PYNIFLY')
        sys.path.insert(0, str(addon))
        from pyn import pynifly
        cls.api = pynifly
        cls.api.NifFile.Load(str(addon / 'NiflyDLL.dll'))
        cls.trip = module('claw_playeronly_integration_trip', addon / 'tri/tripfile.py')
        cls.package = module('claw_playeronly_integration_package',
            ROOT / 'src/main/python/build-tools/package-source-build.py')
        cls.materials = module('claw_playeronly_integration_materials',
            ROOT / 'src/main/python/build-tools/player_only_materials.py')
        with zipfile.ZipFile(cls.package_path) as archive:
            cls.files = {name: archive.read(name) for name in archive.namelist()}
        with zipfile.ZipFile(cls.baseline_path) as archive:
            cls.baseline = {name: archive.read(name) for name in archive.namelist()}
        cls.selections = cls.package.selection_audit(cls.files)
        target = ROOT / 'target/test-player-only-resources'
        target.mkdir(parents=True, exist_ok=True)
        cls.temporary = tempfile.TemporaryDirectory(dir=target)
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.temp = Path(cls.temporary.name)

    def materialized(self, name, data):
        path = self.temp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_twenty_choices_install_all_endpoint_aliases_without_extra_mesh_payload(self):
        self.assertEqual(len(self.selections), 20)
        self.assertEqual(len([name for name in self.files if name.lower().endswith('.nif')]),
                         len([name for name in self.baseline if name.lower().endswith('.nif')]))
        self.assertFalse(any(name.lower().endswith('.dds') or data.startswith(b'DDS ')
                             for name, data in self.files.items()))
        self.assertEqual(json.loads(self.files['00 Base/RandomElegantWerewolves_MS.json']), [])
        for choice in self.selections:
            self.assertEqual(choice['runtimeFiles'], 20 if choice['obody'] else 18)
            installed = {row['path']: row['source'] for row in choice['files']}
            for sex in ('male', 'female'):
                for endpoint in (0, 1):
                    alias = MESH + sex + f'PlayerWerewolf_{endpoint}.nif'
                    normal = MESH + sex + f'bodywerewolf_{endpoint}.nif'
                    self.assertEqual(installed[alias], installed[normal])
        for name, original in self.baseline.items():
            if name.lower().endswith('.dll'):
                self.assertEqual(self.files[name], self.native_data, name)
            elif name.lower().endswith(('.tri', '.esp', '.pex')):
                self.assertEqual(self.files[name], original, name)

    def test_independent_reader_preserves_actual_shapes_skin_uvs_head_and_matching_tri(self):
        installed = {row['path']: row['source'] for row in self.selections[0]['files']}
        for sex, morph_count in (('male', 30), ('female', 31)):
            source = '00 Base/' + MESH + sex + 'bodywerewolf_0.nif'
            original = self.api.NifFile(str(self.materialized('baseline/' + sex + '.nif', self.baseline[source])))
            original_shapes = {shape.name: shape for shape in original.shapes}
            tri_path = self.materialized('tri/' + sex + '.tri', self.files['00 Base/' + MESH + sex + 'bodywerewolf.tri'])
            trip = self.trip.TripFile()
            with tri_path.open('rb') as stream:
                self.assertEqual(trip.read(stream), 0)
            self.assertTrue(trip.is_valid)
            self.assertEqual(set(trip.shapes), set(original_shapes))
            self.assertEqual(len({name for shapes in trip.shapes.values() for name in shapes}), morph_count)
            for route in ('bodywerewolf', 'PlayerWerewolf'):
                for endpoint in (0, 1):
                    destination = MESH + sex + route + f'_{endpoint}.nif'
                    path = self.materialized('installed/' + destination, self.files[installed[destination]])
                    actual = self.api.NifFile(str(path))
                    self.assertEqual({shape.name for shape in actual.shapes}, set(original_shapes))
                    for shape in actual.shapes:
                        before = original_shapes[shape.name]
                        self.assertEqual(shape.id, before.id)
                        self.assertEqual(bytes(shape.properties), bytes(before.properties))
                        self.assertEqual(shape.verts, before.verts)
                        self.assertEqual(shape.tris, before.tris)
                        self.assertEqual(shape.uvs, before.uvs)
                        self.assertEqual(shape.normals, before.normals)
                        self.assertEqual(shape.bone_names, before.bone_names)
                        self.assertEqual(shape.bone_weights, before.bone_weights)
                        self.assertEqual({p.id for p in shape.partitions}, {32})
                        self.assertEqual([(e.name, e.string_data) for e in shape.extra_data('NiStringExtraData')],
                                         [('BODYTRI', 'actors\\werewolfbeast\\character assets\\' + sex + 'bodywerewolf.tri')])
                        self.assertEqual({k: v for k, v in shape.textures.items() if k != 'Diffuse'},
                                         {k: v for k, v in before.textures.items() if k != 'Diffuse'})
                        for morph, deltas in trip.shapes[shape.name].items():
                            self.assertEqual(len({index for index, _ in deltas}), len(deltas))
                            self.assertTrue(all(0 <= index < len(shape.verts) and
                                all(math.isfinite(value) for value in delta) for index, delta in deltas))

    def test_real_resource_adapter_is_idempotent_and_rejects_corrupt_or_mixed_materials(self):
        name = '00 Base/' + MESH + 'malebodywerewolf_0.nif'
        actual = self.files[name]
        self.assertEqual(self.materials.adapt_nif(actual)[0], actual)
        with self.assertRaisesRegex(ValueError, 'little-endian SSE'):
            self.materials.adapt_nif(b'Badbryo' + self.baseline[name][7:])
        with self.assertRaises(ValueError):
            self.materials.adapt_nif(self.baseline[name][:-1])
        # Real texture-set sized strings are changed through their parsed slots,
        # then the reconstructed block directory carries the correct sizes.
        prefix, middle, types, indices, blocks, footer = self.materials.container(self.baseline[name])
        import struct
        for index, block in enumerate(blocks):
            if types[indices[index]] == 'BSShaderTextureSet':
                slots = self.materials.texture_slots(block)
                if slots[0].lower().endswith(b'\\body.dds'):
                    slots[0] = slots[0][:-8] + b'playerbody.dds'
                    blocks[index] = struct.pack('<I', 9) + b''.join(
                        struct.pack('<I', len(slot)) + slot for slot in slots)
                    break
        mixed = prefix + struct.pack('<' + str(len(blocks)) + 'I', *map(len, blocks)) + middle + b''.join(blocks) + footer
        with self.assertRaisesRegex(ValueError, 'mixed Main/PlayerOnly'):
            self.materials.adapt_nif(mixed)

    def test_normal_timbersinglecoat_and_randomized_fomod_paths_supply_actual_materials(self):
        sevenzip = os.environ.get('CLAW_PLAYERONLY_SEVENZIP', 'C:/Program Files/7-Zip/7z.exe')
        listing = subprocess.check_output([sevenzip, 'l', '-slt', str(self.elegant_path)],
                                          encoding='utf-8', errors='strict')
        entries = {}
        module_path = None
        for block in listing.split('\n\n'):
            row = dict(line.split(' = ', 1) for line in block.splitlines() if ' = ' in line)
            name = row.get('Path', '')
            if name.lower().endswith('fomod\\moduleconfig.xml'):
                module_path = name
            if 'Size' in row and row.get('Attributes', '') != 'D':
                entries[name] = int(row['Size'])
        self.assertIsNotNone(module_path)
        config = ET.fromstring(subprocess.check_output([sevenzip, 'x', '-so', str(self.elegant_path), module_path]))
        root_name = module_path.rsplit('\\fomod\\', 1)[0] + '\\'
        selected = {'Introduction': 'Intro', 'Mesh Choice': 'Default', 'Pattern': 'Timber', 'Eyes': 'Yellow'}
        for randomized in (False, True):
            with self.subTest(randomized=randomized):
                vfs = {}
                for step in config.findall('installSteps/installStep'):
                    for option in step.findall('.//plugin'):
                        chosen = selected.get(step.get('name')) == option.get('name')
                        chosen |= randomized and option.get('name') == 'Randomized Werewolves'
                        if not chosen:
                            continue
                        for folder in option.findall('files/folder'):
                            prefix = root_name + folder.get('source').rstrip('\\') + '\\'
                            for path, size in entries.items():
                                if path.casefold().startswith(prefix.casefold()):
                                    destination = folder.get('destination', '').rstrip('\\')
                                    target = (destination + '\\' if destination else '') + path[len(prefix):]
                                    vfs[target.replace('/', '\\').casefold()] = size
                self.assertIn('coopplayeronlywerewolf.esp', vfs)
                for name, data in self.files.items():
                    if not name.lower().endswith('.nif'):
                        continue
                    nif = self.api.NifFile(str(self.materialized('textures/' + Path(name).name, data)))
                    for shape in nif.shapes:
                        for texture in shape.textures.values():
                            if texture and '\\werewolf\\elegant\\' in texture.casefold():
                                self.assertIn(texture.replace('/', '\\').casefold(), vfs, texture)
                library = ET.fromstring(self.files['00 Base/SKSE/Plugins/CLAW/CoatLibrary.xml'])
                patterns = library.findall('Patterns/Pattern')
                self.assertEqual(len(patterns), 10)
                for pattern in patterns:
                    for texture in pattern.findall('Texture'):
                        path = texture.get('path').replace('/', '\\').casefold()
                        if randomized:
                            self.assertIn(path, vfs)
                        else:
                            self.assertNotIn(path, vfs)


if __name__ == '__main__':
    unittest.main()
