"""First-person Head-subtree isolation study on the reviewed composed family.

The desired reference locks weighted Head descendants to the existing XP32 Neck
frame. Source Head-local motion is an intentional visual change, not an error
target. Public MorphBench supplies an independent serialized influence inventory;
actual-bind finite-pose LBS is a separate CLAW analysis, never a viewer feature.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import sys
import numpy as np

import body_resource as resource
import selective_visibility as visibility

sys.path.insert(0, str(resource.ROOT / 'src/main/python/build-tools'))
import breast_rig as rig
import composed_vr
import vr_head
import head_split
from fur_motion import snapshot
import surface_collar as surface
import geometry_audit
from body_weight import Projector

HEAD = 'NPC Head [Head]'
NECK = 'NPC Neck [Neck]'
LIMITS = {'normalizedDesiredMax': .005, 'rawDesiredMax': .075,
          'packedSumChange': .0005, 'pureP1MotionChange': .005}


class NumericPlanRejected(RuntimeError):
    """A measured numerical rejection, distinct from a technical build failure."""


def derived_bind(rest_target, rest_source, source_bind):
    """Preserve the complete source rest product, including its skin frame/scale."""
    arrays = [np.asarray(x, float) for x in (rest_target, rest_source, source_bind)]
    if any(x.shape != (4, 4) or not np.isfinite(x).all() for x in arrays):
        raise ValueError('Expected finite 4x4 rest/bind matrices')
    return np.linalg.solve(arrays[0], arrays[1] @ arrays[2])


def collapse_weights(weights, names, descendants):
    """Collapse descendant mass into one new Neck slot; keep foreign slots exact.

    The sum of several packed half values may not itself be a half. Its explicit
    rounding error is measured in raw and normalized LBS; no foreign weight is
    silently renormalized or changed to conceal that error.
    """
    old = np.asarray(weights, float)
    if (old.ndim != 2 or old.shape[1] != len(names) or len(set(names)) != len(names)
            or NECK in names or not np.isfinite(old).all() or (old < 0).any()
            or np.any(old.sum(1) <= 0) or (old > 0).sum(1).max() > 4
            or not np.array_equal(old, old.astype(np.float16).astype(float))):
        raise ValueError('Expected four-slot packed weights and an absent Neck palette entry')
    donor = np.asarray([i for i, n in enumerate(names) if n in descendants], int)
    if not len(donor):
        raise ValueError('No Head-subtree palette entries')
    mass = old[:, donor].sum(1)
    new = np.c_[old, mass.astype(np.float16).astype(float)]
    new[:, donor] = 0
    if (new > 0).sum(1).max() > 4:
        raise ValueError('Collapsed plan exceeds four influences')
    return new, donor


def evaluate(vertices, weights, globals_, binds, normalized):
    weights = np.asarray(weights, float)
    if normalized:
        weights = weights / weights.sum(1)[:, None]
    products = np.einsum('pbij,bjk->pbik', globals_, binds)
    return rig.lbs(vertices, weights, products, normalize=False)


def summary(distance, ids=None, poses=None):
    x = np.asarray(distance, float)
    if not np.isfinite(x).all():
        raise ValueError('Nonfinite LBS metric')
    result = {'n': int(x.size), 'max': float(x.max()) if x.size else 0.,
              'p95': float(np.quantile(x, .95)) if x.size else 0.,
              'rms': float(np.sqrt(np.mean(x*x))) if x.size else 0.}
    if x.size and x.ndim == 2 and ids is not None:
        pose, vertex = np.unravel_index(x.argmax(), x.shape)
        result.update(vertex=int(ids[vertex]), pose=poses[pose] if poses else int(pose))
    return result


class Study:
    def __init__(self, nif, skeleton):
        self.nif = nif
        self.shapes = {s.name: s for s in nif.shapes}
        self.rest, self.parents, self.definitions, bank = composed_vr.pose_bank(skeleton)
        if NECK not in self.rest:
            raise ValueError('Existing XP32 Neck is absent')
        self.descendants = vr_head.descendants(self.parents, HEAD)
        self.names = sorted({n for s in nif.shapes for n in s.bone_weights})
        if NECK in self.names or not set(self.names) <= self.rest.keys():
            raise ValueError('Unsupported source bone inventory')
        self.globals = np.asarray([[p[n] for n in self.names] for p in bank])
        self.neck_globals = np.asarray([p[NECK] for p in bank])
        self.labels = [x[0] for x in self.definitions]
        self.head_only = np.asarray([i for i, (_, _, kind) in enumerate(self.definitions)
                                    if kind in ('visibility-operation-example', 'rotation-example', 'offset-example-not-an-HMD-trace')])
        self.parent_only = np.asarray([i for i, (_, edits, _) in enumerate(self.definitions)
                                       if not set(edits) & self.descendants])
        self.pure_p1 = np.asarray([i for i, (_, _, kind) in enumerate(self.definitions)
                                   if kind.startswith('p1-')])
        self.plans = {}
        for name, shape in self.shapes.items():
            if not resource.visible_by_hidden_flags(shape):
                continue
            if not shape.has_global_to_skin:
                raise ValueError('Missing actual stored skin frame: ' + name)
            weights = rig.read_weights(shape, self.names)
            donor = [j for j, bone in enumerate(self.names) if bone in self.descendants]
            ids = np.flatnonzero(weights[:, donor].sum(1) > 0)
            if not len(ids):
                continue
            if NECK in shape.bone_names or HEAD not in shape.bone_names:
                raise ValueError('Unexpected source Head/Neck palette: ' + name)
            new, donors = collapse_weights(weights, self.names, self.descendants)
            frame = rig.matrix(shape.global_to_skin)
            binds = np.zeros((len(self.names), 4, 4))
            for bone in shape.bone_names:
                bind = shape.get_shape_skin_to_bone(bone)
                if bind is None:
                    raise ValueError('Missing serialized bind: ' + name + '/' + bone)
                binds[self.names.index(bone)] = rig.matrix(bind) @ frame
            head_bind = binds[self.names.index(HEAD)]
            neck_bind = derived_bind(self.rest[NECK], self.rest[HEAD], head_bind)
            candidate_binds = np.concatenate([binds, neck_bind[None]])
            candidate_globals = np.concatenate([self.globals, self.neck_globals[:, None]], axis=1)
            desired_globals = self.globals.copy()
            for j in donors:
                desired_globals[:, j] = self.neck_globals @ np.linalg.solve(self.rest[NECK], self.rest[self.names[j]])
            self.plans[name] = {'weights': weights, 'candidateWeights': new, 'donors': donors,
                                'ids': ids, 'binds': binds, 'neckBindWithSkin': neck_bind,
                                'candidateBinds': candidate_binds, 'candidateGlobals': candidate_globals,
                                'desiredGlobals': desired_globals}

    def points(self, name, ids, delta, mode, version):
        p = self.plans.get(name)
        shape = self.shapes[name]
        vertices = np.asarray(shape.verts, float)[ids] + delta[ids]
        if p is None:
            weights = rig.read_weights(shape, self.names)[ids]
            binds = np.zeros((len(self.names), 4, 4))
            for bone in shape.bone_names:
                binds[self.names.index(bone)] = rig.matrix(shape.get_shape_skin_to_bone(bone)) @ rig.matrix(shape.global_to_skin)
            return evaluate(vertices, weights, self.globals, binds, mode)
        if version == 'candidate':
            return evaluate(vertices, p['candidateWeights'][ids], p['candidateGlobals'], p['candidateBinds'], mode)
        return evaluate(vertices, p['weights'][ids], p['desiredGlobals'] if version == 'desired' else self.globals, p['binds'], mode)


def shape_study(study, raw, sex):
    result = {}
    states = {'neutral': {}, 'girth0.25': {'CLAWTorsoGirth': .25},
              'neck1': {'CLAWTorsoNeckGirth': 1.}}
    if sex == 'female':
        states['breast1'] = {'CLAWTorsoBreastSize': 1.}
    for name, p in study.plans.items():
        shape = study.shapes[name]
        ids = p['ids']
        donor_counts = {bone: int((p['weights'][:, j] > 0).sum()) for j, bone in enumerate(study.names)
                        if bone in study.descendants and p['weights'][:, j].any()}
        rows = {}
        rest_products = {bone: float(np.max(abs(study.rest[bone] @ p['binds'][j] -
                                  study.rest[HEAD] @ p['binds'][study.names.index(HEAD)])))
                         for j, bone in enumerate(study.names) if bone in donor_counts}
        for label, values in states.items():
            delta = sum((amount * rig.dense_morph(raw, name, morph, len(shape.verts)) for morph, amount in values.items()),
                        np.zeros((len(shape.verts), 3)))
            modes = {}
            for normalized in (False, True):
                source, desired, candidate = [study.points(name, ids, delta, normalized, version)
                                               for version in ('source', 'desired', 'candidate')]
                error = np.linalg.norm(candidate - desired, axis=-1)
                intentional = np.linalg.norm(candidate - source, axis=-1)
                p1 = np.linalg.norm((candidate[study.pure_p1]-candidate[:1]) -
                                    (source[study.pure_p1]-source[:1]), axis=-1)
                head = np.linalg.norm(candidate[study.head_only]-candidate[:1], axis=-1)
                parent = intentional[study.parent_only]
                modes['normalized' if normalized else 'rawPacked'] = {
                    'desiredReferenceError': summary(error, ids, study.labels),
                    'sourceVisualChange': summary(intentional, ids, study.labels),
                    'retainedParentChainError': summary(parent, ids, [study.labels[i] for i in study.parent_only]),
                    'headOnlyMotion': summary(head, ids, [study.labels[i] for i in study.head_only]),
                    'pureP1MotionChange': summary(p1),
                    'restChange': summary(intentional[:1], ids, study.labels[:1])}
            rows[label] = modes
        old, new = p['weights'], p['candidateWeights']
        foreign = [j for j, n in enumerate(study.names) if n not in study.descendants]
        result[name] = {'changedVertices': ids.tolist(), 'changedVertexCount': len(ids),
                        'donorInfluenceCounts': donor_counts, 'donorRestProductMaxAbsDifference': rest_products,
                        'neckPresentInSourcePalette': False, 'neckPresentInSourceNif': NECK in study.nif.nodes,
                        'newExistingXp32Bone': NECK, 'foreignPackedWeightsExact': bool(np.array_equal(old[:, foreign], new[:, foreign])),
                        'maxInfluencesBefore': int((old > 0).sum(1).max()),
                        'maxInfluencesAfter': int((new > 0).sum(1).max()),
                        'packedSumMaxChange': float(abs(new.sum(1)-old.sum(1)).max()), 'states': rows}
    return result


def load_snapshot(root):
    root = Path(root).resolve(strict=True)
    manifest = root.parent / 'snapshot.json'
    snapshot = resource.read_json(manifest)
    if snapshot['commit'] != '3ddc3afa0c45b74e69210d26d45df40cfe1eac5b':
        raise ValueError('Unreviewed MorphBench snapshot')
    pins = {str(root / row['path']): row['sha256'] for row in snapshot['files']}
    if any(resource.sha256(path) != digest for path, digest in pins.items()):
        raise ValueError('Changed frozen MorphBench source')
    return root, {str(manifest): resource.sha256(manifest), **pins}


def skin_records(data):
    r = head_split.Reader(data)
    frame = r.take(52)
    count, present = r.unpack('<IB')
    if present != 1:
        raise ValueError('Expected explicit source NiSkinData weights')
    rows = []
    for _ in range(count):
        fixed = r.take(68)
        size, = r.unpack('<H')
        rows.append((fixed, r.take(size * 6)))
    r.done()
    return frame, rows


def node_children(data):
    extra, = struct.unpack_from('<I', data, 4)
    offset = 72 + 4 * extra
    count, = struct.unpack_from('<I', data, offset)
    end = offset + 4 + 4 * count
    if len(data) != end + 4 or struct.unpack_from('<I', data, end)[0]:
        raise ValueError('Unexpected NiNode child/effect layout')
    return offset, list(struct.unpack_from('<' + str(count) + 'I', data, offset + 4))


def compare_native(before, after, study, added, skeleton, *, public_scratch=False):
    old, new = snapshot(before), snapshot(after)
    if set(new['nodes']) != set(old['nodes']) | set(added) or set(new['shapes']) != set(old['shapes']):
        raise ValueError('Unexpected native graph inventory after Neck graft')
    for name, row in old['nodes'].items():
        actual = new['nodes'][name]
        if row[0] != actual[0] or row[3] != actual[3] or any(not np.array_equal(a, b) for a, b in zip(row[1:3], actual[1:3])):
            raise ValueError('Original node ancestry/transform/extra changed: ' + name)
    for name in added:
        actual = after.nodes[name]
        expected = skeleton.nodes[name]
        if (actual.parent.name != expected.parent.name
                or abs(rig.matrix(actual.global_transform) - rig.matrix(expected.global_transform)).max() > 1e-5):
            raise ValueError('Grafted node does not match existing XP32: ' + name)
    for name, row in old['shapes'].items():
        actual = new['shapes'][name]
        for field in ('vertices', 'triangles', 'uvs', 'frame', 'normals', 'colors', 'transform'):
            if not np.array_equal(row[field], actual[field]):
                raise ValueError('Protected native shape field changed: ' + name + '/' + field)
        for field in ('render', 'extras', 'partitions', 'hasFrame'):
            if public_scratch and field == 'render':
                # Its string table is reordered. Final assembly retains the
                # entire original shader/texture/alpha blocks, then checks exact
                # properties again against independent final native readback.
                continue
            if row[field] != actual[field]:
                raise ValueError('Protected native metadata changed: ' + name + '/' + field)
        for bone, bind in row['binds'].items():
            if not np.array_equal(bind, actual['binds'][bone]):
                raise ValueError('Original skin bind changed: ' + name + '/' + bone)
        shape = next(s for s in after.shapes if s.name == name)
        if name in study.plans:
            plan = study.plans[name]
            if tuple(shape.bone_names) != (*before.shapes[list(study.shapes).index(name)].bone_names, NECK):
                raise ValueError('Public writer reordered an existing shape palette')
            if not np.array_equal(rig.read_weights(shape, [*study.names, NECK]), plan['candidateWeights']):
                raise ValueError('Native packed weights differ from the Neck plan: ' + name)
            product = rig.matrix(shape.get_shape_skin_to_bone(NECK)) @ rig.matrix(shape.global_to_skin)
            if np.max(abs(product - plan['neckBindWithSkin'])) > 1e-5:
                raise ValueError('Native derived Neck bind differs: ' + name)
        elif row['bones'] != actual['bones'] or row['weights'] != actual['weights']:
            raise ValueError('Unplanned shape skin changed: ' + name)
    return {'nativeProtectedGeometryMaterialsUvFramesAndForeignWeightsExact': True,
            'originalNodesAndBindsExact': True, 'graftedNodesMatchExistingXp32': list(added),
            'derivedNeckBindMaxAbsTolerance': 1e-5}


def graft_resource(api, source, study, skeleton, target, scratch, hidden_shapes):
    """Use public setters, then retain only reviewed skin fields in source bytes.

    Public save reorders its container. That broad export is diagnostic scratch,
    never the candidate. The final container keeps every original ID/string and
    raw non-skin block. No skeleton asset is produced or copied.
    """
    if target.exists() or scratch.exists():
        raise ValueError('Graft target and public-export scratch must be new files')
    original = api.NifFile(str(source))
    nif = api.NifFile(str(source))
    shapes = {s.name: s for s in nif.shapes}
    added = []
    def add(name):
        if name in nif.nodes:
            return
        parent = skeleton.nodes[name].parent.name
        add(parent)
        parent_world = rig.matrix(nif.nodes[parent].global_transform)
        nif.add_node(name, rig._transform_buffer(api, np.linalg.solve(parent_world, study.rest[name])), parent=parent)
        added.append(name)
    add(NECK)
    for name, plan in study.plans.items():
        shape = shapes[name]
        binds = {bone: shape.get_shape_skin_to_bone(bone).copy() for bone in shape.bone_names}
        frame = shape.global_to_skin.copy()
        partitions, partition_tris = shape.partitions, shape.partition_tris
        shape.add_bone(NECK, rig._transform_buffer(api, study.rest[NECK]), skeleton.nodes[NECK].parent.name)
        shape.set_global_to_skin(frame)
        for bone, bind in binds.items():
            shape.set_skin_to_bone_xform(bone, bind)
        bind = plan['neckBindWithSkin'] @ np.linalg.inv(rig.matrix(frame))
        shape.set_skin_to_bone_xform(NECK, rig._transform_buffer(api, bind))
        for bone in [*binds, NECK]:
            column = [*study.names, NECK].index(bone)
            # Explicit zero rows clear the old packed donor slots.
            shape.setShapeWeights(bone, [(int(i), float(value)) for i, value in enumerate(plan['candidateWeights'][:, column])])
        shape.set_partitions(partitions, partition_tris)
    nif.filepath = str(scratch)
    nif.save()
    native = api.NifFile(str(scratch))
    compare_native(original, native, study, added, skeleton, public_scratch=True)
    source_container = head_split.Nif(source.read_bytes())
    public_container = head_split.Nif(scratch.read_bytes())
    # Assemble a new container from original bytes, with source block IDs stable.
    assembled = head_split.Nif(source.read_bytes())
    changed = set()
    new_ids = {name: len(assembled.blocks) + i for i, name in enumerate(added)}
    for name in added:
        node = native.nodes[name]
        raw = bytearray(public_container.blocks[node.id])
        if public_container.kind(node.id) != 'NiNode' or struct.unpack_from('<I', raw, 4)[0]:
            raise ValueError('Unexpected public new-node layout')
        offset, children = node_children(raw)
        native_names = {native.nodes[n].id: n for n in added}
        if any(i not in native_names for i in children):
            raise ValueError('Public new node has an unreviewed child')
        struct.pack_into('<I', raw, 0, assembled.name(name))
        for i, child in enumerate(children):
            struct.pack_into('<I', raw, offset + 4 + 4*i, new_ids[native_names[child]])
        if assembled.append('NiNode', raw) != new_ids[name]:
            raise ValueError('Appended node index mismatch')
    for name in added:
        parent = skeleton.nodes[name].parent.name
        if parent in new_ids:
            continue  # Copied public new-node children already reference it.
        parent_id = original.nodes[parent].id
        raw = bytearray(assembled.blocks[parent_id])
        offset, children = node_children(raw)
        struct.pack_into('<I', raw, offset, len(children) + 1)
        end = offset + 4 + 4*len(children)
        raw[end:end] = struct.pack('<I', new_ids[name])
        assembled.blocks[parent_id] = bytes(raw)
        changed.add(parent_id)
    native_shapes = {s.name: s for s in native.shapes}
    binary_rows = {}
    for name, plan in study.plans.items():
        old_shape = study.shapes[name]
        new_shape = native_shapes[name]
        def links(container, shape_id):
            block = container.blocks[shape_id]
            extra, = struct.unpack_from('<I', block, 4)
            skin_id, = struct.unpack_from('<I', block, 88 + 4*extra)
            data_id, part_id = struct.unpack_from('<II', container.blocks[skin_id])
            if (container.kind(skin_id), container.kind(data_id), container.kind(part_id)) != ('BSDismemberSkinInstance', 'NiSkinData', 'NiSkinPartition'):
                raise ValueError('Unexpected public skin block graph')
            return skin_id, data_id, part_id
        old_skin, old_data, old_part = links(source_container, old_shape.id)
        new_skin, new_data, new_part = links(public_container, new_shape.id)
        instance = bytearray(source_container.blocks[old_skin])
        count, = struct.unpack_from('<I', instance, 12)
        if count != len(old_shape.bone_names):
            raise ValueError('Source palette/instance count mismatch')
        struct.pack_into('<I', instance, 12, count + 1)
        instance[16 + 4*count:16 + 4*count] = struct.pack('<I', new_ids[NECK])
        assembled.blocks[old_skin] = bytes(instance)
        old_frame, old_records = skin_records(source_container.blocks[old_data])
        _, public_records = skin_records(public_container.blocks[new_data])
        if len(public_records) != len(old_records) + 1:
            raise ValueError('Public skin data palette mismatch')
        data = [old_frame, struct.pack('<IB', len(public_records), 1)]
        for bone, (fixed, rows) in zip(old_shape.bone_names, old_records):
            rows = b'' if bone in study.descendants else rows
            data.extend([fixed, struct.pack('<H', len(rows)//6), rows])
        fixed, rows = public_records[-1]
        data.extend([fixed, struct.pack('<H', len(rows)//6), rows])
        assembled.blocks[old_data] = b''.join(data)
        old_partition = head_split.Partition(source_container.blocks[old_part])
        public_partition = head_split.Partition(public_container.blocks[new_part])
        if (old_partition.desc != public_partition.desc
                or old_partition.vertices.shape != public_partition.vertices.shape
                or not np.array_equal(old_partition.triangles, public_partition.triangles)
                or not np.array_equal(old_partition.vertices[:, :28], public_partition.vertices[:, :28])):
            raise ValueError('Public export altered packed geometry/UV/normal/tangent bytes')
        # Only the twelve packed weight/index bytes may change in a 40-byte row.
        old_partition.vertices[:, 28:] = public_partition.vertices[:, 28:]
        old_partition.bones = public_partition.bones
        old_partition.weights = public_partition.weights
        old_partition.indices = public_partition.indices
        assembled.blocks[old_part] = old_partition.subset(np.arange(len(old_partition.vertices)), np.arange(len(old_partition.triangles)))
        changed.update((old_skin, old_data, old_part))
        binary_rows[name] = {'skinBlocks': [old_skin, old_data, old_part], 'rawPackedGeometryBytesExact': True,
                             'foreignFloatSkinWeightRecordsExact': True, 'originalBindAndSkinSphereRecordsExact': True}
    hidden_ledger = []
    for shape in original.shapes:
        if shape.name in hidden_shapes:
            raw = bytearray(assembled.blocks[shape.id])
            extra, = struct.unpack_from('<I', raw, 4)
            offset = 12 + 4*extra
            flags, = struct.unpack_from('<I', raw, offset)
            struct.pack_into('<I', raw, offset, flags | resource.HIDDEN)
            assembled.blocks[shape.id] = bytes(raw)
            changed.add(shape.id)
            hidden_ledger.append(shape.name)
    if (assembled.strings[:len(source_container.strings)] != source_container.strings
            or any(a != b for i, (a, b) in enumerate(zip(source_container.blocks, assembled.blocks)) if i not in changed)):
        raise ValueError('Unrelated original byte block or string changed')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(assembled.bytes())
    actual = api.NifFile(str(target))
    verification = compare_native(original, actual, study, added, skeleton)
    for shape in actual.shapes:
        if resource.visible_by_hidden_flags(shape) != (shape.name not in hidden_shapes):
            raise ValueError('Unexpected grafted first-person visibility: ' + shape.name)
    verification.update(originalBlockIdsStable=True, originalStringIdsStable=True,
                        originalUnchangedByteBlocks=len(source_container.blocks)-len(changed),
                        changedOriginalBlocks=sorted(changed), appendedExistingXp32Nodes=added,
                        shapeByteAudits=binary_rows, hiddenShapes=hidden_ledger,
                        publicExportScratchOnly=str(scratch), nifSha256=resource.sha256(target))
    return actual, verification


def audit_joins(low, high, candidate_low, candidate_high, skeleton, raw, sex):
    """Frozen visible-skin attachments on the actual serialized endpoints.

    Every visible fur/blend root is included, including unmodified groups over
    changed skin. Card roots use the existing closest-vertex convention. The open
    hidden-head boundary is reported separately; its two sides are not welded.
    """
    baseline = geometry_audit.Model(low, high, skeleton, raw)
    candidate = geometry_audit.Model(candidate_low, candidate_high, skeleton, raw)
    desired = geometry_audit.Model(low, high, skeleton, raw)
    descendants = vr_head.descendants(desired.parents, HEAD)
    neck_globals = np.asarray([pose[NECK] for pose in desired.global_dicts])
    for j, bone in enumerate(desired.names):
        if bone not in descendants:
            continue
        locked = neck_globals @ np.linalg.solve(desired.rest[NECK], desired.rest[bone])
        desired.globals[:, j] = locked
        for name, shape in desired.shapes.items():
            if bone in shape.bone_names:
                bind = rig.matrix(shape.get_shape_skin_to_bone(bone)) @ rig.matrix(shape.global_to_skin)
                desired.effective[name][:, j] = locked @ bind
    shapes = baseline.shapes
    body_v, head_v = baseline.vertices['body'], baseline.vertices['head']
    skin = np.r_[body_v, head_v]
    faces = np.r_[shapes['body'].tris, np.asarray(shapes['head'].tris) + len(body_v)]
    projector = Projector(skin, faces)
    profile = resource.read_json(resource.ROOT / 'src/main/resources/recipes/breast-rig-collar.json')
    rule = dict(profile['collar']); rule['anchorCountRange'] = [55, 55]
    collar = surface.Collar(body_v, shapes['body'].tris, head_v, shapes['head'].tris,
                            rule, Projector(body_v, shapes['body'].tris))
    bindings = {'skin-collar': ('head', collar.anchors,
                 np.asarray(shapes['body'].tris)[collar.binding.indices], collar.binding.weights)}
    selections = {'skin-collar': {'rootVertices': collar.anchors.tolist()}}
    for name in ('ChestBlend', 'fur_back', 'fur_belly', 'fur_chest', 'fur_shoulders'):
        vertices = baseline.vertices[name]
        rule = {'mode': 'vertices' if name == 'ChestBlend' else 'cards',
                'bounds': [(vertices.min(0)-2).tolist(), (vertices.max(0)+2).tolist()],
                'fade': [1, 1, 1], 'distanceFade': [1000, 1001], 'weldDecimals': 5}
        layer = surface.Layer(vertices, shapes[name].tris, skin, faces, rule, projector)
        roots = np.asarray([int(group[np.all(vertices[group] == point, axis=1)][0])
                            for group, point in zip(layer.groups, layer.binding.points)])
        bindings[name] = (name, roots, layer.binding.faces[layer.binding.indices], layer.binding.weights)
        selections[name] = {'rootVertices': roots.tolist(), 'groups': len(layer.groups),
                             'frozenTriangles': layer.binding.indices.tolist(),
                             'frozenBarycentric': layer.binding.weights.tolist(),
                             'restRootDistance': summary(layer.binding.distances)}
        print('HEAD_JOINS|' + sex + '|' + name + '|roots=' + str(len(roots)), flush=True)
    states = {'neutral': {}, 'girth0.25': {'CLAWTorsoGirth': .25}, 'neck1': {'CLAWTorsoNeckGirth': 1.}}
    if sex == 'female':
        states['breast1'] = {'CLAWTorsoBreastSize': 1.}
    report = {'bindings': selections, 'models': {},
              'scope': 'Actual native-readback LBS on fixed nearest visible-skin triangles; all visible fur/blend roots, 55 collar anchors, weights0/0.3/1 and finite poses. Source/desired/candidate signed gaps and interior depth are distinct from transported-offset error. No camera volume or visual-coverage claim.'}
    for label, model in [('source', baseline), ('desiredHeadLocked', desired), ('serializedCandidate', candidate)]:
        rows = {}
        for weight in (0., .3, 1.):
            values = {}
            for state_label, state in states.items():
                values[state_label] = {('normalized' if normalized else 'rawPacked'):
                    {name: geometry_audit.binding_metrics(model, *binding, weight, state, normalized)
                     for name, binding in bindings.items()} for normalized in (False, True)}
            rows[str(weight)] = values
        report['models'][label] = rows
        print('HEAD_JOINS|' + sex + '|' + label + '|complete', flush=True)
    return report


def function_ast_digest(text, name):
    definitions = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name]
    if len(definitions) != 1:
        raise ValueError('Missing or ambiguous captured analysis function')
    return hashlib.sha256(ast.dump(definitions[0], include_attributes=False).encode('utf-8')).hexdigest()


def reuse_verified_joins(directory, report):
    """Reuse expensive immutable measurements only for identical actual inputs.

    Rebuilding an admission wrapper does not require recalculating identical
    geometry. The original executed builder, unchanged analysis function and
    helper source bytes remain part of this explicit provenance chain.
    """
    root = Path(directory).resolve(strict=True)
    old_path = root / 'head-isolation-report.json'
    old_digest = resource.sha256(old_path)
    old = resource.read_json(old_path)
    captured_path = root / 'executed-source/head_isolation.py'
    supplement_path = root / 'source-provenance-supplement.json'
    captured_digest = resource.sha256(captured_path)
    supplement_digest = resource.sha256(supplement_path)
    supplement = resource.read_json(supplement_path)
    if (old['status'] != 'offline-first-person-neck-graft-native-verified-joins-measured-runtime-pending'
            or old['inputSha256'] != report['inputSha256']
            or old['dependencySha256'] != report['dependencySha256']
            or old['morphbenchSnapshotSha256'] != report['morphbenchSnapshotSha256']
            or old['executedSourceSha256'].get(str(Path(__file__))) != captured_digest
            or supplement['builderSnapshotSha256'] != captured_digest):
        raise ValueError('Prior join report does not describe the same admitted inputs/dependencies')
    current_function = function_ast_digest(Path(__file__).read_text(encoding='utf-8'), 'audit_joins')
    captured_function = function_ast_digest(captured_path.read_text(encoding='utf-8'), 'audit_joins')
    if current_function != captured_function:
        raise ValueError('Join-analysis function changed; recomputation required')
    pins = {str(old_path): old_digest, str(captured_path): captured_digest,
            str(supplement_path): supplement_digest}
    for path, row in supplement['helpers'].items():
        if resource.sha256(path) != row['sha256'] or resource.sha256(row['snapshot']) != row['sha256']:
            raise ValueError('Prior analysis helper source changed: ' + path)
        pins[path] = row['sha256']
        pins[row['snapshot']] = row['sha256']
    if set(old['bodies']) != set(report['bodies']) or set(old['joins']) != {'female', 'male'}:
        raise ValueError('Prior join run is incomplete')
    for name, row in report['bodies'].items():
        if (not old['bodies'][name]['numericPlanPasses']
                or old['bodies'][name]['serializedCandidate']['nifSha256'] != row['serializedCandidate']['nifSha256']):
            raise ValueError('Prior joins refer to a different serialized candidate: ' + name)
    report['joins'] = {}
    for sex, row in old['joins'].items():
        path = Path(row['report'])
        if resource.sha256(path) != row['sha256']:
            raise ValueError('Prior join measurement bytes changed')
        pins[str(path)] = row['sha256']
        report['joins'][sex] = {**row, 'reusedFromRun': str(root),
                               'sameActualCandidateBytes': True, 'joinFunctionAstSha256': current_function}
    report['joinEvidenceReused'] = True
    return pins


def require_complete_candidate(report, output):
    expected = {'female0', 'female1', 'male0', 'male1'}
    if set(report.get('bodies', {})) != expected or set(report.get('joins', {})) != {'female', 'male'}:
        raise ValueError('Cannot verify a candidate without all four endpoints and both join receipts')
    for name, row in report['bodies'].items():
        receipt = row.get('serializedCandidate', {})
        if (not row.get('numericPlanPasses') or row.get('numericFailures')
                or receipt.get('nativeProtectedGeometryMaterialsUvFramesAndForeignWeightsExact') is not True
                or receipt.get('originalNodesAndBindsExact') is not True):
            raise ValueError('Missing numerical/native candidate verification: ' + name)
        sex, endpoint = name[:-1], int(name[-1])
        path = Path(output) / 'resources' / sex / f'first-person_{endpoint}.nif'
        if resource.sha256(path) != receipt.get('nifSha256'):
            raise ValueError('A verified candidate payload is missing or changed: ' + name)
    for row in report['joins'].values():
        if resource.sha256(row['report']) != row['sha256']:
            raise ValueError('A required join receipt is missing or changed')
        if set(resource.read_json(row['report'])['models']) != {'source', 'desiredHeadLocked', 'serializedCandidate'}:
            raise ValueError('A required join measurement is incomplete')


def build(body_root, skeleton_file, output, morphbench_root, pynifly=None, write_candidate=False, reuse_joins=None):
    body_root = Path(body_root).resolve(strict=True)
    skeleton_file = Path(skeleton_file).resolve(strict=True)
    profile = visibility.load_profile()
    inputs = {str(skeleton_file): profile['skeletonSha256'], str(visibility.PROFILE): resource.sha256(visibility.PROFILE)}
    for sex, pin in profile['bodies'].items():
        inputs[str(body_root / (sex + 'bodywerewolf.tri'))] = pin['triSha256']
        for endpoint, digest in enumerate(pin['nifSha256']):
            inputs[str(body_root / f'{sex}bodywerewolf_{endpoint}.nif')] = digest
    if any(resource.sha256(path) != digest for path, digest in inputs.items()):
        raise ValueError('Composed family or XP32 source pin mismatch')
    out = resource.safe_output(output, inputs)
    mb, mb_pins = load_snapshot(morphbench_root)
    api, _, Trip, dependencies = resource.dependencies(pynifly, mb)
    if any(resource.sha256(path) != digest for path, digest in inputs.items()):
        raise ValueError('Source changed during dependency loading')
    out.mkdir(parents=True)
    (out / 'NOT_INSTALLABLE.txt').write_text(
        'Offline first-person-only Neck attachment study/candidate. No engine load tree or skeleton asset.\n'
        'Runtime dispatch, camera/neck appearance, morph reloads, IK and physical contacts remain unqualified.\n'
        'Existing ordinary-animation fur/skin defects are not repaired by Head-local isolation. Do not install.\n', encoding='utf-8')
    # All writes are new external evidence. Config does not touch a live profile.
    from morphbench.api import MorphBench
    from morphbench.config import Config
    cfg = Config(out / 'morphbench.json')
    cfg.set('language', 'en')
    cfg.set('pynifly', str(Path(api.__file__).resolve().parents[1]))
    bench = MorphBench(cfg)
    skeleton = api.NifFile(str(skeleton_file))
    source_files = [Path(__file__), Path(__file__).with_name('audit_head_isolation.py'),
                    Path(rig.__file__), Path(composed_vr.__file__), Path(vr_head.__file__), Path(resource.__file__), Path(visibility.__file__), Path(head_split.__file__),
                    Path(surface.__file__), Path(geometry_audit.__file__), resource.ROOT / 'src/main/python/build-tools/body_weight.py', resource.ROOT / 'src/main/resources/recipes/breast-rig-collar.json',
                    *[resource.ROOT / 'src/main/python/build-tools' / name for name in ('fur_motion.py', 'collar_weights.py', 'morph_calibration.py', 'locate.py')]]
    source_pins = {str(p): resource.sha256(p) for p in source_files}
    report = {'schemaVersion': 1, 'status': 'building', 'installable': False,
              'inputSha256': inputs, 'executedSourceSha256': source_pins, 'dependencySha256': dependencies,
              'morphbenchCommit': '3ddc3afa0c45b74e69210d26d45df40cfe1eac5b', 'morphbenchSnapshotSha256': mb_pins,
              'desiredContract': 'Visible Head descendants follow current existing XP32 Neck with their original rest product. Head-local motion is deliberately removed; source visual change is separately reported.',
              'limits': LIMITS, 'bodies': {},
              'joinScopeClarification': {'mixedLayers': ['ChestBlend', 'fur_back', 'fur_belly', 'fur_chest', 'fur_shoulders'],
                                         'collarAnchors': 55, 'otherVisibleFurLayers': ['fur_arms', 'fur_tailtip'],
                                         'hiddenSplitBoundary': 'not joined to the visible neck; no camera/neck closure claim'},
              'scope': ['Four explicit neutral endpoints; neutral, Girth0.25, NeckGirth1 and female BreastSize1.',
                        '151 finite ordinary/held-out/P1 poses plus nine Head-only mathematical examples.',
                        'Actual binds and scale; separate raw-packed and normalized LBS. Not a MorphBench posed preview.',
                        'Optional first-person-only mesh graft; no skeleton asset, camera, engine path, runtime or appearance claim.']}
    try:
        prepared = {}
        for sex in ('female', 'male'):
            tri = body_root / (sex + 'bodywerewolf.tri')
            raw = Trip.from_filepath(str(tri)).shapes
            for endpoint in (0, 1):
                source = body_root / f'{sex}bodywerewolf_{endpoint}.nif'
                nif = api.NifFile(str(source))
                # Reuse the exact selective flag patch in memory so analysis sees
                # the intended first-person visibility, without serializing it.
                for shape in nif.shapes:
                    if shape.name in profile['hiddenShapes']:
                        shape.flags |= resource.HIDDEN
                study = Study(nif, skeleton)
                bench.open(source, tri=tri, skeleton=skeleton_file)
                inventory = {name: bench.bones(shape=name) for name in study.plans}
                for name, plan in study.plans.items():
                    expected = {bone: int((plan['weights'][:, j] > 0).sum()) for j, bone in enumerate(study.names)
                                if bone in study.descendants and plan['weights'][:, j].any()}
                    actual = {r['bone']: r['vertices'] for r in inventory[name] if r['bone'] in study.descendants and r['vertices']}
                    if expected != actual:
                        raise ValueError('Independent MorphBench donor inventory differs: ' + name)
                measured = shape_study(study, raw, sex)
                if set(measured) != set(study.plans) or not measured:
                    raise ValueError('Numerical measurement omits planned visible shapes')
                failures = []
                for name, row in measured.items():
                    if not math.isfinite(row['packedSumMaxChange']) or not row['states']:
                        raise ValueError('Invalid numerical weight/state measurement')
                    if row['packedSumMaxChange'] > LIMITS['packedSumChange']:
                        failures.append(name + ': packed sum change')
                    for state, modes in row['states'].items():
                        for mode, values in modes.items():
                            if mode not in ('normalized', 'rawPacked') or not all(math.isfinite(values[key]['max']) for key in ('desiredReferenceError', 'pureP1MotionChange')):
                                raise ValueError('Invalid numerical pose measurement')
                            limit = LIMITS['normalizedDesiredMax' if mode == 'normalized' else 'rawDesiredMax']
                            if values['desiredReferenceError']['max'] > limit:
                                failures.append('/'.join((name, state, mode, 'desired reference')))
                            if values['pureP1MotionChange']['max'] > LIMITS['pureP1MotionChange']:
                                failures.append('/'.join((name, state, mode, 'P1 motion')))
                report['bodies'][sex + str(endpoint)] = {'morphbenchSummary': bench.summary(),
                    'morphbenchInfluenceInventory': inventory, 'shapes': measured, 'numericFailures': failures,
                    'numericPlanPasses': not failures}
                prepared[sex, endpoint] = source, tri, study
                print('HEAD_ISOLATION|' + sex + str(endpoint) + '|numeric failures=' + str(len(failures)), flush=True)
        if set(report['bodies']) != {'female0', 'female1', 'male0', 'male1'}:
            raise ValueError('Numerical preflight is missing an endpoint')
        if any(not row['numericPlanPasses'] for row in report['bodies'].values()):
            raise NumericPlanRejected('One or more endpoints failed numerical admission; no candidate was written')
        reused_pins = {}
        if write_candidate:
            # All four numerical admissions precede every mesh write.
            for (sex, endpoint), (source, tri, study) in prepared.items():
                target = out / 'resources' / sex / f'first-person_{endpoint}.nif'
                actual, receipt = graft_resource(api, source, study, skeleton, target,
                                                 out / f'{sex}{endpoint}-public-export-scratch.nif', profile['hiddenShapes'])
                tri_target = target.parent / tri.name
                if not tri_target.exists():
                    shutil.copyfile(tri, tri_target)
                if resource.sha256(tri_target) != resource.sha256(tri):
                    raise ValueError('Absolute TRI bytes changed')
                report['bodies'][sex + str(endpoint)]['serializedCandidate'] = receipt
            report['joins'] = {}
            if reuse_joins is not None:
                reused_pins = reuse_verified_joins(reuse_joins, report)
            else:
                for sex in ('female', 'male'):
                    old = [api.NifFile(str(body_root / f'{sex}bodywerewolf_{i}.nif')) for i in (0, 1)]
                    new = [api.NifFile(str(out / 'resources' / sex / f'first-person_{i}.nif')) for i in (0, 1)]
                    raw = Trip.from_filepath(str(body_root / (sex + 'bodywerewolf.tri'))).shapes
                    joins = audit_joins(*old, *new, skeleton, raw, sex)
                    target = out / (sex + '-join-audit.json')
                    target.write_text(json.dumps(joins, indent=2) + '\n', encoding='utf-8')
                    report['joins'][sex] = {'report': str(target), 'sha256': resource.sha256(target)}
            require_complete_candidate(report, out)
        elif reuse_joins is not None:
            raise ValueError('Join reuse requires --write-candidate')
        report['reusedEvidenceSha256'] = reused_pins
        all_pins = {**inputs, **source_pins, **dependencies, **mb_pins, **reused_pins}
        if any(resource.sha256(path) != digest for path, digest in all_pins.items()):
            raise ValueError('Source or dependency changed during study')
        report['status'] = ('offline-first-person-neck-graft-native-verified-joins-measured-runtime-pending' if write_candidate
                            else 'offline-neck-isolation-plan-measured-no-serialized-candidate')
    except Exception as exc:
        report['status'] = 'REJECTED-numeric-plan-no-candidate' if isinstance(exc, NumericPlanRejected) else 'failed'
        report['failure'] = str(exc)
        raise
    finally:
        (out / 'head-isolation-report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
