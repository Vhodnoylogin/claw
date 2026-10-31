"""Explicit opt-in post-export breast rig candidate; never installs files."""
from pathlib import Path
import argparse
import breast_rig

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--body',type=Path,required=True,help='Pinned raw 85-node body NIF')
    parser.add_argument('--tri',type=Path,required=True,help='Pinned moderate shape-only TRI')
    parser.add_argument('--skeleton',type=Path,required=True,help='Pinned existing XP32 skeleton, read only')
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True,help='NEW external staging directory; no live/MO2/repository destinations')
    parser.add_argument('--pynifly',type=Path,help='PyNifly add-on directory; otherwise ignored build.local.json')
    args=parser.parse_args()
    try:
        report=breast_rig.build_candidate(args.body,args.tri,args.skeleton,args.profile,args.out,args.pynifly)
    except (ValueError,RuntimeError,OSError) as exc:
        parser.exit(1,'Breast rig candidate rejected: '+str(exc)+'\n')
    print('Offline candidate verified; runtime/driver/visual acceptance pending: '+str(report))

if __name__=='__main__':main()
