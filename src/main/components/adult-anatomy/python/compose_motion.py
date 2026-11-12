"""Compose only original CLAW motion XML and the frozen neutral male candidate.

No provider, global settings, installation, solver or gameplay operation is used.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[5]
HERE = Path(__file__).resolve().parent
HOOK = 'HDT Skinned Mesh Physics Object'
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
XML = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWMotionNeutralAnatomyMale.xml'
NEUTRAL_XML = 'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWNeutralAnatomy.xml'
RECEIPT = '3bea79ebb8e529a57f3c838a1d6407f0c3402687ba28e13c90da910ced0726b3'
FROZEN = {
    MESH+'malebodywerewolf_0.nif': 'b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
    MESH+'malebodywerewolf_1.nif': 'b4270d4a781dec510ec4bc67623cb7d2bb1a7ee8284f1554b85bca4d1481c9f3',
    MESH+'malebodywerewolf.tri': '3ff00f50493664ec68bbbfbe4843bd64f268df9a5659e6a6bd4baea14ae085fc',
    'SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/CLAWNeutralAnatomy.xml': '9bf501b9f5e5ecd0b33fe725af74779a28c4213ee4ae1e2ce9edfcc0269b0529',
}
MOTION_HASHES = {False: 'b42bfa436a4e53baa48ff2249d4659718603798dabdb1e6b9427dc37efa0ea34',
                 True: '8d3a1fd08901e0ef2a9a2defe34548ba0cf4112f352778c27832a4f85a697a35'}
VECTORS = {'inertia', 'linearLowerLimit', 'linearUpperLimit', 'angularLowerLimit',
           'angularUpperLimit', 'linearStiffness', 'angularStiffness', 'linearDamping',
           'angularDamping', 'linearEquilibrium', 'angularEquilibrium'}
BONE = {'mass', 'inertia', 'linearDamping', 'angularDamping', 'gravity-factor', 'wind-factor'}
JOINT = VECTORS-{'inertia'} | {'frameInA', 'frameInB', 'useLinearReferenceFrameA'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def signature(node):
    """Authored identities, parameter tokens and nesting, excluding formatting."""
    return node.tag, tuple(sorted(node.attrib.items())), (node.text or '').strip(), tuple(signature(x) for x in node)


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError('Finite explicit numeric parameter required') from error
    if not math.isfinite(number):
        raise ValueError('Finite explicit numeric parameter required')
    return number


def _properties(node, allowed):
    seen = set()
    for item in node:
        if item.tag not in allowed or item.tag in seen:
            raise ValueError('Unknown or duplicate motion parameter: '+str(item.tag))
        if (item.tail or '').strip(): raise ValueError('Unexpected motion parameter text')
        seen.add(item.tag)
        if item.tag in ('frameInA', 'frameInB'):
            if item.attrib or (item.text or '').strip():
                raise ValueError('Only original explicit or identity frames admitted')
            if len(item):
                if [x.tag for x in item] != ['basis', 'origin']:
                    raise ValueError('Unknown frame layout')
                for part, keys in zip(item, ({'x','y','z','w'}, {'x','y','z'})):
                    if set(part.attrib) != keys or len(part) or (part.text or '').strip():
                        raise ValueError('Unknown frame parameter')
                    for value in part.attrib.values(): _finite(value)
        elif item.tag == 'useLinearReferenceFrameA':
            if item.attrib or len(item) or (item.text or '').strip() not in ('true', 'false'):
                raise ValueError('Explicit reference-frame boolean required')
        elif item.attrib:
            if item.tag not in VECTORS or set(item.attrib) != {'x','y','z'} or len(item) or (item.text or '').strip():
                raise ValueError('Unknown vector parameter')
            for value in item.attrib.values(): _finite(value)
        else:
            if len(item): raise ValueError('Unexpected nested motion parameter')
            if item.tag == 'inertia' or node.tag == 'generic-constraint':
                raise ValueError('Explicit three-axis parameter required')
            _finite(item.text)
    return seen


def inspect_xml(payload, drivers, anchors):
    """Bounded motion-only graph; reject implicit bodies, collisions and globals."""
    if len(drivers) != len(set(drivers)) or len(anchors) != len(set(anchors)) or set(drivers) & set(anchors):
        raise ValueError('Unique disjoint driver and anchor catalogs required')
    if not isinstance(payload, bytes) or len(payload) > 100000 or any(x in payload.upper() for x in (b'<!DOCTYPE', b'<!ENTITY')):
        raise ValueError('Bounded XML without DTD/entities required')
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise ValueError('Malformed motion XML') from error
    if root.tag != 'system' or root.attrib or (root.text or '').strip():
        raise ValueError('Only an original local motion system is admitted')
    bones, dynamic, static, incoming, folded = {}, set(), set(), {}, set()
    for item in root:
        if (item.tail or '').strip(): raise ValueError('Unexpected motion text')
        if item.tag == 'bone':
            name = item.get('name')
            if set(item.attrib) != {'name'} or not name or name.casefold() in folded or (item.text or '').strip():
                raise ValueError('Missing or duplicate bone identity')
            folded.add(name.casefold())
            props = _properties(item, BONE)
            if 'mass' not in props: raise ValueError('Missing explicit bone mass')
            mass = _finite(item.findtext('mass'))
            if mass < 0: raise ValueError('Negative bone mass')
            (dynamic if mass > 0 else static).add(name)
            bones[name] = item
        elif item.tag == 'generic-constraint':
            if set(item.attrib) != {'bodyA','bodyB'} or (item.text or '').strip():
                raise ValueError('Only explicit local body constraints admitted')
            a, b = item.get('bodyA'), item.get('bodyB')
            if a not in bones or b not in bones or a == b or b not in dynamic or b in incoming:
                raise ValueError('Duplicate, missing or not-yet-declared constraint driver')
            props = _properties(item, JOINT)
            if len(props & {'frameInA','frameInB'}) != 1 or not VECTORS-{'inertia'} <= props:
                raise ValueError('Complete original constraint parameters required')
            incoming[b] = a
        else:
            raise ValueError('Unknown/global/collision XML record: '+str(item.tag))
    if dynamic != set(drivers) or static != set(anchors) or set(incoming) != dynamic:
        raise ValueError('Missing or unexpected dynamic drivers/anchors')
    for name in dynamic:
        visited = set()
        while name in incoming:
            if name in visited: raise ValueError('Cyclic constraint graph')
            visited.add(name); name = incoming[name]
        if name not in static: raise ValueError('Constraint chain lacks an explicit anchor')
    return root, bones


def compose_xml(motion, anatomy, motion_drivers, anatomy_drivers, motion_anchors, anatomy_anchors):
    """Keep each authored record; only identical kinematic anchors may coalesce."""
    a, ab = inspect_xml(motion, motion_drivers, motion_anchors)
    b, bb = inspect_xml(anatomy, anatomy_drivers, anatomy_anchors)
    if set(motion_drivers) & set(anatomy_drivers): raise ValueError('Dynamic driver collision')
    all_names = {}
    for name in [*ab, *bb]:
        prior = all_names.setdefault(name.casefold(), name)
        if prior != name: raise ValueError('Case-ambiguous bone collision')
    shared = set(ab) & set(bb)
    for name in shared:
        if name not in set(motion_anchors) & set(anatomy_anchors) or signature(ab[name]) != signature(bb[name]):
            raise ValueError('Incompatible anchor or dynamic driver collision: '+name)
    root = ET.Element('system')
    for original in (a, b):
        for item in original:
            if original is b and item.tag == 'bone' and item.get('name') in shared: continue
            root.append(copy.deepcopy(item))
    ET.indent(root)
    output = ET.tostring(root, encoding='utf-8', xml_declaration=True)+b'\n'
    inspect_xml(output, set(motion_drivers)|set(anatomy_drivers), set(motion_anchors)|set(anatomy_anchors))
    return output


def redirect_hook(payload, expected, combined, Nif):
    """Redirect the single known root hook by appending its new value string."""
    if expected != NEUTRAL_XML or combined != XML: raise ValueError('Explicit original/combined CLAW namespaces required')
    original, result = Nif(payload), Nif(payload)
    if original.kind(0) != 'NiNode': raise ValueError('Known Scene Root NiNode required')
    hooks, owners = [], []
    for i, block in enumerate(original.blocks):
        if original.kind(i) == 'NiStringExtraData':
            if len(block) != 8: raise ValueError('Unknown string-extra layout')
            name, value = struct.unpack('<II', block)
            if max(name,value) >= len(original.strings): raise ValueError('Invalid string-extra index')
            if original.strings[name] == HOOK.encode():
                if original.strings[value] != expected.encode(): raise ValueError('Unknown existing FSMP hook')
                hooks.append(i)
    if len(hooks) != 1: raise ValueError('Exactly one known existing FSMP hook required')
    hook = hooks[0]
    for i, block in enumerate(original.blocks):
        if original.kind(i) in ('NiNode', 'BSTriShape', 'BSFadeNode', 'NiTriShape'):
            if len(block) < 8: raise ValueError('Truncated extra-data owner')
            count, = struct.unpack_from('<I', block, 4)
            if 8+4*count > len(block): raise ValueError('Truncated extra-data array')
            refs = struct.unpack_from('<'+str(count)+'I', block, 8)
            owners.extend(i for ref in refs if ref == hook)
    if owners != [0]: raise ValueError('FSMP hook must have exactly one root owner')
    if combined.casefold() in {s.decode('utf8').casefold() for s in original.strings}:
        raise ValueError('Combined XML namespace already occurs in input')
    raw = bytearray(result.blocks[hook]); struct.pack_into('<I', raw, 4, result.name(combined)); result.blocks[hook] = bytes(raw)
    output = result.bytes(); check = Nif(output)
    if (check.strings[:-1] != original.strings or check.strings[-1] != combined.encode()
            or check.kinds != original.kinds or check.footer != original.footer
            or len(check.blocks) != len(original.blocks)
            or any(x != check.blocks[i] for i,x in enumerate(original.blocks) if i != hook)):
        raise ValueError('Hook redirect changed unrelated blocks/strings/IDs')
    return output, {'hookBlock': hook, 'rootBlockExact': True, 'allOtherBlocksExact': True,
                    'originalStringsExact': True, 'newValueStringIndex': len(original.strings),
                    'before': expected, 'after': combined}


def modules():
    spec = importlib.util.spec_from_file_location('claw_neutral_composition_source', HERE/'build.py')
    anatomy = importlib.util.module_from_spec(spec); spec.loader.exec_module(anatomy)
    for directory in (anatomy.TOOLS, anatomy.VR, anatomy.PHYSICS): sys.path.insert(0,str(directory))
    import fsmp_motion
    if Path(fsmp_motion.__file__).resolve() != anatomy.PHYSICS/'fsmp_motion.py':
        raise ValueError('A different FSMP source module is already loaded')
    return anatomy, fsmp_motion


def build(candidate, receipt, skeleton, out, pynifly, morphbench):
    anatomy, fsmp = modules(); p = anatomy.load_profile()
    candidate, receipt, skeleton = [Path(x).resolve(strict=True) for x in (candidate, receipt, skeleton)]
    if anatomy.sha(receipt) != RECEIPT: raise ValueError('Only frozen anatomy04 receipt admitted')
    frozen = json.loads(receipt.read_text())
    if Path(frozen['candidate']).resolve() != candidate or {k:v['sha256'] for k,v in frozen['files'].items()} != FROZEN:
        raise ValueError('Only frozen anatomy04 resource set admitted')
    inputs = {str(candidate/name): value for name,value in FROZEN.items()}
    inputs[str(receipt)] = RECEIPT; inputs[str(skeleton)] = p['inputs']['skeleton.nif']
    for rel, expected in frozen['sourcePins'].items():
        if anatomy.sha(REPO/rel) != expected: raise ValueError('Original anatomy04 source changed: '+rel)
    rig, resource, _, api, Patch, Trip, dependencies = anatomy._imports(pynifly,morphbench)
    motion, female = fsmp.render_xml(False), fsmp.render_xml(True)
    if any(digest(data) != MOTION_HASHES[breast] for breast,data in [(False,motion),(True,female)]):
        raise ValueError('Original CLAW ear/tail/P1 XML changed')
    neutral = (candidate/p['xml']).read_bytes()
    if neutral != anatomy.render_xml(p): raise ValueError('Original anatomy XML parameters changed')
    drivers = fsmp.common.source.NODES
    anchors = ('NPC Head [Head]', 'Tails')
    inspect_xml(female, (*drivers,*fsmp.common.source.BREAST_NODES), (*anchors,'NPC L PreBreast P1','NPC R PreBreast P1'))
    combined = compose_xml(motion, neutral, drivers, p['drivers'], anchors, [p['anchor']])
    # Pin all local Python source in the imported tool families, not only direct imports.
    sources = {str(path): anatomy.sha(path) for directory in (HERE, anatomy.TOOLS, anatomy.VR, anatomy.PHYSICS)
               for path in sorted(directory.rglob('*.py'))}
    sources[str(anatomy.PROFILE)] = anatomy.sha(anatomy.PROFILE)
    pins = {**inputs, **sources, **dependencies}
    if any(anatomy.sha(path) != expected for path,expected in pins.items()): raise ValueError('Frozen input/source/dependency changed')
    out = resource.safe_output(out, pins); prepared = {}; coverage = {}; anchor_coverage = {}
    skel = api.NifFile(str(skeleton))
    if not set((*anchors,p['anchor'])) <= set(skel.nodes): raise ValueError('Missing anchor in pinned existing XP32 skeleton')
    for filename in ('malebodywerewolf_0.nif','malebodywerewolf_1.nif'):
        source = candidate/MESH/filename
        nif = api.NifFile(str(source))
        coverage[filename] = fsmp.common.inspect_body(nif, (*drivers,*p['drivers']), filename)
        anchor_coverage[filename] = {name:{'inMesh':name in nif.nodes,'inPinnedExistingSkeleton':True}
                                     for name in (*anchors,p['anchor'])}
        prepared[filename] = redirect_hook(source.read_bytes(), p['xml'], XML, fsmp.Nif)
    out.mkdir(parents=True); package = out/'candidate'
    pending = out/'FAILED-unverified-do-not-install'; pending.write_text('Offline combined candidate incomplete.\n')
    try:
        for filename,(data,proof) in prepared.items():
            target = package/MESH/filename; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(data)
            actual = api.NifFile(str(target)); hook = actual.root.get_extra_data(blockname='NiStringExtraData',name=HOOK)
            if hook is None or hook.string_data != XML or not Patch(target).consistent(): raise ValueError('Actual native hook/block readback differs')
            fsmp.common.inspect_body(actual, (*drivers,*p['drivers']), filename)
            proof['nativeHookAndBlocksReadback'] = True
        tri = package/MESH/'malebodywerewolf.tri'; tri.write_bytes((candidate/MESH/tri.name).read_bytes())
        target = package/XML; target.parent.mkdir(parents=True,exist_ok=True); target.write_bytes(combined)
        evidence = out/'original-xml'; evidence.mkdir()
        for name,data in [('CLAWMotionMale.xml',motion),('CLAWMotionFemale.xml',female),('CLAWNeutralAnatomy.xml',neutral)]: (evidence/name).write_bytes(data)
        if any(anatomy.sha(path) != expected for path,expected in pins.items()): raise ValueError('Input/source/dependency changed during composition')
        files = {str(x.relative_to(package)).replace('\\','/'): anatomy.sha(x) for x in package.rglob('*') if x.is_file()}
        report = {'status':'offline-combined-original-motion-and-neutral-anatomy; runtime-unqualified',
            'inputs':inputs, 'sources':sources, 'dependencies':dependencies, 'files':files,
            'combinedDrivers':[*drivers,*p['drivers']], 'combinedAnchors':[*anchors,p['anchor']],
            'bodyProofs':{name:proof for name,(_,proof) in prepared.items()}, 'storedDriverCoverage':coverage,
            'existingSkeletonAnchorCoverage':anchor_coverage,
            'femaleP1SourceXmlExact':digest(female), 'femaleResourcesSupplied':False,
            'providerAuditPerformed':False, 'providerBinarySupplied':False, 'globalSettingsSupplied':False,
            'installed':False, 'gameStarted':False, 'runtimeQualified':False,
            'limits':['Male12-driver source/resource composition only; female11-driver XML remains an unchanged source witness.',
                'No solver, rendered-motion, joint-response, camera, culling, contact or game qualification.',
                'Live provider/config ownership and selected VFS paths require a separate explicit conflict audit before installation.',
                'Original Tails anchor is supplied by the pinned existing XP32 skeleton, not grafted into the flat mesh; live resolution remains unqualified.',
                'Original anatomy04 bounds and all original morphology retained byte-for-byte; overall bounds are not requalified.']}
        (out/'build-report.json').write_text(json.dumps(report,indent=2)+'\n'); pending.unlink()
        return report
    except BaseException:
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','receipt','skeleton','out','pynifly','morphbench'): parser.add_argument('--'+name,type=Path,required=True)
    args = parser.parse_args()
    try:
        result = build(**vars(args)); print(json.dumps({'status':result['status'],'files':len(result['files'])}))
    except (OSError,ValueError,RuntimeError,KeyError) as error:
        print('CLAW original motion composition: '+str(error),file=sys.stderr); raise SystemExit(2)
