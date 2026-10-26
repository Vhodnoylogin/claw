"""Apply only the measured local male weight-delta guard and compose final resources."""
from pathlib import Path
import argparse
import male_weight_guard as guard

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('prior-manifest','skeleton','morphbench','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--profile',type=Path,default=guard.ROOT/'recipes/body-weight-guard.json');p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(guard.build(a.prior_manifest,a.profile,a.skeleton,a.morphbench,a.out,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Male neutral weight guard rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
