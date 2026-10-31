"""Measure a first-person-only XP32 Neck attachment plan; never install."""
import argparse
from pathlib import Path
import head_isolation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body-root', type=Path, required=True)
    parser.add_argument('--skeleton', type=Path, default=head_isolation.resource.ROOT / 'src/main/resources/donors/skeleton.nif')
    parser.add_argument('--morphbench', type=Path, required=True, help='Exact externally frozen 3ddc3af export')
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--write-candidate', action='store_true', help='After numerical admission, graft a separate offline first-person mesh via verified public skin data')
    parser.add_argument('--reuse-joins', type=Path, help='Explicit completed run with identical payloads/inputs and captured identical analysis source; reuse its immutable measurements')
    args = parser.parse_args()
    try:
        report = head_isolation.build(args.body_root, args.skeleton, args.out_dir, args.morphbench, args.pynifly, args.write_candidate, args.reuse_joins)
    except head_isolation.NumericPlanRejected as exc:
        parser.exit(2, 'Head isolation plan rejected: ' + str(exc) + '\n')
    except (ValueError, RuntimeError, OSError) as exc:
        parser.exit(1, 'Head isolation study failed: ' + str(exc) + '\n')
    print(report['status'] + ': ' + str(args.out_dir / 'head-isolation-report.json'))


if __name__ == '__main__':
    main()
