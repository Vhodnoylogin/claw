"""Pure finite uniform-scale adapter; accepted unit helpers/contracts unchanged."""
import math
if __package__:
    from . import fsmp_joint_limit_readback as unit, fsmp_angular_limit_readback as angular
else:
    import fsmp_joint_limit_readback as unit
    import fsmp_angular_limit_readback as angular

probe, cached, witness = unit.probe, unit.cached, unit.witness
PARENTS, DRIVERS, STAGES = unit.PARENTS, unit.DRIVERS, unit.STAGES
REQUESTED_SCALE, SCALE_TOLERANCE = 1.1, 1e-5
MASS_TOLERANCE, WORLD_TOLERANCE = 2e-5, .0015
ANGULAR_TOLERANCE = .0001
require = unit.require


def owner_unchanged(initial, current):
    """Only scale and root identity may turn over during acknowledged setup."""
    for field in ('session', 'generation', 'identity', 'actor'):
        require(initial['guard'][field] == current['guard'][field], 'Setup owned actor/base/race/world changed')
    require(probe.max_delta(initial['position'], current['position']) <= .025 and
            probe.max_delta(initial['angles'], current['angles']) <= 1e-5 and
            probe.max_delta(initial['root']['translation'], current['root']['translation']) <= .025 and
            probe.max_delta(initial['root']['rotationRowMajor'], current['root']['rotationRowMajor']) <= 1e-5,
            'Setup changed undeclared position/orientation')
    for name in PARENTS+DRIVERS:
        a, b = initial['nodes'][name]['local'], current['nodes'][name]['local']
        require(probe.max_delta(a['translation'], b['translation']) <= 1e-4 and
                probe.max_delta(a['rotationRowMajor'], b['rotationRowMajor']) <= 1e-5 and
                abs(a['scale']-1) <= SCALE_TOLERANCE and abs(b['scale']-1) <= SCALE_TOLERANCE,
                'Setup changed undeclared local rest frame')


def transition_context(row, getter):
    require(type(getter) in (int, float) and math.isfinite(getter) and getter > 0, 'Actual GetScale unavailable')
    roles = {name: {'local': row['nodes'][name]['local']['scale'], 'world': row['nodes'][name]['world']['scale']}
             for name in PARENTS+DRIVERS}
    values = [getter, row['guard']['scale'], row['root']['scale'], *[r['world'] for r in roles.values()]]
    require(all(math.isfinite(x) and 1-SCALE_TOLERANCE <= x <= REQUESTED_SCALE+SCALE_TOLERANCE for x in values),
            'Scale setup left declared1→1.1 interval')
    require(all(abs(r['local']-1) <= SCALE_TOLERANCE for r in roles.values()), 'Local rest scale is not unit')
    return {'requested': REQUESTED_SCALE, 'getter': float(getter), 'reference': row['guard']['scale'],
            'rootWorld': row['root']['scale'], 'roles': roles,
            'ready': all(abs(x-REQUESTED_SCALE) <= SCALE_TOLERANCE for x in values)}


def scale_context(row, getter):
    context = transition_context(row, getter)
    require(context['ready'], 'Requested scale is not independently observed in getter/root/roles')
    for parent, driver in zip(PARENTS, DRIVERS):
        require(abs(context['roles'][parent]['world']-context['roles'][driver]['world']) <= SCALE_TOLERANCE,
                'Nonuniform parent/driver scale is outside this case')
    return context


def establish_measurement(initial, before, getter_before, after, getter_after, *, acknowledged):
    require(acknowledged is True, 'No known SetScale ACK; root/scale rebind refused')
    owner_unchanged(initial, before); owner_unchanged(initial, after)
    a, b = scale_context(before, getter_before), scale_context(after, getter_after)
    require(before['guard'] == after['guard'] and a == b and after['sample'] > before['sample'] and
            after['time']-before['time'] >= 200_000_000, 'Scaled measurement root/scales are not fresh and stable')
    return {'guard': after['guard'], 'scaleContext': b}


def joint_world_frame(anchor, driver, rest, scale):
    require(type(scale) in (int, float) and math.isfinite(scale) and scale > 0, 'Measured pivot scale unavailable')
    pivot = {'rotationRowMajor': rest['rotationRowMajor'],
             'translation': [scale*x for x in rest['translation']], 'scale': rest['scale']}
    return unit.joint_frame(anchor, driver, pivot)


