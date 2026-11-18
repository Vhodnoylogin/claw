"""Pure one-axis angular correspondence using the unchanged four-token pairing.

RO_XYZ extraction follows the PDB-matched FSMP Bullet3.25 implementation,
including its column-indexed btGetMatrixElem convention. No collector or I/O.
"""
import math
if __package__:
    from . import fsmp_joint_limit_readback as linear
else:
    import fsmp_joint_limit_readback as linear

# Reuse the canonical pairing/frame helpers and their sole witness validator.
witness, cached, probe = linear.witness, linear.cached, linear.probe

PARENTS, DRIVERS, STAGES = linear.PARENTS, linear.DRIVERS, linear.STAGES
pair, joint_frame, pose_transform = linear.pair, linear.joint_frame, linear.pose_transform
JOINT_TOLERANCE = linear.JOINT_TOLERANCE
ANGULAR_TOLERANCE = .0001
LOWER_LEFT, UPPER_LEFT = .005, .01
require = linear.require


def euler_xyz(rotation):
    """Bullet XYZ angles in radians for a unit row-major joint basis.

    Positive Bullet x is negative ordinary active Rx. Reject invalid rotations
    and leave the singular regime unavailable rather than selecting a branch.
    """
    r = probe.numbers(rotation, 9)
    error = max(abs(sum(r[k*3+i]*r[k*3+j] for k in range(3)) - (1 if i == j else 0))
                for i in range(3) for j in range(3))
    det = (r[0]*(r[4]*r[8]-r[5]*r[7]) - r[1]*(r[3]*r[8]-r[5]*r[6])
           + r[2]*(r[3]*r[7]-r[4]*r[6]))
    require(error <= .0001 and abs(det-1) <= .0001, 'Unit proper angular basis unavailable')
    require(abs(r[6]) < .02, 'Outside frozen near-zero nonsingular XYZ regime')
    return [math.atan2(-r[7], r[8]), math.asin(r[6]), math.atan2(-r[3], r[0])]


def _coordinates(associated, native, rest_local):
    require(native['status'] == 'ready' and native['pid'] == associated['pid'], 'Angular native process differs')
    sample, tokens = native['sample'], associated['A']['tokens']
    window = sample['objectWindow']
    witness.validate_window(window, sample['loadEpoch'])
    require(sample['loadEpoch'] == associated['loadEpoch'] and window['nonce'] == associated['nonce'],
            'Angular window epoch/nonce differs')
    require(set(tokens) == set(PARENTS+DRIVERS) and len(set(tokens.values())) == 4,
            'Exact injective four-token association required')
    objects = {item['token']: item for item in window['objects']}
    require(all(token in objects for token in tokens.values()), 'Associated angular objects unavailable')
    angles, translations = {}, {}
    for stage in STAGES:
        angles[stage], translations[stage] = {}, {}
        for parent, driver in zip(PARENTS, DRIVERS):
            p, d = objects[tokens[parent]][stage], objects[tokens[driver]][stage]
            require(p['rigidBody'] is True and p['inverseMass'] == 0 and p['flags']&3 == 2 and
                    d['rigidBody'] is True and d['inverseMass'] == 20 and d['flags']&3 == 0,
                    'Angular original-mass/kinematic metadata differs')
            joint = joint_frame(pose_transform(p), pose_transform(d), rest_local[driver])
            angles[stage][driver] = euler_xyz(joint['rotationRowMajor'])
            translations[stage][driver] = joint['translation']
    return {'anglesRadians': angles, 'jointTranslations': translations}


def _gate(coordinates):
    angles, translations = coordinates['anglesRadians'], coordinates['jointTranslations']
    for stage in STAGES:
        left, right = angles[stage][DRIVERS[0]], angles[stage][DRIVERS[1]]
        require(abs(left[0]-LOWER_LEFT) <= ANGULAR_TOLERANCE, 'Left positive angular lower-limit correspondence absent')
        require(abs(right[0]) <= ANGULAR_TOLERANCE, 'Unchanged right angular x rest control moved')
        require(all(abs(value) <= .01+ANGULAR_TOLERANCE for xyz in (left, right) for value in xyz[1:]),
                'Unchanged angular y/z limits exceeded')
        require(all(abs(value) <= .15+JOINT_TOLERANCE for xyz in translations[stage].values() for value in xyz),
                'Original linear joint limits exceeded')
    for driver in DRIVERS:
        require(probe.max_delta(angles['initialPre'][driver], angles['lastPost'][driver]) <= ANGULAR_TOLERANCE,
                'Bilateral angular window was not settled')
        require(probe.max_delta(translations['initialPre'][driver], translations['lastPost'][driver]) <= JOINT_TOLERANCE,
                'Bilateral original-linear window was not settled')


def score_limit(associated, native_a, native_b, rest_local):
    require(associated['expectedInverseMass'] == dict.fromkeys(DRIVERS, 20.), 'Angular case requires original20/20 masses')
    require(cached.paused_signature(native_a) == cached.paused_signature(native_b), 'Angular paused state changed')
    require(native_a['requestSerial'] != native_b['requestSerial'] and
            native_b['sample']['sampledQpc'] > native_a['sample']['sampledQpc'], 'Angular native samples did not advance')
    require(associated['A']['tokens'] == associated['B']['tokens'], 'Angular role tokens changed')
    observed = {label: _coordinates(associated, native, rest_local)
                for label, native in (('A', native_a), ('B', native_b))}
    for value in observed.values(): _gate(value)
    return {'status': 'left-positive-angular-lower-limit-functional-correspondence-observed',
            'rotationOrder': 'Bullet RO_XYZ', 'units': 'radians', 'leftTarget': LOWER_LEFT,
            'angularTolerance': ANGULAR_TOLERANCE, 'leftUpperUnchanged': UPPER_LEFT,
            'associated': associated, 'pausedAngularCoordinates': observed,
            'scope': 'One original-mass unit-scale angular stop; no exact live limit getter or general solver calibration'}


def score_case(associated, final_native, rest_local, *, native_a, native_b):
    result = score_limit(associated, native_a, native_b, rest_local)
    sample, window = final_native['sample'], final_native['sample']['objectWindow']
    require(final_native['status'] == 'ready' and final_native['pid'] == associated['pid'], 'Final angular native process differs')
    witness.validate_window(window, sample['loadEpoch'])
    require(sample['loadEpoch'] == associated['loadEpoch'] and window['nonce'] == associated['nonce'] and
            window['status'] == 'complete' and window['pairedSteps'] == 900 and
            window['pairedSteps'] > associated['pairedStepsAtPause'], 'Same final complete900-pair angular window required')
    require(sample['mainFreezeTime'] is False and sample['mainFreezeNextFrame'] is False and sample['uiPaused'] is False and
            sample['engineMultiplier'] == 1 and sample['timerPauseCount'] == 0, 'Original normal angular clock was not restored')
    final = _coordinates(associated, final_native, rest_local)
    _gate(final)
    result['completed900AngularCoordinates'] = final
    return result
