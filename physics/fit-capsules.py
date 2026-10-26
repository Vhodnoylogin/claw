"""Measure a bounded morph-aware CBPC capsule model; never edit/install a mesh.

The numeric model has affine end points and affine radius. Every corner of
each node's *actual* 0..1 TRI support box is checked. Every selected vertex has
a fixed baseline segment fraction. Its residual from that fraction of the
affine segment is affine, so convexity of its norm and an affine upper radius
prove containment at every interior coefficient vector, including axis turns.
This proves selected rest-pose vertex containment, not anatomical surface fit,
animated skin containment, engine contact or full-body Havok behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
NODES = ("NPC EarL [EarL]Bone01", "NPC EarL [EarL]Bone02",
         "NPC EarR [EarR]Bone01", "NPC EarR [EarR]Bone02",
         "TailBone01", "TailBone02", "TailBone03", "TailBone04", "TailBone05")
MORPHS = ("CLAWHeadEarSize", "CLAWHeadEarTilt", "CLAWHeadMuzzleLong",
          "CLAWHeadMuzzleWide", "CLAWHeadSize", "CLAWTailFluff",
          "CLAWTailLength", "CLAWTailLift", "CLAWTorsoFlankWidth", "CLAWTorsoGirth")
BUNDLE_COUNTS = (8, 3, 8, 3, 5, 2, 1, 0, 2)
P1_NODES = ('NPC L Breast P1','NPC R Breast P1')
CONTACT_NODES = NODES+P1_NODES


def triangle_regions(shape, skeleton, records, nodes=NODES):
    """Whole mixed faces, uniquely assigned by average actual skin influence.

    The ownership threshold only selects which faces touch the requested ear/
    tail anatomy. Every vertex of a touching face is transformed by *all* its
    weights, including head/torso vertices across the boundary. No boundary
    face is silently discarded. Owners without vertices can still own faces.
    """
    vertices=finite_points(shape.verts); names=list(shape.bone_weights)
    weights=np.zeros((len(vertices),len(names)))
    for j,name in enumerate(names):
        for vertex,weight in shape.bone_weights[name]:weights[vertex,j]+=weight
    sums=weights.sum(axis=1)
    if not np.isfinite(weights).all() or weights.min()<0 or np.any(sums<=0):raise ValueError("Invalid full skin weights")
    normalized=weights/sums[:,None]
    transforms=np.einsum('vb,bjk->vjk',normalized,np.asarray([
        _matrix(skeleton.nodes[name].global_transform)@_matrix(shape.get_shape_skin_to_bone(name))@_matrix(shape.global_to_skin)
        for name in names]))
    world=np.einsum('vjk,vk->vj',transforms,np.column_stack([vertices,np.ones(len(vertices))]))[:,:3]
    target=np.column_stack([weights[:,names.index(node)] if node in names else np.zeros(len(vertices)) for node in nodes])
    dominant=weights.argmax(axis=1)
    selected=np.array([names[int(i)] in nodes and weights[v,int(i)]>=.5 for v,i in enumerate(dominant)])
    for node in P1_NODES:
        if node not in nodes or node not in names:continue
        side=float(skeleton.nodes[node].global_transform.translation[0])
        if abs(side)<1e-8:raise ValueError('P1 side node has no explicit rest X sign')
        selected|=(weights[:,names.index(node)]>1e-6)&(world[:,0]*side>0)
    faces=np.asarray(shape.tris,dtype=int).reshape(-1,3)
    face_ids=np.flatnonzero(selected[faces].any(axis=1)); selected_faces=faces[face_ids]
    ownership=np.argmax(target[selected_faces].mean(axis=1),axis=1)
    fields={}
    for (shape_name,morph,vertex),record in records.items():
        if shape_name!=shape.name:continue
        delta=fields.setdefault(morph,np.zeros_like(world))
        delta[vertex]=transforms[vertex,:3,:3]@(np.asarray(record.packed)*record.scale)
    result={}
    for owner,node in enumerate(nodes):
        local_faces=selected_faces[ownership==owner]
        if not len(local_faces):continue
        ids=np.unique(local_faces.reshape(-1)); mapping={int(v):i for i,v in enumerate(ids)}
        inverse=np.linalg.inv(_matrix(skeleton.nodes[node].global_transform))
        points=(np.column_stack([world[ids],np.ones(len(ids))])@inverse.T)[:,:3]
        deltas={name:delta[ids]@inverse[:3,:3].T for name,delta in fields.items() if np.max(abs(delta[ids]))>1e-12}
        result[node]=(points,deltas,{"shape":shape.name,"vertices":ids.tolist(),
            "fullRegionTriangles":[[mapping[int(v)] for v in face] for face in local_faces],
            "sourceTriangleIndices":face_ids[ownership==owner].tolist(),
            "mixedOwnershipTrianglesIncluded":int(np.sum(~selected[local_faces].all(axis=1))),
            "boundaryTrianglesExcluded":0,"packedWeightSumMaximumError":float(abs(sums[ids]-1).max()),
            "restLBSMatricesSha256":hashlib.sha256(transforms[ids].tobytes()).hexdigest(),
            "selectionRule":"actual positive side-matched minority P1 skin support" if node in P1_NODES else "dominant target influence >=0.5"})
    return result


def write_cpp_model(report,path):
    """Emit the exact schema3 evidence as a compiled immutable native model."""
    def vector(points):return '{'+','.join('{'+','.join(format(float(v),'.17g') for v in p)+'}' for p in points)+'}'
    lines=['#pragma once','#include "claw/PhysicsFit.h"','namespace claw::physics {',
           'inline const Model& CompiledModel(bool isFemale) {']
    for sex in ('male','female'):
        lines.append('static const Model '+sex+' = [] { Model m;')
        lines.append('m.identity='+json.dumps(report['modelIdentity'])+';')
        lines.append('m.morphs={'+','.join(json.dumps(n) for n in report['morphs'])+'};')
        lines.append('m.contactPasses='+str(report.get('contactPasses',0))+';')
        lines.append('m.weightDependent='+str(report.get('weightDependent',False)).lower()+';')
        for slot in report['slots']:
            if slot.get(sex) is None:
                lines.append('{ Slot s; s.node='+json.dumps(slot['node'])+'; s.active=false; m.slots.push_back(std::move(s)); }');continue
            model=report['regions'][sex+'/'+slot['node']]; ids=slot[sex]['partitionIndices']
            lines.append('{ Slot s; s.node='+json.dumps(slot['node'])+'; s.points='+vector(np.asarray(model['points'])[ids])+';')
            if 'weightDeltas' in model:lines.append('s.weightDeltas='+vector(np.asarray(model['weightDeltas'])[ids])+';')
            for name,delta in model['deltas'].items():
                values=np.asarray(delta)[ids]
                if np.max(abs(values))>1e-12:lines.append('s.fields.push_back({'+str(report['morphs'].index(name))+','+vector(values)+'});')
            if report.get('contactPasses',0):
                mapping={int(v):i for i,v in enumerate(ids)}
                faces=[[mapping[int(v)] for v in model['faces'][i]] for i in slot[sex]['triangleIndices']]
                lines.append('s.triangles={'+','.join('{'+','.join(str(v) for v in face)+'}' for face in faces)+'};')
            if 'axisHints' in model:
                lines.append('s.prescribedAxis=true; s.axis='+vector([model['axisHints'][slot['partition']]])[1:-1]+';')
                for name,values in model.get('axisDeltas',{}).items():
                    lines.append('s.axisFields.push_back({'+str(report['morphs'].index(name))+','+vector([values[slot['partition']]])+'});')
            lines.append('m.slots.push_back(std::move(s)); }')
        lines.append('return m; }();')
    lines.extend(['return isFemale ? '+ 'female : male;','}','}'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def write_cpp_fixtures(report,path):
    def values(row):return '{'+','.join(format(float(v),'.17g') for v in row)+'}'
    lines=['#pragma once','#include "claw/PhysicsFit.h"','namespace claw::physics {',
        'struct NumericFixture { bool female; std::string identity; std::vector<double> values; std::vector<Capsule> capsules; double weight{}; };',
        'inline const std::vector<NumericFixture>& CompiledFixtures() { static const std::vector<NumericFixture> result = {']
    for fixture in report['fixtures']:
        for sex in ('male','female'):
            caps='{'+','.join('{'+values(c['p1'])+','+values(c['p2'])+','+format(c['radius'],'.17g')+'}' for c in fixture['sexes'][sex]['capsules'])+'}'
            lines.append('{'+str(sex=='female').lower()+','+json.dumps(report['modelIdentity'])+','+
                values([fixture['values'].get(name,0.) for name in report['morphs']])+','+caps+','+format(fixture.get('weight',0.),'.17g')+'},')
    lines.extend(['}; return result; }','}'])
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')


def finite_points(value):
    p = np.asarray(value, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError("Expected finite Nx3 points")
    return p


def distance(points, p1, p2, radius):
    p = finite_points(points); a = np.asarray(p1, float); b = np.asarray(p2, float)
    axis = b - a; square = float(axis @ axis)
    t = np.zeros(len(p)) if square <= 1e-20 else np.clip((p - a) @ axis / square, 0, 1)
    return np.linalg.norm(p - a - t[:, None] * axis, axis=1) - float(radius)


def evaluate(model, values):
    if set(values) - set(model["coefficients"]):
        raise ValueError("Unknown capsule morph")
    result = {k:np.asarray(v, float).copy() if k != "radius" else float(v)
              for k, v in model["base"].items()}
    for name, coefficient in values.items():
        if isinstance(coefficient, bool) or not isinstance(coefficient, (int, float)) or not math.isfinite(coefficient) or not 0 <= coefficient <= 1:
            raise ValueError("Morph coefficients must be finite and in the qualified 0..1 box")
        for key in result:
            result[key] += np.asarray(model["coefficients"][name][key]) * coefficient
    if float(result["radius"]) <= 0:
        raise ValueError("Nonpositive capsule radius")
    return result


def describe(clearance):
    d = np.asarray(clearance, float)
    return {"points":len(d), "outsideFraction":float(np.mean(d > 1e-5)),
            "worstOutside":float(max(0., d.max())),
            "insideDepthP95":float(np.quantile(np.maximum(-d, 0), .95)),
            "insideDepthMax":float(np.maximum(-d, 0).max()),
            "absoluteVertexClearanceP95":float(np.quantile(abs(d), .95))}


def _affine_bound(design, values, upper):
    fit = np.linalg.lstsq(design, values, rcond=None)[0]
    residual = values - design @ fit
    fit[0] += (float(residual.max()) if upper else float(residual.min()))
    return fit


def _anchored_radius(design, wanted):
    """Keep neutral contact on the measured skin; raise only active slopes.

    Starting with a least-squares slope, each unsatisfied corner adds a positive
    correction to its active coefficients. Since corners are nonnegative this
    cannot invalidate an earlier corner. Negative shrink slopes are retained
    whenever the measured box allows them. This is a feasible envelope, not a
    claim of a globally optimal linear program.
    """
    base=float(wanted[0]); coefficients=np.zeros(design.shape[1])
    coefficients[0]=base
    if design.shape[1] == 1:return coefficients
    slopes=np.linalg.lstsq(design[1:,1:],wanted[1:]-base,rcond=None)[0]
    for row,value in sorted(zip(design[1:,1:],wanted[1:]),key=lambda x:(sum(x[0]),tuple(x[0]))):
        deficit=float(value-base-row@slopes)
        if deficit>0:slopes+=row*deficit/float(row@row)
    coefficients[1:]=slopes
    return coefficients


def fit(points, deltas, *, padding=1e-4):
    """An enclosing affine family over a fixed, bounded, linear skin field.

    Neither percentile rejection nor a radius cap silently discards skin. This
    single-capsule approximation can be loose; all depths and sampled surface
    separation must be reviewed before contact acceptance.
    """
    p = finite_points(points)
    if len(p) < 4 or not math.isfinite(padding) or not 0 < padding <= .01:
        raise ValueError("Insufficient points or invalid numeric padding")
    ds = {name:finite_points(delta) for name, delta in sorted(deltas.items())}
    if any(d.shape != p.shape for d in ds.values()) or len(ds) > 8:
        raise ValueError("Mismatched delta topology or excessive unreviewed support")
    ds = {name:d for name, d in ds.items() if np.max(abs(d)) > 1e-12}
    names = list(ds); fields = np.asarray(list(ds.values())) if ds else np.zeros((0, len(p), 3))
    centre = p.mean(axis=0); _, singular, vh = np.linalg.svd(p - centre, full_matrices=False)
    if singular[0] <= 1e-6:
        raise ValueError("Degenerate point cloud")
    axis = vh[0]
    # Fix SVD's arbitrary sign deterministically; coefficients never rotate it.
    if axis[int(np.argmax(abs(axis)))] < 0: axis = -axis
    corners = np.asarray(list(itertools.product((0., 1.), repeat=len(names)))).reshape(-1, len(names)) if names else np.zeros((1, 0))
    design = np.column_stack([np.ones(len(corners)), corners])
    clouds = p[None, :, :] + np.einsum('cm,mvk->cvk', corners, fields)
    relative=p-centre; along=relative@axis
    radial=np.linalg.norm(relative-along[:,None]*axis,axis=1)
    initial_radius=float(radial.max())+padding
    slack=np.sqrt(np.maximum(0.,initial_radius**2-radial**2))
    lower=float(np.min(along+slack)); upper=float(np.max(along-slack))
    if upper < lower: lower=upper=(lower+upper)*.5
    endpoints=np.asarray([centre+axis*lower,centre+axis*upper])
    segment=endpoints[1]-endpoints[0]; span=float(segment@segment)
    fraction=np.zeros(len(p)) if span<1e-20 else np.clip((p-endpoints[0])@segment/span,0,1)
    # Approximate each serialized morph as a local affine deformation. Residuals
    # are not dropped: the exact per-vertex corner bound below encloses them.
    x=np.column_stack([p-centre,np.ones(len(p))])
    endpoint_fields=[]; regression=[]
    for field in fields:
        affine=np.linalg.lstsq(x,field,rcond=1e-8)[0]
        transformed=np.column_stack([endpoints-centre,np.ones(2)])@affine
        endpoint_fields.append(transformed)
        regression.append(float(np.linalg.norm(x@affine-field,axis=1).max()))
    endpoint_fields=np.asarray(endpoint_fields) if names else np.zeros((0,2,3))
    corner_ends=endpoints+np.einsum('cm,mek->cek',corners,endpoint_fields)
    assigned=corner_ends[:,0,None,:]*(1-fraction)[None,:,None]+corner_ends[:,1,None,:]*fraction[None,:,None]
    wanted_radius=np.linalg.norm(clouds-assigned,axis=2).max(axis=1)+padding
    radius=_anchored_radius(design,wanted_radius)
    if (design@radius).min() <= 0: raise ValueError("Affine envelope has a nonpositive radius")
    base = {"p1":endpoints[0].tolist(),"p2":endpoints[1].tolist(),"radius":float(radius[0])}
    coefficients = {name:{"p1":endpoint_fields[i,0].tolist(),
                         "p2":endpoint_fields[i,1].tolist(),
                         "radius":float(radius[i+1])} for i, name in enumerate(names)}
    model = {"base":base, "coefficients":coefficients, "axis":axis.tolist(),
             "fitPoints":len(p), "proof":"all-corners-fixed-vertex-segment-fraction-convex-residual-envelope",
             "domain":[0., 1.], "padding":padding,
             "fixedSegmentFractions":fraction.tolist(),
             "affineFieldMaximumResiduals":dict(zip(names,regression))}
    checks = []
    for state, cloud in zip(corners, clouds):
        values = dict(zip(names, state.tolist())); cap = evaluate(model, values)
        residual = distance(cloud, **cap)
        if residual.max() > 1e-8:
            raise ValueError("Corner containment proof failed")
        checks.append({"values":values, "capsule":{k:np.asarray(v).tolist() for k,v in cap.items()},
                       "coverage":describe(residual)})
    # These are additional diagnostics, not a replacement for the corner proof.
    rng = np.random.default_rng(20261026)
    heldout = []
    for state in rng.random((12, len(names))):
        cap = evaluate(model, dict(zip(names, state.tolist())))
        residual = distance(p + np.einsum('m,mvk->vk', state, fields), **cap)
        if residual.max() > 1e-8: raise ValueError("Interior containment check failed")
        heldout.append(describe(residual))
    model["verification"] = {"cornerCount":len(checks), "corners":checks, "heldout":heldout,
                              "selectedVertexCoverage":True, "surfaceFitAccepted":False,
                              "gameValidated":False}
    return model


def fit_bundle(points, deltas, count, triangles=None):
    """Fixed geometric strips, choosing the measured least-loose PCA direction.

    Partitions are frozen before morphing. Each supplied full region triangle
    is assigned to one partition by its neutral centroid, and all three of its
    vertices are included there. Convexity of a capsule then also encloses the
    complete linear triangle at every qualified coefficient vector.
    """
    p=finite_points(points)
    if type(count) is not int or not 1 <= count <= 8 or len(p) < count*4:
        raise ValueError("Invalid bundle count or insufficient region points")
    faces=np.asarray(triangles if triangles is not None else [],dtype=int).reshape(-1,3)
    if faces.size and (faces.min()<0 or faces.max()>=len(p)):raise ValueError("Invalid region triangle")
    if count == 1:
        model=fit(p,deltas); model["partitionIndices"]=list(range(len(p)))
        model["triangleIndices"]=list(range(len(faces)))
        return [model], {"method":"single", "count":1}
    _,_,axes=np.linalg.svd(p-p.mean(axis=0),full_matrices=False)
    choices=[]; partitions=[]
    for direction,axis in enumerate(axes):
        if axis[int(np.argmax(abs(axis)))] < 0:axis=-axis
        order=np.argsort(p@axis,kind="stable")
        partitions.append((np.array_split(order,count),{"method":"fixed-PCA-equal-count-strips",
                           "axis":axis.tolist(),"direction":direction}))
    # A curved ear base need not follow one straight strip. Try compact spatial
    # groups too; seed every group deterministically by farthest-point distance.
    centres=[p[int(np.argmin(p@axes[0]))]]
    while len(centres)<count:
        square=np.min(np.sum((p[:,None,:]-np.asarray(centres)[None,:,:])**2,axis=2),axis=1)
        centres.append(p[int(np.argmax(square))])
    centres=np.asarray(centres); labels=np.full(len(p),-1)
    for _ in range(50):
        next_labels=np.argmin(np.sum((p[:,None,:]-centres[None,:,:])**2,axis=2),axis=1)
        if np.array_equal(labels,next_labels):break
        labels=next_labels
        if any(np.sum(labels==i)<4 for i in range(count)):break
        centres=np.asarray([p[labels==i].mean(axis=0) for i in range(count)])
    groups=[np.flatnonzero(labels==i) for i in range(count)]
    if all(len(ids)>=4 for ids in groups):
        partitions.append((groups,{"method":"fixed-farthest-seeded-spatial-kmeans","direction":"spatial"}))
    for groups,description in partitions:
        triangle_groups=[[] for _ in groups]
        if len(faces):
            group_centres=np.asarray([p[ids].mean(axis=0) for ids in groups])
            centroids=p[faces].mean(axis=1)
            assignment=np.argmin(np.sum((centroids[:,None,:]-group_centres[None,:,:])**2,axis=2),axis=1)
            expanded=[]
            for i,ids in enumerate(groups):
                tri_ids=np.flatnonzero(assignment==i);triangle_groups[i]=tri_ids.tolist()
                expanded.append(np.unique(np.concatenate([ids,faces[tri_ids].reshape(-1)])))
            groups=expanded
        models=[]
        for group,ids in enumerate(groups):
            model=fit(p[ids],{name:delta[ids] for name,delta in deltas.items()})
            model["partitionIndices"]=ids.tolist();model["triangleIndices"]=triangle_groups[group];models.append(model)
        # Weight by source points so small partitions cannot dominate the score.
        neutral=sum(m["fitPoints"]*m["verification"]["corners"][0]["coverage"]["insideDepthP95"] for m in models)/len(p)
        extreme=sum(m["fitPoints"]*max(c["coverage"]["insideDepthP95"] for c in m["verification"]["corners"]) for m in models)/len(p)
        score=neutral+extreme
        choices.append((score,models,{**description, "count":count,
                                      "neutralPointWeightedDepthP95":neutral,
                                      "worstCornerPointWeightedDepthP95":extreme}))
    _,models,choice=min(choices,key=lambda c:c[0])
    choice["alternatives"]=[{"direction":c[2]["direction"],"score":c[0]} for c in choices]
    return models,choice


def _matrix(transform):
    result=np.eye(4); result[:3,:3]=np.asarray(transform.rotation)*float(transform.scale)
    result[:3,3]=list(transform.translation)
    return result


def _shape_fields(shape, skeleton, node, records):
    """Normalized packed-weight rest LBS, then the selected XP32 node frame.

    Read every influence, not just the dominant bone. Weight ownership selects a
    region; it does not replace the actual skin deformation transform.
    """
    vertices=finite_points(shape.verts); names=list(shape.bone_weights)
    weights=np.zeros((len(vertices), len(names)))
    for j, name in enumerate(names):
        for vertex, weight in shape.bone_weights[name]: weights[vertex,j] += weight
    if not np.isfinite(weights).all() or weights.min() < 0 or np.any(weights.sum(axis=1) <= 0):
        raise ValueError("Invalid serialized skin weights")
    if node not in names: return None
    j=names.index(node)
    selected=np.flatnonzero((weights[:,j] >= .5) & (weights.argmax(axis=1) == j))
    if not len(selected): return None
    normalized=weights[selected] / weights[selected].sum(axis=1)[:, None]
    inverse=np.linalg.inv(_matrix(skeleton.nodes[node].global_transform))
    bind=np.asarray([inverse @ _matrix(skeleton.nodes[name].global_transform) @
                     _matrix(shape.get_shape_skin_to_bone(name)) @ _matrix(shape.global_to_skin)
                     for name in names])
    transforms=np.einsum('vb,bjk->vjk', normalized, bind)
    points=np.einsum('vjk,vk->vj', transforms, np.column_stack([vertices[selected], np.ones(len(selected))]))[:,:3]
    by_morph={}
    selected_map={int(v):i for i,v in enumerate(selected)}
    for (shape_name, morph, vertex), record in records.items():
        if shape_name != shape.name or vertex not in selected_map: continue
        delta=by_morph.setdefault(morph, np.zeros((len(selected),3)))
        i=selected_map[vertex]
        delta[i]=transforms[i,:3,:3] @ (np.asarray(record.packed)*record.scale)
    faces=np.asarray(shape.tris,dtype=int)
    complete=np.asarray([[selected_map[int(v)] for v in face] for face in faces if all(int(v)in selected_map for v in face)],dtype=int).reshape(-1,3)
    touching=sum(any(int(v)in selected_map for v in face) for face in faces)
    return points, by_morph, {"shape":shape.name, "vertices":selected.tolist(),
                               "fullRegionTriangles":complete.tolist(),
                               "boundaryTrianglesExcluded":int(touching-len(complete)),
                               "packedWeightSumMaximumError":float(abs(weights[selected].sum(axis=1)-1).max())}


def safe_output(path, inputs):
    out=Path(path).resolve()
    if out.exists(): raise ValueError("Output must be a new external directory")
    if any(x.casefold() in {"mods", "data", "downloads", "overwrite", "mo2", "mo2 se", "modorganizer"} for x in out.parts):
        raise ValueError("Output cannot target a live game/mod/archive tree")
    if ROOT == out or ROOT in out.parents or any(p.resolve().parent == out or p.resolve().parent in out.parents for p in inputs):
        raise ValueError("Output cannot be in a source directory")
    return out


def solid_tail(regions,sex,skeleton,count,prescribe=False):
    """Keep opposite tail surfaces together in axial solid sections.

    A whole connected tail is partitioned before assigning its sections to the
    nearest existing XP32 node. This avoids clustering separate circumference
    patches into outward-facing spheres. A section's tangent is derived from
    neighboring section centres; its signed TRI tangent field comes from local
    affine regression. Every actual support point still sets the enclosing
    radius, so direction regression never discards a skin residual.
    """
    import contact_fit as contact
    chunks=[]; fields=[]; faces=[];offset=0;names=set();source=[]
    for node in NODES[4:]:
        region=regions.pop(sex+'/'+node,None)
        if region is None:continue
        frame=_matrix(skeleton.nodes[node].global_transform);p=np.asarray(region['points'])
        chunks.append((np.column_stack([p,np.ones(len(p))])@frame.T)[:,:3])
        fields.append({n:np.asarray(v)@frame[:3,:3].T for n,v in region['deltas'].items()});names.update(region['morphs'])
        faces.extend((np.asarray(region['faces'])+offset).tolist());offset+=len(p);source.extend(region['sources'])
    p=np.concatenate(chunks);names=sorted(names)
    ds={n:np.concatenate([d.get(n,np.zeros_like(points)) for points,d in zip(chunks,fields)]) for n in names}
    groups,tri_groups=contact.partitions(p,faces,count,'strips-0');centres=np.asarray([p[g].mean(axis=0) for g in groups])
    positions=np.asarray([list(skeleton.nodes[node].global_transform.translation) for node in NODES[4:]])
    owners=np.argmin(np.sum((centres[:,None,:]-positions[None,:,:])**2,axis=2),axis=1)
    face_array=np.asarray(faces,dtype=int)
    for owner,node in enumerate(NODES[4:]):
        assigned=np.flatnonzero(owners==owner)
        if not len(assigned):continue
        chosen=np.unique(np.concatenate([groups[i] for i in assigned]));mapping={int(v):i for i,v in enumerate(chosen)}
        inverse=np.linalg.inv(_matrix(skeleton.nodes[node].global_transform))
        local=(np.column_stack([p[chosen],np.ones(len(chosen))])@inverse.T)[:,:3]
        deltas={n:ds[n][chosen]@inverse[:3,:3].T for n in names}
        part=[[mapping[int(v)] for v in groups[i]] for i in assigned]
        owned_faces=[];face_groups=[];axes=[];axis_fields={n:[] for n in names}
        for i in assigned:
            tri_ids=tri_groups[i];start=len(owned_faces)
            owned_faces.extend([[mapping[int(v)] for v in face] for face in face_array[tri_ids]])
            face_groups.append(list(range(start,len(owned_faces))))
            direction=centres[min(len(centres)-1,i+1)]-centres[max(0,i-1)]
            direction=inverse[:3,:3]@direction;direction/=np.linalg.norm(direction);axes.append(direction.tolist())
            local_ids=np.asarray(part[len(axes)-1]);x=np.column_stack([local[local_ids]-local[local_ids].mean(axis=0),np.ones(len(local_ids))])
            for name in names:
                affine=np.linalg.lstsq(x,deltas[name][local_ids],rcond=1e-8)[0]
                axis_fields[name].append((direction@affine[:3]).tolist())
        regions[sex+'/'+node]={"points":local.tolist(),"deltas":{n:v.tolist() for n,v in deltas.items()},
            "faces":owned_faces,"partitions":part,"triangleGroups":face_groups,"morphs":names,"padding":1e-4,
            "sources":source,
            "partitionChoice":"whole-tail-axial-solid-sections-nearest-existing-XP32-node",
            "tangentRule":"current deformed support PCA"}
        if prescribe:
            regions[sex+'/'+node].update(axisHints=axes,axisDeltas=axis_fields,
                tangentRule="neighboring neutral section centroids with local signed affine TRI tangent regression; radius retains all actual residuals")


def build_current(args,api,records_by_sex,skeleton,snapshots,out):
    import contact_fit as contact
    counts=tuple(int(x) for x in args.current_counts.split(',')) if args.current_counts else (8,3,8,3,5,2,1,0,2)
    if len(counts)!=len(NODES) or min(counts)<0 or sum(counts)>128:raise ValueError("Supply nine current counts, total <=128")
    p1_counts=tuple(int(x) for x in args.female_p1_counts.split(','))
    if len(p1_counts)!=2 or min(p1_counts)<0 or sum(counts)+sum(p1_counts)>128:raise ValueError('Female P1 counts require two nonnegative counts within total128 budget')
    count_map=dict(zip(CONTACT_NODES,counts+p1_counts));weight_dependent=bool(args.male_nif_1 or args.female_nif_1)
    if weight_dependent and not(args.male_nif_1 and args.female_nif_1):raise ValueError('Independent weight requires both sex endpoint1 NIFs')
    if args.solid_tail and weight_dependent:raise ValueError('Experimental solid-tail regrouping is not weight-qualified')
    if args.solid_tail and args.tail_axis=='tangent' and args.contact_passes:raise ValueError('Prescribed-axis contact optimization is not a supported family')
    report={"schemaVersion":3,"frame":"node-local-game-units","domain":[0.,1.],
            "status":"offline-current-vector-triangle-fit","runtimeQualified":False,"gameValidated":False,
            "evaluator":"deform-actual-normalized-rest-LBS-support-then-PCA-refit-v1",
            "ownership":"Each face touching a >=.5 dominant ear/tail vertex is owned once by mean full target skin influence; all three full-LBS vertices retained",
            "sourceInputs":[{"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()} for p,b in snapshots.items()],
            "regions":{},"slots":[],"omittedNodes":[],"geometryChangesWithMorphVector":True,
            "proofScope":"For each current vector, every support vertex and assigned complete mixed skin triangle is enclosed by its freshly fitted convex capsule. This is an algebraic current-state containment property, not an affine full-box envelope or animated-skin proof.",
            "excluded":"fur/blend layers, faces with no dominant ear/tail vertex, animation/pose/actor or bone scale, engine contact and Havok"}
    report.update(weightDependent=weight_dependent,weightDomain=[0.,1.],
        weightFormula='P0 + independentActorWeight*(P1-P0) + sum(actualEffectiveMorph*absoluteTRIdelta)',
        coveredShapes=args.skin_shapes.split(','),femaleP1Contacts=bool(sum(p1_counts)),endpointChecks=[])
    report['configuration']={'requestedEarTailCounts':list(counts),'requestedFemaleP1Counts':list(p1_counts),
        'partitionMethod':args.partition_method,'solidTail':args.solid_tail,'tailAxis':args.tail_axis,
        'contactPasses':args.contact_passes,'fixtureSet':args.fixture_set,'signedDiagnostics':args.signed_diagnostics,
        'independentWeightSamples':[0.,.5,1.] if weight_dependent else [0.],
        'requireDistinctWeightEndpoints':args.require_distinct_weight_endpoints}
    if args.contact_passes:
        report.update(contactPasses=args.contact_passes,evaluator='deform-rest-LBS-support-then-symmetric-triangle-contact-minimax-RMS-v3',
            proofScope='Finite symmetric skin/capsule-surface minimax/RMS optimization at each actual vector. Explicit measured undercoverage and separation replace unconditional convex containment. No continuous Hausdorff, animation or game-contact proof.',
            constructionObjective={'maximumSampleDistanceWeight':1.,'rmsSampleDistanceWeight':.2,'coordinatePasses':args.contact_passes,'objectiveImprovementEpsilon':1e-7,
                'axisComponentTieEpsilon':1e-10,'pcaVarianceRelativeTieEpsilon':1e-12,'targetSampleP95GameUnits':1.,'targetIsNotAcceptanceThreshold':True})
    for sex in ('male','female'):
        mesh=api.NifFile(str(getattr(args,sex+'_nif'))); chunks={node:[] for node in CONTACT_NODES}
        mesh1=api.NifFile(str(getattr(args,sex+'_nif_1'))) if weight_dependent else None
        chosen_nodes=NODES+tuple(n for n in P1_NODES if sex=='female' and count_map[n])
        weight_chunks={node:[] for node in CONTACT_NODES}
        for shape in args.skin_shapes.split(','):
            if shape not in mesh.shape_dict:raise ValueError('Explicit skin shape missing: '+shape)
            selected=triangle_regions(mesh.shape_dict[shape],skeleton,records_by_sex[sex],chosen_nodes)
            other=triangle_regions(mesh1.shape_dict[shape],skeleton,records_by_sex[sex],chosen_nodes) if mesh1 is not None else selected
            if set(selected)!=set(other):raise ValueError('Weight endpoint changes triangle ownership')
            for node,row in selected.items():
                endpoint=other[node]
                if row[2]['vertices']!=endpoint[2]['vertices'] or row[2]['fullRegionTriangles']!=endpoint[2]['fullRegionTriangles'] or row[2]['restLBSMatricesSha256']!=endpoint[2]['restLBSMatricesSha256']:
                    raise ValueError('Weight endpoint changed topology or actual normalized rest skin matrices')
                if set(row[1])!=set(endpoint[1]) or any(not np.array_equal(row[1][name],endpoint[1][name]) for name in row[1]):
                    raise ValueError('Weight endpoint changed absolute TRI skin field')
                chunks[node].append(row);weight_chunks[node].append(endpoint[0]-row[0])
                report['endpointChecks'].append({'sex':sex,'shape':shape,'node':node,'vertices':len(row[0]),
                    'sameTopologyAndRestLBSMatrices':True,'sameAbsoluteTRIFields':True,'maximumWeightDisplacement':float(np.linalg.norm(endpoint[0]-row[0],axis=1).max())})
        for node,rows in chunks.items():
            if not rows:continue
            p=np.concatenate([row[0] for row in rows]); names=sorted({n for row in rows for n in row[1]})
            d={name:np.concatenate([row[1].get(name,np.zeros_like(row[0])) for row in rows]) for name in names}
            faces=[]; offset=0
            for points,_,source in rows:
                faces.extend((np.asarray(source['fullRegionTriangles'])+offset).tolist()); offset+=len(points)
            count=count_map[node]
            if count==0:raise ValueError("Current counts omit a face-bearing node: "+node)
            partition,groups=contact.partitions(p,faces,count)
            choices=[]
            if args.partition_method=='auto':
                for method in ('compact','strips-0','strips-1','strips-2'):
                    ids,tri_ids=contact.partitions(p,faces,count,method)
                    caps=[contact.capsule(p[group]) for group in ids]
                    measure=contact.surface_metrics(p,faces,caps)
                    score=measure['capsuleToSkinP95']+.25*measure['capsuleToSkinMaxSampled']
                    choices.append((score,method,ids,tri_ids))
                _,method,partition,groups=min(choices,key=lambda row:row[0])
            elif args.partition_method!='compact':
                partition,groups=contact.partitions(p,faces,count,args.partition_method)
            report['regions'][sex+'/'+node]={"points":p.tolist(),"deltas":{n:v.tolist() for n,v in d.items()},
                "faces":faces,"partitions":partition,"triangleGroups":groups,"morphs":names,"padding":1e-4,
                "sources":[row[2] for row in rows],"partitionChoice":method if choices else args.partition_method,
                "partitionScores":[{'score':row[0],'method':row[1]} for row in choices],"contactPasses":args.contact_passes}
            if weight_dependent:report['regions'][sex+'/'+node]['weightDeltas']=np.concatenate(weight_chunks[node]).tolist()
    if args.solid_tail:
        for sex in ('male','female'):solid_tail(report['regions'],sex,skeleton,sum(counts[4:]),args.tail_axis=='tangent')
        for region in report['regions'].values():region['contactPasses']=args.contact_passes
    actual=sorted({name for region in report['regions'].values() for name in region['morphs']})
    if len(actual)>32:raise ValueError("Current model has more than 32 actual dependencies")
    report['morphs']=actual
    for node in CONTACT_NODES:
        pair=[report['regions'].get(sex+'/'+node) for sex in ('male','female')]
        if pair[0] is None or pair[1] is None:
            if pair==[None,None]:
                if node in P1_NODES and count_map[node]:raise ValueError('Requested P1 has no actual body-skin region: '+node)
                report['omittedNodes'].append({"node":node,"reason":"No touching skin face assigned by mean influence; not a silently missing source triangle"});continue
            if not(node in P1_NODES and pair[0] is None and pair[1] is not None):raise ValueError("Unsupported sex-specific current-vector region layout")
        if pair[0] is not None and len(pair[0]['partitions'])!=len(pair[1]['partitions']):raise ValueError("Sex-specific partition count")
        for i in range(len(pair[1]['partitions'])):
            report['slots'].append({"node":node,"partition":i,"sexMask":"female" if pair[0] is None else "both",**{sex:None if region is None else {"partitionIndices":region['partitions'][i],"triangleIndices":region['triangleGroups'][i]}
                for sex,region in zip(('male','female'),pair)}})
    canonical=json.dumps({k:report[k] for k in ('evaluator','morphs','regions','slots','weightDependent')},sort_keys=True,separators=(',',':')).encode()
    report['modelIdentity']='CLAW.Physics.CurrentVector.'+hashlib.sha256(canonical).hexdigest()
    states=[('neutral',{}),('all-1',dict.fromkeys(actual,1.)),('mixed-035',dict.fromkeys(actual,.35)),
            ('alternating',{n:float(i%2) for i,n in enumerate(actual)})]
    if args.fixture_set=='full':
        states.extend((name+'-1',{name:1.}) for name in actual)
        rng=np.random.default_rng(20261026)
        states.extend(('heldout-'+str(i),dict(zip(actual,row.tolist()))) for i,row in enumerate(rng.random((6,len(actual)))))
    report['fixtureSet']=args.fixture_set
    states.append(('return-neutral',{})); fixtures=[]
    weighted_states=[(label,values,weight) for weight in ([0.,.5,1.] if weight_dependent else [0.]) for label,values in states]
    for label,values,weight in weighted_states:
        entry={"name":label,"values":values,"weight":weight,"sexes":{}}
        for sex in ('male','female'):
            caps=[]; metrics={}; maxoutside=0.; world_points=[];world_faces=[];world_caps=[];world_offset=0;bundles={}
            for node in CONTACT_NODES:
                region=report['regions'].get(sex+'/'+node)
                if region is None:continue
                selected={n:values.get(n,0.) for n in region['morphs']}; points=contact.deform(region,selected,weight)
                bundle=contact.evaluate(region,selected,weight);bundles[node]=bundle
                outside=float(contact.signed_capsules(points,bundle).max());maxoutside=max(maxoutside,outside)
                if outside>1e-8 and not args.contact_passes:raise ValueError("Current-vector containment failed")
                if label in ('neutral','all-1','mixed-035','alternating'):
                    metrics[node]=contact.surface_metrics(points,region['faces'],bundle)
                    frame=_matrix(skeleton.nodes[node].global_transform)
                    world_points.extend((np.column_stack([points,np.ones(len(points))])@frame.T)[:,:3])
                    world_faces.extend((np.asarray(region['faces'])+world_offset).tolist());world_offset+=len(points)
                    for cap in bundle:
                        world_caps.append({"p1":(frame@np.r_[cap['p1'],1])[:3].tolist(),
                            "p2":(frame@np.r_[cap['p2'],1])[:3].tolist(),"radius":cap['radius']*float(skeleton.nodes[node].global_transform.scale)})
            if world_faces and args.signed_diagnostics:
                from contact_diagnostics import signed_witnesses
                details=signed_witnesses(world_points,world_faces,world_caps);global_surface=details.pop('surfaceMetrics')
                global_surface['signedDiagnostics']=details
            else:global_surface=contact.surface_metrics(world_points,world_faces,world_caps) if world_faces else None
            caps=[bundles[slot['node']][slot['partition']] if slot.get(sex) is not None else {'p1':[0.,0.,0.],'p2':[0.,0.,0.],'radius':0.} for slot in report['slots']]
            entry['sexes'][sex]={"capsules":caps,"worstSupportOutside":maxoutside,"surface":metrics,
                "wholeSelectedSurface":global_surface,"activeSlots":[i for i,slot in enumerate(report['slots']) if slot.get(sex) is not None],
                "regionSurfaceLimit":"Regional seams/endcaps may be hidden by neighboring node capsules; use wholeSelectedSurface for union fit."}
        fixtures.append(entry)
    report['returnNeutralChecks']=[]
    for weight in ([0.,.5,1.] if weight_dependent else [0.]):
        for sex in ('male','female'):
            neutral=next(f['sexes'][sex]['capsules'] for f in fixtures if f['name']=='neutral' and f['weight']==weight)
            high=next(f['sexes'][sex]['capsules'] for f in fixtures if f['name']=='all-1' and f['weight']==weight)
            returned=next(f['sexes'][sex]['capsules'] for f in fixtures if f['name']=='return-neutral' and f['weight']==weight)
            if neutral!=returned:raise ValueError('Return to neutral changed current-vector geometry')
            report['returnNeutralChecks'].append({'sex':sex,'weight':weight,'identicalNeutralCapsules':True,
                'radiiReducedOnReturn':sum(h['radius']>n['radius']+1e-8 for h,n in zip(high,neutral)),
                'radiiIncreasedOnReturn':sum(h['radius']<n['radius']-1e-8 for h,n in zip(high,neutral)),
                'inactiveSlots':sum(c['radius']==0 for c in neutral)})
    report['fixtures']=fixtures; report['surfaceFitAccepted']=False
    report['surfaceAcceptanceNote']='Measured finite sampled distances are retained; engine acceptance and explicit anatomical tolerances remain required.'
    for p,b in snapshots.items():
        if p.read_bytes()!=b:raise ValueError("Input changed during current-vector fit: "+str(p))
    out.mkdir(parents=True)
    (out/'fitted-capsules.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    write_cpp_model(report,out/'physics-fit-model.h')
    write_cpp_fixtures(report,out/'physics-fit-fixtures.h')
    (out/'runtime-fixtures.json').write_text(json.dumps({"modelIdentity":report['modelIdentity'],"morphs":actual,
        "nodes":[slot['node'] for slot in report['slots']],"fixtures":fixtures},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({"status":report['status'],"slots":len(report['slots']),"morphs":len(actual),"output":str(out)}))
    return 0


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for sex in ("male", "female"):
        parser.add_argument("--"+sex+"-nif", type=Path, required=True)
        parser.add_argument("--"+sex+"-nif-1", type=Path,help='Distinct reviewed high-weight endpoint; requires matching other sex endpoint')
        parser.add_argument("--"+sex+"-tri", type=Path, required=True)
    parser.add_argument("--skeleton", type=Path, required=True)
    parser.add_argument("--pynifly", type=Path, help="Installed PyNifly addon directory (read only)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundles", action="store_true", help="Explicit 32-slot fitted bundle candidate; never changes the legacy eight-slot model")
    parser.add_argument("--current-vector",action="store_true",help="Schema3 exact current-vector refit; separate native model, not affine Papyrus input")
    parser.add_argument("--current-counts",help="Nine comma-separated requested triangle group counts; total <=128")
    parser.add_argument("--partition-method",default='compact',choices=['auto','compact','strips-0','strips-1','strips-2'])
    parser.add_argument("--solid-tail",action='store_true',help='Partition the connected tail into solid axial sections before node assignment')
    parser.add_argument("--tail-axis",default='pca',choices=['pca','tangent'],help='Current PCA or experimental signed TRI section tangent for solid tail')
    parser.add_argument("--skin-shapes",default='body,head',help='Explicit comma-separated bound skin shapes; include anatomical head split pieces')
    parser.add_argument("--contact-passes",type=int,default=0,choices=range(9),help='Symmetric current-vector contact optimization passes, rather than an enclosing capsule objective')
    parser.add_argument("--fixture-set",default='full',choices=['full','compact'],help='Compact four-state trial or full per-field/random/return numeric fixtures')
    parser.add_argument("--female-p1-counts",default='0,0',help='Explicit female-only left,right P1 body-skin capsule counts within total128 budget')
    parser.add_argument("--signed-diagnostics",action='store_true',help='Retain oriented nearest-face signed distributions and exact worst witnesses with explicit sign limits')
    parser.add_argument("--contact-recipe",type=Path,help='Explicit development contact recipe; command-line values override its defaults')
    parser.add_argument("--require-distinct-weight-endpoints",action='store_true')
    args=parser.parse_args(argv)
    try:
        if args.contact_recipe is not None:
            recipe=json.loads(args.contact_recipe.read_bytes())
            if recipe.get('schemaVersion')!=1 or recipe.get('weightDomain')!=[0.,1.] or recipe.get('morphDomain')!=[0.,1.]:raise ValueError('Unsupported contact recipe domains')
            provided=list(sys.argv[1:] if argv is None else argv)
            options={'skinShapes':('skin_shapes',lambda v:','.join(v)),
                'currentCounts':('current_counts',lambda v:','.join(str(x) for x in v)),
                'femaleP1Counts':('female_p1_counts',lambda v:','.join(str(x) for x in v)),
                'partitionMethod':('partition_method',str),'contactPasses':('contact_passes',int),
                'fixtureSet':('fixture_set',str),'signedDiagnostics':('signed_diagnostics',bool),
                'requireDistinctWeightEndpoints':('require_distinct_weight_endpoints',bool)}
            for key,(attribute,convert) in options.items():
                option='--'+attribute.replace('_','-')
                if key in recipe and not any(value==option or value.startswith(option+'=') for value in provided):setattr(args,attribute,convert(recipe[key]))
            if args.contact_passes not in range(9) or args.fixture_set not in ('full','compact') or args.partition_method not in ('compact','auto','strips-0','strips-1','strips-2'):raise ValueError('Unsupported contact recipe options')
        if args.require_distinct_weight_endpoints:
            for sex in ('male','female'):
                endpoint=getattr(args,sex+'_nif_1')
                if endpoint is None or endpoint.read_bytes()==getattr(args,sex+'_nif').read_bytes():raise ValueError('Distinct reviewed '+sex+' low/high weight endpoints required')
        sys.path.insert(0, str(ROOT/"scripts"))
        import breast_rig, tri_patch
        api, _, addon=breast_rig.load_pynifly(args.pynifly)
        paths=[args.male_nif,args.male_tri,args.female_nif,args.female_tri,args.skeleton,
               Path(__file__), ROOT/"scripts/breast_rig.py", ROOT/"scripts/tri_patch.py",
               addon/"NiflyDLL.dll", addon/"pyn/pynifly.py"]
        if args.current_vector:paths.extend([ROOT/'physics/contact_fit.py',ROOT/'distribution/include/claw/PhysicsFit.h'])
        paths.extend(path for path in (args.male_nif_1,args.female_nif_1) if path is not None)
        if args.signed_diagnostics:paths.append(ROOT/'physics/contact_diagnostics.py')
        if args.contact_recipe is not None:paths.append(args.contact_recipe)
        snapshots={p.resolve():p.read_bytes() for p in paths}
        out=safe_output(args.out, paths)
        skeleton=api.NifFile(str(args.skeleton))
        if any(n not in skeleton.nodes for n in NODES): raise ValueError("Missing XP32 ear/tail nodes")
        if args.current_vector:
            return build_current(args,api,{sex:tri_patch.offsets(snapshots[getattr(args,sex+'_tri').resolve()]) for sex in ('male','female')},skeleton,snapshots,out)
        report={"schemaVersion":2 if args.bundles else 1,"frame":"node-local-game-units","domain":[0.,1.],
                "status":"offline-selected-skin-envelope","runtimeQualified":False,
                "morphs":list(MORPHS), "nodes":list(NODES), "coveredShapes":["body","head"],
                "ownership":"dominant packed skin weight >= 0.5; normalized full rest LBS into actual XP32 node frame",
                "excluded":"fur/blend layers, non-dominant skin and mixed-ownership boundary triangles, TailBone04, breast, torso/limb/head Havok bodies, animation/pose/scale/contact",
                "sourceInputs":[{"path":str(p),"bytes":len(b),"sha256":hashlib.sha256(b).hexdigest()} for p,b in snapshots.items()]}
        point_evidence={}; bundle_rows={}; bundle_choices={}
        for sex in ("male","female"):
            nif=getattr(args,sex+"_nif"); tri=getattr(args,sex+"_tri")
            mesh=api.NifFile(str(nif)); records=tri_patch.offsets(snapshots[tri.resolve()]); report[sex]={}
            for node in NODES:
                chunks=[]; sources=[]; ds={}
                for name in ("body","head"):
                    if name not in mesh.shape_dict: raise ValueError("Missing required skin shape")
                    found=_shape_fields(mesh.shape_dict[name], skeleton, node, records)
                    if found is None: continue
                    p,d,source=found; chunks.append(p); sources.append(source); ds[name]=d
                if not chunks:
                    if node != "TailBone04": raise ValueError("Missing fitted region: "+node)
                    report[sex][node]=None; continue
                points=np.vstack(chunks)
                triangles=[];offset=0
                for source in sources:
                    triangles.extend((np.asarray(source["fullRegionTriangles"],dtype=int).reshape(-1,3)+offset).tolist())
                    offset+=len(source["vertices"])
                actual=sorted({m for fields in ds.values() for m, values in fields.items() if np.max(abs(values))>1e-12})
                if set(actual)-set(MORPHS): raise ValueError("Previously unreviewed related morph: "+repr(set(actual)-set(MORPHS)))
                deltas={m:np.vstack([ds[s["shape"]].get(m,np.zeros((len(s["vertices"]),3))) for s in sources]) for m in actual}
                fitted=fit(points,deltas); fitted["sourceRegions"]=sources
                report[sex][node]=fitted
                point_evidence[sex+"/"+node]={"points":points.tolist(),"triangles":triangles,"deltas":{m:d.tolist() for m,d in deltas.items()}}
                if args.bundles:
                    models,choice=fit_bundle(points,deltas,BUNDLE_COUNTS[NODES.index(node)],triangles)
                    bundle_rows[sex,node]=models;bundle_choices[sex+"/"+node]=choice
        if args.bundles:
            report["singleCapsuleComparators"]={sex:report.pop(sex) for sex in ("male","female")}
            report["slots"]=[]
            for node,count in zip(NODES,BUNDLE_COUNTS):
                for group in range(count):
                    report["slots"].append({"node":node,"partition":group,
                                            **{sex:bundle_rows[sex,node][group] for sex in ("male","female")}})
            report["bundlePartitions"]=bundle_choices
            report["surfaceFitAccepted"]=False
            report["proofScope"]="Each fixed assigned vertex and each complete dominant-region triangle is contained by its slot for the full 0..1 box. Mixed-ownership boundary triangles, fur, animation and engine collision are excluded."
        for p,b in snapshots.items():
            if p.read_bytes()!=b: raise ValueError("Input changed during measurement: "+str(p))
        out.mkdir(parents=True)
        (out/"selected-skin-points.json").write_text(json.dumps(point_evidence),encoding="utf-8")
        report["pointEvidenceSha256"]=hashlib.sha256((out/"selected-skin-points.json").read_bytes()).hexdigest()
        (out/"fitted-capsules.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":report["status"],"slots":sum(BUNDLE_COUNTS) if args.bundles else 8,"morphs":len(MORPHS),"gameValidated":False,"output":str(out)}))
        return 0
    except (ValueError,KeyError,OSError,TypeError,np.linalg.LinAlgError) as error:
        print("CLAW capsule fit: "+str(error),file=sys.stderr); return 2


if __name__=="__main__": raise SystemExit(main())
