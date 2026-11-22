"""Semantic SE fixture plan and final result checks for the CLAW coat test."""

import argparse
import json
from pathlib import Path

if __package__:
    from .coat_persistence_readback import positive, require, text_matches
    from .coat_turnover_readback import PHASES, verify_same_root_turnover
else:
    from coat_persistence_readback import positive, require, text_matches
    from coat_turnover_readback import PHASES, verify_same_root_turnover


PLUGIN = 'test_CLAW - Coat Turnover Fixture.esp'
TAG = 'ClawCoatTurnover'
BASE, SKIN, REST = '000800', '000820', '000814'
BODY_A, BODY_B, HEAD_A, HEAD_B = '000830', '000831', '000832', '000833'
HUMAN, WOLF, STOCK_TEXTURE = '013746', '0CDD84', '0C0AE7'
STOCK_BODY = 'textures/actors/wolf/wolfblack.dds'
SAMPLE_NAMES = {phase: f'coat-{phase}' for phase in PHASES}


def form(local_id, plugin=PLUGIN):
    return {'plugin': plugin, 'localId': local_id}


def prepare():
    steps, checks = [], []

    def add(name, operation, request, assertions, role, *, poll=False):
        step = {'name': name, 'operation': operation, 'timeout': 20,
                'assert': [{'field': field, 'equals': value} for field, value in assertions.items()]}
        if request is not None:
            step['parameters'] = {'request': {'actorTag': TAG, **request}}
        if poll:
            step['poll'] = True
        steps.append(step)
        checks.append({'name': name, 'role': role})

    def perform(name, action, arguments, *, role='fixture'):
        add(name, 'object.perform', {'domain': 'claw-coat-turnover', 'action': action, **arguments},
            {'action.completed': True}, role)

    def audit(phase, body, head, expect_lease):
        perform(f'coat-refresh-{phase}', 'refresh', {}, role='subject')
        add(SAMPLE_NAMES[phase], 'world.read',
            {'domain': 'claw-coat-turnover', 'observation': 'audit'},
            {'fixture.skin': form(SKIN), 'fixture.fixedAddon': form(REST),
             'fixture.bodyWorn': form(body), 'fixture.headWorn': form(head),
             'coat.applied': expect_lease, 'coat.managedSurfaceCount': 12}, 'subject', poll=True)

    add('world-ready', 'state.read', None, {'world.ready': True}, 'tooling')
    perform('create-coat-fixture', 'create', {'base': form(BASE), 'forwardGameUnits': 200, 'rightGameUnits': 0})
    perform('refresh-human-coat-source', 'refresh', {})
    add('capture-human-source', 'world.read',
        {'domain': 'claw-coat-turnover', 'observation': 'human-source'},
        {'fixture.base': form(BASE), 'actor.race': form(HUMAN, 'Skyrim.esm'),
         'actor.female': True, 'actor.weight': 50, 'coat.humanHairObserved': True}, 'fixture', poll=True)
    perform('transform-coat-fixture', 'transform', {'race': form(WOLF, 'Skyrim.esm')})
    add('verify-fixture-skin', 'world.read',
        {'domain': 'claw-coat-turnover', 'observation': 'transformed-skin'},
        {'actor.race': form(WOLF, 'Skyrim.esm'), 'fixture.skin': form(SKIN), 'fixture.fixedAddon': form(REST),
         'fixture.stockTorsoPresent': False, 'fixture.bodyHeadPresent': False}, 'fixture', poll=True)
    perform('supply-coat-fixture-equipment', 'supply-equipment',
            {'items': [form(item) for item in (BODY_A, BODY_B, HEAD_A, HEAD_B)]})
    perform('equip-body-a', 'equip', {'item': form(BODY_A), 'slotMask': 4})
    perform('equip-head-a', 'equip', {'item': form(HEAD_A), 'slotMask': 1})
    audit('baseline', BODY_A, HEAD_A, True)
    perform('apply-foreign-body-material', 'set-foreign-coat', {
        'geometryName': 'body', 'textureSet': form(STOCK_TEXTURE, 'Skyrim.esm'), 'firstPerson': False}, role='subject')
    audit('foreign', BODY_A, HEAD_A, False)
    perform('equip-head-b', 'equip', {'item': form(HEAD_B), 'slotMask': 1, 'replaces': form(HEAD_A)})
    audit('sibling', BODY_A, HEAD_B, False)
    perform('equip-body-b', 'equip', {'item': form(BODY_B), 'slotMask': 4, 'replaces': form(BODY_A)})
    audit('recovered', BODY_B, HEAD_B, True)
    # The queued refresh alone does not establish a factual subject response.
    return {
        'subjectPlan': {'interface': 'polygon-actions/1', 'fixture': {'cell': 'QASmoke'}, 'steps': steps},
        'testing': {'start': {'kind': 'check', 'name': SAMPLE_NAMES['baseline']}, 'checks': checks},
        'collect': [
            'Owned fixture identity, effective subject hashes and gameplay form',
            'Exact observed worn forms and stable fixed skin/rest through every phase',
            'Four fresh CLAW public audits with geometry IDs, actual material fields and automatic decisions',
            'Native process outcome and exact restoration',
        ],
    }


