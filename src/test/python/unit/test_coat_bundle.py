"""Complete texture inventory/stream boundaries; no third-party pixels in fixtures."""
import copy
import io
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "src/main/python/build-tools"))
import coat_bundle as bundle
import coat_library as c


def texture(tag):
    header = bytearray(128); header[:4] = b"DDS "
    struct.pack_into("<I", header, 4, 124)
    struct.pack_into("<II", header, 12, 4, 4)
    return bytes(header) + tag


class CompleteTextureBundleTests(unittest.TestCase):
    def setUp(self):
        self.coats = c.read_json(bundle.COAT_INDEX)
        self.index = c.read_json(bundle.ALL_INDEX)

    def test_complete_original_inventory_preserves_pattern_mapping(self):
        bundle.validate_inventory(self.index, self.coats)
        expected = c.source_entries(self.coats)
        self.assertEqual(355, len(self.index["files"]))
        extras = [r for r in self.index["files"] if r["archivePath"] not in expected]
        self.assertEqual(49, len(extras))
        self.assertEqual(11, sum('/Data/' not in r['archivePath'].split('/', 1)[1] for r in extras))
        self.assertEqual(28, sum('/eyes/' in r['gamePath'] for r in extras))
        self.assertEqual(10, sum('/source-patches/lobo/' in r['gamePath'] for r in extras))

    def test_missing_alias_and_misdirected_coat_rejected(self):
        variants = []
        missing = copy.deepcopy(self.index); missing['files'].pop(); variants.append(missing)
        alias = copy.deepcopy(self.index); alias['files'][1]['gamePath'] = alias['files'][0]['gamePath'].upper(); variants.append(alias)
        traversal = copy.deepcopy(self.index); traversal['files'][0]['gamePath'] = 'textures/../clobber.dds'; variants.append(traversal)
        wrong = copy.deepcopy(self.index)
        row = next(r for r in wrong['files'] if '/Patterns/' in r['archivePath'])
        row['gamePath'] = 'textures/unrelated.dds'; variants.append(wrong)
        for value in variants:
            with self.subTest(value=value['files'][0]['gamePath']), self.assertRaises(c.ValidationError):
                bundle.validate_inventory(value, self.coats)

    def test_stream_pins_order_size_crc_and_dds(self):
        first, second = texture(b'one'), texture(b'two')
        rows = {name: {'archivePath': name, 'gamePath': 'textures/'+name, 'bytes': len(data),
                       'crc32': f'{zlib.crc32(data):08x}'}
                for name, data in [('first.dds', first), ('second.dds', second)]}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            result = bundle.extract(io.BytesIO(first+second), list(rows), rows, target)
            self.assertEqual([first, second], [(target/r['gamePath']).read_bytes() for r in result])
            self.assertEqual([4, 4], [r['dds']['width'] for r in result])
        for data in (first+second[:-1], second+first, first+second+b'extra'):
            with tempfile.TemporaryDirectory() as temporary, self.assertRaises(c.ValidationError):
                bundle.extract(io.BytesIO(data), list(rows), rows, Path(temporary))

    def test_source_identity_and_unexpected_metadata_rejected(self):
        for field, value in [('source', {**c.SOURCE, 'version': 'unknown'}), ('schemaVersion', 2)]:
            candidate = copy.deepcopy(self.index); candidate[field] = value
            with self.assertRaises(c.ValidationError): bundle.validate_inventory(candidate, self.coats)
        candidate = copy.deepcopy(self.index); candidate['files'][0]['installRoot'] = 'Data'
        with self.assertRaises(c.ValidationError): bundle.validate_inventory(candidate, self.coats)


if __name__ == '__main__': unittest.main()
