"""Measure decoded body-field contrast on frozen skin and outer-coat sections.

These are alpha-ignorant, rest-space triangle envelopes, not artistic acceptance,
physical volume or a posed/collision proof. A missing coat section stays missing;
the outer envelope combines skin with coat rather than treating empty fur as skin.
"""
from pathlib import Path
import argparse
import json
import math

import numpy as np

import expressive_body as body


REGIONS = {
    'upperArm': (0, 33., 'CLAWArmLean', 'CLAWArmGirth'),
    'thigh': (2, 62., 'CLAWLegThighLean', 'CLAWLegThighGirth'),
    'torso': (2, 84., 'CLAWTorsoLean', 'CLAWTorsoGirth'),
    'abdomen': (2, 80., None, 'CLAWTorsoBellyRound'),
}
FAMILIES = {'skin': ('body', 'head'), 'coat': body.COAT,
            'outer': ('body', 'head', *body.COAT)}


def region_mask(centres, region):
    x, y, z = np.asarray(centres).T
    if region == 'upperArm':
        return (z > 65) & (z < 118)
    if region == 'thigh':
        return (x > 4) & (x < 29) & (y > -18) & (y < 25)
    if region == 'torso':
        return np.abs(x) < 23
    if region == 'abdomen':
        return (np.abs(x) < 14) & (y > -12)
    raise ValueError('Unknown anatomical region')


def effective_diameter(section):
    if section is None:
        return None
    area = section['hullArea']
    if not np.isfinite(area) or area < 0:
        raise ValueError('Finite nonnegative envelope area required')
    return 2 * math.sqrt(area / math.pi)


def contrast(region, sections):
    if any(sections[name] is None for name in ('minimum', 'maximum', 'neutral')):
        return None
    if region == 'abdomen':
        result = sections['maximum']['front'] - sections['neutral']['front']
    else:
        result = effective_diameter(sections['maximum']) - effective_diameter(sections['minimum'])
    if not np.isfinite(result) or result <= 0:
        raise ValueError('Regional contrast must be positive')
    return float(result)


def measure(geometry, faces, fields):
    result = {region: {} for region in REGIONS}
    for family, wanted in FAMILIES.items():
        selected = [name for name in wanted if name in geometry]
        vertices, triangles, offsets = [], [], {}
        start = 0
        for name in selected:
            offsets[name] = slice(start, start + len(geometry[name]))
            vertices.append(geometry[name])
            triangles.append(faces[name] + start)
            start += len(geometry[name])
        if not vertices:
            raise ValueError('Required family is absent: ' + family)
        neutral, all_faces = np.concatenate(vertices), np.concatenate(triangles)
        centres = neutral[all_faces].mean(axis=1)
        for region, (axis, level, lean, growth) in REGIONS.items():
            frozen = all_faces[region_mask(centres, region)]
            sections = {}
            for state, morph in (('neutral', None), ('minimum', lean), ('maximum', growth)):
                current = neutral.copy()
                if morph is not None:
                    for name, indices in offsets.items():
                        current[indices] += fields.get((name, morph), np.zeros_like(geometry[name]))
                sections[state] = body.section(current, frozen, axis, level)
            result[region][family] = {'sections': sections, 'contrast': contrast(region, sections)}
    return result


def compare_measures(reference, candidate, required_ratio=1.25):
    if not np.isfinite(required_ratio) or required_ratio <= 1:
        raise ValueError('A contrast ratio greater than one is required')
    rows = {}
    for region in REGIONS:
        rows[region] = {}
        for family in FAMILIES:
            before = reference[region][family]['contrast']
            after = candidate[region][family]['contrast']
            if any(value is not None and (not np.isfinite(value) or value <= 0) for value in (before, after)):
                raise ValueError('Finite positive measured contrast required')
            ratio = None if before is None or after is None else after / before
            rows[region][family] = {'reference': before, 'candidate': after, 'ratio': ratio}
        ratio = rows[region]['outer']['ratio']
        rows[region]['outer']['passesRequiredRatio'] = ratio is not None and ratio >= required_ratio
    return rows


def analyze(reference, candidate, output, pynifly=None):
    reference, candidate, output = map(lambda path: Path(path).resolve(), (reference, candidate, output))
    body.authored_output(output)
    api, _ = body.load_api(pynifly)
    report = {'schema': 'claw-expressive-contrast/1', 'requiredOuterRatio': 1.25,
              'metric': 'Effective envelope diameter maximum-minus-minimum; abdomen front maximum-minus-neutral.',
              'scope': __doc__, 'scriptSha256': body.sha(Path(__file__).read_bytes()), 'sexes': {}}
    # The shoulder field shares the arm's radial fade; widening that transition
    # to avoid normal turns changes its support even though its amplitude stays.
    changed = {name for _, _, lean, growth in REGIONS.values() for name in (lean, growth) if name}
    changed.add('CLAWTorsoShoulderGirth')
    for sex in ('male', 'female'):
        for ending in ('_0.nif', '_1.nif'):
            name = sex + 'bodywerewolf' + ending
            if (reference/name).read_bytes() != (candidate/name).read_bytes():
                raise ValueError('Neutral NIF bytes changed: ' + name)
        nif = api.NifFile(str(reference/(sex+'bodywerewolf_0.nif')))
        geometry = {shape.name: np.asarray(shape.verts, float) for shape in nif.shapes}
        faces = {shape.name: np.asarray(shape.tris, int) for shape in nif.shapes}
        counts = {name: len(value) for name, value in geometry.items()}
        decoded = {label: body.decode((folder/(sex+'bodywerewolf.tri')).read_bytes(), counts)
                   for label, folder in (('reference', reference), ('candidate', candidate))}
        if decoded['reference'].keys() != decoded['candidate'].keys():
            raise ValueError('Morph/shape inventory changed')
        protected = [key for key in decoded['reference'] if key[1] not in changed]
        if any(not np.array_equal(decoded['reference'][key], decoded['candidate'][key]) for key in protected):
            raise ValueError('A protected field outside the scoped regions changed')
        measured = {label: measure(geometry, faces, value) for label, value in decoded.items()}
        comparisons = compare_measures(measured['reference'], measured['candidate'])
        report['sexes'][sex] = {'measures': measured, 'comparison': comparisons,
                               'unchangedProtectedFields': len(protected),
                               'triSha256': {label: body.sha((folder/(sex+'bodywerewolf.tri')).read_bytes())
                                             for label, folder in (('reference', reference), ('candidate', candidate))}}
    report['passesContrastGate'] = all(row['comparison'][region]['outer']['passesRequiredRatio']
                                      for row in report['sexes'].values() for region in REGIONS)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    args = parser.parse_args()
    result = analyze(args.reference, args.candidate, args.out, args.pynifly)
    print(json.dumps({'report': str(args.out), 'passesContrastGate': result['passesContrastGate']}))
