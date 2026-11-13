"""Case-local readback checks for the existing39a camera/time/node APIs."""
import math
import hashlib
from pathlib import Path

CAMERA_FIELDS = ('camX', 'camY', 'camZ', 'camPitch', 'camYaw', 'stateId',
                 'freeCam', 'freeCamOwned', 'freeCamBackend', 'camAngles')

def require(value, message):
    if not value:
        raise ValueError(message)

def number(value):
    return type(value) in (int, float) and math.isfinite(value)

def time_status(raw):
    require(type(raw) is dict and all(k in raw for k in
            ('requested', 'effective', 'owner', 'leased', 'leaseRemainingMs')),
            'Actual game-rate state is unavailable')
    require(number(raw['requested']) and number(raw['effective']) and
            type(raw['owner']) is str and type(raw['leased']) is bool and
            type(raw['leaseRemainingMs']) is int and raw['leaseRemainingMs'] >= 0,
            'Actual game-rate fields have wrong types')
    return raw

def admit_baseline(raw):
    raw = time_status(raw)
    require(raw['leased'] is False and raw['requested'] == raw['effective'] == 1,
            'Off-normal or foreign leased game-rate: refuse without mutation')
    return raw

def set_receipt(raw, scale, frozen):
    time_status(raw)
    require(type(raw.get('generation')) is int and raw['generation'] > 0 and
            type(raw.get('currentGeneration')) is int and
            raw['generation'] == raw['currentGeneration'] and
            raw.get('state') == 'reached' and raw.get('reached') is True and
            raw.get('applied') is True and raw['requested'] == raw['effective'] == scale and
            raw['leased'] is frozen and (not frozen or bool(raw['owner'])),
            'Exact game-rate completion/generation receipt unavailable')
    return raw

def frozen_readback(raw, admitted, previous=None):
    raw = time_status(raw)
    require(raw['requested'] == raw['effective'] == 0 and raw['leased'] is True and
            raw['owner'] == admitted['owner'] and raw['leaseRemainingMs'] > 0,
            'Capture game-rate lease changed or expired')
    if previous is not None:
        require(raw['leaseRemainingMs'] <= previous['leaseRemainingMs'],
                'Capture lease unexpectedly renewed or replaced')
    # getTimeScale has no generation field: this is observable owner/rate/lease
    # continuity, not proof that an unobserved same-owner request never occurred.
    return raw

def camera_key(raw):
    require(type(raw) is dict and all(k in raw for k in CAMERA_FIELDS) and
            raw['freeCam'] is True and raw['freeCamOwned'] is True and
            all(number(raw[k]) for k in ('camX', 'camY', 'camZ', 'camPitch', 'camYaw')),
            'Actual complete owned camera state is unavailable')
    return {k: raw[k] for k in CAMERA_FIELDS}

def _transform(value):
    require(type(value) is dict and type(value.get('translation')) is list and
            len(value['translation']) == 3 and type(value.get('rotationRowMajor')) is list and
            len(value['rotationRowMajor']) == 9 and
            all(number(v) for v in value['translation'] + value['rotationRowMajor']) and
            number(value.get('scale')), 'Complete finite actual scene transform unavailable')
    return value

def validate_sample(raw, specs, positions, heading, protocol):
    require(type(raw) is dict and raw.get('ok') is True and
            len(raw.get('refs', [])) == len(specs), 'Complete actual actor anchor sample unavailable')
    wanted = {s['reference'].casefold(): (tag, s) for tag, s in specs.items()}
    refs = {}
    for row in raw['refs']:
        key = row.get('identity', {}).get('form', '').casefold()
        require(key in wanted and key not in refs and row.get('status') == 'available' and
                row.get('loaded3D') is True, 'Actor anchor identity/availability differs')
        tag, spec = wanted[key]
        require(row.get('baseForm') == spec['base'], 'Actual actor base differs')
        transform = _transform(row.get('sceneTransform'))
        role = 'human' if tag.endswith('Human') else 'wolf'
        require(math.dist(row['position'], positions[role]) <= protocol['positionTolerance'] and
                math.dist(transform['translation'], positions[role]) <= protocol['positionTolerance'],
                'Actual actor/root moved from the declared anchor')
        angle = math.degrees(row['anglesRadians'][2]) % 360
        require(abs((angle-heading+180) % 360-180) <= protocol['headingToleranceDegrees'],
                'Actual actor heading differs')
        refs[key] = row
    nodes = {}
    names = protocol['alignment']['boneNames']
    require(len(raw.get('nodes', [])) == len(specs)*len(names), 'Six bones per actor unavailable')
    for row in raw['nodes']:
        key = (row.get('form', '').casefold(), row.get('name'))
        require(key[0] in wanted and key[1] in names and key not in nodes and
                row.get('status') == 'available' and row.get('firstPerson') is False and
                row['identity'] == refs[key[0]]['identity'] and
                row['rootIdentity'] == refs[key[0]]['rootIdentity'],
                'Actual skeleton bone/root identity unavailable')
        _transform(row.get('world')); _transform(row.get('local'))
        nodes[key] = row
    return raw

