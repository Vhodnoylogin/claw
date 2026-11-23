"""Fit offline contact capsules against the equipped VR world body's exact geometry."""
from __future__ import annotations

import argparse
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
from zipfile import BadZipFile, ZipFile

import profile_contract as contract

sys.path.insert(0, str(contract.ROOT / 'src/main/components/vr-body'))
from vr_dispatch import SEXES, armor_path, require_static_nif, resource_paths


PLUGIN = 'test_CLAW - VR Player Body32.esp'
ARCHIVE = PurePosixPath(PLUGIN).with_suffix('.zip').name
WORLD_SHAPES = contract.EQUIPPED_SKIN


def world_path(sex, suffix):
    return PurePosixPath(resource_paths(sex)).with_name('EarWorldTrial' + suffix).as_posix()


def file_pin(path):
    return {'path': str(path), **contract.pin(path)}


def read_package(directory):
    manifest, archive = directory / 'player-body32.json', directory / ARCHIVE
    data = manifest.read_bytes()
    info = json.loads(data)
    payload = archive.read_bytes()
    world_paths = {sex: world_path(sex, '.nif').removeprefix('Meshes/').replace('/', '\\') for sex in SEXES}
    if (not isinstance(info, dict) or info.get('schema') != 'claw-vr-player-body32-outfit/3' or info.get('archive') != ARCHIVE
            or info.get('archiveSha256') != sha256(payload).hexdigest()
            or info.get('declaredModels') != {sex: armor_path(sex) for sex in SEXES}
            or info.get('declaredWorldModels') != world_paths
            or info.get('worldMarkers') != {'male': 'W_M', 'female': 'W_F'}
            or info.get('markers') != {'male': 'P_M', 'female': 'P_F'}
            or (info.get('item'), info.get('addon')) != ('000801:' + PLUGIN.lower(), '000800:' + PLUGIN.lower())
            or type(info.get('slot')) is not int or info['slot'] != 32 or info.get('race') != '0CDD84:skyrim.esm'
            or info.get('runtimeQualified') is not False):
        raise ValueError('Expected the verified equipped static world-ear package')

    first = {resource_paths(sex, endpoint) for sex in SEXES for endpoint in (None, 0, 1)}
    world = {world_path(sex, suffix) for sex in SEXES for suffix in ('.nif', '.tri')}
    expected = {PLUGIN, *first, *world}
    member_pins = info.get('payloadSha256')
    sources = {}
    with ZipFile(BytesIO(payload)) as bundle:
        names = bundle.namelist()
        if set(names) != expected or len(names) != len(expected) or not isinstance(member_pins, dict) or set(member_pins) != expected:
            raise ValueError('Expected exactly the 11 authored equipped-package members')
        for name in names:
            content = bundle.read(name)
            if sha256(content).hexdigest() != member_pins[name]:
                raise ValueError('Equipped archive member differs from its build receipt: ' + name)
            if name in world:
                sources[name] = content

    for sex in SEXES:
        expected_tri = world_path(sex, '.tri').removeprefix('Meshes/').replace('/', '\\').lower()
        require_static_nif(sources[world_path(sex, '.nif')], expected_tri=expected_tri)
    inputs = [{'path': str(path), 'sha256': sha256(raw).hexdigest(), 'bytes': len(raw)}
              for path, raw in ((manifest, data), (archive, payload))]
    return sources, inputs


def stage_inputs(directory, sources):
    directory.mkdir()
    files = []
    for sex in SEXES:
        prefix = sex + 'bodywerewolf'
        for suffix, kind in (('_0.nif', '.nif'), ('_1.nif', '.nif'), ('.tri', '.tri')):
            path = directory / (prefix + suffix)
            path.write_bytes(sources[world_path(sex, kind)])
            files.append(file_pin(path))
    manifest = directory / 'runtime-inputs.json'
    manifest.write_text(json.dumps({'files': files}, indent=2) + '\n', encoding='utf-8')
    return manifest, files


