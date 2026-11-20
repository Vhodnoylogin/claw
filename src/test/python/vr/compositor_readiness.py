"""Read SteamVR frame timing and scene ownership in a background client.

The caller supplies the owned game PID and a process-identity check. The C ABI
below uses Valve's openvr_capi.h at 60eb187801956ad277f1cae6680e3a410ee0873b.
"""

from contextlib import contextmanager
import ctypes as C
from dataclasses import asdict, dataclass
import math
from pathlib import Path
import sys
import time
from typing import Callable


_INTERFACE = b'FnTable:IVRCompositor_022'
_BACKGROUND = 3  # Does not start SteamVR or keep it running.
_TIMING_SLOT, _SCENE_PID_SLOT, _RENDERER_PID_SLOT = 8, 22, 23


class _TrackedDevicePose(C.Structure):
    _fields_ = [
        ('device_to_absolute_tracking', C.c_float * 12),
        ('velocity', C.c_float * 3),
        ('angular_velocity', C.c_float * 3),
        ('tracking_result', C.c_int),
        ('pose_valid', C.c_bool),
        ('device_connected', C.c_bool),
    ]


class _FrameTiming(C.Structure):
    _fields_ = [
        ('size', C.c_uint32),
        ('index', C.c_uint32),
        ('presents', C.c_uint32),
        ('mis_presented', C.c_uint32),
        ('dropped', C.c_uint32),
        ('reprojection_flags', C.c_uint32),
        ('system_time_seconds', C.c_double),
        # The 16 float timers from PreSubmitGpuMs through CompositorRenderStartMs.
        ('timers', C.c_float * 16),
        ('hmd_pose', _TrackedDevicePose),
    ]


@dataclass(frozen=True)
class Frame:
    index: int
    system_time_seconds: float
    presents: int
    dropped: int
    reprojection_flags: int


@dataclass(frozen=True)
class Sample:
    # Each pair is (scene focus PID, last-frame renderer PID).
    owners_before: tuple[int, int]
    owners_after: tuple[int, int]
    frame: Frame | None


def classify(game_pid: int, first: Sample, second: Sample) -> dict:
    """Distinguish owned frame metadata and eye-content evidence."""
    expected = (game_pid, game_pid)
    owned = game_pid > 0 and all(sample.owners_before == sample.owners_after == expected
                                 for sample in (first, second))
    index_advanced = clock_advanced = False
    if first.frame is not None and second.frame is not None:
        # Frame indexes are uint32. Exclude backward movement and ambiguous wraps.
        delta = (second.frame.index - first.frame.index) & 0xFFFFFFFF
        index_advanced = 0 < delta < 0x80000000
        before, after = first.frame.system_time_seconds, second.frame.system_time_seconds
        clock_advanced = math.isfinite(before) and math.isfinite(after) and 0 < before < after
    return {
        'expectedGamePid': game_pid,
        'samples': [asdict(first), asdict(second)],
        'sceneAndRendererOwned': owned,
        'frameIndexAdvanced': index_advanced,
        'compositorClockAdvanced': clock_advanced,
        'compositorReady': owned and index_advanced and clock_advanced,
        'eyeFramesCaptured': False,
    }


class _Compositor:
    def __init__(self, address: int):
        table = C.cast(address, C.POINTER(C.c_void_p))
        timing, scene, renderer = (table[slot] for slot in (_TIMING_SLOT, _SCENE_PID_SLOT, _RENDERER_PID_SLOT))
        if not all((timing, scene, renderer)):
            raise RuntimeError('OpenVR compositor returned an incomplete read interface')
        pid_callback = C.WINFUNCTYPE(C.c_uint32)
        self._scene_pid = pid_callback(scene)
        self._renderer_pid = pid_callback(renderer)
        self._frame_timing = C.WINFUNCTYPE(C.c_bool, C.POINTER(_FrameTiming), C.c_uint32)(timing)

    def sample(self) -> Sample:
        before = (self._scene_pid(), self._renderer_pid())
        timing = _FrameTiming(size=C.sizeof(_FrameTiming))
        available = self._frame_timing(C.byref(timing), 0)
        renderer, scene = self._renderer_pid(), self._scene_pid()
        frame = None
        if available and timing.size == C.sizeof(_FrameTiming) and math.isfinite(timing.system_time_seconds):
            frame = Frame(timing.index, timing.system_time_seconds, timing.presents,
                          timing.dropped, timing.reprojection_flags)
        return Sample(before, (scene, renderer), frame)


@contextmanager
def _open_compositor(runtime: Path):
    if sys.platform != 'win32' or C.sizeof(C.c_void_p) != 8 or C.sizeof(_FrameTiming) != 176:
        raise OSError('The compositor probe requires the Windows x64 OpenVR ABI')
    runtime = Path(runtime)
    if not runtime.is_absolute():
        raise ValueError('Expected the caller-verified absolute SteamVR runtime path')
    library = C.CDLL(str((runtime / 'bin/win64/openvr_api.dll').resolve(strict=True)))
    library.VR_InitInternal.argtypes = [C.POINTER(C.c_int), C.c_int]
    library.VR_InitInternal.restype = C.c_ssize_t
    library.VR_GetGenericInterface.argtypes = [C.c_char_p, C.POINTER(C.c_int)]
    library.VR_GetGenericInterface.restype = C.c_ssize_t
    library.VR_ShutdownInternal.argtypes = []
    library.VR_ShutdownInternal.restype = None
    error = C.c_int()
    library.VR_InitInternal(C.byref(error), _BACKGROUND)
    if error.value:
        raise RuntimeError(f'OpenVR background initialization failed ({error.value})')
    try:
        address = library.VR_GetGenericInterface(_INTERFACE, C.byref(error))
        if error.value or not address:
            raise RuntimeError(f'OpenVR IVRCompositor_022 unavailable ({error.value})')
        yield _Compositor(address)
    finally:
        library.VR_ShutdownInternal()


def probe(runtime: Path, game_pid: int, owns_live_game: Callable[[], bool], *, interval_seconds: float = .25) -> dict:
    """Take two bounded observations during one already owned Skyrim VR process."""
    if type(game_pid) is not int or not 0 < game_pid <= 0xFFFFFFFF:
        raise ValueError('Expected the owned game PID')
    if not .05 <= interval_seconds <= 1.:
        raise ValueError('Frame observation interval must be between 0.05 and 1 second')
    if not owns_live_game():
        raise RuntimeError('Owned Skyrim VR process unavailable')
    with _open_compositor(runtime) as compositor:
        first = compositor.sample()
        time.sleep(interval_seconds)
        if not owns_live_game():
            raise RuntimeError('Owned Skyrim VR process ended during sampling')
        second = compositor.sample()
        if not owns_live_game():
            raise RuntimeError('Owned Skyrim VR process ended during sampling')
    return classify(game_pid, first, second)
