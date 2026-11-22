"""Check the surgical P1 transfer without a release archive or a live game."""

import importlib.util
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location(
    'claw_breast_attachment_trial_tests', ROOT / 'src/main/python/physics/breast_attachment_trial.py')
trial = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(trial)


def skin_data(rows):
    frame = bytes(range(52))
    bones = (bytes([10 + bone]) * 68 + struct.pack('<H', len(entries)) +
             b''.join(struct.pack('<Hf', vertex, weight) for vertex, weight in entries)
             for bone, entries in enumerate(rows))
    return frame + struct.pack('<IB', len(rows), 1) + b''.join(bones)


class BreastAttachmentTrialTests(unittest.TestCase):
    def test_move_pair_preserves_native_order_in_both_weight_encodings(self):
        shift = .0281982421875
        cases = (
            ('<4e', (.72021484375, .09844970703125, .181396484375, 0), (0, 4, 14, 0), 2, .1531982421875),
            ('<4f', (.7201365828514099, .18139564990997314, .09846773743629456, 0),
             (0, 14, 4, 0), 1, .15319740772247314),
        )
        for fmt, values, indices, left_slot, remaining in cases:
            with self.subTest(encoding=fmt):
                encoding = struct.Struct(fmt)
                original = encoding.pack(*values)
                updated, new_indices, mirror = trial.move_pair(original, bytes(indices), 14, 15, shift)
                self.assertEqual(new_indices, bytes((*indices[:3], 15)))
                self.assertEqual(mirror, (values[left_slot], remaining, shift))
                after = encoding.unpack(updated)
                self.assertEqual(after[left_slot], remaining)
                self.assertEqual(after[3], shift)
                self.assertEqual(sum(after), sum(encoding.unpack(original)))
                width = encoding.size // 4
                for foreign_slot in {0, 1, 2} - {left_slot}:
                    cell = slice(foreign_slot * width, (foreign_slot + 1) * width)
                    self.assertEqual(updated[cell], original[cell])

    def test_move_pair_rejects_full_or_already_bilateral_rows_and_bad_transfer(self):
        cases = (
            ((.5, .25, .125, .125), (0, 4, 14, 3), .0625, 'three influences'),
            ((.5, .25, .25, 0), (0, 15, 14, 0), .0625, 'three influences'),
            ((.5, .25, .25, 0), (0, 4, 3, 0), .0625, 'three influences'),
            ((.5, .25, .25, 0), (0, 4, 14, 0), .25, 'does not fit'),
            ((.5, .25, .25, 0), (0, 4, 14, 0), .001, 'no longer exact'),
        )
        for weights, indices, shift, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                trial.move_pair(struct.pack('<4e', *weights), bytes(indices), 14, 15, shift)

    def test_skin_patch_preserves_unrelated_raw_bytes_and_updates_mirrors(self):
        rows = (
            [(4, .8125), (15, .75)], [(20, .0625), (4, .125), (40, .125), (15, .25)],
            [(1, .125), (10, .5), (22, .75)], [(99, -0.0), (4, .0625)],
        )
        expected = (
            rows[0], [(20, .0625), (4, .09375), (40, .125), (15, .1875)],
            [(1, .125), (4, .03125), (10, .5), (15, .0625), (22, .75)], rows[3],
        )
        transfers = {15: (.25, .1875, .0625), 4: (.125, .09375, .03125)}
        original = skin_data(rows)
        result = trial.patch_skin_data(original, 1, 2, transfers)
        self.assertEqual(result, skin_data(expected))
        self.assertEqual(len(result) - len(original), 2 * struct.calcsize('<Hf'))

    def test_skin_patch_refuses_disagreeing_left_or_existing_right_mirror(self):
        data = skin_data(([(4, .75)], [(4, .25)], [(10, .25)]))
        discrepancy = struct.unpack('<f', struct.pack('<I', 0x3e800001))[0]  # One float32 ULP above .25.
        with self.assertRaisesRegex(ValueError, 'float weights disagree'):
            trial.patch_skin_data(data, 1, 2, {4: (discrepancy, .1875, .0625)})
        with self.assertRaisesRegex(ValueError, 'float weights disagree'):
            trial.patch_skin_data(data, 1, 2, {5: (.25, .1875, .0625)})
        data = skin_data(([], [(4, .25)], [(4, .015625)]))
        with self.assertRaisesRegex(ValueError, 'stored right P1 influence'):
            trial.patch_skin_data(data, 1, 2, {4: (.25, .1875, .0625)})


if __name__ == '__main__':
    unittest.main()
