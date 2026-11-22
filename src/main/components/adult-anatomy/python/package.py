"""Build a private base and optional neutral-anatomy overlay from pinned inputs."""
from __future__ import annotations

import argparse
import hashlib
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
NAME = 'test_CLAW - Neutral Anatomy Candidate'
ARCHIVE = NAME + '.zip'
BASE_NAME = 'test_CLAW - Core with Optional Anatomy'
BASE_ARCHIVE = BASE_NAME + '.zip'
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
XML_ROOT = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/'
GUIDE = 'CLAW-Neutral-Anatomy-README.md'
NOTICE = 'NOTICES/CLAW-Neutral-Anatomy.txt'
DESTINATIONS = tuple(MESH + 'male' + route + '_' + str(weight) + '.nif'
                     for route in ('bodywerewolf', 'PlayerWerewolf') for weight in (0, 1))
CORE_MESHES = {
    'none': ('00 Base/' + MESH + 'malebodywerewolf_0.nif', STATIC_SHA),
    'fsmp': ('40 Motion/FSMP/' + MESH + 'malebodywerewolf_0.nif', CORE_FSMP_SHA),
}
VARIANTS = {
    ('none', 'off'): ('10 Static', None),
    ('fsmp', 'off'): ('20 Core FSMP', None),
    ('none', 'on'): ('30 Anatomy FSMP', 'CLAWNeutralAnatomy.xml'),
    ('fsmp', 'on'): ('40 Combined FSMP', 'CLAWMotionNeutralAnatomyMale.xml'),
}
PINS = {
    'none': {'nif': 'b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
                'xml': '9bf501b9f5e5ecd0b33fe725af74779a28c4213ee4ae1e2ce9edfcc0269b0529'},
    'fsmp': {'nif': 'f93d5038cb17493517cf8f80dba63601edbf1f98678d781c3ae31589da7ff89d',
                 'xml': '7cb169385c37b28038643c406c07d6b91937672b872c908420e2172822647d8e'},
}
RUNTIME_GUIDE = b'''# CLAW neutral anatomy - private developer candidate

Use the companion private CLAW core archive, with Elegant Werewolf Replacer
and compatible XP32 installed separately. Install this overlay after that core
and let its male meshes win. Removing the overlay restores the core appearance.

The default, Keep current male meshes, installs only these notes and credits.
It leaves the current appearance and motion unchanged. To add neutral anatomy,
explicitly select the motion setting used by your core. Anatomy motion then
defaults to Off, preserving that selected core ear/tail motion. For optional
anatomy motion, install the runtime-matched Faster HDT-SMP separately:
https://www.nexusmods.com/skyrimspecialedition/mods/57339
The overlay cannot detect the core motion choice. Reinstall it when changing
that setting to keep the selected motion in sync.
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


def choice(steps, name, flag, options):
    step = ET.SubElement(steps, 'installStep', name=name)
    groups = ET.SubElement(step, 'optionalFileGroups', order='Explicit')
    group = ET.SubElement(groups, 'group', name=name, type='SelectExactlyOne')
    plugins = ET.SubElement(group, 'plugins', order='Explicit')
    for index, (value, label, description) in enumerate(options):
        plugin = ET.SubElement(plugins, 'plugin', name=label)
        ET.SubElement(plugin, 'description').text = description
        flags = ET.SubElement(plugin, 'conditionFlags')
        ET.SubElement(flags, 'flag', name=flag).text = value
        descriptor = ET.SubElement(plugin, 'typeDescriptor')
        ET.SubElement(descriptor, 'type', name='Recommended' if index == 0 else 'Optional')
    return step


def installer():
    config = ET.Element('config', {'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'xsi:noNamespaceSchemaLocation': 'http://qconsulting.ca/fo3/ModConfig5.0.xsd'})
    ET.SubElement(config, 'moduleName').text = NAME
    ET.SubElement(ET.SubElement(config, 'moduleDependencies', operator='And'), 'fileDependency', file='CLAW.esp', state='Active')
    required = ET.SubElement(config, 'requiredInstallFiles')
    for path in (GUIDE, NOTICE):
        ET.SubElement(required, 'file', source=path, destination=path)
    steps = ET.SubElement(config, 'installSteps', order='Explicit')
    choice(steps, 'Core CLAW motion', 'coreMotion', (
        ('keep', 'Keep current male meshes', 'Default: install notes only and leave current appearance and motion unchanged. To add anatomy, select your core motion setting below.'),
        ('none', 'Add anatomy: core motion None', 'Choose this only if your CLAW core has motion disabled. Anatomy motion is a separate choice on the next page.'),
        ('fsmp', 'Add anatomy: core motion Faster HDT-SMP', 'Choose this only if your CLAW core uses Faster HDT-SMP for ear and tail motion. Anatomy motion is a separate choice on the next page.'),
    ))
    motion_step = choice(steps, 'Anatomy motion', 'anatomyMotion', (
        ('off', 'Off', 'Add the neutral anatomy and preserve your core motion setting.'),
        ('on', 'Faster HDT-SMP', 'Add neutral anatomy motion. Requires the separate Faster HDT-SMP provider.'),
    ))
    visible = ET.Element('visible', operator='Or')
    for mode in CORE_MESHES:
        ET.SubElement(visible, 'flagDependency', flag='coreMotion', value=mode)
    motion_step.insert(0, visible)
    patterns = ET.SubElement(ET.SubElement(config, 'conditionalFileInstalls'), 'patterns')
    for (core_motion, anatomy_motion), (folder, xml) in VARIANTS.items():
        pattern = ET.SubElement(patterns, 'pattern')
        dependencies = ET.SubElement(pattern, 'dependencies', operator='And')
        ET.SubElement(dependencies, 'flagDependency', flag='coreMotion', value=core_motion)
        ET.SubElement(dependencies, 'flagDependency', flag='anatomyMotion', value=anatomy_motion)
        files = ET.SubElement(pattern, 'files')
        for destination in DESTINATIONS:
            ET.SubElement(files, 'file', source=folder+'/male.nif', destination=destination)
        if xml:
            ET.SubElement(files, 'file', source=folder+'/'+xml, destination=XML_ROOT+xml)
    ET.indent(config)
    return ET.tostring(config, encoding='utf-8')


def _config(entries, reader, active):
    config = ET.fromstring(entries['fomod/ModuleConfig.xml'])
    expected = ET.fromstring(installer())
    require(ET.tostring(config) == ET.tostring(expected), 'Installer changed its exact exclusive default/mapping contract')
    require(reader.dependency(config.find('moduleDependencies'), '1.7.104.0', set(active), {}), 'CLAW.esp must be active')
    return config


def _selected_files(entries, config, reader, active, flags):
    files = list(config.findall('requiredInstallFiles/file'))
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


def selection(entries, motion, reader, *, core_motion, active=('CLAW.esp',)):
    """Evaluate an explicit existing variant or the safe keep selection.

    Keep has no anatomy-motion choice: that page is hidden. Stale flags are
    refused by this API, and XML patterns also cannot match keep with any flag.
    """
    require((core_motion, motion) in VARIANTS or (core_motion == 'keep' and motion is None),
            'Explicit known component/core selection required')
    config = _config(entries, reader, active)
    flags = {'coreMotion': core_motion}
    if motion is not None:
        flags['anatomyMotion'] = motion
    return _selected_files(entries, config, reader, active, flags)


def default_selection(entries, reader, *, active=('CLAW.esp',)):
    """Replay literal Recommended options in visible steps; inject no core mode."""
    config = _config(entries, reader, active)
    flags, visible_steps = {}, []
    for step in config.findall('installSteps/installStep'):
        visible = step.find('visible')
        if visible is not None and not reader.dependency(visible, '1.7.104.0', set(active), flags):
            continue
        visible_steps.append(step.get('name'))
        step_flags = {}
        for group in step.findall('optionalFileGroups/group'):
            recommended = [p for p in group.findall('plugins/plugin')
                           if reader.plugin_type(p, '1.7.104.0', set(active), flags) == 'Recommended']
            require(group.get('type') == 'SelectExactlyOne' and len(recommended) == 1,
                    'Exactly one literal default required per visible group')
            for flag in recommended[0].findall('conditionFlags/flag'):
                require(flag.get('name') not in flags and flag.get('name') not in step_flags, 'Duplicate default flag')
                step_flags[flag.get('name')] = flag.text
        flags.update(step_flags)
    require(flags == {'coreMotion': 'keep'}, 'Literal defaults must keep current male resources')
    installed = _selected_files(entries, config, reader, active, flags)
    require(set(installed) == {GUIDE, NOTICE}, 'Literal defaults must install notes only')
    return {'flags': flags, 'visibleSteps': visible_steps, 'files': installed}


def check_motion(payload, xml, core_motion, package, materials, composition, drivers):
    fields = package._nif_fields(materials, payload)
    extras, records = fields[-2:]
    hook = b'HDT Skinned Mesh Physics Object'
    path = (XML_ROOT + VARIANTS[core_motion, 'on'][1]).encode('ascii')
    require(extras.get(hook) == path and [value for key, value in records if key == hook] == [path],
            'Exactly one known root FSMP binding required')
    tris = {value.decode('ascii').replace('\\', '/').casefold() for key, value in records if key == b'BODYTRI'}
    require(tris == {'actors/werewolfbeast/character assets/malebodywerewolf.tri'}, 'Inherited male BODYTRI path differs')
    require(materials.adapt_nif(payload)[0] == payload, 'Expected existing PlayerOnly material paths')
    anatomy = ('WWD 2', 'WWLB 1', 'WWRB 1')
    composition.inspect_xml(xml, (*drivers, *anatomy) if core_motion == 'fsmp' else anatomy,
                            ('NPC Head [Head]', 'Tails', 'WWD 1') if core_motion == 'fsmp' else ('WWD 1',))


def build_core(core, visuals):
    """Keep the original installer/aliases and hide only the two male sources."""
    base = dict(core)
    visibility = {}
    for name, digest in CORE_MESHES.values():
        require(sha(core[name]) == digest, 'Unexpected core male model')
        hidden, ledger = visuals.hide_anatomy(core[name])
        require(hidden != core[name] and visuals.restore_anatomy(hidden, ledger) == core[name],
                'Core visibility change is not independently reversible')
        base[name] = hidden
        visibility[name] = ledger
    for filename, element in (('ModuleConfig.xml', 'moduleName'), ('info.xml', 'Name')):
        path = 'fomod/' + filename
        # Preserve original namespace and whitespace; only replace the text in the name element.
        previous = ET.fromstring(core[path]).findtext(element)
        needle = f'>{previous}</{element}>'.encode()
        require(bool(previous) and core[path].count(needle) == 1, 'Unexpected core installer identity')
        base[path] = core[path].replace(needle, f'>{BASE_NAME}</{element}>'.encode())
        require(ET.fromstring(base[path]).findtext(element) == BASE_NAME, 'Core installer name did not change')
    return base, visibility


def audit(entries, base, core, package, reader):
    expected = {GUIDE, NOTICE, 'fomod/ModuleConfig.xml', 'fomod/info.xml'}
    for folder, xml in VARIANTS.values():
        expected.add(folder + '/male.nif')
        if xml:
            expected.add(folder + '/' + xml)
    require(set(entries) == expected, 'Unexpected or missing component archive member')
    require(entries[GUIDE] == RUNTIME_GUIDE and entries[NOTICE] == ASSET_NOTICE, 'Required candidate guide or asset notice changed')
    for (core_motion, motion), (folder, xml) in VARIANTS.items():
        digest = PINS[core_motion]['nif'] if xml else CORE_MESHES[core_motion][1]
        require(sha(entries[folder + '/male.nif']) == digest
                and (not xml or sha(entries[folder + '/' + xml]) == PINS[core_motion]['xml']),
                'Changed component payload')
    allowed = {name for name, _ in CORE_MESHES.values()} | {'fomod/ModuleConfig.xml', 'fomod/info.xml'}
    require(set(base) == set(core) and {name for name in base if base[name] != core[name]} == allowed,
            'Unexpected change to the companion core archive')
    literal_default = default_selection(entries, reader)
    plans = []
    for plan in package.selection_audit(base):
        core_motion = plan['physics']
        core_source = CORE_MESHES[core_motion][0]
        installed = {row['path']: row['source'] for row in plan['files']}
        require(all(installed[name] == core_source for name in DESTINATIONS), 'All core male routes must use the hidden source')
        baseline = {path: base[source] for path, source in installed.items()}
        require(sha(baseline[MESH + 'malebodywerewolf.tri']) == TRI_SHA, 'Incompatible core male TRI selection')
        shared = {'maleFamily': plan['maleFamily'], 'femaleFamily': plan['family'], 'obody': plan['obody'], 'coreMotion': core_motion}
        plans.append({**shared, 'anatomy': 'absent', 'selectedFiles': {name: sha(baseline[name]) for name in DESTINATIONS}})
        default_files = literal_default['files']
        result = {**baseline, **{name: entries[source] for name, source in default_files.items()}}
        require(all(result[name] == data for name, data in baseline.items()), 'Literal defaults replaced core resources')
        plans.append({**shared, 'anatomy': 'default', 'coreProtectedDestinations': len(baseline),
                      'maleModelOverrides': 0, 'physicsXmlOverrides': 0, 'literalFlags': literal_default['flags'],
                      'selectedFiles': {name: sha(entries[source]) for name, source in default_files.items()}})
        for motion in ('off', 'on'):
            selected = selection(entries, motion, reader, core_motion=core_motion)
            result = {**baseline, **{destination: entries[source] for destination, source in selected.items()}}
            changed = {name for name, data in baseline.items() if result[name] != data}
            require(changed == set(DESTINATIONS), 'Component changed protected core destinations')
            _, xml = VARIANTS[core_motion, motion]
            extra = {XML_ROOT + xml} if xml else set()
            require(set(selected) == {*DESTINATIONS, GUIDE, NOTICE} | extra, 'Nonminimal component selection')
            require(motion == 'on' or all(result[name] == core[core_source] for name in DESTINATIONS),
                    'Anatomy motion off must restore exact appearance and retain core motion')
            plans.append({**shared, 'anatomy': motion, 'coreProtectedDestinations': len(baseline)-len(changed),
                          'maleModelOverrides': len(changed), 'selectedFiles': {name: sha(entries[source]) for name, source in selected.items()}})
    require(len(plans) == 160, 'All core-only, literal-default and compatible overlay selections must be verified')
    return plans


def build(*, core_archive, neutral, combined, out):
    paths = [Path(__file__), HERE/'compose_motion.py', TOOLS/'package-source-build.py',
             TOOLS/'build-unified-release.py', TOOLS/'player_only_materials.py',
             REPO/'src/main/python/physics/recipe.json', HERE.parent/'README.md',
             REPO/'src/main/resources/donors/README.md', REPO/'src/main/python/build-tools/build-genitals.py',
             HERE/'visual_variants.py', REPO/'src/main/python/vr/body_resource.py']
    sources = {path.resolve(): path.read_bytes() for path in paths}
    package = load(paths[2], sources[paths[2]])
    inputs = package.Inputs()
    for path, payload in sources.items():
        require(inputs.read(path) == payload, 'Source changed before packaging')
    reader, materials, composition = [load(path, sources[path]) for path in paths[3:5]+paths[1:2]]
    visuals = load(HERE/'visual_variants.py', sources[HERE/'visual_variants.py'])
    core_bytes = inputs.read(core_archive)
    require(sha(core_bytes) == CORE_SHA, 'Explicit reviewed CLAW core archive differs')
    core = package.read_zip(core_bytes)
    drivers = tuple(node for group in json.loads(sources[paths[5]])['groups'] for node in group['nodes'])
    base, visibility = build_core(core, visuals)
    package._check_motion_nif(materials, base[CORE_MESHES['none'][0]], base[CORE_MESHES['fsmp'][0]], 'male')
    entries = {GUIDE: RUNTIME_GUIDE, NOTICE: ASSET_NOTICE, 'fomod/ModuleConfig.xml': installer(),
               'fomod/info.xml': b'<fomod><Name>'+NAME.encode()+b'</Name><Author>CLAW</Author><Version>0.3.0</Version></fomod>'}
    roots = {'none': Path(neutral).resolve(), 'fsmp': Path(combined).resolve()}
    inventories = {}
    for core_motion, root in roots.items():
        static_folder, _ = VARIANTS[core_motion, 'off']
        entries[static_folder + '/male.nif'] = core[CORE_MESHES[core_motion][0]]
        folder, xml = VARIANTS[core_motion, 'on']
        expected = {MESH+'malebodywerewolf_'+str(weight)+'.nif' for weight in (0, 1)} | {MESH+'malebodywerewolf.tri', XML_ROOT+xml}
        inventories[root] = expected
        require({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == expected,
                'Candidate must contain exactly its reviewed four files')
        payloads = {relative: inputs.read(root/relative) for relative in sorted(expected)}
        require(sha(payloads[MESH+'malebodywerewolf.tri']) == TRI_SHA, 'Candidate TRI no longer matches required core')
        nifs = [payloads[MESH+'malebodywerewolf_'+str(weight)+'.nif'] for weight in (0, 1)]
        require(all(sha(data) == PINS[core_motion]['nif'] for data in nifs) and nifs[0] == nifs[1]
                and sha(payloads[XML_ROOT+xml]) == PINS[core_motion]['xml'], 'Frozen component input pin differs')
        check_motion(nifs[0], payloads[XML_ROOT+xml], core_motion, package, materials, composition, drivers)
        entries[folder+'/male.nif'], entries[folder+'/'+xml] = nifs[0], payloads[XML_ROOT+xml]
    base_archive_bytes = package.zip_bytes(base)
    archive_bytes = package.zip_bytes(entries)
    reopened_base, reopened = (package.read_zip(x) for x in (base_archive_bytes, archive_bytes))
    require(reopened_base == base and reopened == entries, 'Serialized candidate archives differ')
    plans = audit(reopened, reopened_base, core, package, reader)
    output = Path(out).resolve()
    require(not output.exists() and not any(part.casefold() in ('mods', 'data', 'overwrite', 'downloads') for part in output.parts)
            and not any((parent/'.git').exists() for parent in (output, *output.parents)), 'Use a new external build directory')
    require(output.parent.is_dir() and not any(path.parent == output or path.parent in output.parents for path in inputs.records),
            'Output parent must exist outside all input directories')
    inputs.verify()
    require(all({p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} == names
                for root, names in inventories.items()), 'Candidate inventory changed during packaging')
    output.mkdir()
    records = {}
    for key, filename, data, expected in (('archive', ARCHIVE, archive_bytes, entries),
                                         ('baseArchive', BASE_ARCHIVE, base_archive_bytes, base)):
        archive = output / filename
        archive.write_bytes(data)
        require(package.read_zip(archive.read_bytes()) == expected, 'Written ZIP readback differs: ' + filename)
        records[key] = {'path': str(archive), 'sha256': sha(data), 'bytes': len(data), 'members': len(expected)}
    inputs.verify()
    report = {'status': 'built-private-offline-anatomy-candidate-runtime-unqualified',
              **records,
              'inputs': {str(path): {'sha256': sha(data), 'bytes': len(data)} for path, data in inputs.records.items()},
              'members': {name: {'sha256': sha(data), 'bytes': len(data)} for name, data in entries.items()},
              'plans': plans, 'planCount': len(plans), 'baseVisibilityEdits': visibility,
              'default': 'keep-current-male-resources-and-core-motion',
              'literalDefault': default_selection(reopened, reader),
              'explicitVariantPayloads': {name: sha(data) for name, data in reopened.items() if name.endswith(('.nif', '.xml')) and not name.startswith('fomod/')},
              'sharedCoreTriSha256': TRI_SHA, 'installed': False, 'gameStarted': False,
              'runtimeQualified': False, 'renderedAppearanceQualified': False, 'contactQualified': False,
              'retainedMotionResult': {'run': '20261113-064151-968880', 'result': 'failed'},
              'limits': ['The neutral shape is embedded and hidden in the companion core. The overlay restores its visibility.',
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
        print(json.dumps({'status': result['status'], 'archive': result['archive'], 'baseArchive': result['baseArchive'], 'plans': result['planCount']}))
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2)
