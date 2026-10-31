import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('claw_fur_colour_audit', Path(__file__).resolve().parents[4]/'src/main/python/build-tools/audit-fur-colour.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


class FurColourAuditTests(unittest.TestCase):
    def test_texture_identity_is_case_insensitive_but_rejects_path_escape(self):
        self.assertEqual(audit.texture_key(r'Textures\Actors\Fur.dds'), 'textures/actors/fur.dds')
        for value in ('../textures/x.dds', 'textures/../x.dds', 'C:/textures/x.dds', '/textures/x.dds', 'body.dds'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                audit.texture_key(value)

    def test_blend_layers_are_targets_and_eyes_mouth_anatomy_are_excluded(self):
        self.assertEqual(audit.role('ScalpFurBlend'), 'fur')
        self.assertEqual(audit.role('head'), 'skin')
        for name in ('eyes', 'mouth', 'claws', 'genitals'):
            self.assertEqual(audit.role(name), 'excluded')
        self.assertEqual(audit.role('fur_new'), 'unknown')

    def test_serialized_shared_shader_detected_and_not_actor_qualified(self):
        shapes = [{'name': name, 'shaderBlockId': 7, 'textureSetBlockId': 9, 'shaderType': 0}
                  for name in ('body', 'fur_back', 'claws')]
        summary = audit.material_summary(shapes)
        self.assertEqual(summary['targetCount'], 2)
        self.assertEqual(summary['alreadyTintCapableCount'], 0)
        self.assertEqual(summary['serializedSharedBlocks']['shaderBlockId'][0]['shapes'], ['body', 'fur_back', 'claws'])
        self.assertIn('Unknown', summary['runtimeMaterialIsolation'])
        with self.assertRaises(ValueError):
            audit.material_summary(shapes+shapes[:1])

    def test_only_real_tint_feature_counts_even_when_buffer_exists(self):
        shapes = [{'name': name, 'shaderBlockId': index, 'textureSetBlockId': index+10, 'shaderType': kind}
                  for index, (name, kind) in enumerate((('body', 0), ('head', 5), ('fur_back', 6)))]
        summary = audit.material_summary(shapes)
        self.assertEqual(summary['alreadyTintCapableCount'], 2)
        self.assertEqual(summary['targetsNeedingShaderConversion'], ['body'])

    def test_dds_metadata_and_dx10_extension_require_valid_headers(self):
        header = bytearray(148)
        header[:4] = b'DDS '
        for offset, value in ((4, 124), (12, 256), (16, 512), (28, 10), (76, 32)):
            struct.pack_into('<I', header, offset, value)
        header[84:88] = b'DXT5'
        self.assertEqual(audit.dds_header(header)['width'], 512)
        self.assertEqual(audit.dds_header(header)['fourCC'], 'DXT5')
        header[84:88] = b'DX10'
        struct.pack_into('<5I', header, 128, 98, 3, 0, 1, 0)
        self.assertEqual(audit.dds_header(header)['dxgiFormat'], 98)
        for data in (b'', header[:128], b'BAD '+header[4:]):
            with self.assertRaises(ValueError):
                audit.dds_header(data)

    def test_outputs_cannot_overwrite_or_enter_repository_or_input_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            existing = root/'existing.json'
            existing.write_text('keep')
            for path, protected in ((existing, []), (root/'wrong.txt', []),
                                    (audit.ROOT/'audit.json', []), (root/'input/out.json', [root/'input'])):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    audit.checked_output(path, protected)
            self.assertEqual(existing.read_text(), 'keep')
            self.assertEqual(audit.checked_output(root/'new.json', []), (root/'new.json').resolve())
            for folder in ('Data', 'mods', 'profiles', 'overwrite'):
                with self.subTest(folder=folder), self.assertRaises(ValueError):
                    audit.checked_output(root/folder/'new.json', [])
            (root/'.git').mkdir()
            with self.assertRaises(ValueError):
                audit.checked_output(root/'new.json', [])


if __name__ == '__main__':
    unittest.main()
