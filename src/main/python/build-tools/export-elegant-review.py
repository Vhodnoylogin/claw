"""Export the pinned donor-only author-review tool from canonical CLAW functions.

The standalone file is generated output; maintain the shared splitter, skinning
and pose functions in their existing modules instead of copying implementations.
This exporter preserves the exact published review tool, including its original
mixed newline encoding. Source changes require an explicit new review contract.
"""
from pathlib import Path
import argparse
import ast
import hashlib


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REVIEW_SHA256 = '702d89a6e5035bc74afe751b48209d40e5afab7dcac73255f17f08a911c9e089'

HEADER = '''"""Donor-only Elegant head/body split for Wolflady500's review.

All original triangles remain visible. No textures, replacement skeleton,
physics, runtime plugin or body-shape changes are produced. Verification probes
exercise TRI remapping but are not linked from or shipped with the mesh payload.
Original algorithm: CLAW's lossless head_split.py, extracted into this standalone
review helper; no CLAW installation is required.
"""
from pathlib import Path
from types import SimpleNamespace
import argparse, hashlib, importlib.util, json, math, struct, sys
import numpy as np
SUFFIX = '_HeadOnly'
HEAD = 'NPC Head [Head]'
'''
ENTRYPOINT = r'''INPUTS = {
    'male': '22689f28006f21c58f10ca640eb3ea4741fbad00fe3edd4d0d2ed0339a3a2349',
    'female': 'ec9c70bf5ed62fdf481bbfc0aad43c7d8d2e8d0ca90833a323b9b222e437265b',
    'skeleton': 'b64b614d06eb854512ef4a9d6b08777fe0f9580f47d495d20db16dabb9fc2dd0',
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def probe_trip(nif):
    """Synthetic verification field over EVERY original vertex; never a game asset."""
    records = []
    def label(text):
        raw = text.encode('iso-8859-15')
        return encode('<B', len(raw))+raw
    for shape in nif.shapes:
        count = len(shape.verts)
        if not 0 < count <= 65535:
            raise ValueError('Probe requires supported SSE vertex count')
        pairs = b''.join(encode('<H3h', i, i % 7 - 3, i % 11 - 5, i % 13 - 6) for i in range(count))
        records.append(label(shape.name)+encode('<H',1)+label('VerificationProbe')+encode('<fH',.000125,count)+pairs)
    return b'PIRT'+encode('<H',len(records))+b''.join(records)

def load_pynifly(path):
    path=Path(path).resolve(strict=True)
    sys.path.insert(0,str(path))
    from pyn import pynifly as api
    api.NifFile.Load(str(path/'NiflyDLL.dll'))
    spec=importlib.util.spec_from_file_location('elegant_review_trip',path/'tri/tripfile.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return api,module.TripFile,path

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--male',type=Path,required=True)
    parser.add_argument('--female',type=Path,required=True)
    parser.add_argument('--skeleton',type=Path,required=True,help='Read-only XP32 reference, never copied or changed')
    parser.add_argument('--pynifly',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True,help='A NEW directory outside game/MO2/source directories')
    args=parser.parse_args()
    inputs={key:Path(getattr(args,key)).resolve(strict=True) for key in INPUTS}
    if any(sha(path)!=INPUTS[key] for key,path in inputs.items()):
        parser.error('Original donor/reference SHA256 mismatch; this prototype supports only recorded inputs.')
    out=args.out.resolve()
    if out.exists() or any(out==path.parent or out.is_relative_to(path.parent) for path in inputs.values()):
        parser.error('Output must be a NEW directory outside input directories.')
    if any(part.casefold() in {'mods','profiles','overwrite','data','skyrim vr','skyrimvr','skyrim special edition','mo2','modorganizer'} for part in out.parts):
        parser.error('Output must not be inside a live game/mod-manager tree.')
    api,Trip,dependency=load_pynifly(args.pynifly)
    skeleton=api.NifFile(str(inputs['skeleton']))
    parents={name:node.parent.name if node.parent else None for name,node in skeleton.nodes.items()}
    head_names=descendants(parents,HEAD)
    profile={'threshold':.5,'comparedThresholds':[.25,.4,.5,.6,.75]}
    out.mkdir(parents=True)
    report={'status':'BUILDING','scope':'Original Elegant donor-only lossless anatomical split. All pieces visible. Offline author review, not game acceptance.',
        'inputs':{key:{'sha256':sha(path),'bytes':path.stat().st_size,'name':path.name} for key,path in inputs.items()},
        'sourceSha256':sha(__file__),'pynifly':{str(path.relative_to(dependency)):sha(path) for path in [dependency/'NiflyDLL.dll',dependency/'pyn/pynifly.py',dependency/'tri/tripfile.py']},
        'headDescendantNames':sorted(head_names),'threshold':.5,'bodies':{}}
    try:
        for sex in ('male','female'):
            source=inputs[sex];before=api.NifFile(str(source))
            planned,comparisons=plan(before,{},head_names,profile)
            data,binary_audit=split_nif(source.read_bytes(),planned,{})
            folder=out/'meshes/actors/werewolfbeast/character assets';folder.mkdir(parents=True,exist_ok=True)
            target=folder/(sex+'bodywerewolf_1.nif');target.write_bytes(data)
            probe_dir=out/'verification-probes';probe_dir.mkdir(exist_ok=True)
            old_probe=probe_dir/(sex+'-original.tri');new_probe=probe_dir/(sex+'-split.tri')
            old_probe.write_bytes(probe_trip(before));new_probe.write_bytes(split_trip(old_probe.read_bytes(),planned))
            readback=verify(api,Trip,source,target,old_probe,new_probe,planned,skeleton)
            aliases=[]
            if sex=='female':
                # Both original female archive endpoints have the same pinned bytes.
                alias=folder/'femalebodywerewolf_0.nif';alias.write_bytes(data);aliases.append(str(alias.relative_to(out)))
            index={name:{'action':p['action'],'wholeFurCards':p['cards'],**{key:value.tolist() for key,value in p['mapping'].items()}} for name,p in planned.items()}
            (out/(sex+'-index-map.json')).write_text(json.dumps(index,separators=(',',':'))+'\n',encoding='utf-8')
            report['bodies'][sex]={'output':str(target.relative_to(out)),'outputSha256':sha(target),'aliases':aliases,'options':comparisons,
                'binaryAudit':binary_audit,'readback':readback,'originalMorphData':'Original Elegant donors have no authored TRIP input. TRI checks use synthetic verification probes only; no runtime TRI file is included.'}
            print(sex,report['bodies'][sex]['outputSha256'],flush=True)
        if any(sha(path)!=INPUTS[key] for key,path in inputs.items()):
            raise ValueError('Input changed during build')
        report['status']='PASS_OFFLINE_ORIGINAL_DONOR_SPLIT_AUTHOR_REVIEW'
    except Exception:
        report['status']='FAILED_DO_NOT_USE';raise
    finally:
        (out/'verification-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(out/'verification-report.json')

if __name__=='__main__':
    main()
'''


