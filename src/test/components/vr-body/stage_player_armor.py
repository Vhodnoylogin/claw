"""Build an isolated VR Body32 outfit with engine-selected male/female models."""
from __future__ import annotations

from argparse import ArgumentParser
from contextlib import closing
from hashlib import sha256 as digest
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/components/vr-body'))
from vr_dispatch import BASE, SEXES, armor_path, assemble, resource_layout
from body_resource import safe_output, sha256
from engine_audit import RACE, arma_summary, slot_summary
from plugin import Spriggit, WRAPPER
from record_reader import FormKey, PluginFile
from stage_world_motion_markers import PLAYER_ARMOR_MARKERS, add_marker


PLUGIN = 'test_CLAW - VR Player Body32.esp'
ARMOR = FormKey(PLUGIN, 0x801)
ADDON = FormKey(PLUGIN, 0x800)
EDITOR_ID = 'CLAWTestVRPlayerBody32'


def verify_record(path):
    with closing(PluginFile(path)) as plugin:
        if plugin.masters != ['skyrim.esm', 'claw.esp'] or set(plugin.records) != {ARMOR, ADDON}:
            raise ValueError('Expected a local armor pair without shared race, player or skin overrides')
        item, addon = plugin.records[ARMOR], plugin.records[ADDON]
        if (item.signature, addon.signature) != ('ARMO', 'ARMA') or item.flags or addon.flags:
            raise ValueError('Expected unflagged armor and armor addon records')
        if (item.ref('RNAM') != RACE or addon.ref('RNAM') != RACE or item.ref('MODL') != ADDON or
                slot_summary(item)['mask'] != 4 or slot_summary(addon)['mask'] != 4):
            raise ValueError('Armor must use its own single werewolf Body32 addon')
        for record, name in ((item, EDITOR_ID), (addon, EDITOR_ID + 'Addon')):
            if record.one('EDID') != name.encode('ascii') + b'\0' or record.one('VMAD', False) is not None:
                raise ValueError('Unexpected test armor identity or attached script')
        models = {sex: armor_path(sex) for sex in SEXES}
        record = arma_summary(addon)
        if (record['worldModels'] != models or record['firstPersonRecordModels'] != models or
                record['weightFlagBytes'] != dict.fromkeys(SEXES, 0)):
            raise ValueError('Expected both views to use the separately authored static models by sex')
    return {'item': ARMOR.text(), 'addon': ADDON.text(), 'race': RACE.text(), 'slot': 32, 'declaredModels': models}


def write_sources(root):
    meta = json.loads((BASE / 'spriggit-meta.json').read_bytes()) | {'ModKey': PLUGIN}
    root.mkdir(parents=True)
    (root / 'spriggit-meta.json').write_text(json.dumps(meta, indent=2) + '\n', encoding='utf-8')
    (root / 'RecordData.yaml').write_text(f'''SpriggitSource:
  PackageName: {meta['PackageName']}
  Version: 0.41
ModKey: {PLUGIN}
GameRelease: {meta['Release']}
ModHeader:
  Author: CLAW nonshipping test source
  MasterReferences:
  - Master: Skyrim.esm
    FileSize: 0
  - Master: CLAW.esp
    FileSize: 0
''', encoding='utf-8')
    common = '''BodyTemplate:
  FirstPersonFlags:
  - Body
  ArmorType: Clothing
Race: 0CDD84:Skyrim.esm
'''
    paths = ''.join(f'  {sex.title()}:\n    File: {armor_path(sex)}\n' for sex in SEXES)
    records = {
        'Armors': (ARMOR, EDITOR_ID, f'''{common}Name:
  TargetLanguage: English
  Value: Test CLAW VR Player Body32
Armature:
- 000800:{PLUGIN}
'''),
        'ArmorAddons': (ADDON, EDITOR_ID + 'Addon', f'''{common}Priority:
  Male: 0
  Female: 0
WeightSliderEnabled:
  Male: False
  Female: False
Unknown: 2
Unknown2: 23
WorldModel:
{paths}FirstPersonModel:
{paths}'''),
    }
    for directory, (key, editor, payload) in records.items():
        folder = root / directory
        folder.mkdir()
        local_key = f'{key.local_id:06X}'
        (folder / f'{editor} - {local_key}_{PLUGIN}.yaml').write_text(
            f'FormKey: {local_key}:{PLUGIN}\nEditorID: {editor}\n' + payload, encoding='utf-8')


def stage_marked_resources(candidate, staging):
    candidate = candidate.resolve(strict=True)
    manifest_path = candidate / 'install-manifest.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    original = dict(resource_layout(manifest))
    staged = {}
    for relative, expected in original.items():
        path = candidate / 'resources' / relative
        if path.resolve(strict=True) != path:
            raise ValueError('Expected an ordinary source resource: ' + relative)
        data = path.read_bytes()
        if digest(data).hexdigest() != expected:
            raise ValueError('Body resource differs from its source manifest: ' + relative)
        if path.suffix == '.nif':
            data = add_marker(data, PLAYER_ARMOR_MARKERS[path.parent.name])
        target = staging / 'resources' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        staged[relative] = digest(data).hexdigest()
    (staging / manifest_path.name).write_text(json.dumps(manifest | {'files': staged}, sort_keys=True), encoding='utf-8')
    return {'manifestSha256': digest(manifest_bytes).hexdigest(), 'payloadSha256': original}


def build(body, output, compiler=WRAPPER):
    output = safe_output(output, [body, BASE])
    source = output / 'sources'
    write_sources(source)
    esp = output / PLUGIN
    Spriggit(compiler).build(source, esp)
    records = verify_record(esp)
    with TemporaryDirectory(prefix='marked-resources-', dir=output) as scratch:
        staging = Path(scratch)
        inputs = stage_marked_resources(body, staging)
        archive = assemble(esp, staging, output / (esp.stem + '.zip'))
    report = {'schema': 'claw-vr-player-body32-outfit/2', **records, **archive,
              'sourceResources': inputs, 'markers': PLAYER_ARMOR_MARKERS,
              'runtimeQualified': False}
    (output / 'player-body32.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--spriggit', type=Path, default=WRAPPER)
    args = parser.parse_args()
    print(json.dumps(build(args.resources, args.out, args.spriggit), indent=2))


if __name__ == '__main__':
    main()
