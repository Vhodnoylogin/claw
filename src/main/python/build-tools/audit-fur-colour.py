"""Read-only frozen-body colour audit; emits metadata, never textures or runtime claims."""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PureWindowsPath
import struct
import sys

ROOT = Path(__file__).resolve().parents[4]
FUR = frozenset(('ChestBlend', 'FurfaceBlend', 'ScalpFurBlend', 'fur_arms',
                 'fur_back', 'fur_belly', 'fur_chest', 'fur_face',
                 'fur_shoulders', 'fur_tailtip'))
SKIN = frozenset(('body', 'head'))
EXCLUDED = frozenset(('claws', 'eyes', 'mouth', 'genitals'))
TINT_FEATURES = frozenset((5, 6))
SOURCE_FILES = {
    'skee': ('skee64/IPluginInterface.h', 'skee64/OverrideVariant.h',
             'skee64/ShaderUtilities.cpp', 'skee64/OverrideInterface.cpp',
             'skee64/SKEEHooks.cpp', 'skee64/PresetInterface.cpp'),
    'commonlib': ('include/RE/T/TESNPC.h', 'src/RE/T/TESNPC.cpp',
                  'include/RE/B/BGSColorForm.h', 'include/RE/B/BSShaderMaterial.h',
                  'include/RE/B/BSLightingShaderMaterialBase.h',
                  'include/RE/B/BSLightingShaderMaterialHairTint.h',
                  'include/RE/B/BSLightingShaderProperty.h'),
}


def pin(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}


def texture_key(value):
    """Case-insensitive Data-relative identity; reject absolute/traversal paths."""
    path = PureWindowsPath(value)
    if path.is_absolute() or path.drive or path.root or '..' in path.parts:
        raise ValueError('Texture path escapes Data: '+value)
    if not path.parts or path.parts[0].lower() != 'textures':
        raise ValueError('Expected textures-relative NIF reference: '+value)
    return '/'.join(path.parts).casefold()


def role(name):
    return 'fur' if name in FUR else 'skin' if name in SKIN else 'excluded' if name in EXCLUDED else 'unknown'


def material_summary(shapes):
    """Serialized sharing is scoped to ONE NIF, never inferred across actor instances."""
    names = [shape['name'] for shape in shapes]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate geometry name cannot be safely selected')
    groups = {}
    for field in ('shaderBlockId', 'textureSetBlockId'):
        by_id = defaultdict(list)
        for shape in shapes:
            by_id[shape[field]].append(shape['name'])
        groups[field] = [{'blockId': key, 'shapes': values} for key, values in sorted(by_id.items()) if len(values) > 1]
    targets = [shape for shape in shapes if role(shape['name']) in ('fur', 'skin')]
    return {'targets': [shape['name'] for shape in targets],
            'missingExpectedTargets': sorted((FUR | SKIN) - set(names)),
            'unknownShapes': sorted(name for name in names if role(name) == 'unknown'),
            'targetCount': len(targets),
            'alreadyTintCapableCount': sum(shape['shaderType'] in TINT_FEATURES for shape in targets),
            'targetsNeedingShaderConversion': [shape['name'] for shape in targets if shape['shaderType'] not in TINT_FEATURES],
            'serializedSharedBlocks': groups,
            'runtimeMaterialIsolation': 'Unknown: serialized block independence does not prove per-actor shader/material ownership.'}


def dds_header(data):
    """Read format metadata only; do not decode, export or retain texture pixels."""
    if len(data) < 128 or data[:4] != b'DDS ' or struct.unpack_from('<I', data, 4)[0] != 124:
        raise ValueError('Invalid/truncated DDS header')
    if struct.unpack_from('<I', data, 76)[0] != 32:
        raise ValueError('Invalid DDS pixel-format header')
    height, width = struct.unpack_from('<II', data, 12)
    if not width or not height:
        raise ValueError('Invalid DDS dimensions')
    fourcc = data[84:88].decode('ascii', errors='replace').rstrip('\0')
    result = {'width': width, 'height': height, 'mipMaps': struct.unpack_from('<I', data, 28)[0],
              'fourCC': fourcc, 'pixelFormatFlags': struct.unpack_from('<I', data, 80)[0],
              'rgbBits': struct.unpack_from('<I', data, 88)[0]}
    if fourcc == 'DX10':
        if len(data) < 148:
            raise ValueError('Truncated DX10 DDS header')
        result['dxgiFormat'], result['resourceDimension'], result['miscFlag'], result['arraySize'], result['miscFlags2'] = struct.unpack_from('<5I', data, 128)
    return result


