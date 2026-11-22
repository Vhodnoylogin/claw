"""Measure camera-ball clearance of the retained upper-torso skin in VR."""
from __future__ import annotations

from argparse import ArgumentParser
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/main/components/vr-body'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'contact-profiles'))
from posed_contact import Skin, breast_rig, contact_fit, offsets, read_json, read_pinned_asset, require, world_matrix
from vr_dispatch import SEXES, require_static_nif, resource_paths


def retained_torso(nif, tri, pynifly):
    """Read the exact installed candidates from independently admitted pins."""
    virtual_tri = tri['virtualPath'].replace('\\', '/').casefold()
    sexes = [sex for sex in SEXES if virtual_tri == resource_paths(sex).casefold()]
    require(len(sexes) == 1, 'Expected a namespaced VR Body.tri path')
    path, data = read_pinned_asset(nif)
    require_static_nif(data, expected_sex=sexes[0])
    _, raw = read_pinned_asset(tri)
    api, _, _ = breast_rig.load_pynifly(pynifly)
    model = api.NifFile(str(path))
    matches = [shape for shape in model.shapes if shape.name.casefold() == 'head']
    require(len(matches) == 1, 'Expected one retained head-textured torso')
    shape = matches[0]
    records = {key: value for key, value in offsets(raw).items() if key[0] == shape.name}
    require(records, 'Expected TRI fields for the retained upper torso')
    return shape, records


def observation_plan(shape, records):
    skin = Skin(shape, {}, {})
    require(skin.faces.ndim == 2 and skin.faces.shape[1] == 3 and len(skin.faces) > 0
            and skin.faces.min() >= 0 and skin.faces.max() < len(skin.vertices), 'Invalid retained torso topology')
    require(all(name == shape.name and 0 <= index < len(skin.vertices) for name, _, index in records),
            'TRI index is outside the retained torso')
    weights = skin.weights[np.unique(skin.faces)]
    return {'shape': shape.name, 'vertices': len(skin.vertices), 'triangles': len(skin.faces),
            'bones': [name for index, name in enumerate(skin.names) if np.any(weights[:, index] > 0)],
            'morphs': sorted({morph for _, morph, _ in records})}


def matrix(value):
    """Convert the typed post-VRIK/HIGGS pose to the shared skinning convention."""
    rotation = np.asarray(value['rotation'], dtype=float)
    require(rotation.shape == (3, 3), 'Expected three observed rotation rows')
    return world_matrix({'rotationRowMajor': rotation.reshape(9),
                         'translation': value['position'], 'scale': value['scale']})


def clearance(shape, records, observation):
    """Consume one actor-bound native observation, including its effective TRI values.

    The caller verifies the subject, archive winner and native capture provenance.
    This reconstructs the retained surface only. The left camera's near distance
    supplies a ball radius, and the resulting margin is separate from visibility.
    """
    plan = observation_plan(shape, records)
    require(observation.get('phase') == 'PostVrikPostHiggs', 'Expected a co-sampled avatar phase')
    visible = [row for row in observation['shapes'] if row['name'].casefold() == plan['shape'].casefold()]
    require(len(visible) == 1 and visible[0].get('ancestorCull') is False and visible[0].get('skinned') is True,
            'Expected the unculled retained skinned torso')
    missing = sorted(set(plan['bones']) - observation['bones'].keys())
    require(not missing, 'Missing influential torso bones: ' + ', '.join(missing))
    values = observation.get('effectiveMorphs')
    require(isinstance(values, dict) and all(type(values.get(name)) in (int, float) and np.isfinite(values[name])
                                             for name in plan['morphs']), 'Complete co-sampled effective TRI values required')
    near = observation['nearLeft']
    require(type(near) in (float, int) and np.isfinite(near) and near > 0, 'Invalid engine near distance')
    camera = matrix(observation['camera'])[:3, 3]
    frames = {name: matrix(observation['bones'][name]['world']) for name in plan['bones']}
    skin = Skin(shape, records, values)
    selected, triangles = np.unique(skin.faces, return_inverse=True)
    vertices = skin.support(selected, frames, None)
    surface = vertices[triangles.reshape(-1, 3)]
    distance = float(contact_fit.triangle_distance([camera], surface)[0])
    return {'triangles': len(surface), 'closestReconstructedTorsoDistanceGu': distance,
            'leftCameraBallMarginGu': distance - near, 'torsoSeparatesFromBall': distance > near,
            'renderedPixelsVerified': False}


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('assets', type=Path,
                        help='JSON with exact nif and tri pins and the tri virtualPath')
    parser.add_argument('--pynifly', type=Path, required=True)
    parser.add_argument('--observation', type=Path, help='One already admitted native avatar envelope')
    args = parser.parse_args()
    assets = read_json(args.assets)
    shape, records = retained_torso(assets['nif'], assets['tri'], args.pynifly)
    result = observation_plan(shape, records)
    if args.observation:
        observation = read_json(args.observation)
        require(observation.get('schema') == 'claw-vr-vrik-world-avatar/1' and observation.get('status') == 'ready',
                'Expected a ready native avatar envelope')
        result['clearance'] = clearance(shape, records, observation['sample'])
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