def observer_joint_world_frame(anchor, driver, rest):
    """Derive the scale-free rigid WORLD view; never alter raw Ni observations.

    The pinned provider stores Ni scale separately from rigid basis/origin.
    Raw scale remains required here and in the retained measurement context.
    """
    a, b = probe.transform(anchor), probe.transform(driver)
    scale = b['scale']
    require(abs(scale-REQUESTED_SCALE) <= SCALE_TOLERANCE and abs(a['scale']-scale) <= SCALE_TOLERANCE,
            'Observed uniform WORLD scale unavailable for rigid view')
    def rigid_view(value):
        return {'rotationRowMajor': value['rotationRowMajor'], 'translation': value['translation'], 'scale': 1.}
    result = joint_world_frame(rigid_view(a), rigid_view(b), rest, scale)
    return {**result, 'observedNiScale': scale}


def _map(row, native, rest, context):
    window = native['sample']['objectWindow']
    dynamic = cached.paused_match(row, window, 'female')
    require(dynamic['status'] == 'unique-paused-dynamic11-match', 'Scaled dynamic11 association unavailable')
    objects = {o['token']: o for o in window['objects']}; mapping = {}
    for parent, driver in zip(PARENTS, DRIVERS):
        match = next(item for item in dynamic['dynamicBodies'] if item['node'] == driver)
        mapping[driver] = match['candidates'][0]['token']
        actual = row['nodes'][parent]['world']
        parents = [o['token'] for o in window['objects'] if o['lastPost']['rigidBody'] is True and
                   o['lastPost']['inverseMass'] == 0 and o['lastPost']['flags']&3 == 2 and
                   probe.max_delta(o['lastPost']['world'][9:], actual['translation']) <= unit.TRANSLATION_MATCH and
                   probe.max_delta(o['lastPost']['world'][:9], actual['rotationRowMajor']) <= unit.ROTATION_MATCH]
        require(len(parents) == 1, 'Scaled kinematic parent is missing or ambiguous')
        mapping[parent] = parents[0]
        require(probe.max_delta(row['nodes'][driver]['local']['translation'], rest[driver]['translation']) <= unit.TRANSLATION_MATCH and
                probe.max_delta(row['nodes'][driver]['local']['rotationRowMajor'], rest[driver]['rotationRowMajor']) <= unit.ROTATION_MATCH,
                'Scaled local rest pivot differs from frozen NIF')
    require(len(set(mapping.values())) == 4, 'Scaled four-role association is not injective')
    return {'tokens': mapping, 'dynamic11': dynamic, 'scaleContext': context}


def _coordinates(associated, native, rest):
    require(native['status'] == 'ready' and native['pid'] == associated['pid'], 'Scaled native process differs')
    sample = native['sample']; window = sample['objectWindow']
    witness.validate_window(window, sample['loadEpoch'])
    require(sample['loadEpoch'] == associated['loadEpoch'] and window['nonce'] == associated['nonce'], 'Scaled window epoch/nonce differs')
    objects = {o['token']: o for o in window['objects']}; tokens = associated['A']['tokens']
    require(len(set(tokens.values())) == 4 and all(token in objects for token in tokens.values()), 'Scaled token catalogue differs')
    context = associated['A']['scaleContext']; output = {}
    for stage in STAGES:
        output[stage] = {}
        for parent, driver in zip(PARENTS, DRIVERS):
            a, b = objects[tokens[parent]][stage], objects[tokens[driver]][stage]
            scale = context['roles'][driver]['world']
            expected = 20/scale**3
            require(a['rigidBody'] is True and a['inverseMass'] == 0 and a['flags']&3 == 2 and
                    b['rigidBody'] is True and b['flags']&3 == 0 and abs(b['inverseMass']-expected) <= MASS_TOLERANCE,
                    'Measured scaled inverse mass/flags contradict observed node scale')
            joint = joint_world_frame(unit.pose_transform(a), unit.pose_transform(b), rest[driver], scale)
            output[stage][driver] = {'observedWorldScale': scale, 'expectedInverseMass': expected,
                                     'actualInverseMass': b['inverseMass'], 'qWorld': joint['translation'],
                                     'qNominal': [x/scale for x in joint['translation']],
                                     'anglesRadians': angular.euler_xyz(joint['rotationRowMajor'])}
    return output