def owned_fixture(result):
    records = result.get('interactiveActorFixtures')
    require(isinstance(records, dict) and isinstance(records.get(TAG), dict),
            'Exact owned creation record required')
    fixture = records[TAG]
    ref, base = fixture.get('reference'), fixture.get('base')
    witness, game, incarnation = (fixture.get(key) for key in ('creationWitness', 'game', 'incarnation'))
    require(fixture.get('status') == 'created' and fixture.get('runId') == result.get('id')
            and text_matches(ref, r'0xFF[0-9A-F]{6}') and fixture.get('createdReference') == ref
            and text_matches(base, r'0x[0-9A-F]{8}') and int(base, 16) >> 24 < 0xFE and base[-6:] == BASE
            and all(isinstance(row, dict) for row in (witness, game, incarnation)),
            'Owned creation record differs from the expected disposable fixture')
    require(witness.get('runId') == result['id'] and witness.get('reference') == ref and witness.get('base') == base
            and witness.get('nativeReturned') is True and witness.get('forcePersist') is False and witness.get('count') == 1
            and text_matches(witness.get('creationId'), r'[0-9a-f]{32}') and fixture.get('creationId') == witness['creationId']
            and positive(game.get('pid')) and positive(incarnation.get('runtimeHandle'))
            and positive(fixture.get('worldGeneration')), 'Owned native creation or incarnation evidence differs')
    return ref, game['pid'], incarnation['runtimeHandle'], fixture['worldGeneration']


def verify_run(result, *, pattern, expected_paths):
    """Score the archived checks of an admitted attempt, after Polygon's custody review."""
    require(result.get('result') == 'passed' and result.get('restored') is True
            and result.get('restoreErrors') == [] and result.get('collectionComplete') is True
            and result.get('collectionErrors') == [], 'Complete passing, restored attempt required')
    expected = [step['name'] for step in prepare()['subjectPlan']['steps']]
    rows = result.get('checks')
    require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows)
            and [row.get('name') for row in rows] == expected
            and all(row.get('result') == 'passed' for row in rows), 'Missing, reordered or failed fixture check')
    observations = {row['name']: row.get('observation') for row in rows}
    identity = owned_fixture(result)
    exact_gear = {
        'baseline': (BODY_A, HEAD_A), 'foreign': (BODY_A, HEAD_A),
        'sibling': (BODY_A, HEAD_B), 'recovered': (BODY_B, HEAD_B),
    }
    packet = {}
    for phase in PHASES:
        observed = observations[SAMPLE_NAMES[phase]]
        body, head = exact_gear[phase]
        require(isinstance(observed, dict) and isinstance(observed.get('fixture'), dict)
                and isinstance(observed.get('coat'), dict), 'Native fixture and coat observations required')
        fixture, coat = observed['fixture'], observed['coat']
        require(fixture.get('skin') == form(SKIN) and fixture.get('fixedAddon') == form(REST)
                and fixture.get('bodyWorn') == form(body) and fixture.get('headWorn') == form(head),
                'Actual fixture skin, fixed addon or worn form differs')
        require(coat.get('runId') == result.get('id')
                and tuple(coat.get(key) for key in ('reference', 'pid', 'runtimeHandle', 'worldGeneration')) == identity,
                'Audit does not belong to the owned game attempt and disposable reference')
        packet[phase] = coat
    return verify_same_root_turnover(packet, pattern=pattern, expected_paths=expected_paths, foreign_body_path=STOCK_BODY)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--result', type=Path)
    parser.add_argument('--expected', type=Path, help='Independently resolved automatic pattern and expected_paths')
    args = parser.parse_args()
    if bool(args.result) != bool(args.expected):
        parser.error('--result and --expected must be given together')
    result = (verify_run(json.loads(args.result.read_bytes()), **json.loads(args.expected.read_bytes()))
              if args.result else prepare())
    print(json.dumps(result, indent=2))
