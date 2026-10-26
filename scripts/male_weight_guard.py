"""Minimal local correction of measured male neutral-weight pose slivers.

Preserves every _0 byte, female resource and actual selected contact field.
No whole-body scale, new seam, named TRI change or skeleton edit is allowed.
"""
from pathlib import Path
import copy,hashlib,heapq,importlib.util,json,shutil,sys
import numpy as np
import breast_rig as rig
import body_weight
import composed_vr
import geometry_audit
import head_split
import surface_collar as surface

ROOT=Path(__file__).resolve().parents[1]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def distances(vertices,faces,seeds,maximum):
    first,inverse,graph=surface.welded_graph(vertices,faces,5);result=np.full(len(first),np.inf);queue=[]
    for seed in np.unique(inverse[np.asarray(seeds,int)]):result[seed]=0.;heapq.heappush(queue,(0.,int(seed)))
    while queue:
        distance,index=heapq.heappop(queue)
        if distance!=result[index] or distance>=maximum:continue
        for neighbor,length in graph[index]:
            value=distance+length
            if value<result[neighbor]:result[neighbor]=value;heapq.heappush(queue,(value,int(neighbor)))
    return result[inverse]


def check_skin(model,high_positions,critical,cache):
    result={};passed=True
    old=model.high;model.high=high_positions
    try:
        for normalized in (False,True):
            convention='normalized' if normalized else 'rawPacked';shapes={}
            for name in ('body','head'):
                lo=cache[(name,normalized)];hi=model.positions(name,np.arange(len(model.vertices[name])),1.,{},normalized)[:151]
                faces=np.asarray(model.shapes[name].tris,int);rows=[]
                for i,pose in enumerate(model.poses[:151]):
                    row=critical(lo[i,faces],hi[i,faces]);row.update(pose=pose[0],group=pose[2]);rows.append(row)
                    passed &= not row['continuousAreaCollapseTriangles'] and not row['negativeOwnPose0NormalDotTriangles']
                shapes[name]=rows
            result[convention]=shapes
    finally:model.high=old
    return bool(passed),result


def reinhert_fur(low,correction):
    shapes={s.name:s for s in low.shapes};skin=np.r_[shapes['body'].verts,shapes['head'].verts]
    faces=np.r_[shapes['body'].tris,np.asarray(shapes['head'].tris)+len(shapes['body'].verts)]
    skin_delta=np.r_[correction['body'],correction['head']];projector=body_weight.Projector(skin,faces);rows={}
    for name,shape in shapes.items():
        if not(name.startswith('fur_') or name.endswith('Blend')):continue
        v=np.asarray(shape.verts);rule={'mode':'vertices' if name=='ChestBlend' else 'cards','bounds':[(v.min(0)-1).tolist(),(v.max(0)+1).tolist()],
            'fade':[.01,.01,.01],'distanceFade':[1000000.,1000001.],'weldDecimals':5}
        layer=surface.Layer(v,shape.tris,skin,faces,rule,projector);values=layer.binding.evaluate(skin_delta);field=np.zeros_like(v)
        for ids,value in zip(layer.groups,values):field[ids]=value
        correction[name]=field;rows[name]={'changedVertices':int(np.any(field!=0,axis=1).sum()),'maximumCorrection':float(np.linalg.norm(field,axis=1).max())}
    return rows


