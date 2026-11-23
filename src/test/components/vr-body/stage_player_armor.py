"""Build an isolated VR Body32 outfit with engine-selected male/female models."""
from __future__ import annotations

from argparse import ArgumentParser
from contextlib import closing
from hashlib import sha256 as digest
import json
from pathlib import Path, PurePosixPath
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'src/main/components/vr-body'))
from vr_dispatch import BASE, LEGACY_ALIAS, ROOT, SEXES, armor_path, assemble, require_static_nif, resource_layout, resource_paths
from body_resource import safe_output, sha256
from engine_audit import RACE, arma_summary, slot_summary
from plugin import Spriggit, WRAPPER
from record_reader import FormKey, PluginFile
from stage_world_motion_markers import PLAYER_ARMOR_MARKERS, PLAYER_WORLD_MARKERS, add_marker, motion


PLUGIN = 'test_CLAW - VR Player Body32.esp'
ARMOR = FormKey(PLUGIN, 0x801)
ADDON = FormKey(PLUGIN, 0x800)
EDITOR_ID = 'CLAWTestVRPlayerBody32'


def world_ear_path(sex, extension):
    return PurePosixPath(resource_paths(sex)).with_name('EarWorldTrial' + extension).as_posix()


def world_armor_path(sex, visible_ears):
    return world_ear_path(sex, '.nif').removeprefix('Meshes/').replace('/', '\\') if visible_ears else armor_path(sex)


def verify_record(path, *, visible_ears=False):
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
        world_models = {sex: world_armor_path(sex, visible_ears) for sex in SEXES}
        record = arma_summary(addon)
        if (record['worldModels'] != world_models or record['firstPersonRecordModels'] != models or
                record['weightFlagBytes'] != dict.fromkeys(SEXES, 0)):
            raise ValueError('Expected both views to use their own declared models by sex')
    receipt = {'item': ARMOR.text(), 'addon': ADDON.text(), 'race': RACE.text(), 'slot': 32, 'declaredModels': models}
    if visible_ears:
        receipt['declaredWorldModels'] = world_models
    return receipt


def write_sources(root, *, visible_ears=False):
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
    world_paths = ''.join(f'  {sex.title()}:\n    File: {world_armor_path(sex, visible_ears)}\n' for sex in SEXES)
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
{world_paths}FirstPersonModel:
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


def stage_world_ears(directory, fixed_profile, core_resources, pack):
    """Reuse the verified male/female controls on independent world-body routes."""
    receipt_path = directory / 'visible-ears.json'
    receipt_data = receipt_path.read_bytes()
    receipt = json.loads(receipt_data)
    fixed_path = Path(fixed_profile)
    fixed_data = fixed_path.read_bytes()
    if (receipt['schema'] != 'claw-vr-world-visible-ears/1' or receipt['corePhysicsSelection'] != 'None' or
            pack.sha(fixed_data) != motion.FIXED_SHA256 or
            not any(row['sha256'] == motion.FIXED_SHA256 for row in receipt['inputs'])):
        raise ValueError('Expected the visible-ear controls for the reviewed fixed-profile resources')
    fixed = pack.read_zip(fixed_data)
    for path, expected in core_resources.items():
        if pack.sha(fixed['shared/' + path]) != expected:
            raise ValueError('Visible-ear base and first-person model use different sources: ' + path)
    static, active, sources = {}, {}, {}
    for sex in SEXES:
        variants = {}
        for mode in ('static', 'fsmp'):
            path = directory / f'test_CLAW VR Visible Ears - {sex.title()} {mode.upper()}.zip'
            raw = path.read_bytes()
            pin = receipt['candidates'][sex][mode]
            if pin['sha256'] != pack.sha(raw) or pin['bytes'] != len(raw):
                raise ValueError('Visible-ear archive differs from its source receipt: ' + path.name)
            sources[path.name] = pin['sha256']
            variants[mode] = pack.read_zip(raw)
        base, configured = variants['static'], variants['fsmp']
        world, tri = world_ear_path(sex, '.nif'), world_ear_path(sex, '.tri')
        xml = pack.MOTION_XML + sex.title() + '.xml'
        if (set(base) != {LEGACY_ALIAS, tri} or set(configured) != {*base, xml} or
                base[tri] != configured[tri] or configured[xml] != motion.fsmp_motion.render_xml(sex == 'female')):
            raise ValueError('World controls must share one TRI and bind the matching motion configuration')
        original = base[LEGACY_ALIAS]
        expected = tri.removeprefix('Meshes/').replace('/', '\\').lower()
        require_static_nif(original, expected_tri=expected)
        if motion.fsmp_motion.bind_nif(original, xml)[0] != configured[LEGACY_ALIAS]:
            raise ValueError('World control changes more than the FSMP root binding')
        marked = add_marker(original, PLAYER_WORLD_MARKERS[sex])
        static.update({world: marked, tri: base[tri]})
        active.update({world: motion.fsmp_motion.bind_nif(marked, xml)[0], xml: configured[xml]})
    return static, active, {'sourceReceiptSha256': pack.sha(receipt_data), 'visibleEarSources': sources, 'coreMotion': 'None'}


