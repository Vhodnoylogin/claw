"""Expand only new Neck NiSkinData sphere radii after reviewed VR composition."""
import argparse
from pathlib import Path
import neck_bounds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--composition-report', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--morphbench', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    args = parser.parse_args()
    try:
        report = neck_bounds.build(args.resources, args.composition_report, args.out_dir, args.morphbench, args.pynifly)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'New Neck bounds rejected: '+str(exc)+'\n')
    print(report['status']+': '+str(args.out_dir/'neck-bounds-report.json'))


if __name__ == '__main__':
    main()
