"""Build detached static and FSMP controls with visible ear skin on the VR world carrier."""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import xml.etree.ElementTree as ET

import numpy as np

from stage_world_motion_markers import MOTION_ZIPS, motion
from body_resource import HIDDEN, bodytri, dependencies, flags_offset, safe_output, tri_contract, visible_by_hidden_flags
from vr_dispatch import LEGACY_ALIAS, ROOT, SEXES, resource_paths


split = motion.fsmp_motion.head_split
rig = split.rig
SOURCE_SHAPE = 'head_CLAWHead'
EAR_SUFFIX = '_CLAWEars'
EAR_SHAPE = SOURCE_SHAPE + EAR_SUFFIX
EAR_DRIVERS = motion.fsmp_motion.common.source.NODES[:4]
EAR_MORPHS = {'CLAWHeadEarSize', 'CLAWHeadEarTilt'}


def ear_faces(faces, bone_weights, ear_columns):
    """Give a face to an ear when any vertex has an ear-bone share of at least half."""
    totals = bone_weights.sum(axis=1)
    if not np.isfinite(bone_weights).all() or (bone_weights < 0).any() or (totals <= 0).any():
        raise ValueError('Expected positive finite source skin weight sums')
    dominant = bone_weights[:, ear_columns] >= 0.5 * totals[:, None]
    left, right = (dominant[faces, start:start + 2].any(axis=(1, 2)) for start in (0, 2))
    if (left & right).any() or not left.any() or not right.any() or (left | right).all():
        raise ValueError('Expected two distinct ears attached to a nonempty hidden remainder')
    return left, right


def ear_bounds(shape, shape_streams, patch):
    vertices = np.asarray(shape.verts, dtype=float)
    low, high = vertices.copy(), vertices.copy()
    for pairs in shape_streams.values():
        indices = [index for index, _ in pairs]
        values = np.asarray([delta for _, delta in pairs], dtype=float)
        low[indices] += np.minimum(values, 0)
        high[indices] += np.maximum(values, 0)
    center, radius = patch.read_bounds(shape.id)
    reach = float(np.linalg.norm(np.maximum(abs(low - center), abs(high - center)), axis=1).max())
    if not np.isfinite(reach) or not np.isfinite(radius) or reach > radius:
        raise ValueError('The inherited ear shape sphere does not cover the [0,1] TRI box')
    return {'radius': radius, 'triBoxReach': reach, 'independentTriRange': [0, 1]}


def split_carrier(api, Trip, source, source_tri, work):
    original = api.NifFile(str(source))
    shapes = {shape.name: shape for shape in original.shapes}
    head = shapes[SOURCE_SHAPE]
    if len(shapes) != len(original.shapes) or EAR_SHAPE in shapes or not head.flags & HIDDEN:
        raise ValueError('Expected the original hidden head skin and unique source shapes')
    names = list(head.bone_weights)
    columns = [names.index(name) for name in EAR_DRIVERS]
    faces = np.asarray(head.tris, dtype=int)
    left, right = ear_faces(faces, rig.read_weights(head, names), columns)
    mapped = split.mapping(faces, left | right, len(head.verts))
    plan = {name: {'action': 'torso', 'mapping': None} for name in shapes}
    plan[SOURCE_SHAPE] = {'action': 'split', 'mapping': mapped, 'sourceBlock': head.id}

    payload, surgery = split.split_nif(source.read_bytes(), plan, None, suffix=EAR_SUFFIX)
    parsed = split.Nif(payload)
    ear_id = surgery['appendedBlocks'][-1]
    ear_data = bytearray(parsed.blocks[ear_id])
    if parsed.strings[struct.unpack_from('<I', ear_data)[0]].decode() != EAR_SHAPE:
        raise ValueError('The appended shape differs from the planned ear skin')
    offset = flags_offset(ear_data, 0, len(ear_data), parsed.kind(ear_id), head.flags)
    struct.pack_into('<I', ear_data, offset, head.flags & ~HIDDEN)
    parsed.blocks[ear_id] = ear_data
    target = work / 'split.nif'
    target.write_bytes(parsed.bytes())
    target_tri = work / 'split.tri'
    target_tri.write_bytes(split.split_trip(source_tri.read_bytes(), plan, suffix=EAR_SUFFIX))

    verified = split.verify(api, Trip, source, target, source_tri, target_tri, plan, suffix=EAR_SUFFIX)
    native = api.NifFile(str(target))
    visible_before = {shape.name for shape in original.shapes if visible_by_hidden_flags(shape)}
    visible_after = {shape.name for shape in native.shapes if visible_by_hidden_flags(shape)}
    if visible_after != visible_before | {EAR_SHAPE}:
        raise ValueError('An unintended shape visibility change was detected by the native reader')
    coverage = motion.fsmp_motion.common.inspect_body(native, EAR_DRIVERS, 'Visible VR ear skin')
    if any(not counts.get(EAR_SHAPE) for counts in coverage.values()):
        raise ValueError('A driver has no influence on the visible ear skin')
    streams = Trip.from_filepath(str(target_tri)).shapes[EAR_SHAPE]
    if not EAR_MORPHS <= streams.keys():
        raise ValueError('Ear-specific TRI morphs disappeared')
    return target.read_bytes(), target_tri.read_bytes(), {
        'leftTriangles': int(left.sum()), 'rightTriangles': int(right.sum()),
        'earVertices': len(mapped['headVertices']), 'seamVertices': len(mapped['seamVertices']),
        'driverVertices': {name: coverage[name][EAR_SHAPE] for name in EAR_DRIVERS},
        'earMorphPairs': {morph: len(pairs) for morph, pairs in streams.items()},
        'publicMorphCount': verified['publicMorphCount'], 'mappedSparseTriPairs': verified['mappedSparseTriPairs'],
        'surgery': surgery,
    }


