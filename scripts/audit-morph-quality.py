"""Audit complete actual TRI fields, skin overlap, boundary joins and sampled extremes.

Read-only inputs; the only output is a diagnostic JSON in a new external folder.
"""
import argparse
from pathlib import Path

import morph_quality


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('low', 'tri', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--high', type=Path)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--skin', nargs='+', default=['body', 'head'], help='Explicit skin shape names; include anatomical split pieces')
    parser.add_argument('--join-tolerance', type=float, default=1e-4, help='Neutral cross-shape boundary vertex-pair distance in model units')
    args = parser.parse_args()
    try:
        print(morph_quality.build(args.low, args.tri, args.out, high=args.high,
                                  skin=args.skin, pynifly=args.pynifly, join_tolerance=args.join_tolerance))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'Morph quality audit rejected: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
