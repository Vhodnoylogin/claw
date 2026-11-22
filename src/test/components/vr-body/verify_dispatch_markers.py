"""Verify model origin from an admitted VR topology capture's exact Body32 clones."""

from argparse import ArgumentParser
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path


SCHEMA = 'claw-vr-model-topology/5'
TOKENS = ('M0', 'M1', 'F0', 'F1', 'H_M0')
VIEWS = ('thirdPerson', 'firstPerson')
BANKS = ('active', 'buffered')
ROUTES = tuple((view, bank) for view in VIEWS for bank in BANKS)
BODY = 2
ITEM, ADDON, RACE = 0xCDD86, 0xCDD87, 0xCDD84
EARLY = {'unloaded', 'foreign_slot', 'detached'}
COMPLETE = {'unmarked', 'ambiguous', 'marked'}
MARKER_SEX = dict(zip(TOKENS, (0, 0, 1, 1, 0)))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, label, low=0, high=0xFFFFFFFF):
    require(type(value) is int and low <= value <= high, f'Invalid {label}')
    return value


def object_value(value, label):
    require(isinstance(value, dict), f'Invalid {label}')
    return value


def alias(value, ids, label):
    value = integer(value, label, high=48)
    require(not value or value in ids, f'Unknown {label} alias')
    return value


def body_slot(slots):
    require(isinstance(slots, list) and len(slots) <= 42, 'Invalid topology slots')
    numbers = [integer(object_value(row, 'topology slot').get('slot'), 'biped slot', high=41) for row in slots]
    require(len(numbers) == len(set(numbers)), 'Duplicate topology slot')
    return slots[numbers.index(BODY)] if BODY in numbers else None


def origin(token):
    if token == 'H_M0':
        return r'Meshes\Actors\character\character assets\1stperson_werewolf_hands.nif'
    sex = 'male' if MARKER_SEX[token] == 0 else 'female'
    return f'Meshes\\Actors\\WerewolfBeast\\CLAW\\FirstPerson\\{sex}\\Body_{token[-1]}.nif'


def read_row(row, sample_view, root, view, bank, ids):
    row = object_value(row, 'marker row')
    require((row.get('view'), row.get('bank')) == (view, bank) and
            integer(row.get('slot'), 'marker slot', high=41) == BODY, 'Unexpected marker row route or slot')
    slot = body_slot(sample_view.get(bank))
    clone = alias(slot.get('clone') if slot is not None else 0, ids, 'Body32 clone')
    require(alias(row.get('clone'), ids, 'marker clone') == clone, 'Marker row clone differs from topology slot')
    item = integer(slot.get('item') if slot is not None else 0, 'slot item')
    addon = integer(slot.get('addon') if slot is not None else 0, 'slot addon')
    reported_model = slot.get('modelPath') if slot is not None else ''
    require(isinstance(reported_model, str), 'Invalid reported modelPath')
    counts = row.get('counts')
    require(isinstance(counts, list) and len(counts) == len(TOKENS), 'Invalid marker counts')
    total = sum(integer(count, 'marker count', high=2) for count in counts)
    status = row.get('classification')
    require(isinstance(status, str) and status in EARLY | COMPLETE | {'indeterminate'}, 'Invalid marker classification')
    require(bool(clone) == (status != 'unloaded'), 'Unloaded classification conflicts with clone presence')
    require(not clone or sample_view['available'], 'Clone exists under unavailable biped')
    require(status not in EARLY or total == 0, 'Unscanned marker row carries counts')
    if status not in {'unloaded', 'foreign_slot'}:
        require((item, addon) == (ITEM, ADDON), 'Marker walk used a foreign item or addon')
        require(root or status == 'detached', 'Marker walk lacks the requested actor root')
    if status in COMPLETE:
        expected = 'marked' if total == 1 else 'ambiguous' if total else 'unmarked'
        require(status == expected, 'Marker counts contradict classification')
    markers = {token: count for token, count in zip(TOKENS, counts) if count}
    return dict(view=view, bank=bank, clone=clone, actorRoot=root, item=item, addon=addon,
                classification=status, markers=markers, reportedModelPath=reported_model)


