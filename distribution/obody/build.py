"""Build/read back the optional stock-OBody source host; never install or launch."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLUGIN = 'CLAW - OBody Integration.esp'
EDITOR = 'CLAWOBodySourceHostQuest'
MASTERS = ['Skyrim.esm', 'CLAW.esp', 'OBody.esp']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def records(enabled):
    return {
        'RecordData.yaml': {'SpriggitSource': {'PackageName': 'Spriggit.Yaml.Skyrim', 'Version': .41},
            'ModKey': PLUGIN, 'GameRelease': 'SkyrimSE', 'ModHeader': {'FormVersion': 39,
            'Author': 'CLAW', 'Description': 'Optional stock OBody source generation for fresh unassigned beast actors',
            'MasterReferences': [{'Master': name, 'FileSize': 0} for name in MASTERS]}},
        'spriggit-meta.json': {'PackageName': 'Spriggit.Yaml.Skyrim', 'Version': '0.41.0',
                             'Release': 'SkyrimSE', 'ModKey': PLUGIN},
        f'Quests/{EDITOR} - 000800_{PLUGIN}.yaml': {
            'FormKey': '000800:' + PLUGIN, 'EditorID': EDITOR,
            'VirtualMachineAdapter': {'Scripts': [{'Name': 'CLAWOBodySourceHost', 'Properties': [
                {'MutagenObjectType': 'ScriptBoolProperty', 'Name': 'IntegrationOptIn', 'Data': enabled}]}],
                'FileName': '', 'Aliases': []},
            'Name': {'TargetLanguage': 'English', 'Value': 'CLAW stock OBody source integration'},
            'Flags': ['StartGameEnabled'] if enabled else [], 'Priority': 10,
            'NextAliasID': 1, 'Aliases': []}}


def verify_plugin(reader, path, enabled):
    result = reader.inspect_plugin(path)
    if (result['masters'] != MASTERS or result['questForm'] != 0x03000800 or
        result['editorId'] != EDITOR or result['nextAlias'] != 1 or result['aliases']):
        raise ValueError('Host identity, masters or empty alias policy changed')
    expected_data = bytearray.fromhex('00000aff0000000000000000')
    struct.pack_into('<H', expected_data, 0, int(enabled))
    if result['questData'] != expected_data.hex():
        raise ValueError('Quest flags/priority do not match the explicit install choice')
    expected_vmad = {'version': 5, 'format': 2, 'bindVersion': 2, 'aliases': [], 'scripts': [
        {'name': 'CLAWOBodySourceHost', 'flags': 0, 'properties': [
            {'name': 'IntegrationOptIn', 'type': 5, 'flags': 1, 'data': enabled}]}]}
    if result['vmad'] != expected_vmad:
        raise ValueError('Quest script or opt-in VMAD differs from the install choice')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('out', 'compiler', 'spriggit', 'flags', 'obody-declaration'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--import-path', required=True, action='append', type=Path)
    parser.add_argument('--enable-population', action='store_true')
    args = parser.parse_args(argv)
    for name in ('compiler', 'spriggit', 'flags', 'obody_declaration'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    out = args.out.resolve()
    if out.exists() or any(part.lower() in ('mods', 'data', 'overwrite', 'downloads') for part in out.parts):
        raise ValueError('Use a new external output directory')
    if any((parent / '.git').exists() for parent in (out, *out.parents)):
        raise ValueError('Output cannot be inside a source checkout')
    sources = [Path(__file__), ROOT / 'CLAWOBodySourceHost.psc', ROOT / 'README.md',
               REPO / 'physics/wiring.py', REPO / 'distribution/papyrus/CLAWDistributionNative.psc',
               args.obody_declaration, args.compiler, args.spriggit, args.flags]
    imports = [folder.resolve(strict=True) for folder in args.import_path]
    for folder in imports:
        sources.extend(sorted(folder.rglob('*.psc')))
    captured = {path.resolve(strict=True): path.read_bytes() for path in sources}
    declaration = captured[args.obody_declaration.resolve()].decode('utf-8-sig')
    if ('ScriptName OBodyNative'.lower() not in declaration.lower() or
        'Function GenActor(Actor a_actor) Global Native' not in declaration or
        'GetPresetAssignedToActor(Actor a_actor)' not in declaration):
        raise ValueError('Explicit stock OBody declaration does not contain the reviewed APIs')
    for source in captured:
        if out == source.parent or source.parent in out.parents:
            raise ValueError('Output is inside a tool/source input directory')
    # Execute the already captured original binary reader, not another file read.
    helper_path = (REPO / 'physics/wiring.py').resolve()
    reader = types.ModuleType('claw_obody_binary_reader')
    reader.__file__ = str(helper_path)
    exec(compile(captured[helper_path], str(helper_path), 'exec'), reader.__dict__)
    out.mkdir(parents=True)
    report = {'status': 'incomplete', 'enabledInstallChoice': args.enable_population,
              'gameValidated': False, 'installed': False, 'commands': [],
              'inputs': {str(path): sha(data) for path, data in captured.items()}}
    try:
        closure = out / 'compiler-imports'
        closure.mkdir()
        # Flatten only matching script names; a conflicting definition is refused.
        for path, payload in captured.items():
            if path.suffix.lower() != '.psc':
                continue
            name = 'OBodyNative.psc' if path == args.obody_declaration.resolve() else path.name
            target = closure / name
            if target.exists() and target.read_bytes() != payload:
                if name in ('OBodyNative.psc', 'CLAWDistributionNative.psc'):
                    continue  # Explicit current declarations are written below.
                raise ValueError('Conflicting compiler import: ' + name)
            target.write_bytes(payload)
        (closure / 'OBodyNative.psc').write_bytes(captured[args.obody_declaration.resolve()])
        (closure / 'CLAWDistributionNative.psc').write_bytes(captured[(REPO / 'distribution/papyrus/CLAWDistributionNative.psc').resolve()])
        package = out / 'package'
        scripts = package / 'Scripts'
        scripts.mkdir(parents=True)
        temporary = out / 'temporary'
        temporary.mkdir()
        environment = dict(os.environ, TEMP=str(temporary), TMP=str(temporary))

        def run(command, cwd, name):
            value = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, timeout=55)
            report['commands'].append({'argv': list(map(str, command)), 'returnCode': value.returncode})
            (out / (name + '.stdout.log')).write_bytes(value.stdout)
            (out / (name + '.stderr.log')).write_bytes(value.stderr)
            if value.returncode:
                raise ValueError(name + ' failed; see retained logs')

        run([str(args.compiler), '--game', 'skyrim', '--async-read', '0', '--async-write', '0',
             '--allow-unknown-events', '1', '--flags', str(args.flags), '--import', str(closure),
             '--output', str(scripts), 'CLAWOBodySourceHost.psc'], closure, 'caprica')
        if not (scripts / 'CLAWOBodySourceHost.pex').is_file():
            raise ValueError('Compiler did not emit the host PEX')
        tree = out / 'plugin-source'
        for relative, value in records(args.enable_population).items():
            path = tree / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
        esp = package / PLUGIN
        run([str(args.spriggit), 'deserialize', '--InputPath', str(tree), '--OutputPath', str(esp)], REPO, 'spriggit')
        binary = verify_plugin(reader, esp, args.enable_population)
        again = out / 'roundtrip-source'
        run([str(args.spriggit), 'serialize', '--InputPath', str(esp), '--OutputPath', str(again),
             '--GameRelease', 'SkyrimSE', '--PackageName', 'Spriggit.Yaml', '--PackageVersion', '0.41.0'], REPO, 'readback')
        second = out / 'roundtrip' / PLUGIN
        second.parent.mkdir()
        run([str(args.spriggit), 'deserialize', '--InputPath', str(again), '--OutputPath', str(second)], REPO, 'rebuild')
        if verify_plugin(reader, second, args.enable_population) != binary:
            raise ValueError('Binary script/flags changed during Spriggit roundtrip')
        (scripts / 'Source').mkdir()
        (scripts / 'Source/CLAWOBodySourceHost.psc').write_bytes(captured[ROOT / 'CLAWOBodySourceHost.psc'])
        (package / 'README.md').write_bytes(captured[ROOT / 'README.md'])
        if any(path.read_bytes() != payload for path, payload in captured.items()):
            raise ValueError('A source/tool/import changed during compilation')
        report.update(status='built-offline-records-verified-runtime-pending', binary=binary,
                      artifacts=[{'path': p.relative_to(package).as_posix(), 'bytes': p.stat().st_size,
                                  'sha256': sha(p.read_bytes())} for p in sorted(package.rglob('*')) if p.is_file()])
        print(json.dumps({'status': report['status'], 'package': str(package)}))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report.update(status='failed', error=str(error))
        print(str(error), file=sys.stderr)
        return 2
    finally:
        (out / 'obody-host-build.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
