from pathlib import Path
import os,tempfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
FIXTURES=Path(os.environ.get('CLAW_PHOTO_FIXTURE_ROOT',str(ROOT/'src/test/resources/photo_comparison')))
def temporary():
    target=(ROOT/'target/photo-comparison-tests').resolve()
    if not target.is_relative_to(ROOT.resolve()):raise ValueError('Test output escaped owned worktree')
    target.mkdir(parents=True,exist_ok=True)
    return tempfile.TemporaryDirectory(dir=target)
