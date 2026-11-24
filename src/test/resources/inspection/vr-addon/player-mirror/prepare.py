"""Build the disposable mirror NPC bases from the user's installed Skyrim master."""

import argparse
from contextlib import closing
from hashlib import file_digest
import json
import math
from pathlib import Path
from struct import pack, unpack
import sys
import xml.etree.ElementTree as ET


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
sys.path[:0] = [str(HERE.parents[1] / 'lighting'), str(REPO / 'src/main/python/vr')]
from build_lighting import grp, rec, sub
from record_reader import FormKey, PluginFile, subrecords, zstring


SCENE = json.loads((HERE / 'scene.json').read_text(encoding='utf-8'))
PRESET_FLAG = 0x00000004
ESSENTIAL_FLAG = 0x00000002
# Preserve appearance, body traits and neutral stats from the selected preset.
# No copied script, curse, faction, item, package, perk, spell or player record.
FIELDS = {'OBND', 'ACBS', 'VTCK', 'RNAM', 'AIDT', 'CNAM', 'DATA', 'DNAM', 'PNAM',
          'HCLF', 'NAM5', 'NAM6', 'NAM7', 'NAM8', 'FTST', 'QNAM', 'NAM9', 'NAMA',
          'TINI', 'TINC', 'TINV', 'TIAS'}


def sha256(path):
    with path.open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def mirror_payload(source, case, role):
    flags, = unpack('<I', source.one('ACBS')[:4])
    if (source.signature != 'NPC_' or zstring(source.one('EDID')) != case['preset']['editorId']
            or source.ref('RNAM') != FormKey('skyrim.esm', int(SCENE['nordRace'], 16))
            or flags & PRESET_FLAG != PRESET_FLAG or bool(flags & 1) != (case['sex'] == 'female')
            or unpack('<f', source.one('NAM7'))[0] != case['weight']):
        raise ValueError('Installed Nord preset differs from the scene definition')
    label = f'CLAW {role.title()} Mirror ({case["family"]})'
    editor = f'CLAWVRMirror{case["family"]}{role.title()}'
    rows = [('EDID', editor.encode('ascii') + b'\0')]
    for field, value in source.fields():
        if field == 'FULL':
            rows.append((field, label.encode('ascii') + b'\0'))
        if field == 'ACBS':
            value = pack('<I', (flags & ~PRESET_FLAG) | ESSENTIAL_FLAG) + value[4:]
        if field in FIELDS:
            rows.append((field, value))
    return rows


def matrix_channels(document, case):
    matches = [profile for profile in ET.parse(document).getroot().findall('Profile')
               if profile.get('family') == case['family'] and profile.get('sex') == case['sex']]
    if len(matches) != 1 or matches[0].get('id') != case['matrixProfile']:
        raise ValueError('The installed matrix has no single matching mirror family')
    profile, = matches
    for target, expected in case['expectedWolf'].items():
        rules = [rule for rule in profile.findall('Rule') if rule.get('target') == target]
        caps = {float(rule.get('cap')) for rule in rules}
        driven = [rule for rule in rules if rule.get('source') in case['morphs']]
        if (len(caps) != 1 or not driven or any(rule.get('source', '').startswith('$')
                or rule.get('function') == 'constant' for rule in rules)
                or any(rule.get('function', 'identity') not in ('identity', 'positive') for rule in driven)):
            raise ValueError('A selected contrast no longer uses the pinned direct mapping: ' + target)
        uncapped = sum(case['morphs'][rule.get('source')] * float(rule.get('gain')) for rule in driven)
        actual = min(1., max(0., uncapped)) * caps.pop()
        if not math.isclose(actual, expected, abs_tol=1e-6):
            raise ValueError('The expected output differs from the selected matrix: ' + target)
    return profile.get('id')


def prepare(master, matrix, output, variant=None):
    if master.name != SCENE['master']:
        raise ValueError('Use the Skyrim.esm from your VR installation')
    cases = SCENE['variants'] if variant is None else {variant: SCENE['variants'][variant]}
    bodies = []
    with closing(PluginFile(master)) as source:
        if source.masters:
            raise ValueError('The Skyrim master must not depend on another plugin')
        for case in cases.values():
            profile = matrix_channels(matrix, case)
            original = source.records[FormKey(source.name, int(case['preset']['form'], 16))]
            for role, local in case['bases'].items():
                raw = b''.join(sub(tag, value) for tag, value in mirror_payload(original, case, role))
                local = int(local, 16)
                bodies.append((local, raw, {'role': role, 'family': case['family'], 'matrixProfile': profile,
                                            'expectedWolf': case['expectedWolf'],
                                            'local': f'0x{local:08X}', 'preset': original.key.text()}))
    if len({local for local, _, _ in bodies}) != 2 * len(cases):
        raise ValueError('Expected two independent human NPC bases per variant')
    header = b''.join((sub('HEDR', pack('<fII', 1.7, len(bodies) + 1, max(row[0] for row in bodies) + 1)),
                       sub('CNAM', b'CLAW test scene\0'),
                       sub('MAST', b'Skyrim.esm\0'), sub('DATA', b'\0' * 8)))
    data = b''.join(rec('NPC_', 0x01000000 | local, raw) for local, raw, _ in bodies)
    output.mkdir(parents=True, exist_ok=False)
    plugin = output / SCENE['fixture']
    plugin.write_bytes(rec('TES4', 0, header) + grp(b'NPC_', 0, data))
    with closing(PluginFile(plugin)) as actual:
        if actual.masters != ['skyrim.esm'] or len(actual.records) != len(bodies):
            raise ValueError('Generated fixture has unexpected records or masters')
        for local, raw, _ in bodies:
            mirror = actual.records[FormKey(actual.name, local)]
            if mirror.signature != 'NPC_' or mirror.fields() != subrecords(raw):
                raise ValueError('Mirror NPC structural readback differs')
    receipt = {'scene': SCENE['schema'], 'masterSha256': sha256(master), 'matrixSha256': sha256(matrix),
               'plugin': plugin.name, 'pluginSha256': sha256(plugin), 'fixtures': [row for _, _, row in bodies]}
    (output / 'fixture-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master', type=Path, required=True)
    parser.add_argument('--matrix', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--variant', choices=SCENE['variants'])
    inputs = parser.parse_args()
    prepare(inputs.master, inputs.matrix, inputs.out, inputs.variant)