def contact_proof(api,fit,tri_patch,skeleton,old_low,old_high,new_low,new_high,tri):
    records=tri_patch.offsets(tri.read_bytes());skel=api.NifFile(str(skeleton));meshes=[api.NifFile(str(p)) for p in (old_low,old_high,new_low,new_high)];rows=[]
    for name in ('body','head','head_CLAWHead'):
        groups=[fit.triangle_regions(m.shape_dict[name],skel,records,fit.NODES) for m in meshes]
        if any(set(g)!=set(groups[0]) for g in groups):raise ValueError('Guard changed contact ownership')
        for node in groups[0]:
            a,b,c,d=[g[node] for g in groups]
            if not np.array_equal(a[0],c[0]) or not np.array_equal(b[0]-a[0],d[0]-c[0]):raise ValueError('Guard changed actual contact P0/weight field')
            if any(set(g[1])!=set(a[1]) or any(not np.array_equal(g[1][n],a[1][n]) for n in a[1]) for g in (b,c,d)):raise ValueError('Guard changed actual absolute contact TRI field')
            if any(g[2]['fullRegionTriangles']!=a[2]['fullRegionTriangles'] or g[2]['restLBSMatricesSha256']!=a[2]['restLBSMatricesSha256'] for g in (b,c,d)):raise ValueError('Guard changed contact topology/binds')
            rows.append({'shape':name,'node':node,'vertices':len(a[0]),'triangles':len(a[2]['fullRegionTriangles']),
                'exactP0':True,'exactIndependentWeightDelta':True,'exactAbsoluteTriFields':True,'exactNormalizedSkinMatrices':True})
    return rows


