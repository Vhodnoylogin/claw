"""Blender BVH witness using the original generator's exact neutral inside helper.

No geometry is changed or rendered. Parity against body alone is a geometric
proxy, separate from file flags, fur/view occlusion and actual game visibility.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args=sys.argv[sys.argv.index('--')+1:]
p=argparse.ArgumentParser(description=__doc__)
for name in ('nif','pynifly','generator','skeleton','out'):p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--fit-contact', action='store_true', help='Fit and measure candidate capsules on exposed neutral skin')
p.add_argument('--primary-capsules', type=int, choices=range(1, 5), default=1)
p.add_argument('--fsmp-peer-report', type=Path, help='Verified test probe and payload')
p.add_argument('--fsmp-surface-report', type=Path, help='Packed collision receipt for the exact target NIF')
a=p.parse_args(args)
if a.out.exists():raise ValueError('Use a new visibility receipt')
if bool(a.fsmp_peer_report) != bool(a.fsmp_surface_report):
    p.error('Supply both FSMP receipts to plan peer contact')
sys.path.insert(0,str(a.pynifly))
from pyn import pynifly as api
api.NifFile.Load(str(a.pynifly/'NiflyDLL.dll'))
nif=api.NifFile(str(a.nif));shapes={s.name:s for s in nif.shapes};body,gen=shapes['body'],shapes['genitals']
sys.path.insert(0,str(a.generator.parent))
import breast_rig as rig
import numpy as np
skel=api.NifFile(str(a.skeleton))
def rest_vertices(shape):
    names=shape.bone_names;weights=rig.read_weights(shape,names)
    matrices=np.asarray([[rig.matrix(skel.nodes[name].global_transform)@rig.matrix(shape.get_shape_skin_to_bone(name))@rig.matrix(shape.global_to_skin) for name in names]])
    return rig.lbs(shape.verts,weights,matrices,normalize=True)[0]
body_vertices,gen_vertices=rest_vertices(body),rest_vertices(gen)
text=a.generator.read_text(encoding='utf-8')
tree=ast.parse(text);function=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_inside')
helper=ast.get_source_segment(text,function)
scope={'Vector':Vector,'_DIRS':[Vector(d).normalized() for d in ((0,1,0),(0,-1,0),(1,0,0),(-1,0,0),(0,0,-1))],
    '_skin':BVHTree.FromPolygons([Vector(v) for v in body_vertices],body.tris)}
exec(compile(helper,str(a.generator)+'::_inside','exec'),scope)
inside=[scope['_inside'](Vector(v)) for v in gen_vertices]
external=[i for i,x in enumerate(inside) if not x]
external_set=set(external)
triangles=[t for t in gen.tris if all(i in external_set for i in t)]
ancestry=[];node=gen
while node:
    ancestry.append({'name':node.name,'flags':node.flags,'hiddenBit':bool(node.flags&1)})
    node=node.parent
result={'scope':'Exact original generator five-ray BVH body-parity proxy on unchanged neutral geometry; no rendering/game/FSMP acceptance.',
    'nif':str(a.nif),'nifSha256':hashlib.sha256(a.nif.read_bytes()).hexdigest(),'generator':str(a.generator),
    'generatorSha256':hashlib.sha256(a.generator.read_bytes()).hexdigest(),'extractedInsideHelperSha256':hashlib.sha256(helper.encode()).hexdigest(),
    'neutralPoseMethod':'Existing rig.lbs + actual serialized binds and pinned skeleton world frames; normalized packed weights. No identity-shape-frame assumption.',
    'skeletonSha256':hashlib.sha256(a.skeleton.read_bytes()).hexdigest(),
    'vertices':len(inside),'bodyParityInside':sum(inside),'bodyParityOutside':len(external),
    'tubeOutside':sum(i<442 for i in external),'ballsOutside':sum(i>=442 for i in external),
    'fullyOutsideTriangles':len(triangles),'outsideVertexSample':[{'index':i,'position':gen.verts[i]} for i in external[:8]],
    'actualFlagAncestry':ancestry,'materialPaths':gen.textures,
    'limits':'Parity is not an exact solid/visibility oracle for an open mesh. Fur and camera can occlude exterior geometry. File-visible does not prove a visible or acceptable attachment in game. Neutral state remains unchanged.'}

if a.fit_contact or a.fsmp_peer_report:
    repo = Path(__file__).resolve().parents[4]
    profile_path = repo / 'src/main/components/adult-anatomy/resources/neutral-rig.json'
    profile = json.loads(profile_path.read_text(encoding='utf-8'))
    if result['skeletonSha256'] != profile['inputs']['skeleton.nif'] or len(gen_vertices) != profile['vertices']:
        raise ValueError('Expected the exact neutral anatomy skeleton and vertex layout')
    fitter = repo / 'src/main/python/physics'
    sys.path.insert(0, str(fitter))

if a.fsmp_peer_report:
    from contact_fit import triangle_distance
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from peer_contact_geometry import expected_face_digest, plan, read_pinned_probe, verify_face_digest

    peer_points, radius, peer_digest = read_pinned_probe(a.fsmp_peer_report)
    face_digest, surface_digest = expected_face_digest(a.fsmp_surface_report, result['nifSha256'])
    drivers = profile['drivers']
    packed = rig.read_weights(gen, gen.bone_names).astype(np.float16).astype(np.float32)
    exposed = ~np.asarray(inside)
    faces = np.asarray(gen.tris, dtype=int)
    retained, targets = plan(
        gen_vertices, faces, exposed, packed[:, [gen.bone_names.index(name) for name in drivers]],
        peer_points, radius, lambda point: not scope['_inside'](Vector(point)), triangle_distance,
    )
    verify_face_digest(retained, face_digest)
    if not any(targets):
        raise ValueError('No robust separated/overlapping aim in the retained rest geometry')
    result['fsmpTrialAim'] = {
        'basis': 'Rest pose of the pinned skeleton, neutral morphs, test peer at unit scale',
        'peerReportSha256': peer_digest,
        'surfaceReportSha256': surface_digest,
        'providerFaceCount': len(retained),
        'providerFaceIndicesSha256': face_digest,
        'drivers': dict(zip(drivers, targets, strict=True)),
        'gameQualified': False,
    }

if a.fit_contact:
    from contact_fit import capsule, capsule_surface, partitions, signed_capsules, surface_metrics, triangle_distance

    def fit_float_capsule(points):
        fitted = capsule(points)
        # The attachment takes float32 endpoints/radius, so verify those actual values.
        for key in ('p1', 'p2'):
            fitted[key] = np.asarray(fitted[key], dtype=np.float32).tolist()
        gap = float(signed_capsules(points, [fitted]).max())
        radius = np.float32(fitted['radius'] + max(0.0, gap))
        fitted['radius'] = float(np.nextafter(radius, np.float32(np.inf)))
        return fitted

    tube = profile['tubeVertices']
    bilateral = profile['ballVerticesEach']
    boundaries = (0, tube, tube + bilateral, tube + 2 * bilateral)
    faces = np.asarray(gen.tris, dtype=int)
    exposed = np.zeros(len(gen_vertices), dtype=bool)
    exposed[external] = True
    caps = {}
    for driver, start, stop in zip(profile['drivers'], boundaries[:-1], boundaries[1:], strict=True):
        owned = (faces >= start) & (faces < stop)
        if np.any(owned.any(axis=1) != owned.all(axis=1)):
            raise ValueError('Unexpected shared triangle between anatomy regions')
        owned_faces = faces[owned.all(axis=1)]
        visible_faces = owned_faces[exposed[owned_faces].all(axis=1)]
        points = np.flatnonzero(exposed[start:stop]) + start
        if not len(visible_faces):
            raise ValueError('Missing exposed neutral triangles for ' + driver)
        frame = rig.matrix(skel.nodes[driver].global_transform)
        local = np.linalg.solve(frame, np.c_[gen_vertices, np.ones(len(gen_vertices))].T).T[:, :3]
        count = a.primary_capsules if start == 0 else 1
        support = [points] if count == 1 else partitions(local, visible_faces, count, method='compact-extreme')[0]
        fitted = [fit_float_capsule(local[ids]) for ids in support]
        largest_gap = float(signed_capsules(local[points], fitted).max())
        if largest_gap > 0:
            raise ValueError('Candidate capsule excludes fitted support')
        samples = []
        for i, cap in enumerate(fitted):
            surface = capsule_surface(cap)
            others = fitted[:i] + fitted[i+1:]
            samples.extend(surface[signed_capsules(surface, others) >= -1e-7])
        samples = np.asarray(samples)
        sample_world = (np.c_[samples, np.ones(len(samples))] @ frame.T)[:, :3]
        sample_exterior = [not scope['_inside'](Vector(v)) for v in sample_world]
        external_distance = triangle_distance(samples[sample_exterior], local[visible_faces])
        weights = dict(gen.bone_weights[driver])
        caps[driver] = {
            'shapes': fitted,
            'exteriorVertices': len(points),
            'drivenExteriorVertices': sum(bool(weights.get(i, 0) > 0) for i in points),
            'exteriorTriangles': len(visible_faces),
            'partiallyExteriorTriangles': int(np.count_nonzero(exposed[owned_faces].any(axis=1))) - len(visible_faces),
            'capsuleSurfaceSamplesOutsideTorso': sum(sample_exterior),
            'capsuleSurfaceSamples': len(samples),
            'exposedCapsuleToSkinMaxSampled': float(external_distance.max()) if len(external_distance) else None,
            'largestExteriorVertexGap': largest_gap,
            'surfaceDistances': surface_metrics(local, visible_faces, fitted),
        }
    result['contactCandidate'] = {
        'basis': 'Exact candidate-shape rest reconstruction, fitted in each named driver bone frame',
        'sampleScope': 'Finite rest-space estimates for fully exterior triangles; partially buried faces are counted separately',
        'profileSha256': hashlib.sha256(profile_path.read_bytes()).hexdigest(),
        'contactFitSha256': hashlib.sha256((fitter/'contact_fit.py').read_bytes()).hexdigest(),
        'capsules': caps,
        'gameQualified': False,
    }
with a.out.open('x', encoding='utf-8') as report:
    report.write(json.dumps(result, indent=2, allow_nan=False) + '\n')
print('NEUTRAL_VISIBILITY|'+json.dumps({k:result[k] for k in ('bodyParityInside','bodyParityOutside','tubeOutside','ballsOutside','fullyOutsideTriangles')}))