def inspect_texture(key, roots):
    matches = []
    for root in roots:
        path = root.joinpath(*key.split('/')).resolve()
        if not path.is_relative_to(root):
            raise ValueError('Texture resolution escapes root')
        if path.is_file():
            with path.open('rb') as handle:
                header = dds_header(handle.read(148))
            matches.append({**pin(path), 'dds': header})
    return {'reference': key, 'looseFileMatches': matches,
            'resolution': 'Caller-supplied roots only; no MO2 winner or BSA resolution is inferred.',
            'pixelColourAnalysis': 'Not performed; baked albedo/colour response needs a rendered test.'}


def checked_output(output, protected):
    output = Path(output).resolve()
    if output.suffix.lower() != '.json':
        raise ValueError('Output must be a new external .json file')
    if output.exists():
        raise ValueError('Refusing to overwrite output')
    if any((directory/'.git').exists() for directory in output.parents):
        raise ValueError('Generated audit must remain outside Git checkouts')
    if any(directory.name.casefold() in ('data', 'mods', 'profiles', 'overwrite') for directory in output.parents):
        raise ValueError('Generated audit must remain outside live installation/profile trees')
    for directory in (ROOT, *protected):
        if output.is_relative_to(Path(directory).resolve()):
            raise ValueError('Output must be outside repository and input directories')
    return output


def inspect_nif(path, api):
    from pyn.nifconstants import BSLSPShaderType, ShaderFlags1, ShaderFlags2
    nif = api.NifFile(str(path))
    shapes = []
    for shape in nif.shapes:
        if shape.shader_block_name != 'BSLightingShaderProperty':
            raise ValueError('Unsupported shader block: '+shape.name)
        shader = shape.shader
        props = shader.properties
        # Unlike .textures (flag-filtered), read every actual Skyrim texture slot.
        slots = [shader._readtexture(nif._handle, shape._handle, index+1) for index in range(9)]
        alpha = shape.alpha_property
        alpha_props = alpha.properties if alpha is not None else None
        shapes.append({'name': shape.name, 'role': role(shape.name), 'geometryBlock': shape.blockname,
                       'vertices': len(shape.verts), 'vertexColours': len(shape.colors),
                       'shaderBlock': shape.shader_block_name, 'shaderBlockId': shader.id,
                       'textureSetBlockId': int(props.textureSetID), 'shaderType': int(props.Shader_Type),
                       'shaderTypeName': BSLSPShaderType(props.Shader_Type).name,
                       'flags1': {'value': int(props.Shader_Flags_1), 'names': ShaderFlags1(props.Shader_Flags_1).fullname},
                       'flags2': {'value': int(props.Shader_Flags_2), 'names': ShaderFlags2(props.Shader_Flags_2).fullname},
                       'materialAlpha': float(props.Alpha), 'hairTintBuffer': list(props.hairTintColor),
                       'skinTintBuffer': list(props.skinTintColor),
                       'tintBufferNote': 'Buffer defaults do not establish that this shader type uses a tint.',
                       'alphaProperty': None if alpha_props is None else {
                           'flags': int(alpha_props.flags), 'threshold': int(alpha_props.threshold),
                           'blendEnabled': bool(alpha_props.flags & 1),
                           'testEnabled': bool(alpha_props.flags & 512)},
                       'textureSlots': [{'index': index, 'path': value, 'identity': texture_key(value) if value else None}
                                        for index, value in enumerate(slots)]})
    return {'input': pin(path), 'shapes': shapes, 'summary': material_summary(shapes)}


def verify_bodies(release):
    manifest = release/'claw-build.json'
    data = json.loads(manifest.read_text(encoding='utf-8-sig'))
    package = next(item for item in data['packages'] if item['component'] == 'base')
    records = {item['path']: item for item in package['files'] if item['path'].lower().endswith('.nif')}
    expected = {'Meshes/Actors/WerewolfBeast/Character Assets/'+sex+'bodywerewolf_'+str(endpoint)+'.nif'
                for sex in ('male', 'female') for endpoint in (0, 1)}
    if set(records) != expected:
        raise ValueError('Frozen manifest must contain exactly four expected body NIFs')
    paths = []
    for relative in sorted(records):
        path = (release/'base'/relative).resolve(strict=True)
        if not path.is_relative_to((release/'base').resolve()):
            raise ValueError('Manifest path escapes base')
        actual = pin(path)
        if any(actual[key] != records[relative][key] for key in ('bytes', 'sha256')):
            raise ValueError('Frozen body does not match manifest: '+relative)
        paths.append(path)
    return manifest, data['releaseId'], paths


