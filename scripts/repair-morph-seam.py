"""Stage one explicitly missing male WaistNarrow head collar field; never install."""
import argparse
from pathlib import Path

import morph_seam


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('low', 'high', 'tri', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--skeleton', type=Path, help='Read-only existing skeleton for declared LBS pose diagnostics')
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--widths', nargs='+', type=float, default=[2, 4, 6, 8, 8.5, 9, 10, 12, 16])
    args = parser.parse_args()
    try:
        print(morph_seam.build(args.low, args.high, args.tri, args.out, skeleton=args.skeleton, pynifly=args.pynifly, widths=args.widths))
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'Morph seam repair rejected: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
