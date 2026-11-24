"""Pure, component-local readback of the frozen male12 FSMP composition.

No transport, provider calls, installation, or game-launch operations are exposed.
The ordinary male9/female11 readers and their role catalogues remain unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
INTEGRATION = REPO / 'src/test/python/integration'
COMPOSITION = REPO / 'src/main/components/adult-anatomy/python/compose_motion.py'
CATALOGUE = HERE / 'male12-retained-20261113.json'
XML_SHA = '7cb169385c37b28038643c406c07d6b91937672b872c908420e2172822647d8e'
EXTRA_DRIVERS = ('WWD 2', 'WWLB 1', 'WWRB 1')
EXTRA_NODES = (*EXTRA_DRIVERS, 'WWD 1', 'CME Pelvis [Pelv]')
ANATOMY_PARENTS = {'WWD 2': 'WWD 1', 'WWLB 1': 'WWD 2', 'WWRB 1': 'WWD 2'}
SCALE = 1.1299999952316284  # Observed float32(1.13), not a requested game change.
_MODULES = None


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def shared():
    global _MODULES
    if _MODULES is None:
        sys.path.insert(0, str(INTEGRATION))
        import fsmp_probe as probe
        import fsmp_rig_config_readback as rig
        import fsmp_uniform_scale_readback as uniform
        for module in (probe, rig, uniform):
            require(Path(module.__file__).resolve().parent == INTEGRATION,
                    'A different FSMP reader is already imported')
        spec = importlib.util.spec_from_file_location('claw_male12_composition_parser', COMPOSITION)
        composition = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(composition)
        _MODULES = probe, rig, uniform, composition
    return _MODULES


def roles():
    probe, _, _, _ = shared()
    return (*probe.MALE, *EXTRA_DRIVERS)


def parents():
    probe, _, _, _ = shared()
    male = probe.MALE
    return {male[0]: 'NPC Head [Head]', male[1]: male[0],
            male[2]: 'NPC Head [Head]', male[3]: male[2],
            male[4]: 'Tails', **dict(zip(male[5:], male[4:-1])), **ANATOMY_PARENTS}


def anchors():
    return ('NPC Head [Head]', 'Tails', 'WWD 1')


def node_names():
    probe, _, _, _ = shared()
    return tuple(dict.fromkeys((*roles(), *anchors(), *probe.CONTROL,
                               *probe.INTERMEDIATES, 'CME Pelvis [Pelv]')))


def source_profile(xml):
    """Reuse the authored component parser; admit only the exact original graph."""
    _, rig, _, composition = shared()
    root, bones = composition.inspect_xml(xml, roles(), anchors())
    links = root.findall('generic-constraint')
    found = {(row.get('bodyA'), row.get('bodyB')) for row in links}
    require(found == {(parent, driver) for driver, parent in parents().items()}
            and len(links) == 12, 'Exact male12 directed joint graph required')
    require(digest(xml) == XML_SHA, 'Frozen male12 authored XML bytes differ')
    result = {}
    for row in links:
        parent, driver = row.get('bodyA'), row.get('bodyB')
        vectors = {name: list(rig.rig.xml_xyz(row, name))
                   for name in (*rig.rig.FIELDS, *rig.EQUILIBRIUM_FIELDS)}
        result[driver] = {
            'parent': parent, 'frame': 'frameInB', 'declared': vectors,
            'mass': float(bones[driver].findtext('mass')),
            'inertia': list(rig.rig.xml_xyz(bones[driver], 'inertia')),
        }
    return result


def _projection(raw):
    probe, _, _, _ = shared()
    return {**raw, 'nodes': [row for row in raw['nodes'] if row['name'] in probe.node_names('male')]}


def snapshot(raw, reference):
    """Canonical male9 snapshot plus five strictly identified anatomy rows."""
    probe, _, _, _ = shared()
    require(type(raw.get('nodes')) is list, 'Missing actual node inventory')
    names = [row.get('name') for row in raw['nodes']]
    require(len(names) == len(set(names)) == len(node_names()) and set(names) == set(node_names()),
            'Exact male12/control node inventory required')
    result = probe.snapshot(_projection(raw), reference, 'male')
    identity, root = result['guard']['identity'], result['guard']['root']
    for row in raw['nodes']:
        if row['name'] not in EXTRA_NODES:
            continue
        require(row.get('status') == 'available' and row.get('firstPerson') is False
                and probe.form(row.get('form')) == reference and row.get('identity') == identity
                and row.get('rootIdentity') == root, 'Anatomy node actor/root identity changed')
        result['nodes'][row['name']] = {space: probe.transform(row[space]) for space in ('world', 'local')}
    return result


def expected_scales(row):
    require(abs(row['guard']['scale'] - SCALE) <= 1e-5 and abs(row['root']['scale'] - SCALE) <= 1e-5
            and all(abs(node['local']['scale'] - 1) <= 1e-5
                    and abs(node['world']['scale'] - SCALE) <= 1e-5 for node in row['nodes'].values()),
            'Authored male12 uniform actor/root/WORLD 1.13 and LOCAL 1 scales required')


def score_reference(document):
    """Replay the historical on/off/on reference stimulus with unchanged floors.

    This preserves the original ultimate-anchor contrast. It does not infer an
    independent descendant-joint response or a synchronized physics phase.
    """
    probe, _, _, _ = shared()
    require(document.get('sex') == 'male' and document.get('actorRole') == 'disposable-npc'
            and document.get('stimulus', 'reference') == 'reference', 'Exact male reference protocol required')
    reference = probe.form(document['reference'])
    for action, value in (('first-off', True), ('reenable', False), ('second-off', True), ('restore', False)):
        require(probe.bool_vector(document['receipts'][action]['previous'], 12) == [value] * 12,
                'Twelve actual previous-state bits required: ' + action)
    projection = copy.deepcopy(document)
    projection['baseline'] = _projection(document['baseline'])
    for action, row in projection['receipts'].items():
        row['previous'] = row['previous'][:len(probe.MALE)]
        for side in ('before', 'after'):
            row[side] = _projection(row[side])
    for phase in probe.PHASES:
        projection['windows'][phase] = [_projection(raw) for raw in document['windows'][phase]]
    result = probe.score(projection)
    baseline = snapshot(document['baseline'], reference)
    windows = {phase: [snapshot(raw, reference) for raw in document['windows'][phase]] for phase in probe.PHASES}
    transitions = [snapshot(row[side], reference) for row in document['receipts'].values() for side in ('before', 'after')]
    all_rows = [baseline, *transitions, *[row for phase in probe.PHASES for row in windows[phase]]]
    for row in all_rows:
        expected_scales(row)
    plan = probe.prepare(reference, 'male', baseline['position'])  # Pure trajectory construction; never dispatched.
    for phase, rows in windows.items():
        for row, point in zip(rows, plan['windows'][phase], strict=True):
            probe.reference_excitation(row, baseline, point['expectedPosition'])
            delta = [a-b for a, b in zip(row['position'], baseline['position'], strict=True)]
            for anchor in anchors():
                follow = [a-b for a, b in zip(row['nodes'][anchor]['world']['translation'],
                                             baseline['nodes'][anchor]['world']['translation'], strict=True)]
                require(probe.max_delta(follow, delta) <= .025, 'Anchor did not follow actual reference: ' + anchor)
    for name in EXTRA_NODES:
        for channel, floor in probe.FLOORS.items():
            values = [row['nodes'][name]['local'][channel] for row in all_rows]
            result['localAnimationQuiet'] &= all(probe.max_delta(value, values[0]) <= floor for value in values)
    for name in ('WWD 1', 'CME Pelvis [Pelv]'):
        values = [probe.relative(row['nodes'][name]['world'], row['root']) for row in all_rows]
        for channel, floor in probe.FLOORS.items():
            result['controlParentsQuiet'] &= all(probe.max_delta(value[channel], values[0][channel]) <= floor for value in values)
    for name in EXTRA_DRIVERS:
        result['channels'][name] = {'anchor': 'WWD 1', 'immediateParent': ANATOMY_PARENTS[name],
                                    'worldRelative': {}, 'parentRelative': {}, 'local': {}}
        for channel, floor in probe.FLOORS.items():
            stats = {phase: probe.spread([probe.relative(row['nodes'][name]['world'], row['nodes']['WWD 1']['world'])[channel]
                                          for row in rows]) for phase, rows in windows.items()}
            result['channels'][name]['worldRelative'][channel] = stats
            result['channels'][name]['parentRelative'][channel] = {phase: probe.spread([
                probe.relative(row['nodes'][name]['world'], row['nodes'][ANATOMY_PARENTS[name]]['world'])[channel]
                for row in rows]) for phase, rows in windows.items()}
            result['channels'][name]['local'][channel] = {phase: probe.spread([
                row['nodes'][name]['local'][channel] for row in rows]) for phase, rows in windows.items()}
            active = min(stats['active'], stats['restarted'])
            if active > 4 * floor and stats['stopped'] <= max(floor, .25 * active):
                result['selectiveChannels'].append({'node': name, 'channel': channel})
    result['missingDrivers'] = [name for name in roles() if not any(x['node'] == name for x in result['selectiveChannels'])]
    result['anchorsRootRelativeQuiet'] = result['controlParentsQuiet']
    result['status'] = ('sampled-selective-contrast-observed' if not result['missingDrivers']
                        and result['localAnimationQuiet'] and result['controlParentsQuiet']
                        and result['excitationTimingComparable'] else 'unconfirmed')
    result.update(requiredDrivers=list(roles()), actualWorldFollowChecks=sum(map(len, windows.values())),
                  independentDescendantJointResponseClaimed=False, renderedMeshAttachmentQualified=False,
                  protocol='Case-local twelve-driver reference; NOT pulse/2')
    return result


def _associate(row, window, profile):
    probe, rig, uniform, _ = shared()
    objects = {body['token']: body for body in window['objects']}
    require(len(objects) == len(roles()) + len(anchors()), 'Exact fifteen-body solver inventory required')
    children = {token: [] for token in objects}
    for edge in window['incidentConstraints']['constraints']:
        children[edge['bodyAToken']].append(edge['bodyBToken'])

    tokens = {}
    for name in anchors():
        pose = row['nodes'][name]['world']
        candidates = [token for token, body in objects.items()
                      if all(rig._kinematic(body[stage])
                             and probe.max_delta(body[stage]['world'][9:], pose['translation']) <= rig.joint.TRANSLATION_MATCH
                             and probe.max_delta(body[stage]['world'][:9], pose['rotationRowMajor']) <= rig.joint.ROTATION_MATCH
                             for stage in rig.joint.STAGES)]
        require(len(candidates) == 1, 'Missing or ambiguous kinematic anchor: ' + name)
        tokens[name] = candidates[0]

    def native_pose(token, stage):
        values = objects[token][stage]['world']
        return {'rotationRowMajor': values[:9], 'translation': values[9:], 'scale': SCALE}

    # The observer samples the scene on the game thread and Bullet at its
    # callback boundaries. Match only stable anchors by pose and follow the
    # directed graph. Bilateral branches must agree with their scene landmarks.
    branches = {probe.MALE[0]: (0, -1), probe.MALE[2]: (0, 1),
                'WWLB 1': (2, -1), 'WWRB 1': (2, 1)}
    for name, parent in parents().items():
        parent_token = tokens[parent]
        candidates = children[parent_token]
        if name in branches:
            axis, sign = branches[name]
            observed = probe.relative(row['nodes'][name]['world'], row['nodes'][parent]['world'])
            require(sign * observed['translation'][axis] > 1, 'Ambiguous scene branch: ' + name)
            require(len(candidates) == 2, 'Unexpected directed branch: ' + name)
            candidates = [token for token in candidates if all(
                sign * probe.relative(native_pose(token, stage),
                                      native_pose(parent_token, stage))['translation'][axis] > 1
                for stage in rig.joint.STAGES)]
        require(len(candidates) == 1, 'Missing or ambiguous directed solver role: ' + name)
        token, = candidates
        tokens[name] = token
        wanted = profile[name]
        for stage in rig.joint.STAGES:
            body = objects[token][stage]
            require(rig._dynamic(body), 'Body type changed: ' + name)
            require(abs(body['inverseMass'] - 1 / (wanted['mass'] * SCALE**3)) <= uniform.MASS_TOLERANCE,
                    'Scaled inverse mass differs: ' + name)
            require(probe.max_delta(body['inverseLocalInertia'], [1 / (x * SCALE**5) for x in wanted['inertia']])
                    <= uniform.MASS_TOLERANCE, 'Scaled inverse inertia differs: ' + name)
    require(len(set(tokens.values())) == len(objects), 'Full injective male12 role association required')
    return tokens


def _float32(value):
    return struct.unpack('<f', struct.pack('<f', value))[0]


def _expected_spring2(declared, pairs):
    # FSMP parses XML as float32 and forms scale powers in float32 before
    # multiplying the stored fields. This rig uses one uniform 1.13 scale.
    squared = _float32(SCALE * SCALE)
    cubed = _float32(squared * SCALE)
    fifth = _float32(cubed * squared)
    factors = {'lowerLimit': (SCALE, 1), 'upperLimit': (SCALE, 1), 'stiffness': (cubed, fifth)}
    expected = {}
    for key, (linear, angular) in pairs.items():
        ls, ars = factors.get(key, (1, 1))
        expected[key] = [_float32(_float32(x) * ls) for x in declared[linear]] + [
            _float32(_float32(x) * ars) for x in declared[angular]]
    return {**expected, 'springEnabled': [True] * 6, 'stopERP': [.2] * 6,
            'stiffnessLimited': [True] * 6, 'dampingLimited': [True] * 6}


def evaluate_configuration(xml, world, native_before, native_after, *, reference, base, pid, nonce):
    """Require actual schema-4 native windows; scene/toggle receipts cannot replace them."""
    probe, rig, _, _ = shared()
    profile = source_profile(xml)
    require(rig.witness.integer(pid, 1) and rig.witness.integer(nonce, 1),
            'Explicit positive integer native process and window required')
    require(all(type(x) is dict for x in (world, native_before, native_after)),
            'Actual named world and two native schema-4 observations are required')
    reference, base = probe.form(reference), probe.form(base)
    row = snapshot(world, reference)
    expected_scales(row)
    guard = row['guard']
    require(guard['session'].partition('-')[0] == str(pid) and guard['actor']['baseForm'] == base
            and guard['actor']['race'] == guard['actor']['baseRace'] == rig.WOLF_RACE,
            'Admitted male actor/process/base/race changed')
    before, start = rig._normal_window(native_before, pid, nonce, 'collecting')
    after, end = rig._normal_window(native_after, pid, nonce, 'collecting')
    progression = rig.witness.compare(before, after)
    require(progression['providerCompletedStepsObserved'] and start['pairedSteps'] < end['pairedSteps']
            and start['firstPreQpc'] == end['firstPreQpc'] and start['lastPostQpc'] < end['lastPostQpc']
            and start['incidentConstraints'] == end['incidentConstraints']
            and [(b['token'], b['initialPre']) for b in start['objects']] ==
                [(b['token'], b['initialPre']) for b in end['objects']],
            'Advancing unchanged native configuration bracket required')
    tokens = _associate(row, start, profile)
    require(tokens == _associate(row, end, profile), 'Run-local male12 role association changed')
    expected = {(config['parent'], driver): {
        **config, 'expected': _expected_spring2(config['declared'], rig.PARAMETER_PAIRS),
    } for driver, config in profile.items()}
    return {'status': 'configured-se-rig-observed', 'component': 'CLAW.neutral-anatomy.male12',
            'pid': pid, 'nonce': nonce, 'loadEpoch': after['sample']['loadEpoch'], 'sex': 'male', 'reference': reference,
            'worldSample': row['sample'], 'worldGuard': guard, 'firstPreQpc': start['firstPreQpc'],
            'bracketingLastPostQpc': [start['lastPostQpc'], end['lastPostQpc']], 'tokens': tokens,
            'joints': rig._observe_joints(end, tokens, expected), 'xmlSha256': digest(xml),
            'runtimeQualified': False, 'contactQualified': False, 'renderedMeshAttachmentQualified': False,
            'scope': 'Exact male12 anchor poses, directed graph, side landmarks, scaled body mass/inertia and Spring2 values. '
                     'Joint frames/equilibria are authored declarations; no direct owner getter, motion or contact acceptance.'}


def evaluate_motion(configuration, native_final):
    require(configuration.get('component') == 'CLAW.neutral-anatomy.male12'
            and set(configuration.get('joints', {})) == set(roles()), 'Exact associated male12 configuration required')
    return shared()[1].evaluate_motion(configuration, native_final)


def json_object(payload):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value, 'Duplicate JSON field: ' + key)
            value[key] = item
        return value
    value = json.loads(payload, object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    require(type(value) is dict, 'JSON object required')
    return value


def capture(root, pins):
    captured = {}
    for relative, pin in pins.items():
        path = (Path(root) / relative).resolve(strict=True)
        require(Path(root).resolve() in path.parents, 'Input path escaped its explicit root')
        payload = path.read_bytes()
        require(digest(payload) == pin, 'Pinned input differs: ' + relative)
        captured[path] = payload
    return captured


def replay(case_root, candidate, catalogue):
    """Capture all retained bytes first; retain the historical failure verbatim."""
    case_bytes = capture(case_root, catalogue['caseInputs'])
    candidate_bytes = capture(candidate, catalogue['candidateInputs'])
    captured = {**case_bytes, **candidate_bytes}
    data = lambda name: json_object(case_bytes[(Path(case_root) / name).resolve()])
    fixture = data('actual-male12-shape-fixture.json')
    require(fixture['drivers'] == list(roles()) and fixture['anchors'] == list(anchors()), 'Pinned fixture role graph differs')
    for coverage in fixture['storedPositiveDriverCoverage'].values():
        require(all(coverage[name] == {'genitals': count} for name, count in zip(EXTRA_DRIVERS, (361, 222, 222))),
                'Pinned anatomy skin support differs')
    xml = candidate_bytes[(Path(candidate) / catalogue['xml']).resolve()]
    source_profile(xml)
    state = data(catalogue['state'])
    score = score_reference(state)
    require(score == data(catalogue['diagnostic']), 'Current replay differs from the retained male12 diagnostic')
    historical, post = data(catalogue['result']), data('postrun-verification.json')
    require(post['run'] == catalogue['run'] and historical['result'] == post['result'] == 'failed'
            and historical['reason'] == post['reason'] == catalogue['historicalFailure']
            and post['runtimePhysicsQualified'] is False and post['renderedMeshOrContactQualified'] is False,
            'Historical failed motion result changed')
    require(all(path.read_bytes() == payload for path, payload in captured.items()), 'A replay input changed during evaluation')
    return {'status': 'replayed-retained-failed-male12-case', 'historicalResult': 'failed',
            'historicalReason': post['reason'], 'run': post['run'], 'diagnostic': score,
            'configurationReadback': {'status': 'unavailable', 'reason': 'Historical case has no actual schema-4 solver/constraint bracket'},
            'inputs': {str(path): digest(payload) for path, payload in captured.items()},
            'runtimeQualified': False, 'contactQualified': False, 'renderedMeshAttachmentQualified': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest='command', required=True)
    archived = command.add_parser('replay')
    archived.add_argument('--case-root', type=Path, required=True)
    archived.add_argument('--candidate', type=Path, required=True)
    current = command.add_parser('readback')
    for name in ('xml', 'world', 'native-before', 'native-after'):
        current.add_argument('--'+name, type=Path, required=True)
    for name in ('reference', 'base'):
        current.add_argument('--'+name, required=True)
    for name in ('pid', 'nonce'):
        current.add_argument('--'+name, type=int, required=True)
    for sub in (archived, current):
        sub.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output.resolve()
    require(not output.exists() and REPO not in output.parents
            and not any(x.casefold() in ('mods', 'data', 'overwrite', 'downloads') for x in output.parts),
            'Use a new external report path')
    # Capture source before lazy imports or evidence evaluation. End-check only
    # consumed helper modules, so independent work on other readers is harmless.
    sources = [Path(__file__), CATALOGUE, COMPOSITION,
               REPO/'src/test/cpp/fsmp_step_witness/validate_snapshot.py', *INTEGRATION.glob('*.py')]
    source_bytes = {path.resolve(): path.read_bytes() for path in sources}
    if args.command == 'replay':
        report = replay(args.case_root, args.candidate, json_object(source_bytes[CATALOGUE]))
    else:
        inputs = {path.resolve(strict=True): path.read_bytes() for path in
                  (args.xml, args.world, args.native_before, args.native_after)}
        report = evaluate_configuration(inputs[args.xml.resolve()], json_object(inputs[args.world.resolve()]),
            json_object(inputs[args.native_before.resolve()]), json_object(inputs[args.native_after.resolve()]),
            reference=args.reference, base=args.base, pid=args.pid, nonce=args.nonce)
        require(all(path.read_bytes() == payload for path, payload in inputs.items()), 'A readback input changed during evaluation')
        report['inputs'] = {str(path): digest(payload) for path, payload in inputs.items()}
    used = {Path(__file__).resolve(), CATALOGUE, COMPOSITION}
    used.update(Path(m.__file__).resolve() for m in tuple(sys.modules.values())
                if getattr(m, '__file__', None) and Path(m.__file__).resolve() in source_bytes)
    require(all(path.read_bytes() == source_bytes[path] for path in used), 'A consumed reader source changed during evaluation')
    report['sourceInputs'] = {str(path): digest(source_bytes[path]) for path in sorted(used)}
    with output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'output': str(output), 'runtimeQualified': False}))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
