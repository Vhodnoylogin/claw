"""Pure association of configured Spring2 values with previously observed rig roles.

The caller owns current provider/actor admission. Expected values use Bullet's
actual six-axis units, not inferred UI units. This does not score motion.
"""
import math
import struct

if __package__:
    from . import fsmp_joint_limit_readback as joint
else:
    import fsmp_joint_limit_readback as joint

PARAMETERS = frozenset(('lowerLimit', 'upperLimit', 'springEnabled', 'stiffness',
                        'damping', 'stopERP', 'stiffnessLimited', 'dampingLimited'))
BOOLEAN_PARAMETERS = frozenset(('springEnabled', 'stiffnessLimited', 'dampingLimited'))
require = joint.require


def _vector(value, boolean):
    require(type(value) is list and len(value) == 6, 'Explicit six-axis expectation required')
    if boolean:
        require(all(type(v) is bool for v in value), 'Boolean six-axis expectation required')
        return tuple(value)
    require(all(type(v) in (int, float) and math.isfinite(v) for v in value),
            'Finite six-axis expectation required')
    try:
        result = struct.pack('<6f', *value)
    except (OverflowError, struct.error) as error:
        raise ValueError('Float32 expectation unavailable') from error
    require(all(math.isfinite(v) for v in struct.unpack('<6f', result)),
            'Finite float32 expectation required')
    return result


def verify_parameters(associated, native, expected):
    """Bind two directed parent→driver edges; unrelated unknown types stay unknown."""
    require(native.get('schema') == 'claw-fsmp-step-witness/4' and native.get('status') == 'ready',
            'Ready schema4 observation required')
    sample = native['sample']
    window = sample['objectWindow']
    joint.witness.validate_window(window, sample['loadEpoch'])
    require(native['pid'] == associated['pid'] and sample['loadEpoch'] == associated['loadEpoch']
            and window['nonce'] == associated['nonce'], 'Associated process/window changed')
    require(set(expected) == set(joint.DRIVERS), 'Explicit bilateral expectations required')
    tokens = associated['A']['tokens']
    require(all(type(associated[side]['tokens'].get(name)) is int and
                1 <= associated[side]['tokens'][name] <= window['objectCount']
                for side in ('A', 'B') for name in joint.PARENTS + joint.DRIVERS),
            'Exact native integer role tokens required')
    require(tokens == associated['B']['tokens'] and
            len({tokens[name] for name in joint.PARENTS + joint.DRIVERS}) == 4,
            'Stable injective four-role association required')
    incident = window['incidentConstraints']
    require(incident['status'] in ('observed', 'unsupported'), 'Complete incident enumeration unavailable')
    result = {}
    for parent, driver in zip(joint.PARENTS, joint.DRIVERS):
        endpoints = {tokens[parent], tokens[driver]}
        edges = [row for row in incident['constraints']
                 if {row['bodyAToken'], row['bodyBToken']} == endpoints]
        require(len(edges) == 1, 'Unique target constraint unavailable: ' + driver)
        row = edges[0]
        require(row['bodyAToken'] == tokens[parent] and row['bodyBToken'] == tokens[driver],
                'Directed constraint endpoints differ: ' + driver)
        require(row['type'] == 12 and row['status'] == 'spring2' and row['enabled'] is True,
                'Enabled target Spring2 unavailable: ' + driver)
        actual, wanted = row['spring2'], expected[driver]
        require(type(wanted) is dict and set(wanted) == PARAMETERS,
                'Every expected parameter must be explicit: ' + driver)
        for field in sorted(PARAMETERS):
            boolean = field in BOOLEAN_PARAMETERS
            require(_vector(actual[field], boolean) == _vector(wanted[field], boolean),
                    'Configured ' + field + ' differs: ' + driver)
        result[driver] = {'token': row['token'], 'bodyAToken': row['bodyAToken'],
                          'bodyBToken': row['bodyBToken'],
                          'parameters': {key: list(value) for key, value in actual.items()}}
    return {'status': 'configured-target-spring2-values-observed', 'targets': result,
            'scope': 'Directed rig association and configured fields only; no solver impulse, '
                     'effective cap, waveform, rendering, contact or VR acceptance'}
