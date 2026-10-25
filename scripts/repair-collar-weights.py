"""Standalone experimental collar weights; writes only a NEW external directory."""
import argparse
import json
import sys

import collar_weights


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nif', required=True)
    parser.add_argument('--tri', required=True)
    parser.add_argument('--skeleton', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--pynifly', help='Override the ignored build.local.json PyNifly directory')
    args = parser.parse_args(argv)
    try:
        result = collar_weights.repair(args.nif, args.tri, args.skeleton, args.profile, args.out_dir, args.pynifly)
    except (ValueError, OSError, KeyError, RuntimeError) as exc:
        parser.exit(1, 'COLLAR_WEIGHTS|rejected: %s\n' % exc)
    print('COLLAR_WEIGHTS|' + json.dumps({'status': result['status'], 'outputs': result['outputs'],
          'nodeCount': result['verification']['nodeCount'], 'publicMorphCount': len(result['publicMorphs'])}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