def definitions(file, names):
    text = Path(file).read_text(encoding='utf-8')
    nodes = [node for node in ast.parse(text).body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if {node.name for node in nodes} != set(names) or len(nodes) != len(names):
        raise ValueError('Missing or repeated reviewed definition in ' + str(file))
    return '\n\n'.join(ast.get_source_segment(text, node) for node in nodes)


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Reviewed source pattern changed; review before exporting')
    return text.replace(old, new, 1)


def render(source=HERE):
    source = Path(source)
    utilities = definitions(source/'breast_rig.py',
                            {'rotation', 'lbs', 'matrix', 'read_weights', 'dense_morph'})
    utilities += '\n\nrig = SimpleNamespace(rotation=rotation, lbs=lbs, matrix=matrix, read_weights=read_weights, dense_morph=dense_morph)\n'
    poses = definitions(source/'vr_head.py', {'descendants', 'impose', 'pose_bank'})
    poses += '\n\nvr_head = SimpleNamespace(HEAD=HEAD, descendants=descendants, impose=impose, pose_bank=pose_bank)\n'
    core = definitions(source/'head_split.py', {
        'Reader', 'encode', 'Nif', 'Partition', 'subset_skin_data', 'components',
        'classify', 'mapping', 'option', 'plan', 'clone_shape_shader', 'split_nif',
        'split_trip', 'pose_equivalence', 'verify'})
    core = replace_once(core,
        "'breastSupportVerticesInHead':int(np.any(breast[m['headVertices']]!=0,axis=1).sum())",
        "'classificationUsesOriginalWeightsOnly':True")
    core = replace_once(core,
        "breast=rig.dense_morph(raw,shape.name,'CLAWTorsoBreastSize',len(vertices))",
        'breast=np.zeros((len(vertices),3))  # No body morph is authored or applied.')
    core = replace_once(core,
        "        if comparisons[shape.name][str(profile['threshold'])]['breastSupportVerticesInHead']:\n            raise ValueError('Chosen boundary removes breast support: '+shape.name)\n", '')
    start = core.index("    states=[('neutral',{})")
    end = core.index('\n    for b in before.shapes:', start)
    core = core[:start] + "    states=[('neutral',{}),('verification-probe-half',{'VerificationProbe':.5}),('verification-probe-full',{'VerificationProbe':1.})]" + core[end:]
    core = replace_once(core, 'head/breast susceptibility', 'head influence')
    # The original exporter wrote its assembled core through Windows text I/O;
    # the subsequently appended donor entrypoint used LF. Preserve those bytes.
    prefix = (HEADER+'\n'+utilities+'\n\n'+poses+'\n\n'+core+'\n').replace('\n', '\r\n')
    payload = (prefix+'\n'+ENTRYPOINT.removesuffix('\n')+'\r\n').encode('utf-8')
    if hashlib.sha256(payload).hexdigest() != REVIEW_SHA256:
        raise ValueError('Export differs from the published review tool; qualify a new revision first')
    return payload


def export(output):
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Choose a new output file')
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'target'):
        raise ValueError('Generated repository output belongs under target/')
    payload = render()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as destination:
        destination.write(payload)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        output = export(args.out)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(str(output))
    print('SHA256 ' + REVIEW_SHA256)


if __name__ == '__main__':
    main()
