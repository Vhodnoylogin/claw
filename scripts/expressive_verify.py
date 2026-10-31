"""Independently read an expressive candidate through PyNifly's public TRIP API."""
import argparse
import importlib.util
import json
from pathlib import Path

import expressive_body as body


def verify(candidate, output, base=None, pynifly=None):
    candidate, output = Path(candidate).resolve(), Path(output).resolve()
    base = Path(base or body.ROOT/'assets/release/se-core-20261030/base/Meshes/Actors/WerewolfBeast/Character Assets').resolve()
    if output.exists() or body.ROOT in output.parents:
        raise ValueError('New external verification report required')
    _, addon = body.load_api(pynifly)
    spec = importlib.util.spec_from_file_location('claw_expressive_verify_trip', addon/'tri/tripfile.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    report = {'schema': 'claw-expressive-public-reader-verification/1',
              'scriptSha256': body.sha(Path(__file__).read_bytes()), 'sexes': {}}
    api, _ = body.load_api(pynifly)
    for sex in ('male', 'female'):
        for suffix in ('_0.nif', '_1.nif'):
            name = sex+'bodywerewolf'+suffix
            if (candidate/name).read_bytes() != (base/name).read_bytes():
                raise ValueError('NIF baseline bytes changed: '+name)
        nif = api.NifFile(str(candidate/(sex+'bodywerewolf_0.nif')))
        counts = {s.name: len(s.verts) for s in nif.shapes}
        tri = candidate/(sex+'bodywerewolf.tri')
        public = module.TripFile.from_filepath(str(tri))
        if not public.is_valid:
            raise ValueError('Public TRIP reader rejected candidate')
        decoded, stats = body.quality.decode_fields(tri.read_bytes(), public.shapes, counts)
        _, old = body.trip_records((base/tri.name).read_bytes())
        _, new = body.trip_records(tri.read_bytes())
        old = {(n, row[0]): row for n, rows in old for row in rows}
        new = {(n, row[0]): row for n, rows in new for row in rows}
        protected = {key: value for key, value in old.items() if key[1] not in body.NAMES}
        if any(new.get(key) != value for key, value in protected.items()):
            raise ValueError('Unrelated named morph record changed')
        additions = sorted({m for n, m in new}-{m for n, m in old})
        if additions != sorted(body.NAMES[:4]):
            raise ValueError('Unexpected public morph inventory change')
        report['sexes'][sex] = {'publicReaderValid': True, 'nifBytesExact': True,
            'publicTargetCount': len({m for n, m in decoded}), 'newNames': additions,
            'unrelatedRecordsExact': len(protected), 'decodedRecordCounts': stats,
            'triSha256': body.sha(tri.read_bytes())}
    report['status'] = 'passed-public-reader-and-protected-payload-checks'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--base', type=Path)
    p.add_argument('--pynifly', type=Path)
    a = p.parse_args()
    print(json.dumps(verify(a.candidate, a.out, a.base, a.pynifly), indent=2))
