"""Score a Hands33 equipment control from native topology captures."""
from human_firstperson_readback import human_first_person


VIEWS = ('thirdPerson', 'firstPerson')
MARKERS = {'thirdPerson': 'CLAWTestWolfHands33World', 'firstPerson': 'CLAWTestWolfHands33First'}
WOLF = 0xCDD84
HUMAN = 0x13746
REALM = 0x0A01A5C6


def slot(view, bank, index):
    rows = [row for row in view[bank] if row['slot'] == index]
    if len(rows) > 1:
        raise ValueError('Duplicate native biped slot')
    return rows[0] if rows else None


def describe(roots, identity):
    if not identity:
        return {'id': 0, 'complete': False, 'names': [], 'markers': [], 'localUnculledMarkers': []}
    root = roots[identity]
    geometry = root['geometryDetails']
    return {'id': identity,
            'complete': root['collection'] == 0 and root['geometryDetailsComplete'] is True
                and len(geometry) == root['geometries'],
            'rootChainAppCull': root['appCull']['effective'],
            'names': [shape['name'] for shape in geometry],
            'markers': [shape['name'] for shape in geometry if shape['name'] in MARKERS.values()],
            'localUnculledMarkers': [shape['name'] for shape in geometry
                if shape['name'] in MARKERS.values() and shape['appCulled'] is False]}


def wolf_snapshot(sample, fixture_forms):
    roots = {row['id']: row for row in sample['distinctRoots']}
    if len(roots) != len(sample['distinctRoots']):
        raise ValueError('Duplicate native inventory ID')
    observations = {}
    for name in VIEWS:
        view = sample['views'][name]
        active, buffered = (slot(view, bank, 3) for bank in ('active', 'buffered'))
        actor, biped = sample['roots'][name], view['bipedRoot']
        observations[name] = {
            'active': active,
            'buffered': buffered,
            'actor': describe(roots, actor),
            'biped': describe(roots, biped),
            'clone': describe(roots, active['clone'] if active else 0),
            'bufferedClone': describe(roots, buffered['clone'] if buffered else 0),
        }
    body = slot(sample['views']['thirdPerson'], 'active', 2)
    carrier = describe(roots, body['clone'] if body else 0)
    stock_body = None
    if body and (body['item'], body['addon']) == (0xCDD86, 0xCDD87) and carrier['complete']:
        stock_body = [body['item'], body['addon'], body['modelPath'], carrier['names']]
    world_ids = {observations['thirdPerson'][role]['id'] for role in ('actor', 'biped', 'clone', 'bufferedClone')}
    for view, found in observations.items():
        observed = found['active']
        clone = found['clone']
        expected = MARKERS[view]
        first = view == 'firstPerson'
        distinct_clone = clone['id'] not in {0, found['actor']['id'], found['biped']['id']}
        exact = observed and (observed['item'], observed['addon']) == fixture_forms
        part = bool(exact and distinct_clone and clone['complete'] and clone['names'] == [expected]
                    and (not first or clone['id'] not in world_ids))
        direct = [found[role] for role in ('actor', 'biped')
                  if found[role]['id'] != clone['id'] and found[role]['complete']
                  and (not first or found[role]['id'] not in world_ids)
                  and found[role]['markers'] == [expected]]
        found['activeExpectedClone'] = part
        found['activeOtherViewMarker'] = bool(exact and distinct_clone and clone['complete']
                                              and len(clone['markers']) == 1 and clone['markers'] != [expected])
        found['directMatchIds'] = [row['id'] for row in direct]
        found['rootChainAndLocalAppCullClearForMatch'] = part and clone['rootChainAppCull'] is False \
            and expected in clone['localUnculledMarkers'] and any(
                row['rootChainAppCull'] is False and expected in row['localUnculledMarkers'] for row in direct)
    first = observations['firstPerson']
    first_absence = all(first[role]['complete'] and first[role]['id'] not in world_ids and not first[role]['markers']
                        for role in ('actor', 'biped')) and all(
                            first[role]['id'] == 0 or (first[role]['complete'] and not first[role]['markers'])
                            for role in ('clone', 'bufferedClone'))
    return {'routes': observations, 'stockBody32': stock_body,
            'noMarkersInCompleteFirstPersonRoutes': first_absence,
            'cameraStateId': sample['cameraStateId']}


