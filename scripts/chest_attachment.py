"""Localized chest-card root attachment on the actual existing-XP32 carrier.

The earlier belly experiment only admitted full-weight cards and optimized P1.
This separate stage also measures fade roots, then corrects Head/Spine2 mismatch
against actual posed skin. It never transfers head influences on the skin itself.
"""
from pathlib import Path
import json
import shutil
import numpy as np
import breast_rig as rig
import fur_motion as fur
import surface_collar as surface
from collar_weights import write_active_weights

ROOT=Path(__file__).resolve().parents[1]


def transfer_pair(weights,ids,root,desired,first,second):
    """Common local pair fraction; exact packed sums and foreign support survive."""
    old=np.asarray(weights,float);result=old.copy();pool=old[:,first]+old[:,second]
    if pool[root]<=0:raise ValueError('Root pair has no pool')
    # A common normalized correction translates a card coherently. Scaling it
    # by each vertex's pair pool amplified root corrections at tips whose pool
    # happened to be larger, creating avoidable strain on otherwise rigid cards.
    fraction=(desired-old[root,second])/old[root].sum()
    for i in ids:
        if old[i,second]==0 and np.count_nonzero(old[i])>=4:continue
        wanted=float(np.clip(old[i,second]+fraction*old[i].sum(),0,pool[i]))
        result[i,[first,second]]=fur.exact_half_pair(old[i,first],old[i,second],wanted)
    foreign=[j for j in range(old.shape[1]) if j not in (first,second)]
    if (not np.array_equal(old[:,foreign],result[:,foreign]) or not np.array_equal(old.sum(1),result.sum(1))
            or (result>0).sum(1).max()>4):raise ValueError('Pair transfer changed foreign support/sums/capacity')
    return result


def head_request(model,layer,group,root):
    """One bounded scalar fit on ordinary controls; held-out combinations are excluded."""
    name='fur_chest';old=model.weights[name];spine=model.index['NPC Spine2 [Spn2]'];head=model.index['NPC Head [Head]']
    train=[i for i,p in enumerate(model.poses) if p[2]=='ordinary']
    x=[];y=[];total=old[root].sum()
    for c in (0.,.5,1.):
        points=model.points(name,[root],c)[:,0];motion=np.einsum('pbj,b->pj',points,old[root])/total
        response=(points[:,head]-points[:,spine])/total;response-=response[:1]
        target=model.target(layer,group,root,c);baseline=motion-motion[:1]
        x.append(response[train]);y.append((target-baseline)[train])
    delta=fur.fit_scalar(x,y,-float(old[root,head]),float(old[root,spine]))
    return float(old[root,head]+delta)


