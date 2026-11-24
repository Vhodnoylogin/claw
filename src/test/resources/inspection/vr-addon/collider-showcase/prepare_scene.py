"""Place the already-staged showcase in one admitted, disposable Skyrim VR session."""

from __future__ import annotations

import math
from pathlib import Path
import time


FIXTURE = 'test_CLAW - VR CBPC Contact Fixture.esp'
OVERLAY = 'test_CLAW - VR Collider Showcase.esp'
WOLF = 0x000CDD84
PLAYER = 0x14
SLOT_MASK = 1 << (60 - 30)
ROOT_DRIFT = .15
MAX_LANDING_ADJUSTMENT = 48.
NATIVE = {
    'Game': ('globalFunctions', {
        'GetModByName': (('string',), 'int'),
        'GetModName': (('int',), 'string'),
        'GetFormFromFile': (('int', 'string'), 'form'),
    }),
    'ObjectReference': ('memberFunctions', {
        'PlaceAtMe': (('form', 'int', 'bool', 'bool'), 'objectreference'),
        'SetPosition': (('float', 'float', 'float'), 'none'),
        'SetAngle': (('float', 'float', 'float'), 'none'),
        'GetAngleZ': ((), 'float'),
        'AddItem': (('form', 'int', 'bool'), 'none'),
        'GetBaseObject': ((), 'form'),
    }),
    'Actor': ('memberFunctions', {
        'GetRace': ((), 'race'),
        'IsDead': ((), 'bool'),
        'IsInCombat': ((), 'bool'),
        'EnableAI': (('bool',), 'none'),
        'SetRestrained': (('bool',), 'none'),
        'SetHeadTracking': (('bool',), 'none'),
        'EquipItem': (('form', 'bool', 'bool'), 'none'),
        'UnequipItem': (('form', 'bool', 'bool'), 'none'),
        'GetWornForm': (('int',), 'form'),
    }),
    'ActorBase': ('memberFunctions', {
        'GetSex': ((), 'int'),
        'GetWeight': ((), 'float'),
    }),
}
NODES = ('NPC Root [Root]', 'NPC Head [Head]', 'NPC Spine2 [Spn2]',
         'NPC EarL [EarL]Bone01', 'NPC EarR [EarR]Bone01', 'TailBone02')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def ref(number):
    return f'0x{number:08X}'


def form(value):
    if isinstance(value, dict):
        value = value.get('formId')
    require(type(value) is str and value.lower().startswith('0x'), 'Expected an exact typed runtime FormID')
    number = int(value, 16)
    require(0 < number <= 0xFFFFFFFF, 'Runtime FormID is outside uint32')
    return number


def position_from(player, heading, forward):
    angle = math.radians(heading)
    return [player[0] + forward * math.sin(angle), player[1] + forward * math.cos(angle), player[2]]


