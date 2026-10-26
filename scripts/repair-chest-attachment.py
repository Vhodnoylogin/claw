"""Build the localized chest-fur root attachment candidate, outside live files."""
from pathlib import Path
import argparse
import chest_attachment as chest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('body','tri','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',type=Path,default=chest.ROOT/'recipes/chest-attachment.json');p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(chest.build(a.body,a.tri,a.skeleton,a.profile,a.out,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Chest attachment rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
