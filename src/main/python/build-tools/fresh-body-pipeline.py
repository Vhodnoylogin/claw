"""Build the legacy and repaired bodies from pinned original donors, not a release.

Everything generated stays below target/. Historical release files, when present,
are independent read-only references. A hash mismatch is diagnosed, never waived.
No MO2 read, installation or game launch is required by this source-only route.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MESH = Path('Meshes/Actors/WerewolfBeast/Character Assets')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def new_output(path):
    out = Path(path).resolve()
    if out.exists() or (ROOT/'target').resolve() not in out.parents:
        raise ValueError('Choose a new directory below the ignored target/')
    for ancestor in (out, *out.parents):
        if ancestor.exists() and (ancestor.is_symlink() or ancestor.is_junction()):
            raise ValueError('Output ancestry cannot contain a link/junction')
    return out


def block_diagnostics(reference, fresh):
    """Identify actual NIF container differences without accepting substitutions."""
    from head_split import Nif
    a, b = Nif(reference.read_bytes()), Nif(fresh.read_bytes())
    count = min(len(a.blocks), len(b.blocks))
    return {'referenceBlocks': len(a.blocks), 'freshBlocks': len(b.blocks),
            'prefixEqual': a.prefix == b.prefix,
            'typeNamesEqual': a.type_names == b.type_names,
            'blockKindsEqual': a.kinds == b.kinds,
            'stringTableEqual': a.strings == b.strings,
            'footerEqual': a.footer == b.footer,
            'differentBlocks': [{'index': i, 'referenceKind': a.kind(i), 'freshKind': b.kind(i),
                                  'referenceBytes': len(a.blocks[i]), 'freshBytes': len(b.blocks[i]),
                                  'referenceSha256': hashlib.sha256(a.blocks[i]).hexdigest(),
                                  'freshSha256': hashlib.sha256(b.blocks[i]).hexdigest()}
                                 for i in range(count) if a.blocks[i] != b.blocks[i]]}


def compare_release(candidate, reference):
    """Read actual installer file directives; references never generate a model."""
    config = reference/'fomod/ModuleConfig.xml'
    if not config.is_file():
        return {'available': False, 'checked': 0, 'usedAsBuildInput': False}
    mappings = {Path(row.attrib['destination']).name: row.attrib['source']
                for row in ET.parse(config).getroot().findall('requiredInstallFiles/file')
                if row.attrib['destination'].startswith(MESH.as_posix()+'/')}
    expected = {sex+'bodywerewolf'+suffix for sex in ('male', 'female')
                for suffix in ('_0.nif', '_1.nif', '.tri')}
    if set(mappings) != expected:
        raise ValueError('Historical installer has an unexpected body destination inventory')
    rows = {}
    for name, source in mappings.items():
        ref = (reference/source).resolve()
        if reference.resolve() not in ref.parents:
            raise ValueError('Historical reference path escapes its directory')
        rows[name] = {'archiveSource': source, 'referenceSha256': sha(ref),
                      'freshSha256': sha(candidate/name),
                      'exact': ref.read_bytes() == (candidate/name).read_bytes()}
    return {'available': True, 'checked': len(rows), 'usedAsBuildInput': False,
            'allExact': all(row['exact'] for row in rows.values()), 'files': rows}


def build(out, reference, blender=None, release_reference=None):
    out = new_output(out)
    builder = module('claw_fresh_legacy_builder', HERE/'build-all.py')
    if blender is not None:
        builder.P.blender = Path(blender).resolve(strict=True)
    producer = subprocess.run([str(builder.P.blender), '--version'], check=True,
                              capture_output=True, text=True).stdout.splitlines()[0]
    recipe_path = ROOT/'src/main/resources/recipes/build.json'
    repair_path = ROOT/'src/main/resources/recipes/surface-repair-v1.json'
    spec = json.loads(recipe_path.read_text(encoding='utf-8-sig'))
    repair = json.loads(repair_path.read_text(encoding='utf-8'))
    pipe = builder.Pipeline(spec, out/'legacy-build')
    sources = pipe.check_sources(False)
    pinned_source = {str(pipe.source(k)): sha(pipe.source(k)) for k in spec['sources'] if not k.startswith('_')}
    source_files = [recipe_path, repair_path, HERE/'build-all.py', Path(__file__),
                    *[HERE/step['script'] for step in spec['steps'] if step.get('script')],
                    HERE/'morphlib.py', HERE/'surface_edits.py', HERE/'expressive_body.py',
                    HERE/'expressive_verify.py', ROOT/'src/main/resources/recipes/expressive-body-v1.json',
                    ROOT/'src/main/resources/recipes/expressive-fixture-vectors-v1.json']
    source_pins = {str(p): sha(p) for p in source_files}
    bench = builder.morphbench(HERE)
    tool_files = [Path(builder.P.blender), Path(builder.P.pynifly)/'NiflyDLL.dll', bench]
    tool_files += sorted(Path(builder.P.pynifly).rglob('*.py'))
    tool_pins = {str(p): sha(p) for p in tool_files}
    out.mkdir(parents=True)
    report = {'schema': 'claw-fresh-source-body-build/1', 'status': 'building',
              'sources': sources, 'sourceSha256': source_pins, 'donorSha256': pinned_source,
              'tools': {'blenderVersion': producer, 'originalProducer': 'Blender 5.2.2 LTS',
                        'sha256': tool_pins, 'morphbenchEntry': str(bench)},
              'historicalReferenceDirectory': str(reference),
              'referenceUsedAsBuildInput': False, 'installedSourceFallback': False,
              'installedVerification': False, 'installed': False, 'gameStarted': False,
              'steps': [], 'legacy': {}}
    def save():
        (out/'fresh-body-report.json').write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    save()
    try:
        for index, step in enumerate(spec['steps']):
            started = time.monotonic()
            print('Source stage %d/%d: %s' % (index+1, len(spec['steps']), step['name']), flush=True)
            pipe.run_step(step, False)
            report['steps'].append({'index': index, 'name': step['name'], 'runner': step['runner'],
                                    'elapsedSeconds': time.monotonic()-started, 'completed': True})
            save()
        legacy = out/'legacy'/MESH
        legacy.mkdir(parents=True)
        for name, source in spec['mods']['base']['files'].items():
            path = pipe.built(source)
            target = legacy/name
            shutil.copyfile(path, target)
            pin = repair['files'][name]
            if 'alias' in pin:
                pin = repair['files'][pin['alias']]
            digest = sha(target)
            row = {'sha256': digest, 'expectedBeforeRepair': pin['before'],
                   'exactBeforeRepair': digest == pin['before']}
            historical = reference/name
            if historical.is_file():
                row['referenceSha256'] = sha(historical)
                row['exactHistoricalReference'] = historical.read_bytes() == target.read_bytes()
                if not row['exactHistoricalReference']:
                    row['semanticDiagnostic'] = (builder._diff_tri(historical, target) if name.endswith('.tri')
                                                  else builder._diff_nif(historical, target, bounds=True))
                    if name.endswith('.nif'):
                        row['blockDiagnostic'] = block_diagnostics(historical, target)
            report['legacy'][name] = row
        if any(not r['exactBeforeRepair'] for r in report['legacy'].values()):
            report['status'] = 'legacy-built-strict-surface-input-mismatch'
            save()
            return report
        import surface_edits
        report['repairedSha256'] = surface_edits.build(legacy, repair_path, out/'repaired'/MESH)
        save()
        import expressive_body
        import expressive_verify
        expressive = expressive_body.build(out/'repaired'/MESH,
            ROOT/'src/main/resources/recipes/expressive-body-v1.json', out/'expressive',
            vectors=ROOT/'src/main/resources/recipes/expressive-fixture-vectors-v1.json')
        if any(row['normalOrCollapseIssues'] for row in expressive['sexes'].values()):
            raise ValueError('Expressive static geometry sample gates failed')
        report['expressiveSha256'] = expressive['outputSha256']
        public = expressive_verify.verify(out/'expressive'/MESH, out/'expressive-public-reader.json',
                                          base=out/'repaired'/MESH)
        report['publicReaderStatus'] = public['status']
        report['releaseComparison'] = compare_release(out/'expressive'/MESH,
            Path(release_reference or ROOT/'target/references/releases/0.7.0.0'))
        if report['releaseComparison'].get('allExact') is False:
            raise ValueError('Fresh expressive output differs from the independently retained release')
        if any(sha(path) != digest for path, digest in {**pinned_source, **source_pins, **tool_pins}.items()):
            raise ValueError('A source or donor changed during the fresh build')
        report['status'] = 'fresh-source-through-070-built'
        save()
        return report
    except BaseException as exc:
        report['status'] = 'source-build-failed'
        report['error'] = str(exc)
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'target/bodies/fresh')
    parser.add_argument('--reference', type=Path,
                        default=ROOT/'target/references/releases/0.6.2.0/base'/MESH)
    parser.add_argument('--blender', type=Path,
                        help='Explicit producer executable; the original legacy producer was Blender 5.2.2 LTS')
    parser.add_argument('--release-reference', type=Path,
                        help='Optional independently retained 0.7 FOMOD reference; never a build input')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    result = build(args.out, args.reference, args.blender, args.release_reference)
    print(json.dumps({'status': result['status'], 'report': str(args.out/'fresh-body-report.json')}))
    sys.exit(0 if result['status'] == 'fresh-source-through-070-built' else 2)
