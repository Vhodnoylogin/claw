"""Capture the owned Skyrim SE window without changing desktop focus."""

from datetime import datetime, timezone
from hashlib import file_digest
from time import sleep


def utc_stamp():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def capture_game_frame(native, game, path):
    from PIL import ImageGrab

    def window():
        observed = native.focus_owned(game, activate=False)
        windows = [row['hwnd'] for row in observed.get('ownedWindows', [])
                   if row['class'] == 'Skyrim Special Edition' or row['title'] == 'Skyrim Special Edition']
        if len(windows) != 1:
            raise RuntimeError('Expected one visible window for the owned Skyrim SE process')
        return windows[0]

    hwnd = window()
    for attempt in range(4):
        if attempt:
            sleep(.4)
        started = utc_stamp()
        image = ImageGrab.grab(window=hwnd)
        ended = utc_stamp()
        if window() != hwnd:
            raise RuntimeError('Skyrim window changed while capturing the frame')
        if image.size == (1920, 1080) and any(lo != hi for lo, hi in image.getextrema()):
            break
    else:
        raise RuntimeError(f'Expected a non-uniform 1920×1080 Skyrim capture, last size {image.size}')
    with path.open('xb') as stream:
        image.save(stream, format='PNG')
    with path.open('rb') as stream:
        digest = file_digest(stream, 'sha256').hexdigest()
    return {'path': str(path), 'startUtc': started, 'endUtc': ended, 'size': list(image.size),
            'sha256': digest, 'captureAttempts': attempt + 1}
