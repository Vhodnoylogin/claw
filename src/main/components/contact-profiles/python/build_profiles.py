"""Build current-body flat/VR contact models in a NEW external directory; never install.

Uses the existing full-triangle ancestry/current-vector fitter twice. No physics
provider, separate platform DLL, solver, borrowed contact rig or live actor is used.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

import profile_contract as contract


def runtime_inputs(path):
    value = json.loads(path.read_bytes())
    names = {sex + 'bodywerewolf' + suffix for sex in ('male', 'female')
             for suffix in ('_0.nif', '_1.nif', '.tri')}
    files = value.get('files')
    if not isinstance(files, list) or len(files) != len(names):
        raise ValueError('Runtime manifest must pin all six body NIF/TRI files')
    result = {}
    for row in files:
        source = Path(row['path']).resolve()
        if source.name not in names or source.name in result or contract.pin(source) != {key: row[key] for key in ('sha256', 'bytes')}:
            raise ValueError('Missing, duplicate or changed runtime body input')
        result[source.name] = source
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-inputs', type=Path, required=True)
    parser.add_argument('--skeleton', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    out = contract.host.destination(args.out)
    files = runtime_inputs(args.runtime_inputs)
    recipes = contract.read_recipes()
    inputs = {str(path.resolve()): contract.pin(path) for path in
              [args.runtime_inputs, args.skeleton, *files.values(), Path(__file__), Path(contract.__file__),
               contract.PHYSICS / 'fit-capsules.py', contract.PHYSICS / 'current_model.py',
               contract.PHYSICS / 'contact_fit.py', contract.PHYSICS / 'contact_diagnostics.py',
               contract.PHYSICS / 'build.py', contract.ROOT / 'src/main/cpp/include/claw/PhysicsFit.h',
               *(contract.RESOURCES / row[0] for row in contract.PROFILES.values())]}
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'incomplete', 'runtimeQualified': False, 'surfaceFitAccepted': False,
               'gameValidated': False, 'higgsPlanckHavokImplemented': False, 'maximumOwnedSlots': 128,
               'oneUniversalDLLRequired': True, 'inputs': inputs, 'commands': [], 'profiles': {}}
    report = out / 'contact-profiles-build.json'
    report.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    try:
        models = {}
        for edition, (filename, _, _) in contract.PROFILES.items():
            command = [sys.executable, str(contract.PHYSICS / 'fit-capsules.py'), '--current-vector',
                       '--contact-recipe', str(contract.RESOURCES / filename), '--skeleton', str(args.skeleton.resolve()),
                       '--out', str(out / edition)]
            for sex in ('male', 'female'):
                command += ['--' + sex + '-nif', str(files[sex + 'bodywerewolf_0.nif']),
                            '--' + sex + '-nif-1', str(files[sex + 'bodywerewolf_1.nif']),
                            '--' + sex + '-tri', str(files[sex + 'bodywerewolf.tri'])]
            if args.pynifly:
                command += ['--pynifly', str(args.pynifly.resolve())]
            receipt['commands'].append({'edition': edition, 'argv': command, 'returnCode': None})
            report.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
            environment = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
            with (out / (edition + '.log')).open('wb') as log:
                result = subprocess.run(command, cwd=contract.ROOT, env=environment, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=1800)
            receipt['commands'][-1]['returnCode'] = result.returncode
            if result.returncode:
                raise ValueError(edition + ' fit failed; retain its raw log')
            model = json.loads((out / edition / 'fitted-capsules.json').read_bytes())
            models[edition] = model
        contract.validate_models(models)
        header = contract.write_pair_header(models, out)
        recipe = json.loads((contract.PHYSICS / 'recipe.json').read_bytes())
        capsules = json.loads((contract.PHYSICS / 'capsules.json').read_bytes())
        for edition, model in models.items():
            data = out / edition / 'CLAWPhysicsData.psc'
            data.write_text(contract.host.render_data(recipe, capsules, model), encoding='utf-8')
            receipt['profiles'][edition] = {'profile': recipes[edition]['supportProfile'], 'modelIdentity': model['modelIdentity'],
                'slots': len(model['slots']), 'activeMale': contract.host.expected_capsule_count_for_sex(model, 'male'),
                'activeFemale': contract.host.expected_capsule_count_for_sex(model, 'female'), 'dataSource': contract.pin(data),
                'model': contract.pin(out / edition / 'fitted-capsules.json'),
                'hostBuild': 'Use existing physics/build-host.py --fitted-capsules with this exact JSON; no PEX was built here'}
        if any(contract.pin(Path(path)) != expected for path, expected in inputs.items()):
            raise ValueError('Source/runtime input changed while fitting')
        receipt.update(status='offline-model-pair-generated-game-pending', pairedHeader=contract.pin(header),
            activationEnabled=False, compiledHost=False, compiledGameDLL=False,
            endpointRule='Use exactly the supplied runtime endpoints, including intentional identical low/high bytes',
            ownership='One selected profile, one existing0x434C0000..0x434C007f ledger; never append both profiles')
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        receipt.update(status='failed', error=str(error))
        print(str(error), file=sys.stderr)
        return 2
    finally:
        report.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    raise SystemExit(main())