def validate_fit(model, recipe, runtime_files):
    contract.host.validate_fitted_model(model)
    measured = model['supportDeclaration']['regions']
    regions = [{key: row[key] for key in ('node', 'count', 'sexMask')} for row in measured]
    coverage = model['supportCoverage']
    if (model['supportProfile'] != recipe['supportProfile'] or regions != recipe['supportRegions']
            or model['coveredShapes'] != recipe['skinShapes'] or len(model['slots']) != recipe['capsuleBudget']
            or model['fixtureSet'] != recipe['fixtureSet'] or model['surfaceFitAccepted'] is not False
            or model['runtimeQualified'] is not False or model['gameValidated'] is not False
            or len(coverage) != len(SEXES) * len(WORLD_SHAPES)
            or {(row['sex'], row['shape']) for row in coverage} != {(sex, shape) for sex in SEXES for shape in WORLD_SHAPES}
            or any(row['sourceTriangles'] <= 0 or row['sourceTriangles'] != row['assignedTriangles']
                   or row['droppedTriangles'] or row['duplicateTriangleAssignments'] for row in coverage)):
        raise ValueError('Fitted model does not cover the exact equipped skin and declared slot allocation')
    fitted_inputs = {row['path']: row for row in model['sourceInputs']}
    if any(fitted_inputs.get(row['path']) != row for row in runtime_files):
        raise ValueError('Fitter used a different equipped NIF or TRI')


def build(package, skeleton, pynifly, output):
    sources, package_inputs = read_package(package.resolve(strict=True))
    skeleton = skeleton.resolve(strict=True)
    pynifly = pynifly.resolve(strict=True)
    out = contract.host.destination(output)
    recipe = contract.read_recipes()['vr']
    recipe.update(skinShapes=list(WORLD_SHAPES), fixtureSet='compact', signedDiagnostics=False)
    out.mkdir(parents=True, exist_ok=False)
    manifest, runtime_files = stage_inputs(out / 'inputs', sources)
    recipe_path = out / 'inputs/contact-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n', encoding='utf-8')
    inputs = [*package_inputs, file_pin(skeleton), file_pin(manifest), file_pin(recipe_path), *runtime_files]
    fit = out / 'fit'
    command = [sys.executable, '-B', str(contract.PHYSICS / 'fit-capsules.py'), '--current-vector',
               '--contact-recipe', str(recipe_path), '--skeleton', str(skeleton), '--pynifly', str(pynifly), '--out', str(fit)]
    for sex in SEXES:
        prefix = manifest.parent / (sex + 'bodywerewolf')
        command += ['--' + sex + '-nif', str(prefix) + '_0.nif', '--' + sex + '-nif-1', str(prefix) + '_1.nif',
                    '--' + sex + '-tri', str(prefix) + '.tri']
    log, report = out / 'fit.log', out / 'equipped-contact-build.json'
    result = {'schema': 'claw-vr-equipped-contact-build/1', 'status': 'incomplete', 'runtimeQualified': False,
              'gameValidated': False, 'surfaceFitAccepted': False, 'inputs': inputs, 'command': command, 'exitCode': None}
    try:
        with log.open('wb') as stream:
            fit_result = subprocess.run(command, cwd=contract.ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                        env=dict(os.environ, PYTHONIOENCODING='utf-8'), timeout=1800)
        result['exitCode'] = fit_result.returncode
        if fit_result.returncode:
            raise ValueError(f'Equipped VR fit failed; see {log}')
        model_path = fit / 'fitted-capsules.json'
        model = json.loads(model_path.read_bytes())
        validate_fit(model, recipe, runtime_files)
        if any(file_pin(Path(row['path'])) != row for row in inputs):
            raise ValueError('Equipped fit inputs changed during the build')
        result.update(status='offline-fit-built', modelIdentity=model['modelIdentity'],
                      runtimeInputs=file_pin(manifest), model=file_pin(model_path),
                      fittedHeader=file_pin(fit / 'physics-fit-model.h'), fixtures=file_pin(fit / 'runtime-fixtures.json'),
                      coverage=model['supportCoverage'])
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        result.update(status='failed', error=str(error))
        raise
    finally:
        if log.is_file():
            result['fitLog'] = file_pin(log)
        report.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('package', 'skeleton', 'pynifly', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(args.package, args.skeleton, args.pynifly, args.out)
    except (BadZipFile, KeyError, ValueError, OSError, subprocess.SubprocessError) as error:
        parser.exit(2, f'CLAW equipped contact build: {error}\n')
    print(result['modelIdentity'])


if __name__ == '__main__':
    main()
