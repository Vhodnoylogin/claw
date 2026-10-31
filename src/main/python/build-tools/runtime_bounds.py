"""Derive runtime carriers with morph-inclusive spheres; frozen authoring stays intact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys

import expressive_body as body
from head_split import Nif
import locate

MESH = Path('Meshes/Actors/WerewolfBeast/Character Assets')


def bounds_only(before, after, api):
    """Prove the public writer touched only the 16-byte shape sphere fields."""
    original, result = Nif(before.read_bytes()), Nif(after.read_bytes())
    if (original.prefix, original.type_names, original.kinds, original.strings, original.footer) != (
            result.prefix, result.type_names, result.kinds, result.strings, result.footer):
        raise ValueError('Bounds stage changed the NIF container')
    source = api.NifFile(str(before))
    allowed = {}
    for shape in source.shapes:
        sphere = struct.pack('<4f', *shape.properties.boundingSphereCenter,
                             shape.properties.boundingSphereRadius)
        block = original.blocks[shape.id]
        if block.count(sphere) != 1:
            raise ValueError('Cannot uniquely verify a shape sphere: ' + shape.name)
        allowed[shape.id] = (block.index(sphere), shape.name)
    changed = []
    for index, (left, right) in enumerate(zip(original.blocks, result.blocks)):
        if left == right:
            continue
        if index not in allowed:
            raise ValueError('Bounds stage changed a non-shape block')
        offset, name = allowed[index]
        if len(left) != len(right) or left[:offset] != right[:offset] or left[offset+16:] != right[offset+16:]:
            raise ValueError('Bounds stage changed geometry, skin, material or another shape property')
        changed.append(name)
    return changed


def build(source, out, margin=1.01):
    source, out = Path(source).resolve(), Path(out).resolve()
    body.authored_output(out, [source/'malebodywerewolf_0.nif'])
    if margin < 1.01:
        raise ValueError('At least one percent morph-inclusive bounds margin required')
    names = [sex+'bodywerewolf'+suffix for sex in ('male', 'female')
             for suffix in ('_0.nif', '_1.nif', '.tri')]
    inputs = {n: body.sha((source/n).read_bytes()) for n in names}
    bench = locate.morphbench(Path(__file__))
    api, _ = body.load_api()
    out.mkdir(parents=True)
    target = out/MESH
    target.mkdir(parents=True)
    report = {'schema': 'claw-runtime-body-bounds/1', 'status': 'building',
              'sourceSha256': inputs, 'scriptSha256': body.sha(Path(__file__).read_bytes()),
              'morphbenchSha256': body.sha(bench.read_bytes()), 'margin': margin,
              'scope': 'Named morphs in 0..1; bounds only. No posed skeleton or physics-motion coverage.',
              'sexes': {}, 'outputSha256': {}}
    for sex in ('male', 'female'):
        low, high, tri = (sex+'bodywerewolf'+ending for ending in ('_0.nif', '_1.nif', '.tri'))
        shutil.copyfile(source/tri, target/tri)
        command = [sys.executable, str(bench), 'bounds', str(source/low),
                   '--tri', str(source/tri), '--write', str(target/low), '--margin', str(margin), '--shrink', '--json']
        done = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace')
        (out/(sex+'-bounds.log')).write_text(done.stdout+'\n'+done.stderr, encoding='utf-8')
        if done.returncode or not (target/low).is_file():
            raise ValueError('Morph-inclusive bounds failed; see '+str(out/(sex+'-bounds.log')))
        changed = bounds_only(source/low, target/low, api)
        if (source/low).read_bytes() != (source/high).read_bytes():
            raise ValueError('This derived stage requires the explicit frozen equal-weight endpoints')
        shutil.copyfile(target/low, target/high)
        report['sexes'][sex] = {'changedShapeSpheres': changed,
                               'highCopiedFromIdenticalLowSource': True,
                               'outsideSpheresBytesExact': True}
    if inputs != {n: body.sha((source/n).read_bytes()) for n in names}:
        raise ValueError('Bounds input changed during derivation')
    report['outputSha256'] = {n: body.sha((target/n).read_bytes()) for n in names}
    report['status'] = 'runtime-morph-bounds-built-no-posed-or-physics-acceptance'
    (out/'runtime-bounds-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--margin', type=float, default=1.01)
    args = parser.parse_args()
    print(json.dumps(build(args.source, args.out, args.margin), indent=2))
