"""Build the frozen authored CLAW surface repair into a new external directory."""
import argparse
import json
from pathlib import Path
import surface_edits

ROOT=Path(__file__).resolve().parents[4]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=ROOT / 'target/references/releases/0.6.2.0/base/Meshes/Actors/WerewolfBeast/Character Assets')
    p.add_argument('--recipe',type=Path,default=ROOT / 'src/main/resources/recipes/surface-repair-v1.json')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    try:
        result=surface_edits.build(a.base,a.recipe,a.out)
    except (ValueError,OSError,KeyError,TypeError) as e:
        p.exit(1,'Surface repair rejected: '+str(e)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
