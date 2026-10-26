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


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for sex in ("male", "female"):
        parser.add_argument("--"+sex+"-nif", type=Path, required=True)
        parser.add_argument("--"+sex+"-tri", type=Path, required=True)
    parser.add_argument("--skeleton", type=Path, required=True)
    parser.add_argument("--pynifly", type=Path, help="Installed PyNifly addon directory (read only)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bundles", action="store_true", help="Explicit 32-slot fitted bundle candidate; never changes the legacy eight-slot model")
    args=parser.parse_args(argv)
    try:
        sys.path.insert(0, str(ROOT/"scripts"))
        import breast_rig, tri_patch
        api, _, addon=breast_rig.load_pynifly(args.pynifly)
        paths=[args.male_nif,args.male_tri,args.female_nif,args.female_tri,args.skeleton,
               Path(__file__), ROOT/"scripts/breast_rig.py", ROOT/"scripts/tri_patch.py",
               addon/"NiflyDLL.dll", addon/"pyn/pynifly.py"]
        snapshots={p.resolve():p.read_bytes() for p in paths}
        out=safe_output(args.out, paths)
        skeleton=api.NifFile(str(args.skeleton))
        if any(n not in skeleton.nodes for n in NODES): raise ValueError("Missing XP32 ear/tail nodes")
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
