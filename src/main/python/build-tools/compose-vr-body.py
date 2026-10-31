"""Build one composed existing-XP32, bounded anatomical body resource candidate."""
from pathlib import Path
import argparse
import composed_vr

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('female','female-tri','male','male-tri','skeleton','out','morphbench'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',type=Path,default=composed_vr.ROOT / 'src/main/resources/recipes/composed-vr.json');p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(composed_vr.build(a.female,a.female_tri,a.male,a.male_tri,a.skeleton,a.profile,a.out,a.morphbench,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Composed VR resources rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
