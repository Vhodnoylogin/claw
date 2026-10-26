"""Build pinned offline VR body resources into a new external directory."""
import argparse
from pathlib import Path
import struct

import body_resource


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body-root', type=Path, default=body_resource.ROOT / 'assets/release/0.6.2.0/base/Meshes/Actors/WerewolfBeast/Character Assets')
    parser.add_argument('--skeleton', type=Path, default=body_resource.ROOT / 'assets/donors/skeleton.nif')
    parser.add_argument('--profile', type=Path, default=Path(__file__).with_name('profile.json'))
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--morphbench', type=Path)
    parser.add_argument('--reference-vr-skeleton', type=Path, help='Optional read-only installed reference; never copied or patched')
    args = parser.parse_args()
    try:
        report = body_resource.build(args.body_root, args.skeleton, args.profile, args.out_dir,
                                     args.pynifly, args.morphbench, args.reference_vr_skeleton)
    except (ValueError, OSError, KeyError, RuntimeError, ImportError, struct.error) as exc:
        parser.exit(1, 'VR_BODY|rejected: %s\n' % exc)
    print('VR_BODY|' + report['status'] + '|male+female|installable=false|' + str(args.out_dir))


if __name__ == '__main__':
    main()
