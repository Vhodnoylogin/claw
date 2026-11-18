import struct
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/python/build-tools'))
import tri_patch


def stream(records=((7, 10, -20, 30), (9, 40, 50, 60))):
    return (b'PIRT' + struct.pack('<H', 1) + b'\x04head' + struct.pack('<H', 1)
            + b'\x01G' + struct.pack('<fH', .01, len(records))
            + b''.join(struct.pack('<H3h', *x) for x in records))


class PatchTests(unittest.TestCase):
    def test_empty_patch_preserves_every_byte(self):
        self.assertEqual(tri_patch.patch(stream(), {}), stream())

    def test_only_requested_coordinates_change(self):
        raw = stream()
        key = ('head', 'G', 7)
        record = tri_patch.offsets(raw)[key]
        changed = tri_patch.patch(raw, {key: (11, -20, 31)})
        self.assertEqual(raw[:record.position], changed[:record.position])
        self.assertEqual(raw[record.position + 6:], changed[record.position + 6:])
        self.assertEqual(tri_patch.offsets(changed)[key].packed, (11, -20, 31))

    def test_rejects_missing_overflow_float_and_bool(self):
        for key, value in [(('head', 'G', 8), (1, 2, 3)),
                           (('head', 'G', 7), (32768, 2, 3)),
                           (('head', 'G', 7), (1.0, 2, 3)),
                           (('head', 'G', 7), (True, 2, 3))]:
            with self.assertRaises(ValueError):
                tri_patch.patch(stream(), {key: value})

    def test_rejects_truncation_extensions_and_duplicate_vertex(self):
        for raw in [stream()[:-1], stream() + b'extra', stream(((7, 1, 2, 3), (7, 4, 5, 6)))]:
            with self.assertRaises(ValueError):
                tri_patch.offsets(raw)

    def test_empty_uv_section_is_accepted_and_preserved(self):
        raw = stream() + b'\x00\x00'
        self.assertEqual(tri_patch.offsets(raw), tri_patch.offsets(stream()))
        self.assertEqual(tri_patch.patch(raw, {}), raw)
        key = ('head', 'G', 7)
        position = tri_patch.offsets(raw)[key].position
        expected = raw[:position] + struct.pack('<3h', 11, -20, 31) + raw[position + 6:]
        self.assertEqual(tri_patch.patch(raw, {key: (11, -20, 31)}), expected)

    def test_nonempty_uv_section_or_other_trailer_is_rejected(self):
        for trailer in (b'\x01\x00', b'\x00', b'\x00\x00\x00', b'\x01\x00\x00\x00', b'\x00\x00\x00\x00'):
            with self.subTest(trailer=trailer), self.assertRaises(ValueError):
                tri_patch.offsets(stream() + trailer)


if __name__ == '__main__':
    unittest.main()
