"""Build a new external, opt-in layer-only fur/P1 motion candidate."""
from pathlib import Path
import argparse
import fur_motion


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('body', 'tri', 'skeleton', 'profile', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    args = parser.parse_args()
    try:
        report = fur_motion.build_candidate(args.body, args.tri, args.skeleton, args.profile, args.out, args.pynifly)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'Fur motion candidate rejected: '+str(exc)+'\n')
    print('Offline layer candidate verified; game/appearance pending: '+str(report))


if __name__ == '__main__':
    main()
