"""Read back configured SE FSMP limits for one quiet, owned werewolf graph.

The caller supplies the pinned XML, admitted fixture and native snapshots taken
immediately around the WORLD read. Configuration is independent of excitation:
the incident catalogue covers every target and remains stable in that window.
"""

import json
import math
import xml.etree.ElementTree as ET

if __package__:
    from . import fsmp_cached_world as cached, fsmp_constraint_readback as constraints
    from . import fsmp_probe as probe, fsmp_vr_actor_binding as rig
else:
    import fsmp_cached_world as cached
    import fsmp_constraint_readback as constraints
    import fsmp_probe as probe
    import fsmp_vr_actor_binding as rig


joint = constraints.joint
witness = joint.witness
require = probe.require
V4_SE = 'claw-fsmp-step-witness/4'
WOLF_RACE = '0x000CDD84'
EQUILIBRIUM_FIELDS = ('linearEquilibrium', 'angularEquilibrium')
PARAMETER_PAIRS = {
    'lowerLimit': ('linearLowerLimit', 'angularLowerLimit'),
    'upperLimit': ('linearUpperLimit', 'angularUpperLimit'),
    'stiffness': ('linearStiffness', 'angularStiffness'),
    'damping': ('linearDamping', 'angularDamping'),
}


def authored_joints(xml, sex):
    """Read the original identity-frame motion-only XML, with all fields explicit."""
    try:
        _, _, configured = rig.source_profile(xml, sex)
        root = ET.fromstring(xml)
        result = {}
        for row in root.findall('generic-constraint'):
            edge = (row.attrib['bodyA'], row.attrib['bodyB'])
            names = [child.tag for child in row]
            frame = 'frameInA' if edge[1] in probe.FEMALE[len(probe.MALE):] else 'frameInB'
            vectors = set(rig.FIELDS + EQUILIBRIUM_FIELDS)
            require(set(row.attrib) == {'bodyA', 'bodyB'}
                    and set(names) == vectors | {frame} and len(names) == len(vectors) + 1
                    and all(set(child.attrib) == {'x', 'y', 'z'} and len(child) == 0
                            and not (child.text or '').strip() for child in row if child.tag in vectors),
                    'Missing, duplicate, or unsupported constraint element: ' + edge[1])
            values = {name: list(configured[edge][name]) for name in rig.FIELDS}
            values.update({name: list(rig.xml_xyz(row, name)) for name in EQUILIBRIUM_FIELDS})
            expected = {key: values[linear] + values[angular]
                        for key, (linear, angular) in PARAMETER_PAIRS.items()}
            require(all(lo <= hi for lo, hi in zip(expected['lowerLimit'], expected['upperLimit'], strict=True))
                    and all(abs(value) < math.pi for key in ('lowerLimit', 'upperLimit') for value in expected[key][3:])
                    and all(value > 0 for value in expected['stiffness'])
                    and all(value >= 0 for value in expected['damping']),
                    'Supported six-axis Spring2 configuration required: ' + edge[1])
            # Pinned SE FSMP defaults for this motion-only XML subset.
            expected.update(springEnabled=[True] * 6, stopERP=[.2] * 6,
                            stiffnessLimited=[True] * 6, dampingLimited=[True] * 6)
            result[edge] = {'frame': frame, 'declared': values, 'expected': expected}
        return result
    except (ET.ParseError, KeyError, TypeError) as error:
        raise ValueError('Invalid original FSMP motion XML') from error


def _normal_window(native, pid, nonce, status):
    require(type(native) is dict and native.get('schema') == V4_SE,
            'SE native v4 snapshot required')
    native = witness.parse(json.dumps(native, allow_nan=False))
    require(native['status'] == 'ready' and native['pid'] == pid, 'Native process/phase changed')
    sample = native['sample']
    window = witness.validate_window(sample['objectWindow'], sample['loadEpoch'], nonce, version=4)
    require(window['status'] == status and window['pairedSteps'] >= 2 and not window['awaitingPost']
            and window['lastPostQpc'] <= sample['sampledQpc']
            and window['lastPreThreadId'] == window['lastPostThreadId']
            and sample['mainFreezeTime'] is False and sample['mainFreezeNextFrame'] is False
            and sample['uiPaused'] is False and sample['mainGameActive'] is True
            and sample['worldRootPresent'] is True and sample['timerPauseCount'] == 0
            and sample['engineMultiplier'] == 1, 'Unpaused normal-rate coherent pair required')
    return native, window


def _kinematic(body):
    return body['rigidBody'] is True and body['inverseMass'] == 0 and body['flags'] & 3 == 2


