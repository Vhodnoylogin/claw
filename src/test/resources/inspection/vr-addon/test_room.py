"""Stand the owned VR player on the fixed QASmoke floor for inspection."""

import math
import time


CELL = '0x00032AE7'
PLAYER = '0x00000014'
MARKER = [-2633.919189453125, 1521.9630126953125, 6976.0]
STATIONS = {
    'collider': ([-2750., 1536., 6976.], 90.),
    'mirror': ([-2542.945, 1591., 6976.], 270.),
}
COLLIDER_WOLF = [-2697.9448, 1646., 6976.0991]


def position_player(session, station):
    from skyrim_autotest import actor_domain, native
    from skyrim_autotest.platform import Backend
    from skyrim_autotest.runner import atomic_json

    state = session.state
    game = state['game']
    generation = state['ownedWorldGeneration']
    path = session.dir / 'claw-qasmoke-room.json'
    if (state['configuration']['game_edition'] != 'vr' or not state.get('testProfile')
            or state['configuration']['reuse_test_profile'] or not state['gameplayBootstrap']['completed']
            or path.exists()):
        raise ValueError('The test-room station requires a fresh owned VR run')
    destination, heading = STATIONS[station]
    end = time.monotonic() + 35
    backend = Backend(session, end)

    def check_run():
        if (native.identity(game['pid']) != game or state['ownedWorldGeneration'] != generation
                or not any(row['role'] == 'game' and row['identity'] == game for row in state['owned'])):
            raise ValueError('The owned QASmoke game changed')

    def read():
        check_run()
        identity, row, audit = actor_domain.anchor(backend, PLAYER)
        if row['baseForm'] != '0x00000007':
            raise ValueError('The owned player base changed')
        return identity, row, audit['sampleId']

    identity, initial, sample_id = read()
    record = {'station': station, 'cell': CELL, 'identity': identity, 'initialCell': initial['cellForm'],
              'initialPosition': initial['position'], 'requestedPosition': destination,
              'requestedHeadingDegrees': heading, 'samples': []}

    def mutate(function, args):
        if read()[0] != identity:
            raise ValueError('The player incarnation changed before ' + function)
        record['pending'] = function
        atomic_json(path, record)
        reply = session.tool('papyrus', {'action': 'call', 'script': 'ObjectReference', 'function': function,
                                       'self': {'form': PLAYER}, 'args': args, 'timeoutMs': 4000},
                             timeout=6, deadline=end)
        if reply.get('called') is not True or reply.get('returnedType', '').casefold() != 'none':
            raise ValueError('No typed completion for ' + function)
        record['pending'] = None
        atomic_json(path, record)

    if initial['cellForm'] != CELL:
        marker = actor_domain.returned_form(backend.pap('Game', 'GetFormFromFile', [0x02A1B9, 'Dragonborn.esm']))
        if not marker.endswith('02A1B9') or int(marker, 16) >> 24 >= 0xFE:
            raise ValueError('The original QASmoke marker FormID did not resolve')
        _, row, _ = actor_domain.anchor(backend, marker)
        if row['baseForm'] != '0x0000003B' or row['cellForm'] != CELL or math.dist(row['position'], MARKER) > .01:
            raise ValueError('The QASmoke marker does not match the original identity and location')
        transfer = [destination[axis] - MARKER[axis] for axis in range(3)]
        record['marker'] = marker
        mutate('MoveTo', [{'form': marker}, *transfer, False])

    while time.monotonic() < end:
        current, row, _ = read()
        if current != identity:
            raise ValueError('The player incarnation changed after the room transfer')
        if row['cellForm'] == CELL and row['loaded3D'] is True:
            break
        time.sleep(.25)
    else:
        raise ValueError('The test room did not load for the owned player')

    mutate('SetAngle', [0., 0., heading])
    mutate('SetPosition', destination)
    previous = None
    while time.monotonic() < end:
        current, row, fresh = read()
        if current != identity or row['cellForm'] != CELL or row['loaded3D'] is not True:
            raise ValueError('The player identity or loaded test room changed during placement')
        position = row['position']
        facing = backend.pap('ObjectReference', 'GetAngleZ', target=PLAYER)
        sample = {'id': fresh, 'position': position, 'heading': facing}
        record['samples'].append(sample)
        atomic_json(path, record)
        if (previous is not None and fresh > previous['id'] > sample_id and math.dist(position, destination) <= 4.
                and math.dist(position, previous['position']) <= 1. and abs((facing - heading + 180.) % 360. - 180.) <= 1.):
            record['status'] = 'positioned'
            atomic_json(path, record)
            return record
        previous = sample
        time.sleep(.25)
    raise ValueError('The player did not settle at the QASmoke station')
