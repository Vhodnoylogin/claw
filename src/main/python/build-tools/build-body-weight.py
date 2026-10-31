"""Build distinct CLAW neutral weight endpoints from pinned actual human pairs."""
from pathlib import Path
import argparse
import body_weight

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('female','female-tri','male','male-tri','human-root','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',type=Path,default=body_weight.ROOT / 'src/main/resources/recipes/body-weight.json');p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(body_weight.build(a.female,a.female_tri,a.male,a.male_tri,a.human_root,a.profile,a.out,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Body weight endpoints rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
