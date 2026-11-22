"""Verify coat ownership and geometry turnover beneath a retained actor root."""

if __package__:
    from .coat_persistence_readback import positive, require, text_matches, verify_sample
else:
    from coat_persistence_readback import positive, require, text_matches, verify_sample


PHASES = ('baseline', 'foreign', 'sibling', 'recovered')
IDENTITY = ('runId', 'pid', 'reference', 'runtimeHandle', 'worldGeneration')


def checked_identity(observation):
    require(isinstance(observation, dict)
            and text_matches(observation.get('runId'), r'[A-Za-z0-9_-]{1,84}')
            and text_matches(observation.get('reference'), r'0x[0-9A-F]{8}')
            and observation['reference'] != '0x00000000'
            and all(positive(observation.get(key)) for key in ('pid', 'runtimeHandle', 'worldGeneration')),
            'Missing exact coat fixture or world identity')
    return tuple(observation[key] for key in IDENTITY)


def positive_token(value):
    return text_matches(value, r'[1-9][0-9]{0,19}') and int(value) <= 0xFFFFFFFFFFFFFFFF


def read_audit(observation, expected_paths):
    audit = observation.get('audit')
    require(isinstance(audit, dict) and type(audit.get('schema')) is int and audit['schema'] == 1
            and audit.get('stringEncoding') == 'bytes-u00xx'
            and type(audit.get('ageMs')) in (int, float) and 0 <= audit['ageMs'] <= 2000
            and audit.get('leaseRootCurrent') is True and positive_token(audit.get('sample'))
            and positive_token(audit.get('modelGeneration')), 'Fresh native coat audit from the retained root required')
    surfaces = audit.get('surfaces')
    require(isinstance(surfaces, list) and all(isinstance(row, dict) for row in surfaces),
            'Native surface inventory unavailable')
    managed, ids = {}, set()
    for row in surfaces:
        geometry = row.get('geometryId')
        require(positive_token(geometry) and int(geometry) not in ids and type(row.get('managed')) is bool,
                'Duplicate or invalid geometry identity in the complete surface inventory')
        ids.add(int(geometry))
        if row.get('managed') is not True:
            continue
        name = row.get('name')
        require(isinstance(name, str) and name.casefold() not in managed, 'Duplicate or invalid managed surface name')
        managed[name.casefold()] = row
    require(managed.keys() == expected_paths.keys(), 'Expected all twelve named managed surfaces')
    return audit, managed, ids


def stock_path(text):
    return text.replace('\\', '/').casefold().removeprefix('data/')


def verify_same_root_turnover(observations, *, pattern, expected_paths, foreign_body_path):
    """Use four consecutive typed snapshots from one owned actor and game run.

    Each phase uses the coat persistence envelope (runId, pid, reference,
    runtimeHandle, worldGeneration, manualOverride, appliedPattern, audit).
    The caller joins the snapshots to the actual live tool evidence and verifies
    the exact fixture, operation completions and final restoration separately.
    """
    require(isinstance(observations, dict) and set(observations) == set(PHASES),
            'Expected the four ordered coat-turnover observations')
    require(isinstance(pattern, str) and pattern and isinstance(expected_paths, dict)
            and len(expected_paths) == 12 and {'body', 'head'} <= expected_paths.keys()
            and all(isinstance(name, str) and name and name == name.casefold()
                    and isinstance(path, str) and path for name, path in expected_paths.items()),
            'Expected the automatic pattern and its twelve exact material paths')
    require(isinstance(foreign_body_path, str) and stock_path(foreign_body_path)
            and stock_path(foreign_body_path) != stock_path(expected_paths['body']),
            'Expected a foreign BODY material distinct from the applied coat')

    reference = checked_identity(observations['baseline'])
    run_id, pid, actor_ref, handle, world = reference
    native = {'runId': run_id, 'pid': pid}
    actor = {'currentReference': actor_ref, 'runtimeHandle': handle}
    geometry, inventories, variations = {}, {}, []
    root, previous_sample = None, 0
    for phase in PHASES:
        observation = observations[phase]
        require(checked_identity(observation) == reference, 'Coat audit belongs to another actor or world')
        require(observation.get('manualOverride') == '', 'Manual coat override in the automatic fixture')
        audit, managed, inventories[phase] = read_audit(observation, expected_paths)
        generation, sample = audit['modelGeneration'], int(audit['sample'])
        require(root is None or generation == root, 'The observed model root changed')
        require(sample > previous_sample, 'Native coat audit sample was replayed or out of order')
        root, previous_sample = generation, sample
        geometry[phase] = {name: int(row['geometryId']) for name, row in managed.items()}

        if phase in ('baseline', 'recovered'):
            verify_sample(observation, native, actor, world, pattern, expected_paths)
            decision = audit.get('coatDecision')
            require(isinstance(decision, dict) and decision.get('pattern') == pattern
                    and type(decision.get('variation')) in (float, int) and 0 <= decision['variation'] <= 1,
                    'Missing actual automatic coat decision or variation')
            variations.append(decision['variation'])
        else:
            require(observation.get('appliedPattern') == '' and 'coatDecision' not in audit
                    and all(row.get('healthyLease') is False and row.get('ownDiffuse') is False
                            for row in managed.values()), 'The foreign phase retained a private coat lease')
            body = managed['body']
            require(all(isinstance(body.get(field), str) and stock_path(body[field]) == stock_path(foreign_body_path)
                        for field in ('diffusePath', 'diffuseResource')), 'Actual foreign BODY path or resource differs')

    baseline, foreign, sibling, recovered = (geometry[phase] for phase in PHASES)
    require(baseline == foreign and inventories['baseline'] == inventories['foreign'],
            'External material change replaced managed geometry or changed the full inventory')
    require({name for name in sibling if sibling[name] != foreign[name]} == {'head'}
            and sibling['head'] > max(inventories['foreign']) and foreign['head'] not in inventories['sibling'],
            'Sibling phase must replace only HEAD with a new geometry identity and detach the old geometry')
    require({name for name in recovered if recovered[name] != sibling[name]} == {'body'}
            and recovered['body'] > max(inventories['foreign'] | inventories['sibling'])
            and inventories['recovered'].isdisjoint((sibling['body'], foreign['head'])),
            'Recovery must replace only BODY with a new geometry identity and keep the superseded geometry detached')
    require(variations[0] == variations[1], 'Automatic coat variation changed across geometry replacement')
    return {'pattern': pattern, 'variation': variations[0], 'worldGeneration': world,
            'modelGeneration': root, 'managedSurfaces': len(expected_paths),
            'replacedGeometry': {'head': str(sibling['head']), 'body': str(recovered['body'])}}
