"""Probe one split-view Body32 outfit in an admitted disposable Skyrim VR session.

The caller supplies the reviewed static outfit, topology witness, and verified
body mesh VFS winners. The ordinary executor owns startup, exit and restoration.
"""
import json
import time

from verify_dispatch_markers import paired_routes, verify_dispatch_markers

PLAYER = {'form': '0x00000014'}
FIXTURE = 'test_CLAW - VR Player Body32.esp'
TOPOLOGY = 'CLAWVRModelTopology'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def run(session, scenario, original_execute):
    original_execute(session, scenario)
    session.phase('claw-vr-body32-equipped-paired', 195)
    end = time.monotonic() + 180
    directory = session.dir / 'claw-body32'
    directory.mkdir()
    result = {'actionScope': 'disposable VR New Game, no save', 'captures': {}, 'qualified': False}
    pid = session.state['game']['pid']
    previous_owner, epoch = None, None
    nonce = 24112401

    def save():
        (directory / 'summary.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')

    def invoke(script, method, args, kind, target=None):
        remaining = end - time.monotonic()
        require(remaining > 1, 'Owned Body32 subject deadline')
        packet = {'action': 'call', 'script': script, 'function': method, 'args': args, 'timeoutMs': 2500}
        if target is not None:
            packet['self'] = target
        reply = session.tool('papyrus', packet, timeout=min(5, remaining), deadline=end)
        require(reply.get('called') is True and str(reply.get('returnedType', '')).casefold() == kind and
                'returned' in reply and not reply.get('error'), f'Unconfirmed typed reply for {script}.{method}')
        value = reply['returned']
        require(kind != 'none' or value is None, f'Unexpected void reply from {script}.{method}')
        return value

    def observe_owner():
        nonlocal previous_owner
        raw = session.tool('inspect', {'kind': 'world_observer', 'refs': ['0x14'], 'actorState': True, 'timeoutMs': 1500},
                           timeout=5, deadline=end)
        ref, = raw['refs']
        identity = ref['identity']
        current = (raw['sessionId'], raw['loadGeneration'], identity['runtimeHandle'], ref['cellForm'])
        require(raw['ok'] is True and raw['observerVersion'] == '0.2.6' and raw['phase'] == 'skse_main_thread_task' and
                ref['loaded3D'] is True and ref['deleted'] is False and ref['disabled'] is False and
                int(identity['form'], 16) == 0x14 and int(ref['baseForm'], 16) == 7 and int(ref['cellForm'], 16) == 0x0A01A5C6 and
                (previous_owner is None or current == previous_owner), 'Expected the original owned loaded Realm player')
        previous_owner = current
        return ref

    def capture(label, fixture):
        nonlocal epoch, nonce
        observe_owner()
        request = json.loads(invoke(TOPOLOGY, 'CaptureDispatch', [nonce], 'string'))
        require((request['pid'], request['nonce'], request['schema']) == (pid, nonce, 'claw-vr-model-topology/8'),
                'Topology request returned a foreign capture')
        raw = request
        for _ in range(9):
            if raw['status'] != 'pending':
                break
            time.sleep(.12)
            raw = json.loads(invoke(TOPOLOGY, 'Read', [nonce], 'string'))
        path = directory / (label + '.json')
        path.write_text(json.dumps({'request': request, 'raw': raw}, indent=2) + '\n', encoding='utf-8')
        require(raw['status'] == 'ready', 'Body32 capture did not complete: ' + str(raw.get('reason')))
        if epoch is None:
            epoch = raw['epoch']
        info = dict(pid=pid, nonce=nonce, epoch=epoch, fixture_forms=fixture)
        stock = label in ('stock', 'restored')
        analysis = (verify_dispatch_markers(raw, view='thirdPerson', **info) if stock else paired_routes(raw, **info))
        require(observe_owner()['identity']['runtimeHandle'] == raw['sample']['runtimeHandle'],
                'Native sample and World Observer player handles differ')
        result['captures'][label] = analysis
        nonce += 1
        save()
        return analysis

    observe_owner()
    require(int(invoke('Actor', 'GetRace', [], 'race', PLAYER)['formId'], 16) == 0x13746 and invoke('ActorBase', 'GetSex', [], 'int', {'form': '0x00000007'}) == 0,
            'Expected the admitted initial male Nord')
    fixture = tuple(int(invoke('Game', 'GetFormFromFile', [local, FIXTURE], 'form')['formId'], 16) for local in (0x801, 0x800))
    require(0 < fixture[0] >> 24 < 0xFE and fixture[0] & 0xFFFFFF == 0x801 and fixture[1] == fixture[0] - 1,
            'Test outfit and addon are not the exact loaded plugin pair')
    armor = {'form': f'0x{fixture[0]:08X}'}
    result['fixtureForms'] = list(fixture)
    require(invoke('ObjectReference', 'GetItemCount', [armor], 'int', PLAYER) == 0, 'The player already has the test item')
    quest = {'form': '0x0004B2D9'}
    init_end = time.monotonic() + 90
    while time.monotonic() < init_end:
        stage = invoke('Quest', 'GetCurrentStageID', [], 'int', quest)
        require(stage in (0, 1), 'The fresh player has an unexpected Companions quest state')
        if stage == 1 and invoke('Quest', 'IsRunning', [], 'bool', quest) is True:
            break
        time.sleep(.5)
    else:
        raise RuntimeError('Natural Companions initializer did not reach stage 1')
    observe_owner()
    require(not any(invoke('Actor', method, [], 'bool', PLAYER) for method in ('IsDead', 'IsInCombat', 'IsOnMount')),
            'The owned player is not eligible for the natural transform')
    result['pending'] = 'vanilla Beast Form Spell.Cast'
    save()
    invoke('Spell', 'Cast', [PLAYER, None], 'none', {'form': '0x00092C48'})
    result['pending'] = None
    result['postCastReadTimeouts'] = 0
    save()
    limit = min(end - 20, time.monotonic() + 55)
    time.sleep(16)
    clear = 0
    ready_status = None
    while time.monotonic() < limit:
        try:
            race = int(invoke('Actor', 'GetRace', [], 'race', PLAYER)['formId'], 16)
            status = invoke('CLAWDistributionNative', 'GetStatus', [PLAYER], 'int')
            active = [invoke('Actor', 'HasMagicEffect', [{'form': effect}], 'bool', PLAYER)
                      for effect in ('0x00092C45', '0x000F8209')]
        except RuntimeError as error:
            if not str(error).startswith('HTTP 504 api/tool/papyrus:') or 'was not dispatched within' not in str(error):
                raise
            # These calls only read. The one Cast above is never replayed.
            result['postCastReadTimeouts'] += 1
            clear = 0
            save()
            time.sleep(1.6)
            continue
        if race == 0xCDD84 and active == [False, False]:
            error = invoke('CLAWDistributionNative', 'GetLastError', [PLAYER], 'string') if status == 4 else ''
            if status == 2 or (status == 4 and error.startswith('required CLAW target model unavailable:')):
                clear = clear + 1 if ready_status == status else 1
                ready_status = status
                result['stockMorphState'] = {'status': status, 'error': error}
            else:
                clear = 0
        else:
            clear = 0
        if clear == 2:
            break
        time.sleep(1.6)
    require(clear == 2, 'Natural transform did not reach two stable, post-effect wolf samples')

    def stock_signature(analysis):
        active = analysis['observations'][0]
        current = (active['item'], active['addon'])
        attached = bool(active['clone']) and active['clone'] != active['actorRoot']
        require(current != fixture and
                (current == (0xCDD86, 0xCDD87) and attached or ready_status == 4 and not attached and
                 current in ((0, 0), (0xCDD86, 0xCDD87))), 'Unexpected pre-existing or restored player Body32')
        return (analysis['status'], current, attached, active['reportedModelPath'])

    stock = capture('stock', fixture)
    stock_route = stock_signature(stock)
    result['pending'] = 'AddItem'
    save()
    invoke('ObjectReference', 'AddItem', [armor, 1, True], 'none', PLAYER)
    result['pending'] = None
    save()
    try:
        require(invoke('ObjectReference', 'GetItemCount', [armor], 'int', PLAYER) == 1, 'Test item did not enter owned inventory')
        result['pending'] = 'EquipItem'
        save()
        invoke('Actor', 'EquipItem', [armor, False, True], 'none', PLAYER)
        result['pending'] = None
        save()
        require(invoke('Actor', 'IsEquipped', [armor], 'bool', PLAYER) is True, 'Owned Body32 fixture was not equipped')
        time.sleep(1)
        paired = capture('equipped', fixture)
        status = invoke('CLAWDistributionNative', 'GetStatus', [PLAYER], 'int')
        error = invoke('CLAWDistributionNative', 'GetLastError', [PLAYER], 'string') if status == 4 else ''
        result['equippedMorphState'] = {'status': status, 'error': error}
        save()
    finally:
        if result['pending'] is None:
            observe_owner()
            require(invoke('ObjectReference', 'GetItemCount', [armor], 'int', PLAYER) == 1, 'Owned fixture inventory count changed')
            if invoke('Actor', 'IsEquipped', [armor], 'bool', PLAYER) is True:
                result['pending'] = 'UnequipItem'
                save()
                invoke('Actor', 'UnequipItem', [armor, False, True], 'none', PLAYER)
                require(invoke('Actor', 'IsEquipped', [armor], 'bool', PLAYER) is False, 'Owned Body32 fixture still equipped')
            result['pending'] = 'RemoveItem'
            save()
            invoke('ObjectReference', 'RemoveItem', [armor, 1, True, None], 'none', PLAYER)
            require(invoke('ObjectReference', 'GetItemCount', [armor], 'int', PLAYER) == 0, 'Owned Body32 fixture item was not retired')
            result['pending'] = None
            save()
    time.sleep(.8)
    require(stock_signature(capture('restored', fixture)) == stock_route, 'Original player Body32 route did not return')
    result['assetDispatch'] = paired.get('status')
    result['qualified'] = paired.get('status') == 'separate_active_routes'
    result['renderVerified'] = False
    save()
    require(result['qualified'], 'Equipped world and first-person routes did not both activate: ' + str(result['assetDispatch']))