def _dynamic(body):
    return body['rigidBody'] is True and body['inverseMass'] > 0 and body['flags'] & 3 == 0


def _associate(row, window, sex):
    # This existing spatial matcher checks poses only. The caller supplies the
    # quiet bracket; its historical name does not imply that this case is paused.
    matched = cached.paused_match(row, window, sex)
    tokens = {}
    for record in matched['dynamicBodies']:
        candidates = record['candidates']
        require(len(candidates) == 1, 'Missing or ambiguous dynamic pose: ' + record['node'])
        tokens[record['node']] = candidates[0]['token']

    objects = {body['token']: body for body in window['objects']}
    for name in rig.anchor_roles(sex):
        world = row['nodes'][name]['world']
        candidates = [token for token, body in objects.items() if _kinematic(body['lastPost'])
                      and probe.max_delta(body['lastPost']['world'][9:], world['translation']) <= joint.TRANSLATION_MATCH
                      and probe.max_delta(body['lastPost']['world'][:9], world['rotationRowMajor']) <= joint.ROTATION_MATCH]
        require(len(candidates) == 1, 'Missing or ambiguous kinematic pose: ' + name)
        tokens[name] = candidates[0]
    require(len(tokens) == len(set(tokens.values())) == len(objects), 'Full injective rig association required')
    for name, token in tokens.items():
        check_type = _dynamic if name in probe.drivers(sex) else _kinematic
        require(all(check_type(objects[token][stage]) for stage in joint.STAGES),
                'Body type changed across native stages: ' + name)
    return tokens


def _observe_joints(window, tokens, expected):
    incident = window['incidentConstraints']
    rows = incident['constraints']
    observed = {(row['bodyAToken'], row['bodyBToken']): row for row in rows}
    require(incident['status'] == 'observed' and len(rows) == len(observed)
            and observed.keys() == {(tokens[parent], tokens[driver]) for parent, driver in expected},
            'Full unique directed rig constraint catalogue required')
    result = {}
    for (parent, driver), config in expected.items():
        row = observed[tokens[parent], tokens[driver]]
        require(row['type'] == 12 and row['status'] == 'spring2' and row['enabled'] is True,
                'Enabled Spring2 constraint required: ' + driver)
        actual = row['spring2']
        for field, wanted in config['expected'].items():
            boolean = field in constraints.BOOLEAN_PARAMETERS
            require(constraints._vector(actual[field], boolean) == constraints._vector(wanted, boolean),
                    'Configured ' + field + ' differs: ' + driver)
        result[driver] = {
            'parent': parent, 'parentToken': tokens[parent], 'driverToken': tokens[driver],
            'constraintToken': row['token'], 'authoredFrame': config['frame'],
            'authoredXml': config['declared'], 'observedSpring2': {key: list(value) for key, value in actual.items()},
        }
    return result


def evaluate(xml, world, native_before, native_after, *, reference, base, sex, pid, nonce, expected_guard=None):
    """Verify all named SE unit-scale joints for the same quiet admitted actor.

    Observer and witness generations are independent. The shared quiet pose,
    process and unchanged provider catalogue establish the join. Equilibrium is
    retained as authored XML only, since the native contract has no such readback.
    """
    require(witness.integer(pid, 1) and witness.integer(nonce, 1), 'Explicit native process and window required')
    reference, base = probe.form(reference), probe.form(base)
    require(int(reference, 16) >= 0xFF000000, 'Owned disposable NPC form required')
    expected = authored_joints(xml, sex)
    row = probe.snapshot(world, reference, sex)
    guard = row['guard']
    actor = guard['actor']
    require(guard['session'].partition('-')[0] == str(pid)
            and actor['baseForm'] == base and actor['race'] == actor['baseRace'] == WOLF_RACE
            and (expected_guard is None or guard == expected_guard),
            'Admitted actor/process incarnation changed')
    require(abs(guard['scale'] - 1) <= 1e-5 and abs(row['root']['scale'] - 1) <= 1e-5
            and all(abs(node[space]['scale'] - 1) <= 1e-5 for node in row['nodes'].values()
                    for space in ('local', 'world')), 'Unit SE actor/root/local/WORLD scales required')

    before, start = _normal_window(native_before, pid, nonce, 'collecting')
    after, end = _normal_window(native_after, pid, nonce, 'collecting')
    progression = witness.compare(before, after)
    require(progression['providerCompletedStepsObserved'] and start['pairedSteps'] < end['pairedSteps']
            and start['firstPreQpc'] == end['firstPreQpc'] and start['lastPostQpc'] < end['lastPostQpc']
            and start['incidentConstraints'] == end['incidentConstraints']
            and [(body['token'], body['initialPre']) for body in start['objects']] ==
            [(body['token'], body['initialPre']) for body in end['objects']],
            'Advancing unchanged native configuration bracket required')
    tokens = _associate(row, start, sex)
    require(tokens == _associate(row, end, sex), 'Run-local role association changed')
    return {
        'status': 'configured-se-rig-observed', 'pid': pid, 'nonce': nonce,
        'loadEpoch': after['sample']['loadEpoch'], 'sex': sex, 'reference': reference,
        'worldSample': row['sample'], 'worldGuard': guard,
        'firstPreQpc': start['firstPreQpc'],
        'bracketingLastPostQpc': [start['lastPostQpc'], end['lastPostQpc']],
        'tokens': tokens, 'joints': _observe_joints(end, tokens, expected),
        'scope': 'Configured Spring2 fields only. Equilibrium and frame are XML declarations. '
                 'No motion, collision, rendered deformation or VR acceptance.',
    }