def qualify(raws, fixture_forms, equip_confirmed):
    if set(raws) != {'human', 'stock', 'equipped', 'restored'}:
        raise ValueError('Need the human control and the three wolf phases')
    item, addon = fixture_forms
    if (type(item) is not int or type(addon) is not int or not 0 < item >> 24 < 0xFE
            or item & 0xFFFFFF != 0x801 or addon != item - 1):
        raise ValueError('Expected the same loaded, regular private item and addon pair')
    identities = set()

    for name, row in raws.items():
        sample = row['sample']
        human = name == 'human'
        if (row['status'] != 'ready' or row['schema'] != 'claw-vr-model-topology/' + ('4' if human else '8')
                or any(type(row[field]) is not int or row[field] <= 0 for field in ('pid', 'epoch', 'nonce'))
                or sample['actor'] != 0x14 or sample['base'] != 7
                or sample['cell'] != REALM
                or type(sample['runtimeHandle']) is not int or sample['runtimeHandle'] <= 0
                or sample['race'] != (HUMAN if human else WOLF)
                or (not human and sample['sex'] != 0)):
            raise ValueError('Capture does not identify the admitted male player and expected form')
        identities.add((row['pid'], row['epoch'], sample['runtimeHandle']))
    nonces = [raws[name]['nonce'] for name in ('human', 'stock', 'equipped', 'restored')]
    if len(identities) != 1 or sorted(set(nonces)) != nonces:
        raise ValueError('Native scene owner, epoch, or ordered phase identity changed')
    human = human_first_person(raws['human']['sample'])
    wolf = {name: wolf_snapshot(raws[name]['sample'], fixture_forms)
            for name in ('stock', 'equipped', 'restored')}
    stock, equipped, restored = (wolf[name] for name in wolf)
    reference = stock['stockBody32']
    unchanged_body = reference is not None and all(row['stockBody32'] == reference for row in wolf.values())
    clean = all(row['noMarkersInCompleteFirstPersonRoutes'] and all(
        not any(route[bank] and route[bank]['item'] == item for bank in ('active', 'buffered'))
        and not any(route[role]['markers'] for role in ('actor', 'biped', 'clone', 'bufferedClone'))
        for route in row['routes'].values()) for row in (stock, restored))
    cameras = [human['cameraStateId'], *(row['cameraStateId'] for row in wolf.values())]
    same_camera = all(type(camera) is int and camera >= 0 and camera == cameras[0] for camera in cameras)
    control = human['state'] == 'ordinary_firstperson_hands_loaded' and same_camera
    world, first = (equipped['routes'][name] for name in VIEWS)
    if not (control and clean and unchanged_body):
        result = 'inconclusive_control_or_restoration'
    elif equip_confirmed is not True:
        result = 'equip_not_confirmed'
    elif first['activeExpectedClone'] and first['directMatchIds']:
        result = 'world_and_first_routes_observed' if world['activeExpectedClone'] else 'first_route_observed'
    elif first['activeOtherViewMarker']:
        result = 'world_marker_in_first_active_clone'
    elif first['activeExpectedClone']:
        result = 'first_clone_without_direct_graph_confirmation'
    elif first['bufferedClone']['markers']:
        result = 'first_marker_in_buffered_clone_only'
    elif equipped['noMarkersInCompleteFirstPersonRoutes']:
        result = 'world_clone_and_no_first_marker' if world['activeExpectedClone'] else 'no_first_marker_after_equip'
    else:
        result = 'inconclusive_first_route'
    return {'result': result, 'ordinaryControl': human, 'samples': wolf, 'sameCameraStateId': same_camera,
            'stockBody32Unchanged': unchanged_body, 'cleanStockAndRestoredHands33': clean,
            'equipConfirmedByCaller': equip_confirmed is True, 'headsetPixelsVerified': False}
