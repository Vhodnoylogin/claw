"""Audit breast/thorax sensitivity to explicit head-only poses without a game."""
from pathlib import Path
import argparse
import vr_head


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body-root', type=Path, default=vr_head.ROOT/'assets/release/0.6.2.0/base/Meshes/Actors/WerewolfBeast/Character Assets')
    parser.add_argument('--skeleton', type=Path, default=vr_head.ROOT/'assets/donors/skeleton.nif')
    parser.add_argument('--profile', type=Path, default=vr_head.ROOT/'vr/profile.json')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    args = parser.parse_args()
    try:
        result = vr_head.build_report(args.body_root, args.skeleton, args.profile, args.out, args.pynifly)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'Head audit unavailable: '+str(exc)+'\n')
    print('Head-only offline measurements: '+str(result))


if __name__ == '__main__':
    main()
