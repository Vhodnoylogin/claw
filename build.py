"""CLAW build entry point. Generated output belongs in ignored target/."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / 'src/main/python/build-tools'

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('test', 'test-integration', 'bodies', 'native', 'plugins', 'package'))
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    extra = args.arguments
    if extra[:1] == ['--']: extra = extra[1:]
    if args.action == 'test':
        if extra: parser.error('test takes no additional arguments')
        commands = [[sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / folder)]
                    for folder in ('src/test/python/unit', 'src/test/python/physics', 'src/test/python/vr')]
    elif args.action == 'test-integration':
        if extra: parser.error('test-integration takes no additional arguments; see src/test/README.md for input locations')
        commands = [[sys.executable, '-m', 'unittest', 'discover', '-s', str(ROOT / 'src/test/python/integration')],
                    [sys.executable, str(ROOT / 'src/test/resources/inspection/validate.py')]]
    elif args.action == 'native':
        commands = [['pwsh', '-NoProfile', '-File', str(ROOT / 'src/main/cpp/build.ps1'), *extra]]
    else:
        script = {'bodies': 'fresh-body-pipeline.py', 'plugins': 'plugin.py',
                  'package': 'package-source-build.py'}[args.action]
        commands = [[sys.executable, str(TOOLS / script), *(['build'] if args.action == 'plugins' else []), *extra]]
    for command in commands:
        result = subprocess.run(command, cwd=ROOT)
        if result.returncode: return result.returncode
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