def build(prior_manifest,profile_file,skeleton,mb_directory,output,pynifly=None):
    prior_manifest,profile_file,skeleton=[Path(p).resolve(strict=True) for p in (prior_manifest,profile_file,skeleton)]
    profile=json.loads(profile_file.read_text());prior=json.loads(prior_manifest.read_text());composition=Path(prior['reports']['composition']);mb_directory=Path(mb_directory).resolve(strict=True)
    if profile!=json.loads((ROOT/'recipes/body-weight-guard.json').read_text()):raise ValueError('Unreviewed local guard profile')
    if rig.sha256(prior_manifest)!=profile['priorManifestSha256'] or rig.sha256(composition)!=profile['priorCompositionSha256']:raise ValueError('Prior selected family changed')
    old=json.loads(composition.read_text());male=old['bodies']['male'];low=Path(male['boundedSource']);high=Path(male['boundedHighSource'])
    raw_tri=next(Path(p) for p,h in old['inputsAndExecutedSha256'].items() if h==old['profile']['inputs']['maleTriSha256'])
    inputs=[prior_manifest,profile_file,skeleton,composition,low,high,raw_tri]+[Path(v['path']) for v in prior['files'].values()]
    for entry in prior['files'].values():
        if rig.sha256(entry['path'])!=entry['sha256']:raise ValueError('Prior resource changed')
    sources=[Path(__file__),ROOT/'scripts/repair-body-weight.py',ROOT/'scripts/body_weight.py',ROOT/'scripts/head_split.py',
        ROOT/'scripts/composed_vr.py',ROOT/'scripts/geometry_audit.py',ROOT/'scripts/check-weight-pose-path.py',ROOT/'scripts/breast_rig.py',
        ROOT/'scripts/surface_collar.py',ROOT/'scripts/calibrate-morph-links.py',ROOT/'scripts/morph_calibration.py',
        ROOT/'physics/fit-capsules.py',ROOT/'scripts/tri_patch.py']
    frozen={str(p):rig.sha256(p) for p in inputs+sources}
    # Retain the already-qualified tool/dependency pins before importing their
    # native reader or public bounds facade. Current selector code is captured
    # separately above; metadata edits do not bypass the end-of-run guard.
    dependency_pins={p:h for p,h in old['inputsAndExecutedSha256'].items()
        if mb_directory in Path(p).parents or 'io_scene_nifly' in Path(p).parts}
    for path,value in dependency_pins.items():
        if rig.sha256(path)!=value:raise ValueError('Qualified bounds/native-reader dependency changed: '+path)
    frozen.update(dependency_pins)
    addon=next(Path(p).parent for p in dependency_pins if Path(p).name=='NiflyDLL.dll')
    if pynifly is not None and Path(pynifly).resolve()!=addon.resolve():raise ValueError('Guard must retain the qualified native reader')
    # Evidence JSON lives at the shared external build root. It remains pinned,
    # but is not a binary source directory which would forbid a new sibling run.
    out=rig.safe_output(output,[low,high,raw_tri,skeleton,*[Path(v['path']) for v in prior['files'].values()]])
    api,Trip,dependency=rig.load_pynifly(addon);lo=api.NifFile(str(low));hi=api.NifFile(str(high));skel=api.NifFile(str(skeleton))
    raw=Trip.from_filepath(str(raw_tri)).shapes;model=geometry_audit.Model(lo,hi,skel,raw);path_check=module('claw_guard_path_check',ROOT/'scripts/check-weight-pose-path.py')
    cache={(name,mode):model.positions(name,np.arange(len(model.vertices[name])),0.,{},mode)[:151] for name in ('body','head') for mode in (False,True)}
    old_positions={s.name:np.asarray(s.verts,float) for s in hi.shapes};low_positions=model.vertices
    distance={name:distances(low_positions[name],model.shapes[name].tris,seeds,max(profile['fadeCandidates'])) for name,seeds in profile['seeds'].items()}
    out.mkdir();report={'status':'building-unverified-do-not-install','inputsAndExecutedSha256':frozen,'trials':[]};chosen=None
    try:
        for width in profile['fadeCandidates']:
            positions={name:v.copy() for name,v in old_positions.items()}
            for name,d in distance.items():
                alpha=rig.smooth(d/width);positions[name]=np.asarray(low_positions[name]+alpha[:,None]*(old_positions[name]-low_positions[name]),np.float32).astype(float)
            passed,check=check_skin(model,positions,path_check.critical,cache);report['trials'].append({'width':width,'passed':passed,'continuousPoseChecks':check})
            print('MALE_WEIGHT_GUARD|fade'+str(width)+'|'+str(passed),flush=True)
            if passed:chosen=width;break
        if chosen is None:raise ValueError('No approved local fade satisfies the continuous posed-weight gate')
        correction={name:positions[name]-old_positions[name] for name in old_positions};fur=reinhert_fur(lo,correction)
        # No correction may alter actual selected ear/tail vertices, even before
        # the stronger final full-field contact qualification below.
        fit=module('claw_guard_fit',ROOT/'physics/fit-capsules.py');tri_patch=module('claw_guard_trip',ROOT/'scripts/tri_patch.py');records=tri_patch.offsets(raw_tri.read_bytes())
        for name in ('body','head'):
            for node,(_,_,source) in fit.triangle_regions(lo.shape_dict[name],skel,records,fit.NODES).items():
                if np.any(correction[name][source['vertices']]):raise ValueError('Local guard touches selected contact support')
        data,changed=body_weight.move_nif(high.read_bytes(),hi,correction);candidate=out/'male-guarded-unsplit_1.nif';candidate.write_bytes(data)
        actual=api.NifFile(str(candidate));actual_positions={s.name:np.asarray(s.verts,float) for s in actual.shapes}
        passed,actual_checks=check_skin(model,actual_positions,path_check.critical,cache)
        if not passed:raise ValueError('Serialized local guard fails continuous posed-weight gate')
        # Measure rather than silently refitting the endpoint feature semantics.
        cal=body_weight.calibration_module();wv,wb,offsets=cal.mesh(lo,['body','head']);wf=cal.fields(wv,wb,np.zeros(len(wv),bool))
        weight_report=json.loads(Path(prior['reports']['weight']).read_text())['bodies']['male']['calibration'];names=weight_report['features'];fields=[wf[n] for n in names]
        before=np.r_[old_positions['body']-low_positions['body'],old_positions['head']-low_positions['head']]
        after=np.r_[actual_positions['body']-low_positions['body'],actual_positions['head']-low_positions['head']]
        target=np.asarray(weight_report['humanEndpointFeatureDelta']);old_response=body_weight.calibration.response(before,fields);new_response=body_weight.calibration.response(after,fields)
        feature={'features':names,'humanTarget':target.tolist(),'beforeActual':old_response.tolist(),'afterActual':new_response.tolist(),
            'oldResidual':float(np.linalg.norm(old_response-target)),'newResidual':float(np.linalg.norm(new_response-target)),
            'featureChangeNorm':float(np.linalg.norm(new_response-old_response)),'maximumFeatureChange':float(abs(new_response-old_response).max())}
        bounded0,bounded1,bounds=composed_vr.bound_carrier(api,Trip,low,candidate,raw_tri,skeleton,out/'male-bounds',Path(mb_directory),old['profile'])
        if bounded0.read_bytes()!=low.read_bytes():raise ValueError('Guard requires changing the protected _0 bounds')
        mapping=json.loads((composition.parent/'male-index-map.json').read_text());plan={}
        for name,p in mapping.items():plan[name]={'action':p['action'],'sourceBlock':p['sourceBlock'],'cards':p['wholeFurCards'],
            'mapping':{k:np.asarray(p[k],int) for k in ('torsoVertices','headVertices','torsoTriangles','headTriangles','seamVertices')}}
        data,audit=head_split.split_nif(bounded1.read_bytes(),plan,{});folder=out/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True)
        files={}
        for filename,entry in prior['files'].items():
            target_path=folder/filename
            if filename=='malebodywerewolf_1.nif':target_path.write_bytes(data)
            else:shutil.copyfile(entry['path'],target_path)
            files[filename]={'path':str(target_path),'sha256':rig.sha256(target_path),'bytes':target_path.stat().st_size}
        selected=folder/'malebodywerewolf_1.nif';tri=folder/'malebodywerewolf.tri'
        readback=head_split.verify(api,Trip,bounded1,selected,raw_tri,tri,plan,skel)
        proof=contact_proof(api,fit,tri_patch,skeleton,Path(male['nif']),Path(male['highNif']),folder/'malebodywerewolf_0.nif',selected,tri)
        new_composition=copy.deepcopy(old)
        for sex,b in new_composition['bodies'].items():
            b['nif']=files[sex+'bodywerewolf_0.nif']['path'];b['highNif']=files[sex+'bodywerewolf_1.nif']['path'];b['tri']=files[sex+'bodywerewolf.tri']['path']
        new_composition['bodies']['male'].update(highNifSha256=files['malebodywerewolf_1.nif']['sha256'],highReadback=readback,highBinaryAudit=audit,
            boundedHighSource=str(bounded1),boundedHighSourceSha256=rig.sha256(bounded1),boundsReport=str(out/'male-bounds/bounds-report.json'))
        new_composition['maleNeutralWeightRepair']={'priorComposition':str(composition),'guardReport':str(out/'male-weight-guard-report.json')}
        (out/'composed-vr-report.json').write_text(json.dumps(new_composition,indent=2))
        for filename in ('female-index-map.json','male-index-map.json'):shutil.copyfile(composition.parent/filename,out/filename)
        manifest=copy.deepcopy(prior);manifest['files']=files;manifest['reports']['composition']=str(out/'composed-vr-report.json');manifest['reports']['maleWeightGuard']=str(out/'male-weight-guard-report.json')
        manifest['supersedes']=str(prior_manifest);manifest['limitations']=[x for x in manifest['limitations'] if 'male has2body/19head' not in x]
        manifest['continuousWeightRepair']='No primary body/head own-pose-weight0 normal turns or area collapse remain over151poses, raw and normalized. Same _0/female/TRI bytes and exact selected contact fields.'
        (out/'final-resource-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        if any(rig.sha256(p)!=h for p,h in frozen.items()):raise ValueError('Guard input/source changed during build')
        report.update(status='verified-local-male-weight-repair-original-low-and-contact-fields-preserved',selectedFade=chosen,
            changedVertices={name:int(np.any(correction[name]!=0,axis=1).sum()) for name in correction},furRootInheritance=fur,featureProjection=feature,
            serializedContinuousPoseChecks=actual_checks,exactFinalContactFieldProof=proof,manifest=str(out/'final-resource-manifest.json'),
            priorMaleHighSha256=prior['files']['malebodywerewolf_1.nif']['sha256'],newMaleHighSha256=files['malebodywerewolf_1.nif']['sha256'])
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'male-weight-guard-report.json').write_text(json.dumps(report,indent=2))
    return out/'final-resource-manifest.json'