def plan_palette(model,layer):
    """Fit actual root-related palette pairs, with a strain-constrained line search.

    A full optimum can stretch a card. Reducing the corrective step instead of
    weakening the fixed 0.01 strain ceiling admits only its feasible improvement.
    Every P1 weight remains exact, so pure-P1 response is protected independently.
    """
    name='fur_chest';old=model.weights[name];result=old.copy();vertices=np.asarray(model.shapes[name].verts)
    spine=model.index['NPC Spine2 [Spn2]'];p1=[model.index[n] for n in ('NPC L Breast P1','NPC R Breast P1')]
    train=[i for i,p in enumerate(model.poses) if p[2]=='ordinary'];rows=[];changed=[]
    for group,ids in enumerate(layer.groups):
        if layer.weights[group]<=0:
            rows.append({'group':group,'status':'unchanged-outside-frozen-breast-region'});continue
        root=int(ids[np.all(vertices[ids]==layer.binding.points[group],axis=1)][0]);local_root=int(np.flatnonzero(ids==root)[0])
        if vertices[root,2]>108 or vertices[root,1]>46:
            rows.append({'group':group,'root':root,'status':'unchanged-outside-torso-root'});continue
        point_bank=[model.points(name,[root],c)[:,0] for c in (0.,.5,1.)]
        target_bank=[model.target(layer,group,root,c) for c in (0.,.5,1.)]
        baseline=fur.card_metrics(model,layer,group,root,ids,old);best=old[ids].copy();best_metrics=baseline
        current_error=baseline['normalized']['rootSquaredErrorBefore'];steps=[]
        # Original root supports and significant skin-bary supports are local
        # candidates. Existing four-slot capacity remains a hard constraint.
        skin_ids=layer.binding.faces[layer.binding.indices[group]];bary=layer.binding.weights[group];support=old[root].copy()
        body_n=len(model.shapes['body'].verts)
        for sid,q in zip(skin_ids,bary):
            source,index=('body',int(sid)) if sid<body_n else ('head',int(sid-body_n))
            support+=q*model.weights[source][index]
        bones=[j for j in np.flatnonzero(support>1e-5) if j not in [spine,*p1] and model.names[j] in model.shapes[name].bone_weights]
        span=float(np.linalg.norm(vertices[ids].max(0)-vertices[ids].min(0)))
        for sweep in range(2):
            improved=False
            for bone in bones:
                W=best[local_root];total=W.sum()
                if W[bone]==0 and np.count_nonzero(W)>=4:continue
                if W[spine]+W[bone]<=0:continue
                x=[];y=[]
                for points,target in zip(point_bank,target_bank):
                    motion=np.einsum('pbj,b->pj',points,W)/total;response=(points[:,bone]-points[:,spine])/total
                    x.append((response-response[:1])[train]);y.append((target-(motion-motion[:1]))[train])
                try:delta=fur.fit_scalar(x,y,-float(W[bone]),float(W[spine]))
                except ValueError:continue
                for fraction in (1.,.5,.25,.125,.0625):
                    trial=transfer_pair(best,np.arange(len(ids)),local_root,float(W[bone]+fraction*delta),spine,bone)
                    proposed=old.copy();proposed[ids]=trial;metrics=fur.card_metrics(model,layer,group,root,ids,proposed)
                    accept=True
                    for convention,m in metrics.items():
                        base=baseline[convention]
                        accept &= m['edgeStrainChange']['max']<=model.profile['maximumCardStrainChange']
                        accept &= m['pureP1RootAfter']['max']<=base['pureP1RootBefore']['max']+1e-8
                        accept &= m['pureP1SquaredAfter']<=base['pureP1SquaredBefore']+1e-12
                        accept &= m['rootTransportedOffsetAfter']['max']<=base['rootTransportedOffsetBefore']['max']+1e-8
                        accept &= m['ordinaryChangedVertexError']['max']<=base['rootTransportedOffsetBefore']['max']+span*.01+1e-5
                    error=metrics['normalized']['rootSquaredErrorAfter']
                    if accept and error<current_error-1e-10:
                        best=trial;best_metrics=metrics;current_error=error;improved=True
                        steps.append({'bone':model.names[bone],'sweep':sweep,'feasibleFraction':fraction,'rootWeightDelta':float(best[local_root,bone]-W[bone])})
                        break
            if not improved:break
        active=ids[np.any(best!=old[ids],axis=1)]
        before=baseline['normalized']['rootSquaredErrorBefore'];after=best_metrics['normalized']['rootSquaredErrorAfter']
        accept=len(active)>0 and before-after>max(1e-8,.01*before)
        if not np.array_equal(best[:,p1],old[ids][:,p1]):raise ValueError('Root palette fit changed P1')
        rows.append({'group':group,'root':root,'position':vertices[root].tolist(),'frozenLayerWeight':float(layer.weights[group]),
            'status':'accepted-offline' if accept else 'unchanged-no-feasible-root-improvement','metrics':best_metrics,'steps':steps,
            'changedVertices':active.tolist() if accept else [],'originalRootWeights':{model.names[j]:float(v) for j,v in enumerate(old[root]) if v},
            'candidateRootWeights':{model.names[j]:float(v) for j,v in enumerate(best[local_root]) if v},
            'maximumRemovedSupportMass':float(np.maximum(old[ids]-best,0).sum(1).max()) if accept else 0.})
        if accept:result[ids]=best;changed.extend(active.tolist())
    return result,np.asarray(sorted(set(changed)),int),rows


