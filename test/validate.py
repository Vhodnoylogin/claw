"""Validate the portable owner-facing inspection kit; never install or run a game."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'test'
PAIR_TYPES = ('MThin', 'MMuscular', 'MHeavy', 'FThin', 'FMuscular', 'FHeavy')
NAMES = ('Iney', 'Kedr', 'Grom', 'Lada', 'Mira', 'Runa')
BASES = ('013475', '01347D', '0A2C90', '0A2C8E', '0A2C8F', '0A2C91')


def need(condition, message):
    if not condition:
        raise ValueError(message)


def read(name):
    return json.loads((KIT / name).read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    manifest = read('data-manifest.json')
    exact_snapshots = 0
    for item in manifest['files']:
        path = (KIT / item['path']).resolve(strict=True)
        need(path.is_relative_to(KIT), 'Manifest path leaves test kit')
        data = path.read_bytes()
        exact = len(data) == item['bytes'] and sha(data) == item['sha256']
        normalized = sha(data.replace(b'\r\n', b'\n')) == item['lfNormalizedSha256']
        need(exact or normalized, 'Snapshot changed: ' + item['path'])
        exact_snapshots += exact
    host_path = re.compile(r'(?<![A-Za-z0-9])[A-Za-z]:[\\/]')
    for path in KIT.rglob('*'):
        if path.is_file() and path.suffix in ('.json', '.xml', '.ini', '.md', '.yaml'):
            need(not host_path.search(path.read_text(encoding='utf-8-sig')),
                 'Machine-local path in portable kit: ' + str(path.relative_to(KIT)))

    spec = importlib.util.spec_from_file_location('claw_fixture_builder', ROOT / 'scripts/build-test-fixture-package.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    preset_bytes = (KIT / 'data/CLAW-Human-Contrast.xml').read_bytes()
    original = (ROOT / 'tests/fixtures/CLAW-Human-Contrast.xml').read_bytes()
    need(preset_bytes.replace(b'\r\n', b'\n') == original.replace(b'\r\n', b'\n'),
         'Current real presets diverged from the backward-compatible fixture')
    presets = builder.preset_records(preset_bytes)
    assignment = builder.assignment_records((KIT / 'data/OBody_presetDistributionConfig.json').read_bytes())
    plugin = builder.fixture_records((ROOT / 'tests/assets/plugins' / builder.PLUGIN).read_bytes())

    scene = read('scene.json')
    commands = read('commands.json')
    need(scene['automaticSpawn'] is False and scene['freshReferencesRequired'] is True, 'Unexpected automatic or saved scene')
    need(scene['cell'] == {'editorId': 'QASmoke', 'plugin': 'Skyrim.esm', 'localFormId': '032AE7'}, 'Wrong test cell')
    need((scene['anchor']['plugin'], scene['anchor']['localFormId']) == ('Dragonborn.esm', '02A1B9'), 'Unstable room anchor')
    need(scene['beforeAnyFixtureCreation']['globalAIEnabled'] is False and
         scene['beforeAnyFixtureCreation']['globalCollisionEnabled'] is False, 'Scene must freeze AI and collisions before spawn')
    need((scene['pairSeparationGameUnits'], scene['pairPitchGameUnits'], scene['rowSeparationGameUnits']) == (110, 300, 320),
         'Owner-accepted scene spacing changed')
    need(scene['initialVisibility'] == {'pairs': True, 'wild': False}, 'Wild group must not appear initially')
    rows = scene['placements']
    need(len(rows) == 12 and len({r['tag'] for r in rows}) == 12, 'Expected twelve uniquely tagged pair members')
    grouped = defaultdict(list)
    for row in rows:
        grouped[row['pairType']].append(row)
        need(row['initiallyHuman'] is True, 'Both pair members must begin human')
        need(row['role'] in ('human', 'wolf') and row['transformAfterSourceEqualityCheck'] == (row['role'] == 'wolf'),
             'Only the Wolf member transforms after source equality')
        need(len(row['position']) == 3 and all(math.isfinite(n) for n in row['position']), 'Invalid actor position')
        offset = [a-b for a, b in zip(row['position'], scene['anchor']['position'])]
        need(math.dist(offset, row['roomMarkerOffset']) < .00001, 'Absolute position/marker offset mismatch')
    need(set(grouped) == set(PAIR_TYPES), 'Wrong pair classes')
    for index, pair in enumerate(PAIR_TYPES):
        members = {row['role']: row for row in grouped[pair]}
        need(set(members) == {'human', 'wolf'}, 'Missing pair role')
        sex = 'male' if index < 3 else 'female'
        heading = 90 if sex == 'male' else 270
        for role, row in members.items():
            need(row['name'] == NAMES[index] + ' ' + role.title(), 'Ambiguous actor name')
            need(row['tag'] == pair + role.title(), 'Wrong actor tag')
            need(row['sex'] == sex and row['headingDegrees'] == heading, 'Baseline sex/heading changed')
            need(row['initialNpcBase'] == {'plugin': 'Skyrim.esm', 'localFormId': BASES[index]}, 'Wrong human base')
            need(row['humanPreset'] == presets[index]['name'], 'Pair preset differs')
        human, wolf = members['human'], members['wolf']
        need(abs(math.dist(human['position'][:2], wolf['position'][:2]) - 110) <= .01, 'Wrong within-pair spacing')
        expected_x = -2697.94482421875 if sex == 'male' else -2377.94482421875
        need(all(abs(row['position'][0] - expected_x) < .00001 for row in members.values()), 'Actor row moved')
        need(abs(wolf['position'][1] - (1836 - (index % 3) * 300)) < .00001, 'Pair pitch/absolute room placement changed')

    need(set(commands['groupOperations']) == {'show pairs', 'hide pairs', 'show wild', 'hide wild'}, 'Group intents incomplete')
    wild = commands['groups']['wild']
    need(wild['initiallyVisible'] is False and wild['createOnlyOnExplicitCommand'] is True and
         wild['hideOtherGroupBeforeShowing'] == 'pairs', 'Unsafe wild group activation policy')
    need(wild['plugin'] == builder.PLUGIN and len(wild['members']) == 6, 'Wrong wild fixture')
    for index, member in enumerate(wild['members']):
        actual = plugin['npcBases'][index]
        need(member['localFormId'] == actual['localFormId'] and member['sex'] == actual['sex'] and
             member['name'] == actual['name'] and member['preset'] == presets[index]['name'], 'Wild identity/preset mismatch')
        need(member['placementTag'] == PAIR_TYPES[index] + 'Wolf', 'Wild slot differs from fixed paired layout')
    views = commands['rotationViews']
    need([v['offsetDegrees'] for v in views] == [0, 90, 180, 270], 'Missing quarter-turn views')
    need(all(v['maleHeadingDegrees'] == (90+v['offsetDegrees']) % 360 and
             v['femaleHeadingDegrees'] == (270+v['offsetDegrees']) % 360 for v in views), 'A view rewrites or misuses baseline headings')
    dependencies = read('dependencies.json')
    need(dependencies['separateProfileRequired'] is True and dependencies['sourceProfileName'] == 'CLAW', 'Test profile isolation missing')
    need(dependencies['photography']['humanUnderwearRequired'] is True and dependencies['photography']['buildMorphsRequired'] is True,
         'Photography underwear/morph requirement missing')
    print(json.dumps({'passed': True, 'release': manifest['release'], 'pairedActors': 12,
                      'humanPresets': len(presets), 'wildActors': len(plugin['npcBases']),
                      'rotationViews': len(views), 'verifiedSnapshots': len(manifest['files']),
                      'exactOriginalSnapshotBytes': exact_snapshots, 'assignment': assignment,
                      'gameOrInstallationTouched': False}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