def build(args):
    release = args.release.resolve(strict=True)
    addon = args.pynifly.resolve(strict=True)
    roots = [root.resolve(strict=True) for root in args.texture_root]
    sources = {kind: getattr(args, kind).resolve(strict=True) for kind in SOURCE_FILES if getattr(args, kind) is not None}
    output = checked_output(args.out, [release, addon, *roots, *sources.values()])
    manifest, release_id, paths = verify_bodies(release)
    manifest_pin = pin(manifest)
    import_pins = [pin(addon/'NiflyDLL.dll'), *[pin(path) for path in sorted((addon/'pyn').glob('*.py'))]]
    sys.path.insert(0, str(addon))
    from pyn import pynifly as api
    api.NifFile.Load(str(addon/'NiflyDLL.dll'))
    models = [inspect_nif(path, api) for path in paths]
    texture_users = defaultdict(list)
    for model in models:
        for shape in model['shapes']:
            for slot in shape['textureSlots']:
                if slot['identity']:
                    texture_users[slot['identity']].append({'model': Path(model['input']['path']).name,
                                                          'shape': shape['name'], 'role': shape['role'], 'slot': slot['index']})
    evidence = {kind: [pin(root/relative) for relative in SOURCE_FILES[kind]] for kind, root in sources.items()}
    report = {'schemaVersion': 1, 'kind': 'offline-fur-colour-feasibility-audit',
              'releaseId': release_id, 'manifest': manifest_pin, 'script': pin(__file__),
              'parser': import_pins, 'localSourceEvidence': evidence, 'models': models,
              'textureReferences': [{**inspect_texture(key, roots), 'users': users}
                                    for key, users in sorted(texture_users.items())],
              'findings': {
                  'runtimeQualified': False, 'hairColourReadAtRuntime': False,
                  'texturePixelsExported': False,
                  'perActorSafety': 'Never mutate global DDS files, cached NIFs, TESNPC hair-colour forms or shared material pointers. Prove independent property/material ownership for treated/control actor roots first.',
                  'sourceEvidenceLimit': 'Pinned local source is inspected evidence, not proof that the installed official RaceMenu binary implements identical behaviour.',
                  'hairSource': 'Capture human TESNPC/GetRootFaceNPC headRelatedData->hairColor->color before transformation; also sample rendered human HairTint material to detect effective colour overrides. Missing/unsupported/disagreeing sources require an explicit policy, not a fabricated colour.',
                  'selectedExperiment': 'Opt-in transient SKEE IOverrideInterface v2 SetNodeProperty(actor,false,node,7,0,IntRGB,true) on explicit fur AND body/head names after material-isolation inspection. Local source converts Default to FaceGenRGBTint; do not call it HairTint or automatic hair linkage. No persistent AddNodeOverride in the first trial.',
                  'restore': 'Tint removal alone cannot restore the original shader conversion. First trial must not save; restore original per-actor properties or reload baseline 3D and verify features/flags/textures/alpha.',
                  'runtimeGates': ['installed-provider interface and shader behaviour', 'treated/control actor property/material pointer isolation',
                                   'visible tint on opaque skin and all alpha fur/blend layers of both sexes',
                                   'unchanged alpha sorting, normals, lighting, joins, eyes/claws/mouth',
                                   'capture actual human hair colour, then transform/return/reload/save-load without cross-actor leakage'],
                  'appearanceLimit': 'NIF metadata, RGB values and shader readback cannot establish useful visible fur variation or hair-to-fur colour fidelity. Coloured albedo may constrain brightness/hue; render comparison is required.'}}
    # Detect inputs changing during a read; output only after successful validation.
    for model in models:
        if pin(model['input']['path']) != model['input']:
            raise ValueError('Input changed during audit')
    verify_bodies(release)
    if pin(manifest) != manifest_pin:
        raise ValueError('Manifest changed during audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
        handle.write('\n')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release', type=Path, default=ROOT / 'target/references/releases/se-core-20261030')
    parser.add_argument('--pynifly', type=Path, required=True, help='Installed add-on containing pyn/ and NiflyDLL.dll')
    parser.add_argument('--texture-root', type=Path, action='append', default=[], help='Read-only loose Data/mod root; repeatable, no winner order inferred')
    parser.add_argument('--skee', type=Path, help='Read-only SKEE source checkout root for evidence hashes')
    parser.add_argument('--commonlib', type=Path, help='Read-only CommonLib source checkout root for evidence hashes')
    parser.add_argument('--out', type=Path, required=True, help='New external JSON path; never overwritten')
    args = parser.parse_args()
    try:
        print(build(args))
    except (ValueError, RuntimeError, OSError, KeyError, StopIteration) as exc:
        parser.exit(1, 'Fur colour audit rejected: '+str(exc)+'\n')


if __name__ == '__main__':
    main()