def plan_stage(model,layer,mode):
    name='fur_chest';old=model.weights[name];result=old.copy();rows=[];changed=[]
    vertices=np.asarray(model.shapes[name].verts);spine=model.index['NPC Spine2 [Spn2]'];head=model.index['NPC Head [Head]']
    p1=[model.index[n] for n in ('NPC L Breast P1','NPC R Breast P1')]
    for group,ids in enumerate(layer.groups):
        if layer.weights[group]<=0:
            rows.append({'group':group,'status':'unchanged-outside-frozen-breast-region'});continue
        matches=ids[np.all(vertices[ids]==layer.binding.points[group],axis=1)]
        if not len(matches):raise ValueError('Representative is not an actual root vertex')
        root=int(matches[0]);side=int(vertices[root,0]>=0);second=p1[side] if mode=='fade-p1' else head
        if old[root,second]==0 and np.count_nonzero(old[root])>=4:
            rows.append({'group':group,'root':root,'status':'unchanged-saturated-root'});continue
        if mode=='fade-p1' and np.any(old[ids,p1[1-side]]):
            rows.append({'group':group,'root':root,'status':'unchanged-bilateral-card'});continue
        if mode=='head-root' and (vertices[root,2]>108 or vertices[root,1]>46):
            rows.append({'group':group,'root':root,'status':'unchanged-outside-torso-root'});continue
        if old[root,spine]+old[root,second]<=0:
            rows.append({'group':group,'root':root,'status':'unchanged-no-pair-pool'});continue
        try:
            if mode=='head-root':desired=head_request(model,layer,group,root)
            else:
                x=[];y=[];total=old[root].sum();pool=old[root,spine]+old[root,second]
                for c in (0.,.5,1.):
                    points=model.points(name,[root],c)[:,0];response=points[:,second]-points[:,spine]
                    x.append((response-response[:1])[model.pure]);y.append(model.target(layer,group,root,c)[model.pure])
                desired=fur.fit_scalar(x,y,0.,float(pool/total))*total
            candidate=transfer_pair(old[ids],np.arange(len(ids)),int(np.flatnonzero(ids==root)[0]),desired,spine,second)
        except ValueError as exc:
            rows.append({'group':group,'root':root,'status':'unchanged-unobservable','reason':str(exc)});continue
        proposed=result.copy();proposed[ids]=candidate;metrics=fur.card_metrics(model,layer,group,root,ids,proposed)
        active=ids[np.any(candidate!=old[ids],axis=1)];reasons=[]
        for convention,m in metrics.items():
            if m['edgeStrainChange']['max']>model.profile['maximumCardStrainChange']:reasons.append(convention+':card-strain')
            if m['pureP1RootAfter']['max']>m['pureP1RootBefore']['max']+1e-8:reasons.append(convention+':pure-P1-max-regression')
            if m['pureP1SquaredAfter']>m['pureP1SquaredBefore']+1e-12:reasons.append(convention+':pure-P1-square-regression')
            if mode=='fade-p1':
                tolerance=model.profile['normalizedOrdinaryMaxError' if convention=='normalized' else 'rawOrdinaryMaxError']
                if m['ordinaryChangedVertexError']['max']>tolerance:reasons.append(convention+':ordinary-budget')
            else:
                if m['rootTransportedOffsetAfter']['max']>m['rootTransportedOffsetBefore']['max']+1e-8:reasons.append(convention+':attachment-max-regression')
                span=float(np.linalg.norm(vertices[ids].max(0)-vertices[ids].min(0)))
                derived=m['rootTransportedOffsetBefore']['max']+span*model.profile['maximumCardStrainChange']+1e-5
                if m['ordinaryChangedVertexError']['max']>derived:reasons.append(convention+':correction-exceeds-root-error-and-strain-budget')
        m=metrics['normalized'];before=m['pureP1SquaredBefore'] if mode=='fade-p1' else m['rootSquaredErrorBefore'];after=m['pureP1SquaredAfter'] if mode=='fade-p1' else m['rootSquaredErrorAfter']
        if before-after<=max(1e-8,.01*before):reasons.append('no-substantial-root-improvement')
        if not len(active):reasons.append('packed-no-op')
        accept=not reasons
        rows.append({'group':group,'root':root,'position':vertices[root].tolist(),'frozenLayerWeight':float(layer.weights[group]),
            'requestedWeight':desired,'status':'accepted-offline' if accept else 'unchanged-rejected',
            'reasons':reasons,'metrics':metrics,'changedVertices':active.tolist() if accept else []})
        if accept:result[ids]=candidate;changed.extend(active.tolist())
    return result,np.asarray(sorted(set(changed)),int),rows


