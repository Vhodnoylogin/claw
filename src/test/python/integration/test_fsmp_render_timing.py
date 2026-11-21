import unittest

if __package__:
    from .fsmp_render_timing import bracket_render_frames
else:
    from fsmp_render_timing import bracket_render_frames


class RenderTimingTests(unittest.TestCase):
    def setUp(self):
        self.pairs = [{"pair": index, "preQpc": tick, "postQpc": tick + 5}
                      for index, tick in enumerate((10, 30, 50, 70), 1)]

    def bracket(self, *sources, frequency=10_000_000, gap=24):
        frames = [{"index": index, "systemRelativeTime100ns": source, "receiptQpc": 85 + index}
                  for index, source in enumerate(sources)]
        return bracket_render_frames(frames, self.pairs, qpc_frequency=frequency,
                                     capture_start=8, capture_end=100, maximum_gap_ticks=gap)

    def test_brackets_a_frame_inside_one_solver_pair_with_surrounding_pairs(self):
        result = self.bracket(33)[0]
        self.assertEqual(result["status"], "bounded")
        self.assertEqual((result["beforePair"], result["afterPair"]), (1, 3))

    def test_preserves_timestamp_uncertainty_on_another_frequency(self):
        result = self.bracket(138, frequency=3_000_000)[0]
        self.assertEqual(result["compositorQpcRange"], [41, 42])
        self.assertEqual((result["beforePair"], result["afterPair"]), (2, 3))

    def test_distinguishes_capture_clock_outside_trace_and_large_solver_gaps(self):
        states = [row["status"] for row in self.bracket(1, 9, 33, 107, gap=10)]
        self.assertEqual(states, ["outside-capture-clock", "outside-solver-trace", "solver-gap", "outside-capture-clock"])

    def test_refuses_duplicate_frames_and_missing_pairs(self):
        with self.assertRaisesRegex(ValueError, "Compositor frame sequence"):
            self.bracket(33, 33)
        del self.pairs[1]
        with self.assertRaisesRegex(ValueError, "contiguous"):
            self.bracket(33)
