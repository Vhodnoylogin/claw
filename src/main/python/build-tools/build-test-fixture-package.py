"""Build one deterministic test_CLAW archive from explicit, read-only fixture inputs."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import io
import json
import math
from pathlib import Path, PurePosixPath
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[4]
PLUGIN = 'test_CLAW - Wild Preset Fixture.esp'
FIXTURE = 'test_CLAW - Human and Wild Actors'
INSPECTION = 'CLAW - Inspection Configuration'
XML_PATH = 'CalienteTools/BodySlide/SliderPresets/CLAW-Human-Contrast-20261027.xml'
OBODY = 'SKSE/Plugins/OBody_presetDistributionConfig.json'
SETTINGS = ('SKSE/Plugins/skee64.ini', 'SKSE/Plugins/SKSEMenuFramework.ini')
MOD_NAME = 'test_CLAW - Human and Werewolf Comparison'
ARCHIVE = MOD_NAME+' - 20261030.zip'
PAIR_TYPES = ('MThin', 'MMuscular', 'MHeavy', 'FThin', 'FMuscular', 'FHeavy')
HUMAN_IDS = ('00013475', '0001347D', '000A2C90', '000A2C8E', '000A2C8F', '000A2C91')
PRESET_NAMES = tuple('CLAW Human Contrast - '+sex+' '+kind for sex in ('Male', 'Female') for kind in ('Slim', 'Muscular', 'Heavy'))
PAYLOAD = {PLUGIN, XML_PATH, OBODY, *SETTINGS, 'test_CLAW/scene-recipe.json', 'test_CLAW/README.md', 'test_CLAW/package.json'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)+'\n').encode('utf-8')


class Inputs:
    def __init__(self):
        self.data = {}

    def read(self, path):
        path = Path(path)
        if path.is_symlink():
            raise ValueError('Symlink input refused: '+str(path))
        path = path.resolve(strict=True)
        if path not in self.data:
            self.data[path] = path.read_bytes()
        return self.data[path]

    def pins(self):
        return [{'path': str(path), 'bytes': len(data), 'sha256': sha(data)} for path, data in sorted(self.data.items())]

    def verify(self):
        for path, data in self.data.items():
            if path.read_bytes() != data:
                raise ValueError('Input changed during packaging: '+str(path))


def safe_output(path):
    path = Path(path).resolve()
    if path.exists() or path == ROOT or path.is_relative_to(ROOT):
        raise ValueError('Fresh external output directory required')
    if any(parent.name.casefold() in ('data', 'mods', 'profiles', 'overwrite', 'downloads') for parent in (path, *path.parents)):
        raise ValueError('Live installation/profile directories refused')
    if any((parent/'.git').exists() for parent in (path, *path.parents)):
        raise ValueError('Output must remain outside Git')
    return path


def subrecords(raw):
    result = defaultdict(list)
    offset = 0
    while offset < len(raw):
        if offset+6 > len(raw):
            raise ValueError('Truncated ESP subrecord')
        kind, count = struct.unpack_from('<4sH', raw, offset)
        offset += 6
        if kind == b'XXXX':
            if count != 4 or offset+10 > len(raw):
                raise ValueError('Invalid ESP extended subrecord')
            count = struct.unpack_from('<I', raw, offset)[0]
            kind = raw[offset+4:offset+8]
            offset += 10
        if offset+count > len(raw):
            raise ValueError('ESP subrecord exceeds record')
        result[kind.decode('ascii')].append(raw[offset:offset+count])
        offset += count
    return result


def fixture_records(data):
    records = []

    def walk(start, end):
        while start < end:
            if start+24 > end:
                raise ValueError('Truncated ESP record')
            kind, size, flags, form = struct.unpack_from('<4sIII', data, start)
            limit = start+size if kind == b'GRUP' else start+24+size
            if limit > end or limit <= start:
                raise ValueError('ESP record exceeds enclosing group')
            if kind == b'GRUP':
                if size < 24:
                    raise ValueError('Invalid ESP group size')
                walk(start+24, limit)
            else:
                raw = data[start+24:limit]
                if flags & 0x40000:
                    expanded = struct.unpack_from('<I', raw)[0]
                    raw = zlib.decompress(raw[4:])
                    if len(raw) != expanded:
                        raise ValueError('ESP compressed-size mismatch')
                records.append((kind.decode('ascii'), form, subrecords(raw)))
            start = limit

    walk(0, len(data))
    if [kind for kind, _, _ in records].count('TES4') != 1 or any(kind not in ('TES4', 'NPC_') for kind, _, _ in records):
        raise ValueError('Fixture must contain only TES4 and NPC definitions; no placed actors/scripts/quests')
    header = next(fields for kind, _, fields in records if kind == 'TES4')
    masters = [value.rstrip(b'\0').decode('utf-8') for value in header['MAST']]
    if masters != ['Skyrim.esm']:
        raise ValueError('Unexpected fixture masters')
    actors = []
    for kind, form, fields in records:
        if kind != 'NPC_':
            continue
        flags = struct.unpack('<I', fields['ACBS'][0][:4])[0]
        race = struct.unpack('<I', fields['RNAM'][0])[0]
        if form >> 24 != 1 or race != 0xCDD84:
            raise ValueError('Fixture contains an override or non-wolf NPC')
        actors.append({'localFormId': f'{form & 0xFFFFFF:06X}',
                       'editorId': fields['EDID'][0].rstrip(b'\0').decode('utf-8'),
                       'name': fields['FULL'][0].rstrip(b'\0').decode('utf-8'),
                       'sex': 'female' if flags & 1 else 'male', 'race': 'Skyrim.esm:0CDD84',
                       'weight': struct.unpack('<f', fields['NAM7'][0])[0]})
    actors.sort(key=lambda actor: actor['localFormId'])
    if [actor['localFormId'] for actor in actors] != [f'{value:06X}' for value in range(0x800, 0x806)]:
        raise ValueError('Expected exactly the six repository wild bases')
    if [actor['sex'] for actor in actors] != ['male']*3+['female']*3:
        raise ValueError('Fixture sex distribution differs')
    return {'masters': masters, 'npcBases': actors, 'placedReferences': 0, 'scriptsOrQuests': 0}


def preset_records(data):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():
        raise ValueError('XML declarations/entities refused')
    root = ET.fromstring(data)
    presets = root.findall('Preset')
    if root.tag != 'SliderPresets' or [preset.get('name') for preset in presets] != list(PRESET_NAMES):
        raise ValueError('Expected exactly the six current human contrast presets')
    result = []
    for index, preset in enumerate(presets):
        family = 'HIMBO' if index < 3 else 'CBBE 3BBB Body Amazing'
        if preset.get('set') != family:
            raise ValueError('Human preset resource family differs')
        endpoints = {'small': {}, 'big': {}}
        for slider in preset.findall('SetSlider'):
            name, endpoint = slider.get('name'), slider.get('size')
            value = float(slider.get('value'))
            if endpoint not in endpoints or not name or name in endpoints[endpoint] or not math.isfinite(value):
                raise ValueError('Invalid/duplicate human slider value')
            endpoints[endpoint][name] = value
        if not endpoints['small'] or endpoints['small'] != endpoints['big']:
            raise ValueError('Human preset endpoints must be identical')
        result.append({'name': preset.get('name'), 'family': family,
                       'sliderCountPerEndpoint': len(endpoints['small']), 'endpointsEqual': True,
                       'vectorSha256': sha(encoded(endpoints['small']))})
    return result


def assignment_records(data):
    config = json.loads(data)
    if config.get('disablePresetDistribution') != 'none':
        raise ValueError('Effective assignment config unexpectedly disables distribution')
    forms = config.get('npcFormID', {})
    expected = {'Skyrim.esm': dict(zip(HUMAN_IDS, ([name] for name in PRESET_NAMES))),
                PLUGIN: {f'{index+0x800:08X}': [name] for index, name in enumerate(PRESET_NAMES)}}
    if forms != expected:
        raise ValueError('Current exact NPC-to-human-preset assignments differ')
    for sex in ('Male', 'Female'):
        names = [name for name in PRESET_NAMES if ' - '+sex+' ' in name]
        if config.get('race'+sex) != {'WerewolfBeastRace': names}:
            raise ValueError('Wild sex-specific preset pool differs')
    return {'humanNpcAssignments': 6, 'wildNpcAssignments': 6, 'wildRacePools': 2,
            'profileWideOverride': True, 'disablePresetDistribution': 'none'}


def historic_pairs(data):
    source = json.loads(data)
    rows = source.get('pairs', [])
    if not source.get('sourceComparisonPassed') or [row['type'] for row in rows] != list(PAIR_TYPES):
        raise ValueError('Six-pair source-equality evidence missing')
    result = []
    for index, row in enumerate(rows):
        if not row.get('passed') or row.get('errors') or any(row[key] != 0 for key in ('sourceAggregateDifferences', 'sourceKeyDifferences', 'rawWeightDifference')):
            raise ValueError('Historical pair sources were not equal')
        result.append({key: row[key] for key in ('type', 'sourceCount', 'sourceAggregateDifferences', 'sourceKeyDifferences', 'rawWeightDifference')})
        if row['sourceCount'] != (61 if index < 3 else 52):
            raise ValueError('Historical source-vector coverage differs')
    return {'kind': 'historical-comparison-only; fresh instances require fresh readback', 'pairs': result,
            'allSixSourceVectorsEqual': True, 'newSceneSpawnedOrQualified': False}


def scene_recipe(data, equality):
    source = json.loads(data)
    if source.get('cell') != 'QASmoke' or any(source.get(key) != value for key, value in (
            ('pairSeparationGameUnits', 110), ('spacingWithinRowGameUnits', 300),
            ('rowSeparationGameUnits', 320), ('aiEnabled', False), ('collisionEnabled', False))):
        raise ValueError('Owner-accepted scene dimensions/states differ')
    marker = source['anchorReference']['roomMarker']
    if (marker['plugin'], marker['localFormId']) != ('Dragonborn.esm', '02A1B9'):
        raise ValueError('Stable QASmoke anchor differs')
    rows = source['actors']
    if len(rows) != 12 or len({row['tag'] for row in rows}) != 12:
        raise ValueError('Expected twelve uniquely tagged paired placements')
    placements = []
    for index, pair in enumerate(PAIR_TYPES):
        pair_rows = [row for row in rows if row['pairType'] == pair]
        if {row['role'] for row in pair_rows} != {'human', 'wolf'} or len(pair_rows) != 2:
            raise ValueError('Expected human/wolf placement pair')
        for row in pair_rows:
            placement = {key: row[key] for key in ('tag', 'name', 'spokenName', 'sex', 'presetClass', 'pairType', 'role', 'position', 'roomMarkerOffset')}
            placement['headingDegrees'] = row['headingAfterInteractiveDegrees']
            placement['initialNpcBase'] = {'plugin': 'Skyrim.esm', 'localFormId': HUMAN_IDS[index][-6:]}
            placement['humanPreset'] = PRESET_NAMES[index]
            placement['initiallyHuman'] = True
            placement['transformAfterSourceEqualityCheck'] = row['role'] == 'wolf'
            if any(abs(row['position'][axis]-marker['position'][axis]-row['roomMarkerOffset'][axis]) > .001 for axis in range(3)):
                raise ValueError('Absolute/marker-relative placement mismatch')
            placements.append(placement)
    return {'schemaVersion': 1, 'kind': 'reusable-scene-recipe; no saved actor instances',
            'cell': {key: marker['cell'][key] for key in ('plugin', 'localFormId', 'editorId')},
            'anchor': {key: marker[key] for key in ('plugin', 'localFormId', 'position')},
            'playerPreparation': {key: source['anchorReference'][key] for key in ('playerPreparationPosition', 'headingDegrees')},
            'pairSeparationGameUnits': 110, 'pairPitchGameUnits': 300, 'rowSeparationGameUnits': 320,
            'freshReferencesRequired': True, 'automaticSpawn': False,
            'beforeAnyFixtureCreation': {'globalAIEnabled': False, 'globalCollisionEnabled': False,
                'verification': 'Capture actual global states before first spawn. TAI/TCL are toggles: do not blindly replay them.'},
            'appearancePolicy': 'Both pair members start from the same human NPC base, face/hair/skin/body family, scale, weight and complete keyed OBody source vector; verify equality before transforming only the Wolf member.',
            'placementPolicy': 'Use absolute QASmoke/marker anchors, never current player position. Preserve measured individual floor heights; verify all final positions/headings after race changes with two stable reads.',
            'placements': placements, 'historicalSourceEquality': equality,
            'optionalWildGroup': 'Six initially-beast plugin bases are separate optional fixtures; install spawns nothing. Add only on an explicit operator command, not while creating the twelve paired humans.'}


def profile_collisions(inputs, mods, profile, destinations):
    lines = inputs.read(profile/'modlist.txt').decode('utf-8-sig').splitlines()
    active = [line[1:] for line in lines if line.startswith('+')]
    if any(name not in active for name in (FIXTURE, INSPECTION)) or active.index(FIXTURE) > active.index(INSPECTION):
        raise ValueError('Source CLAW profile no longer gives fixture priority over inspection config')
    collisions = []
    for destination in sorted(destinations):
        users = []
        for name in active:
            path = mods/name/destination
            if path.is_file():
                data = inputs.read(path)
                users.append({'mod': name, 'path': str(path.resolve()), 'sha256': sha(data), 'bytes': len(data)})
        collisions.append({'destination': destination, 'winner': users[0] if users else None, 'providers': users})
    return collisions


def production_collisions(inputs, frozen, destinations):
    manifest = json.loads(inputs.read(frozen/'claw-build.json'))
    inventory = []
    for package in manifest['packages']:
        for record in package['files']:
            name = record['path']
            if package['component'] == 'distribution':
                if name.startswith(('00 Core/', '20 OBody Source/')):
                    name = name.split('/', 1)[1]
                elif name.startswith('10 Human Family/'):
                    name = name.split('/', 2)[2]
                else:
                    continue
            if PurePosixPath(name).suffix.lower() in ('.esp', '.dll', '.pex', '.nif', '.tri') or name.endswith('/MorphLinks.xml'):
                inventory.append({'destination': name, 'sha256': record['sha256'], 'bytes': record['bytes']})
    overlaps = sorted(set(destinations) & {row['destination'] for row in inventory})
    if overlaps:
        raise ValueError('Test archive collides with production payload: '+str(overlaps))
    return {'source': 'frozen production manifest; both human-family mappings included',
            'productionPayloads': inventory, 'overlaps': overlaps}


def verify_zip(archive, entries):
    with zipfile.ZipFile(archive) as reader:
        if reader.testzip() or reader.namelist() != sorted(entries) or {name: reader.read(name) for name in reader.namelist()} != entries:
            raise ValueError('ZIP inventory/CRC/byte verification failed')


def working_collisions(inputs, archive, destinations):
    raw = inputs.read(archive)
    reports = []
    with zipfile.ZipFile(io.BytesIO(raw)) as reader:
        manifest = json.loads(reader.read('claw-unified-release.json'))
        for selection in manifest['selections']:
            records = selection['installedFiles']
            overlap = sorted({row['path'].casefold() for row in records} & {name.casefold() for name in destinations})
            if overlap:
                raise ValueError('Test data collides with selected working archive: '+str(overlap))
            for row in records:
                data = reader.read(row['archivePath'])
                if sha(data) != row['sha256'] or len(data) != row['bytes']:
                    raise ValueError('Working archive selected-payload hash mismatch')
            reports.append({'selection': selection['selection'], 'overlaps': overlap, 'installedFiles': records})
    if not reports:
        raise ValueError('Working archive has no verified selections')
    return {'archive': str(Path(archive).resolve()), 'sha256': sha(raw), 'selections': reports}


def build(args):
    output = safe_output(args.out)
    mods, profile = args.mods.resolve(strict=True), args.profile.resolve(strict=True)
    inputs = Inputs()
    inputs.read(__file__)
    plugin = inputs.read(ROOT / 'target/test-assets/plugins' / PLUGIN)
    presets = inputs.read(ROOT / 'src/test/resources/fixtures/CLAW-Human-Contrast.xml')
    if plugin != inputs.read(mods/FIXTURE/PLUGIN) or presets != inputs.read(mods/FIXTURE/XML_PATH):
        raise ValueError('Repository fixture/presets differ from current installed test inputs')
    plugin_info, preset_info = fixture_records(plugin), preset_records(presets)
    entries = {PLUGIN: plugin, XML_PATH: presets, OBODY: inputs.read(mods/FIXTURE/OBODY)}
    assignment_info = assignment_records(entries[OBODY])
    for path in SETTINGS:
        entries[path] = inputs.read(mods/INSPECTION/path)
    if b'bEnableBodyMorph=1' not in entries[SETTINGS[0]] or b'bEnableBodyGen=0' not in entries[SETTINGS[0]]:
        raise ValueError('Expected inspection RaceMenu settings missing')
    equality = historic_pairs(inputs.read(args.pair_readback))
    recipe = scene_recipe(inputs.read(args.scene), equality)
    entries['test_CLAW/scene-recipe.json'] = encoded(recipe)
    entries['test_CLAW/README.md'] = (
        '# test_CLAW — Human and Werewolf Comparison\n\n'
        'Install as one mod named test_CLAW - Human and Werewolf Comparison in an isolated CLAW test profile, together with the working CLAW archive. '
        'This is test data, not an alternate CLAW body or runtime. Enable test_CLAW - Wild Preset Fixture.esp.\n\n'
        'Contains six originally-beast NPC bases, six ordinary HUMAN HIMBO/3BA presets, current exact NPC/OBody assignments, '
        'inspection RaceMenu/menu settings and the owner-accepted twelve-actor QASmoke scene recipe. '
        'No actors are spawned by installation; no save, dynamic reference, game command, order or credentials are included. '
        'The paired scene starts with two identical humans per type and transforms only the Wolf member after verifying complete source equality. '
        'The six wild plugin bases form a separate optional group.\n\n'
        'scene-recipe.json preserves absolute/stable marker anchors, pair separation110, pair pitch300 and row separation320. '
        'Verify global AI and collision Off BEFORE creating any fixtures; TAI/TCL toggle, so do not replay them blindly. '
        'Resolve fresh references and plugin-local forms each session; verify all final poses twice after transformation. '
        'Historical equality records are evidence of the accepted earlier scene, not a new prepared scene.\n\n'
        'Requires separately installed Skyrim/Dragonborn, working CLAW with matching native human linkage, Elegant textures, '
        'XP32, official RaceMenu, OBody NG, HIMBO and CBBE/3BA body resources/output. SKSE Menu Framework settings apply when that provider is installed. '
        'Use the exact SE native runtime/dependency contract from working CLAW. No dependency binaries/assets are bundled.\n\n'
        'Profile-wide conflicts: SKSE/Plugins/OBody_presetDistributionConfig.json replaces ordinary OBody distribution with the current inspection assignments/blacklists. '
        'skee64.ini enables body morphs and disables BodyGen; SKSEMenuFramework.ini changes inspection menu controls. '
        'Give this single mod priority over the original two fixture/configuration folders, and disable those duplicate folders. '
        'Do not use these settings as a general gameplay preset distribution. No production MorphLinks.xml is included.\n'
    ).encode('utf-8')
    selected = {path: sha(data) for path, data in sorted(entries.items())}
    collisions = profile_collisions(inputs, mods, profile, (PLUGIN, XML_PATH, OBODY, *SETTINGS))
    for row in collisions:
        if row['winner'] is None or row['winner']['sha256'] != selected[row['destination']]:
            raise ValueError('Selected bytes differ from effective source-profile winner: '+row['destination'])
    production = production_collisions(inputs, args.frozen.resolve(strict=True), entries)
    working = working_collisions(inputs, args.working_archive, entries)
    public_manifest = {'schemaVersion': 1, 'archive': ARCHIVE, 'installedModName': MOD_NAME, 'kind': 'test-only-data; no automatic scene creation',
                       'plugin': plugin_info, 'presets': preset_info, 'assignment': assignment_info,
                       'files': [{'path': name, 'bytes': len(data), 'sha256': sha(data)} for name, data in sorted(entries.items())],
                       'manifestSelfExcluded': True, 'productionPayloadOverlap': [], 'textureAssetsIncluded': False}
    entries['test_CLAW/package.json'] = encoded(public_manifest)
    if set(entries) != PAYLOAD:
        raise ValueError('Test package exceeds strict minimal allowlist')
    for name, data in entries.items():
        if name.endswith(('.json', '.md', '.xml', '.ini')) and re.search(rb'(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|0xFF[0-9A-Fa-f]{6}|(?:access_token|command-channel\.token))', data):
            raise ValueError('Private path/token/dynamic reference leaked into archive')
    inputs.verify()
    output.mkdir(parents=True, exist_ok=False)
    archive = output/ARCHIVE
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
        for name, data in sorted(entries.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 30, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            writer.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verify_zip(archive, entries)
    inputs.verify()
    receipt = {'archive': str(archive), 'sha256': sha(archive.read_bytes()), 'bytes': archive.stat().st_size,
               'archiveFiles': len(entries), 'runtimePayloads': [PLUGIN], 'gameOrManagerExecuted': False,
               'historicalAllSixPairSourcesEqual': True, 'newSceneCreated': False, 'productionPayloadOverlap': []}
    provenance = {'receipt': receipt, 'inputs': inputs.pins(), 'selectedEntries': public_manifest['files'],
                  'effectiveSourceProfileCollisions': collisions, 'productionPayloadCollisionAudit': production,
                  'workingArchiveCollisionAudit': working,
                  'excluded': ['meta.ini', 'masked inspection OBody config', 'dependency assets/binaries',
                               'production MorphLinks/body/TRI/CLAW ESP/DLL/PEX', 'legacy mods', 'saves/live references/credentials']}
    (output/'build-receipt.json').write_bytes(encoded(receipt))
    (output/'source-provenance.json').write_bytes(encoded(provenance))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('mods', 'profile', 'scene', 'pair-readback', 'working-archive', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--frozen', type=Path, default=ROOT / 'target/references/releases/se-core-20261030')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(args), indent=2))
    except (ValueError, OSError, KeyError, TypeError, ET.ParseError, struct.error, zlib.error) as error:
        parser.exit(1, 'Test fixture package rejected: '+str(error)+'\n')


if __name__ == '__main__':
    main()