def pair(world_a, world_b, native_a, native_b, *, reference, base, rest_local, getter_a, getter_b):
    require(cached.paused_signature(native_a) == cached.paused_signature(native_b), 'Scaled pause/window state changed')
    require(native_a['pid'] == native_b['pid'] and native_a['qpcFrequency'] == native_b['qpcFrequency'] and
            native_a['requestSerial'] != native_b['requestSerial'] and native_b['sample']['sampledQpc'] > native_a['sample']['sampledQpc'],
            'Scaled native samples did not advance')
    mapped, rows = {}, []
    for mark, raw, native, getter in (('A', world_a, native_a, getter_a), ('B', world_b, native_b, getter_b)):
        require(native['status'] == 'ready', 'Ready scaled native sample required')
        witness.validate_window(native['sample']['objectWindow'], native['sample']['loadEpoch'])
        row = probe.snapshot(raw, reference, 'female'); actor = row['guard']['actor']
        require(actor['baseForm'] == base and actor['race'] == actor['baseRace'] == '0x000CDD84', 'Scaled actor/base/race changed')
        context = scale_context(row, getter)
        mapped[mark] = _map(row, native, rest_local, context); rows.append(row)
    require(rows[0]['guard'] == rows[1]['guard'] and rows[1]['sample'] > rows[0]['sample'] and
            rows[1]['time']-rows[0]['time'] >= 200_000_000 and
            mapped['A']['tokens'] == mapped['B']['tokens'] and mapped['A']['scaleContext'] == mapped['B']['scaleContext'],
            'Scaled actor/root/token/context samples are stale or changed')
    result = {'schema': 'claw-uniform-scale-pair/1', 'reference': reference, 'base': base,
              'pid': native_a['pid'], 'loadEpoch': native_a['sample']['loadEpoch'],
              'nonce': native_a['sample']['objectWindow']['nonce'],
              'pairedStepsAtPause': native_a['sample']['objectWindow']['pairedSteps'], **mapped}
    for mark, native in (('A', native_a), ('B', native_b)):
        result[mark]['coordinates'] = _coordinates(result, native, rest_local)
    return result


def _gate(coordinates):
    for stage in STAGES:
        for side, driver in enumerate(DRIVERS):
            row = coordinates[stage][driver]; scale = row['observedWorldScale']; target = .05*scale if side == 0 else 0.
            require(abs(row['qWorld'][0]-target) <= WORLD_TOLERANCE, 'Scaled positive lower limit/right control differs')
            require(abs(row['qNominal'][0]-(.05 if side == 0 else 0.)) <= WORLD_TOLERANCE/scale,
                    'Scale-normalized lower limit/right control differs')
            require(all(abs(x) <= .15*scale+WORLD_TOLERANCE for x in row['qWorld'][1:]), 'Original scaled y/z bounds exceeded')
            require(all(abs(x) <= .01+ANGULAR_TOLERANCE for x in row['anglesRadians']), 'Original unscaled angular bounds exceeded')
    for driver in DRIVERS:
        a, b = coordinates['initialPre'][driver], coordinates['lastPost'][driver]
        require(probe.max_delta(a['qWorld'], b['qWorld']) <= WORLD_TOLERANCE and
                probe.max_delta(a['anglesRadians'], b['anglesRadians']) <= ANGULAR_TOLERANCE,
                'Bilateral scaled window was not settled')


def score_limit(associated):
    for mark in ('A', 'B'): _gate(associated[mark]['coordinates'])
    return {'status': 'uniform-scale-mass-and-linear-limit-correspondence-observed',
            'requestedScale': REQUESTED_SCALE, 'inverseMassTolerance': MASS_TOLERANCE,
            'worldTolerance': WORLD_TOLERANCE, 'associated': associated,
            'scope': 'One finite uniform1.1 scale; no general skeleton, inertia getter, contact or rendering acceptance'}


def score_case(associated, native, rest):
    result = score_limit(associated); sample = native['sample']; window = sample['objectWindow']
    witness.validate_window(window, sample['loadEpoch'])
    require(native['status'] == 'ready' and native['pid'] == associated['pid'] and sample['loadEpoch'] == associated['loadEpoch'] and
            window['nonce'] == associated['nonce'] and window['status'] == 'complete' and window['pairedSteps'] == 900 and
            window['pairedSteps'] > associated['pairedStepsAtPause'], 'Same completed900 scaled window required')
    require(sample['mainFreezeTime'] is False and sample['mainFreezeNextFrame'] is False and sample['uiPaused'] is False and
            sample['engineMultiplier'] == 1 and sample['timerPauseCount'] == 0, 'Normal scaled clock was not restored')
    final = _coordinates(associated, native, rest); _gate(final)
    result['completed900Coordinates'] = final
    return result