def prepare(session, *, cell_form, forward=96., floor_position=None, stage_receipt=None):
    """Return the owned actor/armor IDs with the verified equipment toggle left on."""
    from skyrim_autotest import native
    from skyrim_autotest.readiness_state import gameplay_ready
    from skyrim_autotest.runner import atomic_json

    state = session.state
    game = state['game']
    cfg = state.get('configuration', {})
    require(cfg.get('game_edition') == 'vr' and not cfg.get('reuse_test_profile')
            and state.get('gameplayBootstrap', {}).get('completed') is True
            and state.get('ownedWorldGeneration', 0) > 0,
            'The showcase needs a new, initialized owned VR world')
    require(isinstance(cell_form, int) and 0 < cell_form < 0xFF000000
            and math.isfinite(forward) and 64. <= forward <= 160., 'Invalid cell or bounded spawn distance')
    path = Path(session.dir) / 'claw-vr-collider-showcase.json'
    require(not path.exists() and 'clawColliderShowcase' not in state, 'The showcase may only be prepared once')
    end = time.monotonic() + 90.
    out = {'schema': 'claw-vr-collider-showcase-live/1', 'game': game, 'cellForm': ref(cell_form),
           'stageReceipt': str(stage_receipt) if stage_receipt else None, 'status': 'preparing',
           'commands': [], 'snapshots': [], 'intent': None, 'unknownMutation': False}
    state['clawColliderShowcase'] = str(path)
    actor = base = owner = previous = None

    def save():
        atomic_json(path, out)

    def tool(name, payload):
        require(time.monotonic() < end and state.get('game') == game and
                state.get('ownedGameRestartCount', 0) == 0 and native.identity(game['pid']) == game and
                any(row['role'] == 'game' and row['identity'] == game for row in state.get('owned', [])),
                'Owned game identity or preparation deadline changed')
        return session.tool(name, payload, timeout=min(5., end - time.monotonic()), deadline=end)

    def pap(script, function, args, target=None, phase=None):
        expected = NATIVE[script][1][function][1]
        request = {'action': 'call', 'script': script, 'function': function, 'args': args, 'timeoutMs': 2600}
        if target is not None:
            request['self'] = {'form': ref(target)}
        if phase is not None:
            require(not out['unknownMutation'] and out['intent'] is None
                    and (target == actor or (phase == 'spawn' and target == PLAYER)),
                    'Uncertain previous write or unowned target')
            out['intent'] = {'phase': phase, 'request': request}
            save()
        try:
            reply = tool('papyrus', request)
            returned_type = str(reply.get('returnedType', '')).casefold()
            empty_slot = (script == 'Actor' and function == 'GetWornForm' and returned_type == 'none'
                          and reply.get('returned') is None)
            require(reply.get('called') is True and not (reply.get('error') or reply.get('isError'))
                    and (returned_type == expected or empty_slot) and 'returned' in reply,
                    f'Typed completion unavailable: {script}.{function}')
            if phase is not None:
                out['commands'].append({'phase': phase, 'request': request, 'reply': reply})
                out['intent'] = None
                save()
            return reply['returned']
        except BaseException:
            if phase is not None:
                out['unknownMutation'] = True
                save()
            raise

    def plugin_form(plugin, local):
        index = pap('Game', 'GetModByName', [plugin])
        require(type(index) is int and 0 < index < 0xFE and pap('Game', 'GetModName', [index]) == plugin,
                'Expected exact normal plugin: ' + plugin)
        resolved = form(pap('Game', 'GetFormFromFile', [local, plugin]))
        require(resolved == ((index << 24) | local), 'Resolved a different form')
        return resolved

    def snapshot(label, *, allow_unloaded=False, nodes=False):
        nonlocal owner, previous
        ids = [PLAYER] if actor is None else [PLAYER, actor]
        query = {'kind': 'world_observer', 'action': 'snapshot', 'refs': [ref(x) for x in ids], 'timeoutMs': 1500}
        if nodes:
            query['nodes'] = [{'ref': ref(actor), 'name': name, 'firstPerson': False} for name in NODES]
        observed = tool('inspect', query)
        out['snapshots'].append({'label': label, 'raw': observed})
        save()
        require(observed.get('ok') is True and observed.get('schemaVersion') == 1
                and observed.get('quality') == 'complete' and observed.get('phase') == 'skse_main_thread_task'
                and observed.get('space') == 'world' and observed.get('units') == 'skyrim_engine_units'
                and observed.get('sessionId', '').startswith(f'{game["pid"]}-'),
                'Coherent VR Observer reference sample unavailable')
        if previous is not None:
            require(observed['sessionId'] == previous['sessionId']
                    and observed['loadGeneration'] == previous['loadGeneration']
                    and observed['sampleId'] > previous['sampleId']
                    and observed['producerMonotonicNs'] > previous['producerMonotonicNs'],
                    'VR Observer sample failed to advance within the owned world')
        rows = {form(x['identity']['form']): x for x in observed['refs']}
        require(len(observed['refs']) == len(ids) and set(rows) == set(ids), 'Wrong observed reference census')
        for number, record in rows.items():
            require(form(record['cellForm']) == cell_form and record['disabled'] is False
                    and record['deleted'] is False and (number == actor and allow_unloaded or record['loaded3D'] is True),
                    'An owned reference left the loaded setup cell')
        require(form(rows[PLAYER]['baseForm']) == 7, 'The player base changed')
        if actor is not None:
            require(form(rows[actor]['baseForm']) == base, 'The showcase actor base changed')
            if owner is None:
                owner = rows[actor]['identity']
            require(owner == rows[actor]['identity'], 'The showcase actor incarnation changed')
        previous = observed
        return rows

    def wait_worn(expected, label):
        for _ in range(12):
            rows = snapshot(label)
            require(math.dist(rows[actor]['position'], anchor) <= ROOT_DRIFT, 'The showcase actor drifted during the toggle')
            actual = pap('Actor', 'GetWornForm', [SLOT_MASK], actor)
            if (actual is None if expected is None else actual is not None and form(actual) == expected):
                out['equipment'][label] = actual
                save()
                return
            time.sleep(.16)
        raise ValueError('Armor slot readback remained inconsistent: ' + label)

    save()
    try:
        scene = tool('inspect', {'kind': 'scene'})
        menus = tool('menu', {'action': 'list', 'includeFlags': True})
        require(gameplay_ready(scene, menus) and form(scene['cell']['formId']) == cell_form,
                'The owned showcase cell is not live and unpaused')
        for script, (scope, methods) in NATIVE.items():
            described = tool('papyrus', {'action': 'describe', 'script': script})
            available = {row['name'].casefold(): row for row in described[scope]}
            for function, (params, returns) in methods.items():
                got = available.get(function.casefold(), {})
                require(got.get('native') is True and got.get('returnType', '').casefold() == returns
                        and tuple(arg['type'].casefold() for arg in got.get('params', [])) == params,
                        f'Changed native signature: {script}.{function}')
        base = plugin_form(FIXTURE, 0x800)
        armor = plugin_form(OVERLAY, 0x801)
        census = tool('inspect', {'kind': 'refs', 'formType': 'Actor', 'radius': 0, 'limit': 1024})
        require(census.get('truncated') is False and census.get('count') == census.get('returned') == len(census['refs']),
                'Complete bounded actor census unavailable')
        before = {form(row['formId']) for row in census['refs']}
        require(len(before) == len(census['refs']), 'The starting actor census has duplicate forms')
        player = snapshot('before spawn')[PLAYER]
        heading = pap('ObjectReference', 'GetAngleZ', [], PLAYER)
        if floor_position is None:
            wanted = position_from(player['position'], heading, forward)
        else:
            require(isinstance(floor_position, (list, tuple)) and len(floor_position) == 3 and
                    all(type(axis) in (float, int) and math.isfinite(axis) for axis in floor_position),
                    'The verified showcase floor position must contain three finite coordinates')
            wanted = list(floor_position)
            require(64. <= math.dist(wanted[:2], player['position'][:2]) <= 160. and
                    abs(wanted[2] - player['position'][2]) <= 32.,
                    'The verified floor must be in reach of the current player anchor')
        face_player = math.degrees(math.atan2(player['position'][0] - wanted[0],
                                              player['position'][1] - wanted[1])) % 360.

        new_actor = pap('ObjectReference', 'PlaceAtMe', [{'form': ref(base)}, 1, False, False], PLAYER, 'spawn')
        actor = form(new_actor)
        require(0xFF000000 <= actor < 0xFFFFFFFF and actor not in before, 'Spawn did not yield a new owned actor')
        for _ in range(12):
            rows = snapshot('await actor', allow_unloaded=True)
            if rows[actor]['loaded3D'] is True:
                break
            time.sleep(.18)
        else:
            raise ValueError('Fresh showcase actor did not acquire live 3D')
        require(form(pap('ObjectReference', 'GetBaseObject', [], actor)) == base
                and form(pap('Actor', 'GetRace', [], actor)) == WOLF
                and pap('ActorBase', 'GetSex', [], base) == 0
                and pap('ActorBase', 'GetWeight', [], base) == 50.
                and pap('Actor', 'IsDead', [], actor) is False and pap('Actor', 'IsInCombat', [], actor) is False,
                'Unexpected showcase actor base, race, sex, weight, or combat state')
        out.update(actorForm=ref(actor), actorBase=ref(base), actorIdentity=owner, armorForm=ref(armor),
                   requestedPosition=wanted, equipment={})
        pap('Actor', 'SetRestrained', [True], actor, 'restrain')
        pap('Actor', 'SetHeadTracking', [False], actor, 'stop head tracking')
        pap('Actor', 'EnableAI', [False], actor, 'stop NPC movement')
        pap('ObjectReference', 'SetAngle', [0., 0., face_player], actor, 'face player')
        pap('ObjectReference', 'SetPosition', wanted, actor, 'place on showcase floor')
        first = None
        for _ in range(12):
            current = snapshot('settle actor')[actor]['position']
            lateral_adjustment = math.dist(current[:2], wanted[:2])
            distance_to_player = math.dist(current[:2], player['position'][:2])
            arrived = (lateral_adjustment <= MAX_LANDING_ADJUSTMENT and 64. <= distance_to_player <= 180.
                       and abs(current[2] - player['position'][2]) <= 32.)
            if arrived and first is not None and math.dist(current, first) <= ROOT_DRIFT:
                anchor = current
                break
            first = current if arrived else None
            time.sleep(.22)
        else:
            raise ValueError('The showcase actor failed to settle at the requested floor')
        out['observedPosition'] = anchor
        out['settledPlacement'] = {'horizontalAdjustmentGu': lateral_adjustment,
                                   'horizontalDistanceToPlayerGu': distance_to_player,
                                   'rootDriftLimitGu': ROOT_DRIFT}
        require(pap('Actor', 'GetWornForm', [SLOT_MASK], actor) is None, 'The fresh actor already uses overlay slot 60')
        item = {'form': ref(armor)}
        pap('ObjectReference', 'AddItem', [item, 1, True], actor, 'add owned wire armor')
        pap('Actor', 'EquipItem', [item, False, True], actor, 'show wires')
        wait_worn(armor, 'shown')
        pap('Actor', 'UnequipItem', [item, False, True], actor, 'hide wires')
        wait_worn(None, 'hidden')
        pap('Actor', 'EquipItem', [item, False, True], actor, 'enable review view')
        wait_worn(armor, 'shown again')
        snapshot('ready for operator', nodes=True)
        out.update(status='equipped-ready-for-operator', visualsVerifiedInHeadset=False, handContactsVerified=False)
        save()
        return out
    except BaseException:
        out['status'] = 'failed-retire-disposable-session'
        save()
        raise
