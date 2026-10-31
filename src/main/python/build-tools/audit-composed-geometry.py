"""Measure actual skin collar and fur-root gaps on the composed neutral weight family."""
from pathlib import Path
import argparse
import geometry_audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('low','high','tri','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--baseline',type=Path);p.add_argument('--pynifly',type=Path)
    a=p.parse_args()
    try:print(geometry_audit.build(a.low,a.high,a.tri,a.skeleton,a.out,a.baseline,a.pynifly))
    except (ValueError,RuntimeError,OSError) as exc:p.exit(1,'Composed geometry audit rejected: '+str(exc)+'\n')

if __name__=='__main__':main()
