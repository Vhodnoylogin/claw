"""Compare serialized abdomen profiles on pinned rest meshes, outside the game.

The measurements are fixed-plane alpha-ignorant envelopes. They do not establish
texture quality, physical volume, posed skinning or artistic acceptance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

import expressive_body as body


LEVELS = (64., 68., 72., 76., 80., 84., 88., 92., 96.)
MORPH = 'CLAWTorsoBellyRound'


def sagittal_profile(geometry, faces, fields, state, selected):
    """Front outline at frozen belly planes and neutral triangle-centroid ROI."""
    vertices, triangles, offset = [], [], 0
    for name in selected:
        if name not in geometry:
            continue
        neutral = geometry[name]
        current = neutral.copy()
        for morph, value in state.items():
            current += fields.get((name, morph), np.zeros_like(neutral))*value
        centres = neutral[faces[name]].mean(axis=1)
        keep = ((np.abs(centres[:, 0]) < 8) & (centres[:, 1] > 0) &
                (centres[:, 1] < 40) & (centres[:, 2] > 58) &
                (centres[:, 2] < 104))
        vertices.append(current)
        triangles.append(faces[name][keep]+offset)
        offset += len(neutral)
    vertices, triangles = np.concatenate(vertices), np.concatenate(triangles)
    return {str(int(z)): body.section(vertices, triangles, 2, z) for z in LEVELS}


def compare(reference, candidate, output, pynifly=None):
    reference, candidate, output = map(lambda p: Path(p).resolve(),
                                       (reference, candidate, output))
    if output.exists() or body.ROOT in output.parents:
        raise ValueError('A new report outside the repository is required')
    api, _ = body.load_api(pynifly)
    report = {'schema': 'claw-abdomen-profile-comparison/1',
              'scriptSha256': body.sha(Path(__file__).read_bytes()),
              'scope': 'Fixed rest meshes; plane/front-envelope proxies, not volume or visual acceptance.',
              'roi': {'neutralTriangleCentroid': {'absXLessThan': 8, 'y': [0, 40], 'z': [58, 104]},
                      'horizontalPlanesZ': list(LEVELS), 'forwardAxis': '+Y'},
              'sexes': {}}
    for sex in ('male', 'female'):
        nif_name, tri_name = sex+'bodywerewolf_0.nif', sex+'bodywerewolf.tri'
        if (reference/nif_name).read_bytes() != (candidate/nif_name).read_bytes():
            raise ValueError('Cannot compare different neutral meshes')
        nif = api.NifFile(str(reference/nif_name))
        geometry = {s.name: np.asarray(s.verts, float) for s in nif.shapes}
        faces = {s.name: np.asarray(s.tris, int) for s in nif.shapes}
        counts = {n: len(v) for n, v in geometry.items()}
        decoded = {label: body.decode((folder/tri_name).read_bytes(), counts)
                   for label, folder in (('reference', reference), ('candidate', candidate))}
        if decoded['reference'].keys() != decoded['candidate'].keys():
            raise ValueError('The morph/shape inventory changed')
        protected = {key for key in decoded['reference'] if key[1] != MORPH}
        if any(not np.array_equal(decoded['reference'][key], decoded['candidate'].get(key))
               for key in protected):
            raise ValueError('A non-abdomen field changed')
        row = {'nifSha256': body.sha((reference/nif_name).read_bytes()),
               'triSha256': {label: body.sha((folder/tri_name).read_bytes())
                             for label, folder in (('reference', reference), ('candidate', candidate))},
               'unchangedOtherFields': len(protected), 'families': {}}
        for family, selected in (('skin', ('body', 'head')), ('fur', body.COAT)):
            neutral = sagittal_profile(geometry, faces, decoded['reference'], {}, selected)
            family_row = {'neutral': neutral, 'states': {}}
            for label, fields in decoded.items():
                for coefficient in (.25, .5, .75, 1.):
                    profile = sagittal_profile(geometry, faces, fields, {MORPH: coefficient}, selected)
                    shift = {z: value['front']-neutral[z]['front']
                             if value and neutral[z] else None for z, value in profile.items()}
                    # Dome prominence above a chord between two declared flank
                    # heights. It is a reproducible geometric proxy, not a score.
                    sagitta = (shift['80']-(shift['68']+shift['92'])/2
                                if all(shift[z] is not None for z in ('68', '80', '92')) else None)
                    family_row['states'][label+':'+str(coefficient)] = {
                        'profile': profile, 'frontShift': shift, 'addedDomeSagitta': sagitta}
            row['families'][family] = family_row
        report['sexes'][sex] = row
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    return report


def plot(report, output):
    """Plot actual envelope changes; scientific figure, not a body rendering."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output = Path(output).resolve()
    if output.exists() or body.ROOT in output.parents:
        raise ValueError('A new plot outside the repository is required')
    fig, axes = plt.subplots(2, 2, figsize=(9, 7), constrained_layout=True)
    for row, (sex, data) in enumerate(report['sexes'].items()):
        for col, (family, family_data) in enumerate(data['families'].items()):
            ax = axes[row, col]
            for label, colour in (('reference', '#666666'), ('candidate', '#c07823')):
                state = family_data['states'][label+':1.0']
                xs = [state['frontShift'][str(int(z))] for z in LEVELS]
                ax.plot(xs, LEVELS, 'o-', color=colour,
                        label='CLAW 0.7' if label == 'reference' else 'Dome candidate')
            ax.set_title(sex.capitalize()+' / '+family)
            ax.set_xlabel('Forward outline shift (+Y, model units)')
            ax.set_ylabel('Fixed horizontal plane Z')
            ax.grid(alpha=.25); ax.legend(fontsize=8)
    fig.suptitle('Isolated belly = 1: measured rest-geometry profile\n'
                 'Fixed neutral ROI; alpha-ignorant envelopes, no visual acceptance', fontsize=11)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150); plt.close(fig)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--pynifly', type=Path)
    parser.add_argument('--plot', type=Path, help='Optional new external PNG profile plot')
    args = parser.parse_args()
    result = compare(args.reference, args.candidate, args.out, args.pynifly)
    if args.plot:
        plot(result, args.plot)
    print(json.dumps({'report': str(args.out), 'sexes': list(result['sexes'])}))
