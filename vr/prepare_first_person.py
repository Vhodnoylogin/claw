"""Prepare first-person-only selective visibility on composed CLAW endpoints."""
import argparse
from pathlib import Path

import selective_visibility


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body-root', type=Path, required=True, help='Directory containing the six final-composed-004 NIF/TRI files')
    parser.add_argument('--skeleton', type=Path, default=selective_visibility.resource.ROOT / 'assets/donors/skeleton.nif')
    parser.add_argument('--out-dir', type=Path, required=True, help='New external directory; never a game or mod-manager directory')
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--morphbench', type=Path)
    args = parser.parse_args()
    try:
        report = selective_visibility.build(args.body_root, args.skeleton, args.out_dir, pynifly=args.pynifly, morphbench=args.morphbench)
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'First-person visibility resource rejected: ' + str(exc) + '\n')
    print(report['status'] + ': ' + str(args.out_dir / 'first-person-visibility-report.json'))


if __name__ == '__main__':
    main()
