"""Compositor ownership, timing, and process-guard checks without SteamVR."""

import ctypes as C
from pathlib import Path
import unittest
from unittest.mock import patch

import compositor_readiness as probe


PID = 1729


def sample(index, seconds, before=(PID, PID), after=(PID, PID)):
    return probe.Sample(before, after, probe.Frame(index, seconds, 1, 0, 0))


class CompositorReadinessTests(unittest.TestCase):
    def test_owned_advancing_frames_report_metadata_only(self):
        result = probe.classify(PID, sample(409, 20), sample(414, 20.2))
        self.assertTrue(result['compositorReady'])
        self.assertTrue(result['sceneAndRendererOwned'])
        self.assertTrue(result['frameIndexAdvanced'])
        self.assertTrue(result['compositorClockAdvanced'])
        self.assertFalse(result['eyeFramesCaptured'])
        self.assertEqual(result['samples'][1]['frame']['index'], 414)

    def test_wrong_renderer_or_transient_scene_focus_refuses_readiness(self):
        for second in (sample(414, 20.2, before=(PID, 0)),
                       sample(414, 20.2, after=(PID + 1, PID))):
            with self.subTest(second=second):
                result = probe.classify(PID, sample(409, 20), second)
                self.assertTrue(result['frameIndexAdvanced'])
                self.assertFalse(result['sceneAndRendererOwned'])
                self.assertFalse(result['compositorReady'])

    def test_duplicate_backwards_or_missing_metadata_refuses_readiness(self):
        for second in (sample(409, 20.2), sample(408, 20.2), sample(410, 20),
                       sample(410, 19), sample(410, float('inf')),
                       probe.Sample((PID, PID), (PID, PID), None)):
            with self.subTest(second=second):
                self.assertFalse(probe.classify(PID, sample(409, 20), second)['compositorReady'])

    def test_frame_counter_wrap_with_advancing_clock(self):
        self.assertTrue(probe.classify(PID, sample(0xFFFFFFFF, 20), sample(0, 21))['compositorReady'])

    def test_owned_process_guard_runs_before_open_and_between_reads(self):
        with patch.object(probe, '_open_compositor') as opened, patch.object(probe.time, 'sleep'):
            with self.assertRaisesRegex(RuntimeError, 'unavailable'):
                probe.probe(Path('unused'), PID, lambda: False)
            opened.assert_not_called()

            alive = iter((True, False))
            compositor = opened.return_value.__enter__.return_value
            compositor.sample.return_value = sample(409, 20)
            with self.assertRaisesRegex(RuntimeError, 'ended during sampling'):
                probe.probe(Path('unused'), PID, lambda: next(alive))
            compositor.sample.assert_called_once()
            opened.return_value.__exit__.assert_called_once()

    def test_flat_abi_and_native_sampling_bracket(self):
        self.assertEqual(C.sizeof(probe._TrackedDevicePose), 80)
        self.assertEqual(C.sizeof(probe._FrameTiming), 176)
        self.assertEqual(probe._FrameTiming.system_time_seconds.offset, 24)
        self.assertEqual(probe._FrameTiming.hmd_pose.offset, 96)

        calls = []
        pid = C.CFUNCTYPE(C.c_uint32)

        @pid
        def scene():
            calls.append('scene')
            return PID

        @pid
        def renderer():
            calls.append('renderer')
            return PID

        @C.CFUNCTYPE(C.c_bool, C.POINTER(probe._FrameTiming), C.c_uint32)
        def timing(value, ago):
            calls.append((value.contents.size, ago))
            value.contents.index = 409
            value.contents.system_time_seconds = 20
            value.contents.presents = 1
            return True

        table = (C.c_void_p * 24)()
        for slot, callback in ((8, timing), (22, scene), (23, renderer)):
            table[slot] = C.cast(callback, C.c_void_p)
        with patch.object(C, 'WINFUNCTYPE', C.CFUNCTYPE, create=True):
            self.assertEqual(probe._Compositor(C.addressof(table)).sample(), sample(409, 20))
        self.assertEqual(calls, ['scene', 'renderer', (176, 0), 'renderer', 'scene'])


if __name__ == '__main__':
    unittest.main()
