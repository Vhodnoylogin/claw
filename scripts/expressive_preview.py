"""Render untextured rest-geometry evidence for an expressive-body candidate.

This is an orthographic triangle renderer, without alpha textures, skinning or
game lighting. It is suitable for checking geometry, never artistic acceptance.
"""
import argparse
from pathlib import Path

import numpy as np

import expressive_body as body


def render(candidate, output, pynifly=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    candidate, output = Path(candidate).resolve(), Path(output).resolve()
    if output.exists() or body.ROOT in output.parents:
        raise ValueError('New external image required')
    api, _ = body.load_api(pynifly)
    states = [('Neutral', {}), ('Lean endpoints', dict.fromkeys(body.NAMES[:4], 1.)),
              ('Muscle/bulk endpoints', dict.fromkeys(body.NAMES[4:8], 1.)),
              ('Belly endpoint', {'CLAWTorsoBellyRound': 1.})]
    fig, axes = plt.subplots(4, 4, figsize=(15, 15), facecolor='#e7e9ec')
    for sex_index, sex in enumerate(('male', 'female')):
        nif = api.NifFile(str(candidate/(sex+'bodywerewolf_0.nif')))
        geometry = {s.name: np.array(s.verts) for s in nif.shapes}
        fields = body.decode((candidate/(sex+'bodywerewolf.tri')).read_bytes(), {n: len(v) for n, v in geometry.items()})
        for column, (label, state) in enumerate(states):
            for view, (horizontal, depth) in enumerate(((0, 1), (1, 0))):
                ax = axes[sex_index*2+view, column]
                ax.set_facecolor('#e7e9ec')
                vertices = []; faces = []; offset = 0; kinds = []
                for shape in nif.shapes:
                    if shape.name not in ('body', 'head', *body.COAT):
                        continue
                    v = geometry[shape.name].copy()
                    for morph, value in state.items():
                        v += value*fields.get((shape.name, morph), np.zeros_like(v))
                    vertices.append(v); faces.append(np.array(shape.tris)+offset); offset += len(v)
                    kinds.extend([shape.name in body.COAT]*len(shape.tris))
                triangles = np.concatenate(vertices)[np.concatenate(faces)]
                order = np.argsort(triangles[:, :, depth].mean(1), kind='stable')
                triangles = triangles[order]; coat = np.array(kinds)[order]
                normals = np.cross(triangles[:, 1]-triangles[:, 0], triangles[:, 2]-triangles[:, 0])
                normals /= np.maximum(np.linalg.norm(normals, axis=1)[:, None], 1e-12)
                light = np.array([-.3, .7, .65]); light /= np.linalg.norm(light)
                shade = .45+.45*abs(normals@light)
                color = np.c_[shade*.62, shade*.67, shade*.75, np.ones(len(shade))]
                color[coat, :3] = np.array([.72, .48, .24])*shade[coat, None]
                # Cards are drawn opaque: transparency cannot be reconstructed
                # from NIF geometry without the separately installed textures.
                ax.add_collection(PolyCollection(triangles[:, :, [horizontal, 2]], facecolors=color,
                                                 edgecolors='none', rasterized=True))
                ax.set_xlim((-84, 84) if view == 0 else (-84, 82)); ax.set_ylim(-5, 140)
                ax.set_aspect('equal'); ax.set_xticks([]); ax.set_yticks([])
                ax.set_title(sex.capitalize()+' / '+('front' if view == 0 else 'side')+' / '+label, fontsize=9)
    fig.suptitle('CLAW expressive body — untextured rest geometry\nOpaque alpha-ignorant coat cards; no pose, physics or artistic acceptance', fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, .95))
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=150); plt.close(fig)
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--candidate', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--pynifly', type=Path)
    a = p.parse_args()
    print(render(a.candidate, a.out, a.pynifly))