def verify_dispatch_markers(observation, *, view, pid, nonce, epoch, expect=None):
    observation = object_value(observation, 'capture')
    require(observation.get('schema') == SCHEMA and observation.get('status') == 'ready',
            'Expected a ready native VR topology /5 capture')
    require(view in VIEWS and (expect is None or expect in TOKENS), 'Invalid requested view or marker')
    for name, expected, limit in (('pid', pid, 0xFFFFFFFF), ('nonce', nonce, 0x7FFFFFFF), ('epoch', epoch, 2**64 - 1)):
        require(integer(observation.get(name), name, 1, limit) == integer(expected, f'expected {name}', 1, limit),
                f'Capture {name} differs from requested observation')
    sample = object_value(observation.get('sample'), 'topology sample')
    require(integer(sample.get('actor'), 'actor') == 0x14 and integer(sample.get('race'), 'race') == RACE,
            'Expected the wolf player')
    integer(sample.get('base'), 'actor base', 1)
    integer(sample.get('cell'), 'actor cell', 1)
    handle = integer(sample.get('runtimeHandle'), 'actor runtime handle', 1)
    sex = integer(sample.get('sex'), 'actor sex', high=1)
    weight = sample.get('weight')
    require('weight' in sample and (weight is None or type(weight) in (int, float) and
            0 <= weight <= 100 and isfinite(weight)), 'Invalid actor weight')
    clock = {name: integer(sample.get(name), name, 1, 2**63 - 1) for name in ('qpcBegin', 'qpcEnd', 'qpcFrequency')}
    require(0 < clock['qpcEnd'] - clock['qpcBegin'] <= 3 * clock['qpcFrequency'], 'Invalid capture QPC interval')

    graphs = sample.get('distinctRoots')
    require(isinstance(graphs, list) and len(graphs) <= 48, 'Invalid topology graph inventory')
    ids = [integer(object_value(graph, 'topology graph').get('id'), 'graph alias', 1, 48) for graph in graphs]
    require(len(ids) == len(set(ids)), 'Duplicate graph alias')
    roots = object_value(sample.get('roots'), 'actor roots')
    views = object_value(sample.get('views'), 'topology views')
    observations = sample.get('body32Markers')
    require(isinstance(observations, list) and len(observations) == 4, 'Expected four Body32 marker rows')
    rows = {}
    complete_counts = {}
    for index, (route, bank) in enumerate(ROUTES):
        root = alias(roots.get(route), ids, 'actor root')
        sample_view = object_value(views.get(route), 'topology view')
        require(type(sample_view.get('available')) is bool, 'Invalid biped availability')
        row = read_row(observations[index], sample_view, root, route, bank, ids)
        rows[route, bank] = row
        if row['classification'] in COMPLETE:
            counts = complete_counts.setdefault(row['clone'], row['markers'])
            require(row['markers'] == counts, 'Conflicting marker counts for the same clone alias')

    chosen = rows[view, 'active']
    other_view = next(route for route in VIEWS if route != view)
    other = rows[other_view, 'active']
    status = chosen['classification']
    marker = None
    if status == 'marked':
        marker = next(iter(chosen['markers']))
        if MARKER_SEX[marker] != sex:
            status = 'wrong_sex'
        elif (chosen['actorRoot'] in (other['actorRoot'], other['clone'])
              or chosen['clone'] in (other['clone'], other['actorRoot'], chosen['actorRoot'])):
            status = 'aliased_view'
        elif expect is not None and marker != expect:
            status = 'unexpected_origin'
        else:
            status = 'origin_observed'
    return {'schema': 'claw-vr-dispatch-origin/1', 'status': status, 'view': view,
            'pid': pid, 'nonce': nonce, 'epoch': epoch, 'actorRuntimeHandle': handle,
            'captureClock': clock, 'sex': sex, 'observedActorWeight': weight, 'observations': list(rows.values()),
            'observedMarker': marker and 'CLAW_VR_DISPATCH_PROBE_' + marker,
            'markerFixtureModel': marker and origin(marker), 'modelOriginVerified': status == 'origin_observed',
            'installedAssetWinnerVerified': False, 'weightInterpolationVerified': False, 'renderedPixelsVerified': False}


def unique_json_object(pairs):
    result = dict(pairs)
    require(len(result) == len(pairs), 'Duplicate JSON key')
    return result


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path, help='One admitted CaptureDispatch /5 JSON reply')
    parser.add_argument('--view', required=True, choices=VIEWS)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--nonce', type=int, required=True)
    parser.add_argument('--epoch', type=int, required=True)
    parser.add_argument('--expect', choices=TOKENS, help='Optional exact fixture marker token')
    args = parser.parse_args()
    try:
        payload = args.capture.read_bytes()
        capture = json.loads(payload, object_pairs_hook=unique_json_object)
        result = verify_dispatch_markers(capture, view=args.view, pid=args.pid, nonce=args.nonce, epoch=args.epoch,
                                         expect=args.expect)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    result['captureSha256'] = sha256(payload).hexdigest()
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result['modelOriginVerified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
