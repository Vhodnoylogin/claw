"""Verify a hair-linked coat across one recorded, owned, same-process load."""

import re

if __package__:
    from .coat_variation_readback import verify_skin_variation
else:
    from coat_variation_readback import verify_skin_variation


def require(condition, message):
    if not condition:
        raise ValueError(message)


def positive(value):
    return type(value) is int and value > 0


def text_matches(value, pattern):
    return isinstance(value, str) and re.fullmatch(pattern, value) is not None


def actor_rows(native, focus):
    rows = native['actors']
    by_tag = {row['tag']: row for row in rows}
    require(len(by_tag) == len(rows) and focus in by_tag, 'Native actor roster is incomplete or duplicated')
    return by_tag


def verify_owned_load(saved, loaded, tag):
    """Join the original save, one load and the explicitly remapped subject."""
    before, after = (result['nativePersistenceReceipt'] for result in (saved, loaded))
    require(before.get('schemaVersion') == after.get('schemaVersion') == 1
            and before.get('protocol') == after.get('protocol') == 'npc-persistence/1'
            and before.get('phase') == 'saved' and after.get('phase') == 'loaded',
            'Owned native save/load results required')
    context = ('runId', 'providerSession', 'saveTag', 'bindingId')
    require(all(isinstance(before.get(key), str) and before[key] and before[key] == after.get(key) for key in context)
            and positive(before.get('pid')) and before['pid'] == after.get('pid'),
            'Save/load run, provider, binding or process differs')
    require(positive(before.get('saveOrdinal')) and after.get('saveOrdinal') == before['saveOrdinal']
            and type(before.get('loadOrdinal')) is int and before['loadOrdinal'] >= 0
            and after.get('loadOrdinal') == before['loadOrdinal'] + 1, 'Expected exactly one load of the saved generation')
    old_save, new_save = (result['save'] for result in (saved, loaded))
    lifecycle, load = loaded['lifecycle'], loaded['load']
    require(all(state.get('completed') is True and state.get('ownedByAttempt') is True
                and state.get('saveTag') == before['saveTag'] and state.get('bindingId') == before['bindingId']
                for state in (old_save, new_save))
            and text_matches(old_save.get('stem'), r'[A-Za-z0-9_-]{1,200}')
            and all(text_matches(old_save.get(key), r'[0-9a-f]{64}') for key in ('essSha256', 'skseSha256'))
            and all(old_save[key] == new_save.get(key) for key in ('stem', 'essSha256', 'skseSha256')),
            'Load did not use the identical attempt-owned ESS/SKSE pair')
    require(load.get('completed') is True and load.get('sameProcess') is True
            and load.get('saveTag') == before['saveTag'] and positive(load.get('worldGeneration'))
            and lifecycle.get('worldReady') is True and lifecycle.get('pidChanged') is False
            and lifecycle.get('generationChanged') is True
            and lifecycle.get('worldGeneration') == load['worldGeneration'], 'Loaded world transition was not witnessed')
    old_rows, new_rows = actor_rows(before, tag), actor_rows(after, tag)
    require(old_rows.keys() == new_rows.keys() and load.get('actorWitnessCount') == len(old_rows),
            'Loaded roster differs from the saved roster')
    old, new = old_rows[tag], new_rows[tag]
    stable = ('base', 'creationId', 'savedReference', 'savedVmHandle')
    require(all(old.get(key) == new.get(key) for key in stable)
            and text_matches(old.get('creationId'), r'[0-9a-f]{32}')
            and text_matches(old.get('base'), r'0x[0-9A-F]{8}')
            and text_matches(old.get('savedVmHandle'), r'[1-9][0-9]{0,19}')
            and old.get('currentVmHandle') == old['savedVmHandle']
            and all(text_matches(row.get('currentReference'), r'0xFF[0-9A-F]{6}')
                    and positive(row.get('runtimeHandle')) and row.get('persistent') is True for row in (old, new))
            and old['savedReference'] == old['currentReference']
            and new.get('formResolved') is True and new.get('handleResolved') is True
            and new.get('resolvedReference') == new['currentReference']
            and text_matches(new.get('currentVmHandle'), r'[1-9][0-9]{0,19}')
            and new.get('resolvedVmHandle') == new['currentVmHandle'], 'Actual subject remap is missing or inconsistent')
    return before, old, new, load['worldGeneration']


def verify_sample(observation, native, actor, world, pattern, expected_paths):
    require(observation.get('runId') == native['runId'] and observation.get('pid') == native['pid']
            and observation.get('reference') == actor['currentReference']
            and observation.get('runtimeHandle') == actor['runtimeHandle'] and observation.get('worldGeneration') == world,
            'Coat observation belongs to another fixture or world')
    require(observation.get('manualOverride') == '' and observation.get('appliedPattern') == pattern,
            'The observed coat is not the expected automatic selection')
    audit = observation['audit']
    age = audit.get('ageMs')
    require(audit.get('schema') == 1 and audit.get('stringEncoding') == 'bytes-u00xx'
            and type(age) in (int, float) and 0 <= age <= 2000
            and text_matches(audit.get('sample'), r'[1-9][0-9]{0,19}')
            and text_matches(audit.get('modelGeneration'), r'[1-9][0-9]{0,19}'), 'Fresh native coat audit required')
    rows = [row for row in audit['surfaces'] if row.get('managed') is True]
    require(len(rows) == len(expected_paths) == 12, 'Expected all twelve managed surfaces')
    material = {}
    for row in rows:
        name = row['name'].casefold()
        require(name in expected_paths and name not in material and row.get('healthyLease') is True
                and row.get('ownDiffuse') is True and row.get('feature') == 0 and 'tint' in row and row['tint'] is None,
                'Duplicate, unmanaged or unhealthy surface in applied coat evidence')
        path = expected_paths[name].replace('\\', '/').casefold()
        require(all(isinstance(row.get(field), str) and row[field].replace('\\', '/').casefold() == path
                    for field in ('diffusePath', 'diffuseResource')), 'Actual diffuse-set path or bound resource differs')
        material[name] = path
    return audit


def verify_automatic_roundtrip(saved, loaded, before, after, *, tag, pattern, expected_paths, skin_aware, seed_only):
    """Use the already verified owned co-save's choice, score and catalog paths.

    The caller binds each observation to consecutive typed native coat reads in
    the indicated actor/world. This checks those results and the native load
    receipts. Authoritative file hashes and saved-source decoding remain caller
    inputs. Compare restoration and process exit separately.
    """
    native, previous_actor, restored_actor, world = verify_owned_load(saved, loaded, tag)
    require(world > 1, 'Missing world generation preceding the owned load')
    first = verify_sample(before, native, previous_actor, world - 1, pattern, expected_paths)
    second = verify_sample(after, native, restored_actor, world, pattern, expected_paths)
    require(int(second['sample']) > int(first['sample'])
            and int(second['modelGeneration']) > int(first['modelGeneration']), 'Pre-load coat audit or model generation was reused')
    scores = [verify_skin_variation(audit, pattern, skin_aware, seed_only) for audit in (first, second)]
    require(scores[0] == scores[1], 'Automatic coat score changed after the owned load')
    return {'pattern': pattern, **scores[0], 'worldGeneration': world, 'managedSurfaces': len(expected_paths)}