def _step_motion(anchor, driver, step, begin, end):
    relative = [probe.relative(joint.pose_transform(driver[phase]), joint.pose_transform(anchor[phase]))
                for phase in ('pre', 'post')]
    before, after = relative
    return {'step': step, 'preQpc': begin, 'postQpc': end,
            'translationGU': math.dist(before['translation'], after['translation']),
            'rotationComponentChange': probe.max_delta(before['rotationRowMajor'], after['rotationRowMajor'])}


def evaluate_motion(configuration, native_final, *, translation_floor=.005, rotation_floor=.001):
    """Measure relative pre/post movement on the already associated directed rig."""
    require(configuration['status'] == 'configured-se-rig-observed'
            and all(type(value) in (int, float) and math.isfinite(value) and value > 0
                    for value in (translation_floor, rotation_floor)),
            'Expected an associated rig and positive motion floors')
    final, window = _normal_window(native_final, configuration['pid'], configuration['nonce'], 'complete')
    require(final['sample']['loadEpoch'] == configuration['loadEpoch']
            and window['firstPreQpc'] == configuration['firstPreQpc']
            and window['lastPreQpc'] > configuration['bracketingLastPostQpc'][1],
            'Completed motion belongs to a different rig bracket')
    tokens = configuration['tokens']
    objects = {body['token']: body for body in window['objects']}
    observed = {row['token']: row for row in window['incidentConstraints']['constraints']}
    require(objects.keys() == set(tokens.values())
            and observed.keys() == {edge['constraintToken'] for edge in configuration['joints'].values()},
            'Completed rig body or joint inventory changed')
    movements = {}
    for name, edge in configuration['joints'].items():
        anchor_token, driver_token = tokens[edge['parent']], tokens[name]
        row = observed[edge['constraintToken']]
        require(row['bodyAToken'] == anchor_token and row['bodyBToken'] == driver_token
                and row['enabled'] is True and row['status'] == 'spring2' and row['type'] == 12
                and row['spring2'] == edge['observedSpring2'], 'Completed constraint differs: ' + name)
        anchor, driver = objects[anchor_token], objects[driver_token]
        clocks = ('firstNonzeroStep', 'firstNonzeroPreQpc', 'firstNonzeroPostQpc')
        samples = []
        if (anchor['firstNonzeroPair'] and driver['firstNonzeroPair'] and all(anchor[k] == driver[k] for k in clocks)
                and window['firstPreQpc'] <= anchor['firstNonzeroPreQpc']
                < anchor['firstNonzeroPostQpc'] <= window['lastPostQpc']):
            samples.append(_step_motion(anchor['firstNonzeroPair'], driver['firstNonzeroPair'],
                                        *(anchor[k] for k in clocks)))
        samples.append(_step_motion({'pre': anchor['lastPre'], 'post': anchor['lastPost']},
                                    {'pre': driver['lastPre'], 'post': driver['lastPost']},
                                    window['pairedSteps'], window['lastPreQpc'], window['lastPostQpc']))
        qualified = any(s['translationGU'] >= translation_floor or s['rotationComponentChange'] >= rotation_floor
                        for s in samples)
        movements[name] = {'parent': edge['parent'], 'parentToken': anchor_token, 'driverToken': driver_token,
                           'motionObserved': qualified, 'samples': samples}
    count = sum(item['motionObserved'] for item in movements.values())
    return {'status': 'observed' if count == len(movements) else 'incomplete', 'observedJointCount': count,
            'pairedSteps': window['pairedSteps'], 'translationFloorGU': translation_floor,
            'rotationComponentFloor': rotation_floor, 'joints': movements}