def compare_bracket(before, after, alignment):
    for first, second in zip(before['refs'], after['refs']):
        require(first['identity'] == second['identity'] and
                first['rootIdentity'] == second['rootIdentity'], 'Actor/root changed around capture')
        require(max(abs(x-y) for x, y in zip(first['sceneTransform']['rotationRowMajor'],
                second['sceneTransform']['rotationRowMajor'])) <= alignment['rootRotationTolerance'],
                'Actual actor root rotated around capture')
    a = {(r['form'], r['name']): r for r in before['nodes']}
    b = {(r['form'], r['name']): r for r in after['nodes']}
    require(a.keys() == b.keys(), 'Capture bone catalogue changed')
    for key in a:
        for space in ('local', 'world'):
            x, y = a[key][space], b[key][space]
            require(math.dist(x['translation'], y['translation']) <= alignment['boneTranslationTolerance'] and
                    max(abs(p-q) for p, q in zip(x['rotationRowMajor'], y['rotationRowMajor'])) <=
                    alignment['boneRotationTolerance'] and
                    abs(x['scale']-y['scale']) <= alignment['boneScaleTolerance'],
                    'Actual skeleton pose changed around capture: ' + str(key))

def node_request(specs, names):
    return {'kind': 'world_observer', 'refs': [s['reference'] for s in specs.values()],
            'actors': True, 'nodes': [{'ref': s['reference'], 'name': n, 'firstPerson': False}
                                    for s in specs.values() for n in names], 'timeoutMs': 3000}

def screenshot_inventory(game_path):
    root=Path(game_path).parent.resolve()
    directories=[root,root/'Screenshots']
    files=[]
    for directory in directories:
        if directory.exists():
            require(not directory.lstat().st_file_attributes & 0x400,'Screenshot directory is a reparse point')
            files.extend(str(p.resolve()) for p in directory.iterdir() if p.is_file() and
                         p.suffix.casefold() in ('.bmp','.png','.jpg','.jpeg','.dds'))
    return {'directories':[str(p) for p in directories],'files':sorted(files),
            'scope':'Precall names only; no original image opened or changed'}

def screenshot_source_proof(receipt, retained, inventory):
    raw=receipt.get('sourcePath')
    if type(raw) is not str:return {'provedNewOwnedSource':False,'reason':'Native sourcePath unavailable'}
    source=Path(raw)
    try:
        safe=(source.is_file() and not source.lstat().st_file_attributes & 0x400 and
              str(source.resolve().parent) in inventory['directories'] and
              str(source.resolve()) not in inventory['files'])
        if not safe:return {'provedNewOwnedSource':False,'sourcePath':raw,'reason':'Not new/regular/nonreparse/in exact declared directories'}
        h=hashlib.sha256(source.read_bytes()).hexdigest()
        equal=h==hashlib.sha256(Path(retained).read_bytes()).hexdigest()
        return {'provedNewOwnedSource':equal,'sourcePath':str(source.resolve()),'sha256':h,
                'retainedByteCopyEqual':equal,'cleanupDuringCapture':False,
                'next':'Root may contain/remove only this exact unchanged source AFTER owned game ended/restored'}
    except OSError as error:return {'provedNewOwnedSource':False,'sourcePath':raw,'reason':str(error)}