def build(fixed_profile, motion_dir, pynifly, morphbench, out):
    common = motion.fsmp_motion.common
    pack = motion.open_tools(ROOT / 'src/main/python/build-tools/package-source-build.py')
    namespacing = motion.open_tools(Path(motion.__file__).with_name('build.py'))
    fixed_profile, motion_dir = (Path(path).resolve(strict=True) for path in (fixed_profile, motion_dir))
    overlays = {sex: motion_dir / f'test_CLAW VR World Motion - {sex.title()}.zip' for sex in SEXES}
    out = Path(out).absolute()
    if any(path.is_junction() or path.is_symlink() for path in (out, *out.parents)):
        raise ValueError('Output ancestry must use real directories')
    out = safe_output(out, (fixed_profile, *overlays.values()))
    source_pins = [common.pin(path) for path in (fixed_profile, *overlays.values(), __file__,
                                                split.__file__, namespacing.__file__, motion.__file__)]
    payload = fixed_profile.read_bytes()
    if pack.sha(payload) != motion.FIXED_SHA256:
        raise ValueError('Expected the reviewed fixed-profile diagnostic archive')
    fixed = pack.read_zip(payload)
    config = ET.fromstring(fixed['fomod/ModuleConfig.xml'])
    api, patch, Trip, readers = dependencies(pynifly, morphbench)
    report = {'schema': 'claw-vr-world-visible-ears/1', 'inputs': source_pins, 'readers': readers,
              'corePhysicsSelection': 'None', 'candidates': {}, 'installed': False,
              'gameStarted': False, 'stereoClearanceVerified': False, 'liveCoatVerified': False}
    packages = {}
    with TemporaryDirectory(prefix='claw-vr-ear-readback-') as temporary:
        for sex in SEXES:
            work = Path(temporary) / sex
            work.mkdir()
            source = work / 'source.nif'
            body = fixed[motion.alias_member(config, fixed, sex)]
            source.write_bytes(body)
            tri_path = resource_paths(sex)
            source_tri = work / 'source.tri'
            source_tri.write_bytes(fixed['shared/' + tri_path])
            xml_path = pack.MOTION_XML + sex.title() + '.xml'
            exact_motion = overlays[sex].read_bytes()
            if pack.sha(exact_motion) != MOTION_ZIPS[sex]:
                raise ValueError('Expected the exact reviewed FSMP archive')
            base_fsmp, _ = motion.fsmp_motion.bind_nif(body, xml_path)
            xml = motion.fsmp_motion.render_xml(sex == 'female')
            if pack.read_zip(exact_motion) != {LEGACY_ALIAS: base_fsmp, xml_path: xml}:
                raise ValueError('Legacy FSMP archive differs from the pinned unmodified control')

            nif, tri, measured = split_carrier(api, Trip, source, source_tri, work)
            local_tri = str(Path(tri_path).with_name('EarWorldTrial.tri').as_posix())
            before, after = (path.removeprefix('Meshes/').replace('/', '\\').lower()
                             for path in (tri_path, local_tri))
            nif, path_change = namespacing.namespace_bodytri(nif, before, after)
            animated, binding = motion.fsmp_motion.bind_nif(nif, xml_path)
            for mode, variant in (('static', nif), ('fsmp', animated)):
                nif_file, tri_file = work / f'{mode}.nif', work / f'{mode}.tri'
                nif_file.write_bytes(variant)
                tri_file.write_bytes(tri)
                parsed = api.NifFile(str(nif_file))
                _, fields = tri_contract(Trip, tri_file, parsed, measured['publicMorphCount'], include_trip=True)
                if any(bodytri(shape) != [('BODYTRI', after)] for shape in parsed.shapes):
                    raise ValueError('The final trial mesh does not resolve its separate local TRI')
                hook = parsed.root.get_extra_data(blockname='NiStringExtraData', name=motion.fsmp_motion.HOOK)
                if (hook.string_data if hook is not None else None) != (xml_path if mode == 'fsmp' else None):
                    raise ValueError('The final static/FSMP control has the wrong root binding')
                ear = next(shape for shape in parsed.shapes if shape.name == EAR_SHAPE)
                measured['earBounds'] = ear_bounds(ear, fields.shapes[EAR_SHAPE], patch(nif_file))
                members = {LEGACY_ALIAS: variant, local_tri: tri}
                if mode == 'fsmp':
                    members[xml_path] = xml
                packages[sex, mode] = members
            report['candidates'][sex] = {**measured, 'bodyTri': path_change, 'fsmpBinding': binding}

    common.unchanged(source_pins)
    if any(common.pin(path)['sha256'] != digest for path, digest in readers.items()):
        raise ValueError('Readback dependencies changed')
    out.mkdir(parents=True)
    for (sex, mode), members in packages.items():
        archive = out / f'test_CLAW VR Visible Ears - {sex.title()} {mode.upper()}.zip'
        archive.write_bytes(pack.zip_bytes(members))
        if pack.read_zip(archive.read_bytes()) != members:
            raise ValueError('Detached archive readback differs from the verified resources')
        report['candidates'][sex][mode] = common.pin(archive)
    (out / 'visible-ears.json').write_bytes(pack.encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('fixed-profile', 'motion-dir', 'pynifly', 'morphbench', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    try:
        report = build(**vars(parser.parse_args()))
    except (OSError, ValueError, KeyError, RuntimeError) as error:
        parser.exit(2, f'CLAW VR visible ears: {error}\n')
    print('Detached visible-ear controls for ' + ', '.join(report['candidates']))


if __name__ == '__main__':
    main()
