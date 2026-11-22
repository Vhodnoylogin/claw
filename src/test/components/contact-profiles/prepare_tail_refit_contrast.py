"""Find a stationary sphere position that separates two fitted TailBone02 states."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / 'src/main/python/physics'))
from contact_fit import signed_capsules

PROFILE_SHA = '66f7522934d75573087842f55073a1299338a9dadd2215d813057ba2eeb25918'
NUMERIC_SHA = '2074450336a64f50e4881e065a11ed44fac0e0e9ef89bfe7c01d51c63ef03004'
CHANNEL = 'CLAWTailLength'
STATES = (0.0, 1.0, 0.0)
SLOT_IDS = (108, 109, 110, 111)
HAND_RADIUS = 3.0
CONTROLLER_OFFSET = 12.0
MIN_MARGIN = 0.75


def read_pinned(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f'Expected the exact retained input: {path.name}')
    return raw


def load_bank(binary, profile):
    lines = []
    for state in STATES:
        values = [state if name == CHANNEL else 0.0 for name in profile['morphs']]
        lines.append(' '.join(map(str, (1, 0, 0.5, len(values), *values))))
    process = subprocess.run([str(binary)], input='\n'.join(lines) + '\n', text=True,
                             capture_output=True, check=True, timeout=30)
    rows = process.stdout.splitlines()
    if len(rows) != len(STATES) or rows[0] != rows[2]:
        raise ValueError('Returning to neutral must restore the complete bank exactly')
    banks = []
    for row in rows:
        identity, count, *cells = row.split()
        if identity != profile['modelIdentity'] or int(count) != len(profile['slots']):
            raise ValueError('Numeric executable returned a different profile')
        values = np.asarray(cells, dtype=float).reshape(int(count), 7)
        if not np.isfinite(values).all() or np.any(values[list(SLOT_IDS), 6] <= 0.0):
            raise ValueError('Invalid fitted TailBone02 geometry')
        banks.append([{'p1': values[i, :3].tolist(), 'p2': values[i, 3:6].tolist(), 'radius': float(values[i, 6])}
                      for i in SLOT_IDS])
    return banks


def find_center(banks):
    # Compare the full same-bone union because stock callbacks have no slot ID.
    inflated = [[{**cap, 'radius': cap['radius'] + HAND_RADIUS} for cap in bank] for bank in banks]
    borders = np.array([np.asarray(cap[key]) + sign * cap['radius']
                        for bank in inflated[:2] for cap in bank for key in ('p1', 'p2') for sign in (-1, 1)])
    step = 0.15
    axes = [np.arange(lo, hi + step, step) for lo, hi in zip(borders.min(axis=0), borders.max(axis=0), strict=True)]
    points = np.stack(np.meshgrid(*axes, indexing='ij'), axis=-1).reshape(-1, 3)
    points = points[np.linalg.norm(points, axis=1) <= CONTROLLER_OFFSET]
    separation = signed_capsules(points, inflated[0])
    overlap = -signed_capsules(points, inflated[1])
    best = int(np.argmax(np.minimum(separation, overlap)))
    center = points[best:best + 1]
    gaps = {'neutralSeparation': float(separation[best]), 'morphedOverlap': float(overlap[best]),
            'returnedSeparation': float(signed_capsules(center, inflated[2])[0])}
    return {'centerOwnerLocal': center[0].tolist(), 'gaps': gaps, 'worstMargin': min(gaps.values()),
            'testedCenters': len(points), 'gridStep': step}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('profile', 'numeric', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    output = args.out.resolve()
    if output.exists() or REPO in output.parents or any(part.casefold() in ('mods', 'data', 'overwrite', 'downloads') for part in output.parts):
        raise ValueError('Use a new external report path')
    binary = args.numeric.resolve(strict=True)
    read_pinned(binary, NUMERIC_SHA)
    profile = json.loads(read_pinned(args.profile, PROFILE_SHA))
    found = tuple(i for i, slot in enumerate(profile['slots']) if slot['node'] == 'TailBone02' and slot['male'] is not None)
    if found != SLOT_IDS or len(profile['morphs']) != 31 or CHANNEL not in profile['morphs']:
        raise ValueError('The exact four TailBone02 slots and full input vector are required')
    banks = load_bank(binary, profile)
    contrast = find_center(banks)
    report = {'profileSha256': PROFILE_SHA, 'numericExeSha256': NUMERIC_SHA, 'model': profile['modelIdentity'],
              'morph': CHANNEL, 'values': STATES, 'actorWeight': 0.5, 'handSphereRadiusAtUnitScale': HAND_RADIUS,
              'slots': SLOT_IDS, 'capsulesByPhase': banks, **contrast, 'meetsRequestedMargin': contrast['worstMargin'] >= MIN_MARGIN,
              'gameQualified': False, 'scope': 'Rest-frame counterfactual only. Verify actual actor, scale, transforms and contacts in game.'}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(contrast))
    return 0 if report['meetsRequestedMargin'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
