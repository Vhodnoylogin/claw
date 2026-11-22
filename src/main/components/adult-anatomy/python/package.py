"""Package the frozen neutral-anatomy trial separately; never install or launch."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path
import sys
import types
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
TOOLS = REPO / 'src/main/python/build-tools'
CORE_SHA = 'f571ad5e486600c3fcd06432034eeed9a2837be2706ca59bc0f72be28262c91a'
STATIC_SHA = '6a7fa9e262a8a329dd3dc41a725edbf8c9da0a577176ed8c04dbae9924c45210'
CORE_FSMP_SHA = '7abd65601c1383272f50b413792e7d54e12a5caf17270fb4f018c9868085c36d'
TRI_SHA = '3ff00f50493664ec68bbbfbe4843bd64f268df9a5659e6a6bd4baea14ae085fc'
NAME = 'test_CLAW - Neutral Anatomy Motion Candidate'
ARCHIVE = NAME + '.zip'
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
XML_ROOT = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/'
GUIDE = 'CLAW-Neutral-Anatomy-README.md'
NOTICE = 'NOTICES/CLAW-Neutral-Anatomy.txt'
DESTINATIONS = tuple(MESH + 'male' + route + '_' + str(weight) + '.nif'
                     for route in ('bodywerewolf', 'PlayerWerewolf') for weight in (0, 1))
MODES = {
    'keep': ('Keep current CLAW motion (default)', None, None),
    'anatomy': ('Anatomy motion only - core None', '10 Anatomy FSMP', 'CLAWNeutralAnatomy.xml'),
    'combined': ('Ear, tail and anatomy motion - core FSMP', '20 Combined FSMP', 'CLAWMotionNeutralAnatomyMale.xml'),
}
PINS = {
    'anatomy': {'nif': 'b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
                'xml': '9bf501b9f5e5ecd0b33fe725af74779a28c4213ee4ae1e2ce9edfcc0269b0529'},
    'combined': {'nif': 'f93d5038cb17493517cf8f80dba63601edbf1f98678d781c3ae31589da7ff89d',
                 'xml': '7cb169385c37b28038643c406c07d6b91937672b872c908420e2172822647d8e'},
}
RUNTIME_GUIDE = b'''# CLAW neutral anatomy motion - private developer candidate

Requires the matching CLAW 0.10 body/TRI family, Elegant Werewolf Replacer and
compatible XP32, installed separately. This is an optional overlay after CLAW.
The existing core male mesh already contains the neutral procedural shape.
This candidate adds no adult-state morphs, controller or independent appearance.

Keep current CLAW motion is the default. It installs no mesh or XML override,
so existing core ear/tail motion remains intact with anatomy physics off.
For anatomy motion, install the runtime-matched Faster HDT-SMP separately:
https://www.nexusmods.com/skyrimspecialedition/mods/57339
Choose Anatomy motion only if the core installer uses None, or the combined
ear/tail/anatomy option if the core uses FSMP. The installer cannot detect the
core motion selection. Reinstall this overlay when changing that selection.
Both male armor routes are supplied; female resources remain in core.

The earlier male12 selective-response test failed. This package has offline
file/installer checks only: motion, attachment, rendered appearance, contacts,
animation and SE/VR lifecycle acceptance remain incomplete. It contains no
collision shapes, skeleton replacement, provider binary or global configuration.
It is a private candidate, not an accepted or published anatomy release.

Source project and credits: https://github.com/Vhodnoylogin/claw
'''
ASSET_NOTICE = b'''CLAW neutral anatomy candidate - asset credits and conditions

Body meshes derive from Elegant Werewolf Replacer by Wolflady500 and KaienHash.
Keep Elegant installed separately. No Elegant textures are redistributed.
https://www.nexusmods.com/skyrimspecialedition/mods/93336

Existing XP32 bone ancestry is by Groovtama. XP32 remains a separate dependency;
this archive contains no skeleton replacement.
https://www.nexusmods.com/skyrimspecialedition/mods/1988

The neutral procedural anatomy and motion XML are original CLAW resources.
No BakaFactory ABC mesh, texture, script or provider code is redistributed.
The original asset permissions remain applicable; this notice grants no new
license to third-party artwork. Recorded permissions and source provenance:
https://github.com/Vhodnoylogin/claw/blob/main/src/main/resources/donors/README.md

Faster HDT-SMP and its original notices remain in its separate installation.
No CommonLib, SKEE, OBody or other native implementation is shipped here.
'''


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def load(path, payload):
    module = types.ModuleType('claw_anatomy_package_' + path.stem.replace('-', '_'))
    module.__file__ = str(path)
    exec(compile(payload, str(path), 'exec'), module.__dict__)
    return module


def installer():
    config = ET.Element('config', {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:noNamespaceSchemaLocation': 'http://qconsulting.ca/fo3/ModConfig5.0.xsd'})
    ET.SubElement(config, 'moduleName').text = NAME
    ET.SubElement(ET.SubElement(config, 'moduleDependencies', operator='And'), 'fileDependency', file='CLAW.esp', state='Active')
    required = ET.SubElement(config, 'requiredInstallFiles')
    for path in (GUIDE, NOTICE):
        ET.SubElement(required, 'file', source=path, destination=path)
    step = ET.SubElement(ET.SubElement(config, 'installSteps', order='Explicit'), 'installStep', name='Neutral anatomy motion')
    group = ET.SubElement(ET.SubElement(step, 'optionalFileGroups', order='Explicit'), 'group', name='One motion composition', type='SelectExactlyOne')
    options = ET.SubElement(group, 'plugins', order='Explicit')
    for mode, (name, _, _) in MODES.items():
        plugin = ET.SubElement(options, 'plugin', name=name)
        ET.SubElement(plugin, 'description').text = (
            'Keep the current core meshes and ear/tail motion. Adds no anatomy physics.' if mode == 'keep' else
            'Private unqualified FSMP trial. Match this option to the core None selection; drives anatomy only.' if mode == 'anatomy' else
            'Private unqualified FSMP trial. Match this option to the core FSMP selection; retains ear/tail motion and adds anatomy.')
        ET.SubElement(ET.SubElement(plugin, 'conditionFlags'), 'flag', name='anatomyMode').text = mode
        ET.SubElement(ET.SubElement(plugin, 'typeDescriptor'), 'type', name='Recommended' if mode == 'keep' else 'Optional')
    patterns = ET.SubElement(ET.SubElement(config, 'conditionalFileInstalls'), 'patterns')
    for mode, (_, folder, xml) in MODES.items():
        if mode == 'keep':
            continue
        pattern = ET.SubElement(patterns, 'pattern')
        ET.SubElement(ET.SubElement(pattern, 'dependencies', operator='And'), 'flagDependency', flag='anatomyMode', value=mode)
        files = ET.SubElement(pattern, 'files')
        for destination in DESTINATIONS:
            ET.SubElement(files, 'file', source=folder+'/male.nif', destination=destination)
        ET.SubElement(files, 'file', source=folder+'/'+xml, destination=XML_ROOT+xml)
    ET.indent(config)
    return ET.tostring(config, encoding='utf-8')


def selection(entries, mode, reader, *, core_motion, active=('CLAW.esp',)):
    """Evaluate the literal component XML with a declared baseline core choice."""
    require(mode in MODES and core_motion in ('none', 'fsmp'), 'Explicit known component/core selection required')
    require(mode == 'keep' or mode == ('anatomy' if core_motion == 'none' else 'combined'),
            'Anatomy selection would replace the declared core ear/tail policy')
    config = ET.fromstring(entries['fomod/ModuleConfig.xml'])
    expected = ET.fromstring(installer())
    require(ET.tostring(config) == ET.tostring(expected), 'Installer changed its exact exclusive default/mapping contract')
    require(reader.dependency(config.find('moduleDependencies'), '1.7.104.0', set(active), {}), 'CLAW.esp must be active')
    group = config.find('.//group')
    picked = [p for p in group.findall('plugins/plugin') if p.findtext('conditionFlags/flag') == mode]
    require(group.get('type') == 'SelectExactlyOne' and len(picked) == 1, 'Exactly one component option required')
    files = list(config.findall('requiredInstallFiles/file'))
    flags = {'anatomyMode': mode}
    for pattern in config.findall('conditionalFileInstalls/patterns/pattern'):
        if reader.dependency(pattern.find('dependencies'), '1.7.104.0', set(active), flags):
            files.extend(pattern.findall('files/file'))
    installed = {}
    for row in files:
        source, destination = (reader.safe_path(row.get(key, '')) for key in ('source', 'destination'))
        require(source in entries and destination.casefold() not in {p.casefold() for p in installed},
                'Missing source or duplicate component destination')
        installed[destination] = source
    return installed


def check_variant(payload, xml, mode, package, materials, composition, drivers):
    fields = package._nif_fields(materials, payload)
    extras, records = fields[-2:]
    hook = b'HDT Skinned Mesh Physics Object'
    path = (XML_ROOT + MODES[mode][2]).encode('ascii')
    require(extras.get(hook) == path and [value for key, value in records if key == hook] == [path],
            'Exactly one known root FSMP binding required')
    tris = {value.decode('ascii').replace('\\', '/').casefold() for key, value in records if key == b'BODYTRI'}
    require(tris == {'actors/werewolfbeast/character assets/malebodywerewolf.tri'}, 'Inherited male BODYTRI path differs')
    require(materials.adapt_nif(payload)[0] == payload, 'Expected existing PlayerOnly material paths')
    anatomy = ('WWD 2', 'WWLB 1', 'WWRB 1')
    composition.inspect_xml(xml, (*drivers, *anatomy) if mode == 'combined' else anatomy,
                            ('NPC Head [Head]', 'Tails', 'WWD 1') if mode == 'combined' else ('WWD 1',))


def audit(entries, core, package, reader):
    expected = {GUIDE, NOTICE, 'fomod/ModuleConfig.xml', 'fomod/info.xml'}
    expected.update(folder+'/'+name for mode, (_, folder, xml) in MODES.items() if mode != 'keep' for name in ('male.nif', xml))
    require(set(entries) == expected, 'Unexpected or missing component archive member')
    require(entries[GUIDE] == RUNTIME_GUIDE and entries[NOTICE] == ASSET_NOTICE, 'Required candidate guide or asset notice changed')
    for mode, (_, folder, xml) in MODES.items():
        if mode != 'keep':
            require(sha(entries[folder+'/male.nif']) == PINS[mode]['nif']
                    and sha(entries[folder+'/'+xml]) == PINS[mode]['xml'], 'Changed component payload')
    config = ET.fromstring(core['fomod/ModuleConfig.xml'])
    plans = []
    for male, female, host, motion in itertools.product(package.MALE_FAMILIES, package.FEMALE_FAMILIES, (False, True), ('none', 'fsmp')):
        markers = {'HIMBO.esp'} if male == 'HIMBO' else set()
        markers |= {'CBBE.esp'} if female in ('CBBE', '3BA') else set()
        markers |= {'3BBB.esp'} if female == '3BA' else set()
        markers |= {'BHUNP3BBB.esp'} if female == 'BHUNP' else set()
        base = reader.resolve_selection(config, core, native=True, male_family=male, family=female,
                                        host=host, additional_active=markers, physics=motion)
        for row in config.findall('requiredInstallFiles/file'):
            require(row.get('destination') not in base and row.get('source') in core, 'Invalid core required destination')
            base[row.get('destination')] = row.get('source')
        baseline = {destination: core[source] for destination, source in base.items()}
        require(all(sha(baseline[name]) == (STATIC_SHA if motion == 'none' else CORE_FSMP_SHA) for name in DESTINATIONS)
                and sha(baseline[MESH+'malebodywerewolf.tri']) == TRI_SHA, 'Core model/TRI selection differs from the pinned family')
        for mode in ('keep', 'anatomy' if motion == 'none' else 'combined'):
            selected = selection(entries, mode, reader, core_motion=motion)
            result = {**baseline, **{destination: entries[source] for destination, source in selected.items()}}
            changed = {name for name, data in baseline.items() if result[name] != data}
            require(changed == (set() if mode == 'keep' else set(DESTINATIONS)), 'Component changed protected core destinations')
            require(not set(selected) & set(baseline) if mode == 'keep' else
                    set(selected) == {*DESTINATIONS, XML_ROOT+MODES[mode][2], GUIDE, NOTICE}, 'Nonminimal component selection')
            plans.append({'maleFamily': male, 'femaleFamily': female, 'obody': host, 'coreMotion': motion,
                          'anatomyMode': mode, 'coreProtectedDestinations': len(baseline)-len(changed),
                          'maleModelOverrides': len(changed), 'selectedFiles': {name: sha(entries[source]) for name, source in selected.items()}})
    require(len(plans) == 80, 'All eighty core/component overlays must be verified')
    return plans


def build(*, core_archive, neutral, combined, out):
    paths = [Path(__file__), HERE/'compose_motion.py', TOOLS/'package-source-build.py',
             TOOLS/'build-unified-release.py', TOOLS/'player_only_materials.py',
             REPO/'src/main/python/physics/recipe.json', HERE.parent/'README.md',
             REPO/'src/main/resources/donors/README.md', REPO/'src/main/python/build-tools/build-genitals.py']
    sources = {path.resolve(): path.read_bytes() for path in paths}
    package = load(paths[2], sources[paths[2]])
    inputs = package.Inputs()
    for path, payload in sources.items():
        require(inputs.read(path) == payload, 'Source changed before packaging')
    reader, materials, composition = [load(path, sources[path]) for path in paths[3:5]+paths[1:2]]
    core_bytes = inputs.read(core_archive)
    require(sha(core_bytes) == CORE_SHA, 'Explicit reviewed CLAW core archive differs')
    core = package.read_zip(core_bytes)
    drivers = tuple(node for group in json.loads(sources[paths[5]])['groups'] for node in group['nodes'])
    static = core['00 Base/'+MESH+'malebodywerewolf_0.nif']
    require(sha(static) == STATIC_SHA, 'Static male core input changed')
    package._check_motion_nif(materials, static, core['40 Motion/FSMP/'+MESH+'malebodywerewolf_0.nif'], 'male')
    entries = {GUIDE: RUNTIME_GUIDE, NOTICE: ASSET_NOTICE, 'fomod/ModuleConfig.xml': installer(),
               'fomod/info.xml': b'<fomod><Name>'+NAME.encode()+b'</Name><Author>CLAW</Author><Version>0.1.0</Version></fomod>'}
    roots = {'anatomy': Path(neutral).resolve(), 'combined': Path(combined).resolve()}
    inventories = {}
    for mode, root in roots.items():
        _, folder, xml = MODES[mode]
        expected = {MESH+'malebodywerewolf_'+str(weight)+'.nif' for weight in (0, 1)} | {MESH+'malebodywerewolf.tri', XML_ROOT+xml}
        inventories[root] = expected
        require({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == expected,
                'Candidate must contain exactly its reviewed four files')
        payloads = {relative: inputs.read(root/relative) for relative in sorted(expected)}
        require(sha(payloads[MESH+'malebodywerewolf.tri']) == TRI_SHA, 'Candidate TRI no longer matches required core')
        nifs = [payloads[MESH+'malebodywerewolf_'+str(weight)+'.nif'] for weight in (0, 1)]
        require(all(sha(data) == PINS[mode]['nif'] for data in nifs) and nifs[0] == nifs[1]
                and sha(payloads[XML_ROOT+xml]) == PINS[mode]['xml'], 'Frozen component input pin differs')
        check_variant(nifs[0], payloads[XML_ROOT+xml], mode, package, materials, composition, drivers)
        entries[folder+'/male.nif'], entries[folder+'/'+xml] = nifs[0], payloads[XML_ROOT+xml]
    archive_bytes = package.zip_bytes(entries)
    reopened = package.read_zip(archive_bytes)
    require(reopened == entries, 'Serialized candidate archive differs')
    plans = audit(reopened, core, package, reader)
    output = Path(out).resolve()
    require(not output.exists() and not any(part.casefold() in ('mods', 'data', 'overwrite', 'downloads') for part in output.parts)
            and not any((parent/'.git').exists() for parent in (output, *output.parents)), 'Use a new external build directory')
    require(output.parent.is_dir() and not any(path.parent == output or path.parent in output.parents for path in inputs.records),
            'Output parent must exist outside all input directories')
    inputs.verify()
    require(all({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == names
                for root, names in inventories.items()), 'Candidate inventory changed during packaging')
    output.mkdir()
    archive = output/ARCHIVE
    archive.write_bytes(archive_bytes)
    require(package.read_zip(archive.read_bytes()) == entries, 'Written ZIP readback differs')
    inputs.verify()
    report = {'status': 'built-private-offline-anatomy-candidate-runtime-unqualified',
              'archive': {'path': str(archive), 'sha256': sha(archive_bytes), 'bytes': len(archive_bytes), 'members': len(entries)},
              'inputs': {str(path): {'sha256': sha(data), 'bytes': len(data)} for path, data in inputs.records.items()},
              'members': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in entries.items()},
              'plans': plans, 'planCount': len(plans), 'default': 'keep-current-core-meshes-and-motion',
              'sharedCoreTriSha256': TRI_SHA, 'baseArchiveWritten': False, 'installed': False, 'gameStarted': False,
              'runtimeQualified': False, 'renderedAppearanceQualified': False, 'contactQualified': False,
              'retainedMotionResult': {'run': '20261113-064151-968880', 'result': 'failed'},
              'limits': ['Core already contains neutral geometry. No adult-state morph/controller or independent appearance is added.',
                         'The installer asks for the matching core motion choice; it cannot detect a prior independent FOMOD selection.',
                         'Exact serialized file/selection checks only. No anatomy motion, attachment, contact, SE/VR lifecycle or release acceptance.']}
    (output/'package-report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('core-archive', 'neutral', 'combined', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build(**vars(args))
        print(json.dumps({'status': result['status'], 'archive': result['archive'], 'plans': result['planCount']}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