def build(body, output, compiler=WRAPPER, *, visible_ears=None, fixed_profile=None):
    if (visible_ears is None) != (fixed_profile is None):
        raise ValueError('The visible-ear controls require their fixed-profile source archive')
    sources = [body, BASE] if visible_ears is None else [body, BASE, visible_ears / 'visible-ears.json', fixed_profile]
    output = safe_output(output, sources)
    source = output / 'sources'
    write_sources(source, visible_ears=visible_ears is not None)
    esp = output / PLUGIN
    Spriggit(compiler).build(source, esp)
    records = verify_record(esp, visible_ears=visible_ears is not None)
    motion_report = {}
    with TemporaryDirectory(prefix='marked-resources-', dir=output) as scratch:
        staging = Path(scratch)
        inputs = stage_marked_resources(body, staging)
        name = esp.stem + '.zip'
        if visible_ears is None:
            archive = assemble(esp, staging, output / name)
        else:
            archive = assemble(esp, staging, staging / name)
            pack = motion.open_tools(ROOT / 'src/main/python/build-tools/package-source-build.py')
            original = pack.read_zip((staging / name).read_bytes())
            static, active, motion_report = stage_world_ears(visible_ears, fixed_profile, inputs['payloadSha256'], pack)
            for filename, members in ((name, original | static), (esp.stem + ' - World FSMP.zip', active)):
                target = output / filename
                target.write_bytes(pack.zip_bytes(members))
                if pack.read_zip(target.read_bytes()) != members:
                    raise ValueError('Written VR player trial archive differs from its verified members')
            archive.update(archiveSha256=sha256(output / name),
                           payloadSha256={member: pack.sha(data) for member, data in (original | static).items()})
            motion_report['overlay'] = motion.fsmp_motion.common.pin(output / (esp.stem + ' - World FSMP.zip'))
            motion_report['overlayMembers'] = {member: pack.sha(data) for member, data in active.items()}
    schema = 'claw-vr-player-body32-outfit/3' if motion_report else 'claw-vr-player-body32-outfit/2'
    report = {'schema': schema, **records, **archive,
              'sourceResources': inputs, 'markers': PLAYER_ARMOR_MARKERS,
              'runtimeQualified': False}
    if motion_report:
        report['worldEarMotion'] = motion_report
        report['worldMarkers'] = PLAYER_WORLD_MARKERS
    (output / 'player-body32.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--resources', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--spriggit', type=Path, default=WRAPPER)
    parser.add_argument('--visible-ears', type=Path, help='Verified visible-ear static and FSMP controls')
    parser.add_argument('--fixed-profile', type=Path, help='Fixed-profile archive used to build the visible-ear controls')
    args = parser.parse_args()
    print(json.dumps(build(args.resources, args.out, args.spriggit,
                           visible_ears=args.visible_ears, fixed_profile=args.fixed_profile), indent=2))


if __name__ == '__main__':
    main()
