"""Score ordinary human hands in a sample from the admitted generic VR capture.

The active Hands33 record's model path is a declaration. A positive requires
the stock hands name or the verified VR gauntlet roster in a complete direct
first-person inventory distinct from the world graph. The VR roster also needs
the active stock Hands33 part clone containing exactly those two shapes. The
roster is an observed fingerprint, not exact asset bytes or provider identity.
Complete absence in both direct inventories is a scoped negative. Truncation,
world aliases, and partial or clone-only matches are inconclusive. Root-chain
and local app-cull flags do not describe intermediate geometry ancestors.
"""

HUMAN_HANDS = 'HandMale_Big1stperson'
VR_GAUNTLET = frozenset(('HandMaleVR', 'leatherCuffs'))
HANDS_SLOT = 3
HUMAN_ITEM, HUMAN_ADDON = 0xD64, 0xD6C
HUMAN_MODEL = 'actors/character/character assets/1stpersonmalehands_1.nif'


def hand_slot(view, bank):
    rows = [row for row in view[bank] if row['slot'] == HANDS_SLOT]
    if len(rows) > 1:
        raise ValueError('Duplicate native Hands33 slot')
    if not rows:
        return None
    row, = rows
    path = row['modelPath'].replace('\\', '/').casefold()
    return {**row, 'ordinaryMaleHandsRecordAndPath':
            (row['item'], row['addon'], path) == (HUMAN_ITEM, HUMAN_ADDON, HUMAN_MODEL)}


def exact_vr_gauntlet(rows):
    return len(rows) == len(VR_GAUNTLET) and {row['name'] for row in rows} == VR_GAUNTLET


def human_first_person(sample):
    """Classify loaded geometry separately from application culling and pixels."""
    inventory = {row['id']: row for row in sample['distinctRoots']}
    if len(inventory) != len(sample['distinctRoots']):
        raise ValueError('Duplicate native inventory ID')
    first = sample['views']['firstPerson']
    world_aliases = {sample['roots']['thirdPerson'], sample['views']['thirdPerson']['bipedRoot']}
    active, buffered = (hand_slot(first, bank) for bank in ('active', 'buffered'))
    routes = {'firstActor': sample['roots']['firstPerson'], 'firstBiped': first['bipedRoot'],
              'firstActiveHands': active['clone'] if active else 0,
              'firstBufferedHands': buffered['clone'] if buffered else 0}
    observations = {}
    for name, identity in routes.items():
        if not identity:
            observations[name] = {'rootId': 0, 'state': 'no_root'}
            continue
        root = inventory[identity]
        geometry = root['geometryDetails']
        complete = (root['collection'] == 0 and root['geometryDetailsComplete'] is True
                    and len(geometry) == root['geometries'])
        matches = [row for row in geometry if row['name'] == HUMAN_HANDS]
        gauntlet = [row for row in geometry if row['name'] in VR_GAUNTLET]
        distinct = identity not in world_aliases
        if not distinct or not complete or len(matches) > 1:
            state = 'inconclusive'
        elif matches:
            state = 'found'
        else:
            state = 'inconclusive' if gauntlet else 'absent_in_sampled_root'
        observations[name] = {'rootId': identity, 'state': state, 'censusComplete': complete,
                              'distinctFromWorld': distinct, 'geometryCount': root['geometries'],
                              'reportedNames': [row['name'] for row in geometry],
                              'matchingGeometry': matches, 'vrGauntletGeometry': gauntlet, 'appCull': root['appCull']}
    direct = [observations[name] for name in ('firstActor', 'firstBiped')]
    clone = observations['firstActiveHands']
    stocked = active and (active['item'], active['addon']) == (HUMAN_ITEM, HUMAN_ADDON)
    gauntlet_roots = []
    if (stocked and clone.get('censusComplete') and clone.get('distinctFromWorld')
            and clone['geometryCount'] == len(VR_GAUNTLET) and exact_vr_gauntlet(clone['vrGauntletGeometry'])):
        gauntlet_roots = [row for row in direct if row.get('censusComplete') and row.get('distinctFromWorld')
                          and exact_vr_gauntlet(row['vrGauntletGeometry'])]
    stock_shape_found = any(row['state'] == 'found' for row in direct)
    if gauntlet_roots:
        for row in (*gauntlet_roots, clone):
            row['state'] = 'found'
            row['matchingGeometry'] = row['vrGauntletGeometry']
    positive = [row for row in direct if row['state'] == 'found']
    part_unresolved = any(observations[name]['state'] not in ('no_root', 'absent_in_sampled_root')
                          for name in ('firstActiveHands', 'firstBufferedHands'))
    if positive:
        state = 'ordinary_firstperson_hands_loaded'
    elif all(row['state'] == 'absent_in_sampled_root' for row in direct) and not part_unresolved:
        state = 'ordinary_hands_absent_in_complete_firstperson_graphs'
    else:
        state = 'firstperson_control_inconclusive'
    return {'state': state, 'exactGeometry': HUMAN_HANDS, 'routes': observations,
            'stockHandsShapeConfirmed': stock_shape_found, 'vrGauntletRosterConfirmed': bool(gauntlet_roots),
            'activeHandsSlot': active, 'bufferedHandsSlot': buffered,
            'cameraStateId': sample['cameraStateId'], 'weaponState': sample['weaponState'],
            'rootChainAndLocalAppCullClearForMatch': any(row['appCull']['effective'] is False and
                all(shape['appCulled'] is False for shape in row['matchingGeometry']) for row in positive),
            'headsetPixelsVerified': False}
