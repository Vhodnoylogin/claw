"""Build and measure a new external VR torso weight experiment; never install."""
import argparse
import json
from pathlib import Path
import vr_torso_weights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('body', 'tri', 'skeleton', 'profile', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    args = parser.parse_args()
    try:
        report = vr_torso_weights.build_candidate(args.body, args.tri, args.skeleton,
                                                 args.profile, args.out, args.pynifly)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'VR torso experiment failed: '+str(exc)+'\n')
    admitted = json.loads(report.read_text(encoding='utf-8'))['admitted']
    print(('Offline candidate admitted: ' if admitted else 'Measured candidate rejected; do not install: ')+str(report))
    return 0 if admitted else 2


if __name__ == '__main__':
    raise SystemExit(main())