def build(body,tri,skeleton,profile_file,output,pynifly=None):
    inputs=[Path(x).resolve(strict=True) for x in (body,tri,skeleton,profile_file)];body,tri,skeleton,profile_file=inputs
    p=json.loads(profile_file.read_text());template=json.loads((ROOT/'recipes/chest-attachment.json').read_text())
    if p!=template:raise ValueError('Unreviewed chest attachment profile')
    for path,key in ((body,'bodyNifSha256'),(tri,'triSha256'),(skeleton,'skeletonSha256')):
        if rig.sha256(path)!=p['inputs'][key]:raise ValueError('Pinned input changed: '+key)
    out=rig.safe_output(output,inputs);api,Trip,dependency=rig.load_pynifly(pynifly)
    sources=[Path(__file__),ROOT/'scripts/repair-chest-attachment.py',ROOT/'recipes/chest-attachment.json',
             ROOT/'recipes/breast-rig-collar.json',ROOT/'recipes/breast-rig.json',ROOT/'scripts/breast_rig.py',
             ROOT/'scripts/fur_motion.py',ROOT/'scripts/collar_weights.py',ROOT/'scripts/surface_collar.py',ROOT/'scripts/locate.py']
    deps=[*sorted((dependency/'pyn').glob('*.py')),*sorted((dependency/'tri').glob('*.py')),dependency/'NiflyDLL.dll']
    frozen={str(x):rig.sha256(x) for x in inputs+sources+deps};raw=Trip.from_filepath(str(tri)).shapes
    rp=rig.load_profile(ROOT/'recipes/breast-rig-collar.json');skel=api.NifFile(str(skeleton));out.mkdir()
    current=body;report={'status':'building-unverified-do-not-install','inputsAndExecutedSha256':frozen,'stages':{}}
    try:
        for mode in ('fade-p1','root-palette'):
            source=api.NifFile(str(current));snapshot=fur.snapshot(source);model=fur.MotionModel(source,skel,raw,p,rp);s=model.shapes
            skin=np.r_[s['body'].verts,s['head'].verts];faces=np.r_[s['body'].tris,np.asarray(s['head'].tris)+len(s['body'].verts)]
            rule=next(x for x in rp['layers'] if x['shape']=='fur_chest')
            layer=surface.Layer(s['fur_chest'].verts,s['fur_chest'].tris,skin,faces,rule,rig.SurfaceProjector(skin,faces))
            planned,active,rows=plan_stage(model,layer,mode) if mode=='fade-p1' else plan_palette(model,layer);entry={'changedVertexCount':len(active),'groups':rows,
                'frozenBindings':[{'group':g,'vertices':ids.tolist(),'rootPoint':layer.binding.points[g].tolist(),
                    'skinVertices':layer.binding.faces[layer.binding.indices[g]].tolist(),'barycentric':layer.binding.weights[g].tolist(),
                    'weight':float(layer.weights[g])} for g,ids in enumerate(layer.groups)]}
            if len(active):
                folder=out/mode;folder.mkdir();target=folder/'femalebodywerewolf.nif'
                write_active_weights(s['fur_chest'],planned,active,model.names);source.filepath=str(target);source.save()
                fur.verify_snapshot(snapshot,api.NifFile(str(target)),'fur_chest',planned,model.names)
                shutil.copyfile(tri,target.with_suffix('.tri'));entry['nifSha256']=rig.sha256(target);current=target
            report['stages'][mode]=entry
        if current==body:raise ValueError('No serialized chest attachment improvement')
        folder=out/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True)
        for name in ('femalebodywerewolf_0.nif','femalebodywerewolf_1.nif'):shutil.copyfile(current,folder/name)
        shutil.copyfile(tri,folder/'femalebodywerewolf.tri')
        if any(rig.sha256(x)!=h for x,h in frozen.items()):raise ValueError('Input/source/dependency changed')
        report.update(status='verified-offline-localized-chest-attachment-runtime-pending',nif=str(folder/'femalebodywerewolf_0.nif'),
            nifSha256=rig.sha256(current),triSha256=rig.sha256(tri),
            scope='Fade-P1 stage retains original ordinary-motion gates. Root-palette stage corrects source root-related Spine/Head/Jaw/Clavicle mismatch against actual posed skin using bounded pair fits and strain-constrained line search. Every P1 weight remains exact; packed sums/capacity and the same0.01 card-strain ceiling remain hard gates. Changed related support and old-motion deviations are explicitly reported. No skin weights or skeleton edits.')
    except Exception:
        report['status']='FAILED-unverified-do-not-install';raise
    finally:(out/'report.json').write_text(json.dumps(report,indent=2))
    return out/'report.json'
