"""Pure v3 attachment-point kinematics. No transport or coefficient qualification.

Caller owns actor/module admission and token association. The conditional source
comparison consumes supplied parameters; it never observes solver fps or ERP.
"""
import json

if __package__:
    from . import fsmp_damping_response_readback as response
else:
    import fsmp_damping_response_readback as response

joint, probe, witness = response.joint, response.joint.probe, response.joint.witness
require = joint.require


def cross(a, b):
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def attachment_state(anchor, driver, rest_local, axis=0):
    """Unit-scale frameInA-origin attachment, including angular lever velocity.

    Driver point pB-RB*R0^T*t0 uses the same rest-pivot convention as joint_frame.
    coordinateDerivative additionally includes rotation of the parent axis;
    relativePointVelocityAxis alone is not that derivative for a rotating axis.
    """
    require(type(axis) is int and 0 <= axis < 3, 'Explicit xyz joint axis required')
    witness.pose(anchor, 3); witness.pose(driver, 3)
    require(anchor['rigidBody'] and driver['rigidBody'], 'Rigid-body dynamics required')
    a, b, rest = joint.pose_transform(anchor), joint.pose_transform(driver), joint.unit(rest_local)
    pivot = response.pivot(rest)
    arm = [-sum(b['rotationRowMajor'][i*3+j]*pivot[j] for j in range(3)) for i in range(3)]
    direction = [a['rotationRowMajor'][i*3+axis] for i in range(3)]
    tangent = cross(driver['angularVelocity'], arm)
    point_velocity = [driver['linearVelocity'][i]+tangent[i] for i in range(3)]
    separation = [b['translation'][i]+arm[i]-a['translation'][i] for i in range(3)]
    relative_velocity = [point_velocity[i]-anchor['linearVelocity'][i] for i in range(3)]
    axis_rotation = response.dot(cross(anchor['angularVelocity'], direction), separation)
    projected = response.dot(direction, relative_velocity)
    return {'jointCoordinate': joint.joint_frame(a, b, rest)['translation'][axis],
            'axis': direction, 'bodyPointOffset': arm, 'bodyPointTangentVelocity': tangent,
            'bodyPointVelocity': point_velocity, 'relativePointVelocityAxis': projected,
            'axisRotationContribution': axis_rotation, 'coordinateDerivative': projected+axis_rotation}


def analyze_first_pair(native, parent_token, driver_token, rest_local, *,
                       lower_limit=None, fps=None, stop_erp=None):
    """Read one actually co-temporal first-WORLD-change pair, never splice onsets.

    Optional lower-row math is conditional on supplied parameters and a fixed
    parent axis. No residual threshold, inferred coefficient or passing oracle.
    """
    require(native.get('schema') == 'claw-fsmp-step-witness/3' and native.get('status') == 'ready',
            'Ready explicit v3 dynamics required')
    witness.parse(json.dumps(native))
    require(type(parent_token) is int and type(driver_token) is int and
            parent_token > 0 and driver_token > 0 and parent_token != driver_token,
            'Two distinct associated body tokens required')
    sample = native['sample']; window = sample['objectWindow']
    objects = {row['token']: row for row in window['objects']}
    require(parent_token in objects and driver_token in objects, 'Associated body missing')
    a, b = objects[parent_token], objects[driver_token]
    require(a['firstNonzeroStep'] > 0 and a['firstNonzeroPair'] is not None and
            b['firstNonzeroPair'] is not None and
            all(a[key] == b[key] for key in ('firstNonzeroStep', 'firstNonzeroPreQpc', 'firstNonzeroPostQpc')),
            'Exact co-temporal onset pair required; object first changes can differ')
    states = {stage: attachment_state(a['firstNonzeroPair'][stage], b['firstNonzeroPair'][stage], rest_local)
              for stage in ('pre', 'post')}
    out = {'pid': native['pid'], 'loadEpoch': sample['loadEpoch'], 'nonce': window['nonce'],
           'parentToken': parent_token, 'driverToken': driver_token, 'pair': a['firstNonzeroStep'],
           **states, 'hostCallbackStatistics': {
               'minimum': window['minimumPairedHostTimeStep'], 'sum': window['summedPairedHostTimeStep'],
               'scope': window['timeStepStatisticsScope']},
           'dampingQualified': False, 'constraintParametersDirectlyObserved': False,
           'solverFpsDirectlyObserved': False, 'integratedSimulationTimeProven': False}
    supplied = (lower_limit, fps, stop_erp)
    if any(v is not None for v in supplied):
        require(all(witness.number(v) for v in supplied) and fps > 0 and 0 <= stop_erp <= 1,
                'Complete finite supplied lower/fps/ERP assumptions required')
        require(all(v == 0 for stage in ('pre', 'post')
                    for v in a['firstNonzeroPair'][stage]['angularVelocity']),
                'Conditional lower-row comparison requires a nonrotating parent')
        require(states['pre']['axis'] == states['post']['axis'],
                'Conditional lower-row comparison requires the same observed axis')
        target = -fps*stop_erp*(states['pre']['jointCoordinate']-lower_limit)
        out['conditionalLowerRow'] = {'suppliedLower': lower_limit, 'suppliedFps': fps, 'suppliedStopERP': stop_erp,
            'targetRelativeVelocity': target,
            'observedMinusTarget': states['post']['relativePointVelocityAxis']-target,
            'scope': 'Conditional predictive lower-row source-law comparison, not directly observed parameters or a damping pass.'}
    return out
