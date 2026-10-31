"""Build the chosen offline head/torso split for both pinned CLAW sexes."""
from pathlib import Path
import argparse
import head_split

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--body-root',type=Path,required=True)
    p.add_argument('--skeleton',type=Path,required=True)
    p.add_argument('--profile',type=Path,default=head_split.ROOT / 'src/main/resources/recipes/head-split.json')
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:report=head_split.build(a.body_root,a.skeleton,a.profile,a.out,a.pynifly)
    except (ValueError,RuntimeError,OSError) as e:p.exit(1,'Anatomical split rejected: '+str(e)+'\n')
    print(report)

if __name__=='__main__':main()
