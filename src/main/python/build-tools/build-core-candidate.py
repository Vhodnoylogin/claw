"""Build minimal base/linked-SE candidates; no installation or publication."""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
import surface_edits

ROOT=Path(__file__).resolve().parents[4]
MESH='Meshes/Actors/WerewolfBeast/Character Assets'
BASE_RUNTIME={'CLAW.esp'}|{MESH+'/'+sex+'bodywerewolf'+suffix for sex in ('male','female') for suffix in ('_0.nif','_1.nif','.tri')}
CORE_RUNTIME={'SKSE/Plugins/CLAWDistribution.dll','Scripts/CLAWDistributionNative.pex'}
HOST_RUNTIME={'CLAW - OBody Integration.esp','Scripts/CLAWOBodySourceHost.pex'}

def pin(path):
    p=Path(path)
    return {'path':str(p),'sha256':surface_edits.sha(p.read_bytes()),'bytes':p.stat().st_size}

def checked(row):
    p=Path(row['path'])
    if not p.is_file() or p.is_symlink() or pin(p)!=row:
        raise ValueError('External input drift: '+str(p))
    return p

def destination(value):
    p=PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value or ':' in value:
        raise ValueError('Unsafe package path')
    return str(p)

def family_xml(female):
    root=ET.parse(ROOT / 'src/main/resources/profiles/MorphLinks.xml').getroot()
    profiles={p.attrib['family']:p for p in root.findall('Profile')}
    if female not in ('CBBE','3BA') or root.find('Defaults') is not None:
        raise ValueError('Unexpected source families')
    ET.SubElement(root,'Defaults',male=profiles['HIMBO'].attrib['id'],female=profiles[female].attrib['id'])
    ET.indent(root,space='  ')
    return ET.tostring(root,encoding='utf-8')+b'\n'

def zip_tree(folder,target):
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                info=zipfile.ZipInfo(p.relative_to(folder).as_posix(),(2026,10,30,0,0,0))
                info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,p.read_bytes())
    with zipfile.ZipFile(target) as z:
        if z.testzip():raise ValueError('Archive CRC failure')
        for p in folder.rglob('*'):
            if p.is_file() and z.read(p.relative_to(folder).as_posix())!=p.read_bytes():
                raise ValueError('Archive differs from staged tree')

def inventory(folder):
    return {p.relative_to(folder).as_posix():{'sha256':surface_edits.sha(p.read_bytes()),'bytes':p.stat().st_size} for p in sorted(folder.rglob('*')) if p.is_file()}

def build(external,out):
    external=Path(external).resolve();out=Path(out).resolve()
    if out.exists() or out==ROOT or ROOT in out.parents or out in ROOT.parents:
        raise ValueError('Fresh external output required')
    inputs=json.loads(external.read_text(encoding='utf-8'))
    if inputs['schema']!='claw-linked-se-inputs/1':raise ValueError('Unknown inputs')
    frozen=json.loads((ROOT / 'src/main/resources/publication/core-input-hashes.json').read_text(encoding='utf-8'))
    if inputs['nativeCommit']!=frozen['nativeCommit'] or inputs['correspondingSource']['sha256']!=frozen['correspondingSource']:
        raise ValueError('Native source identity differs from reviewed build')
    for group in ('core','host','notices'):
        if {k:v['sha256'] for k,v in inputs[group].items()}!=frozen[group]:
            raise ValueError('External build differs from reviewed '+group)
    groups={}
    for name,expected in [('core',CORE_RUNTIME),('host',HOST_RUNTIME)]:
        rows=inputs[name]
        if set(rows)!=expected:raise ValueError('Unexpected runtime input inventory')
        groups[name]={destination(k):checked(v) for k,v in rows.items()}
    notices={destination(k):checked(v) for k,v in inputs['notices'].items()}
    if not notices or any(not k.startswith('NOTICES/') for k in notices):raise ValueError('License notices required')
    source=checked(inputs['correspondingSource'])
    source_files=[ROOT/p for p in ('scripts/build-core-candidate.py','scripts/build-surface-repair.py','scripts/surface_edits.py','scripts/head_split.py','scripts/breast_rig.py','scripts/vr_head.py','src/main/resources/recipes/surface-repair-v1.json','src/main/resources/profiles/MorphLinks.xml','release/core-input-hashes.json')]
    source_files+=sorted((ROOT / 'src/main/resources/publication').glob('Core-*.md'))+sorted((ROOT / 'src/main/resources/publication/core-installer').glob('*.xml'))
    closure={p.relative_to(ROOT).as_posix():surface_edits.sha(p.read_bytes()) for p in source_files}
    # All input bytes are verified before creating any output.
    out.mkdir(parents=True)
    base=out/'base';dist=out/'distribution';base.mkdir();dist.mkdir()
    hashes=surface_edits.build(ROOT / 'target/references/releases/0.6.2.0/base' / MESH,ROOT / 'src/main/resources/recipes/surface-repair-v1.json',base/MESH)
    shutil.copyfile(ROOT / 'target/references/releases/0.6.2.0/base/CLAW.esp',base/'CLAW.esp')
    for group,prefix in [('core','00 Core'),('host','20 OBody Source')]:
        for name,path in groups[group].items():
            target=dist/prefix/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for name,path in notices.items():
        target=dist/'00 Core'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,target)
    for female in ('CBBE','3BA'):
        target=dist/'10 Human Family'/('HIMBO-and-'+female)/'SKSE/Plugins/CLAW/MorphLinks.xml'
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(family_xml(female))
    # Preserve the already reviewed FOMOD structure, with current source-owned text.
    for name in ('ModuleConfig.xml','info.xml'):
        src=ROOT / 'src/main/resources/publication/core-installer' / name;target=dist/'fomod'/name;target.parent.mkdir(exist_ok=True);shutil.copyfile(src,target)
    for folder,name in [(base,'Base'),(dist/'00 Core','Distribution')]:
        (folder/'README.md').write_bytes((ROOT / 'src/main/resources/publication' / ('Core-' + name + '.en.md')).read_bytes())
        (folder/'README.ru.md').write_bytes((ROOT / 'src/main/resources/publication' / ('Core-' + name + '.ru.md')).read_bytes())
    (dist/'00 Core/NOTICES/CORRESPONDING-SOURCE.json').write_text(json.dumps({'nativeCommit':inputs['nativeCommit'],'archive':source.name,'sha256':pin(source)['sha256'],'repository':'https://github.com/Vhodnoylogin/claw','note':'Keep the exact native corresponding-source download beside the binary release. This file does not claim a public archive URL.'},indent=2)+'\n')
    base_set=set(inventory(base))
    if base_set!=BASE_RUNTIME|{'README.md','README.ru.md'}:raise ValueError('Base contains excess files')
    for name in inventory(dist):
        if name.endswith(('.nif','.tri','.dds','.exe','.pdb','.log','.psc')) or 'SliderPresets' in name or 'meta.ini' in name:
            raise ValueError('Unexpected distribution payload: '+name)
    if sum(p.suffix.lower()=='.dll' for p in dist.rglob('*'))!=1:raise ValueError('Exactly own native DLL required')
    report={'schemaVersion':1,'kind':'CLAW minimal linked-SE release candidate','releaseAccepted':False,'visualAcceptedByOwner':False,'nativeCommit':inputs['nativeCommit'],'inputManifest':pin(external),'surfaceRecipe':pin(ROOT / 'src/main/resources/recipes/surface-repair-v1.json'),'mapping':pin(ROOT / 'src/main/resources/profiles/MorphLinks.xml'),'surfaceHashes':hashes,'base':inventory(base),'distribution':inventory(dist),'limits':['Exact native runtime SE1.7.104 only','Per-sex weight endpoints remain equal','Physics/VR/Anatomy excluded; native contains dormant development code','Untextured offline comparison cannot certify textured fur/seams']}
    if closure!={p.relative_to(ROOT).as_posix():surface_edits.sha(p.read_bytes()) for p in source_files}:
        raise ValueError('Source changed while building')
    report['sourceFiles']=closure
    report['sourceCommit']=subprocess.run(['git','-C',str(ROOT),'rev-parse','HEAD'],capture_output=True,text=True,check=True).stdout.strip()
    report['sourceDirty']=bool(subprocess.run(['git','-C',str(ROOT),'status','--porcelain'],capture_output=True,text=True,check=True).stdout.strip())
    for folder,name in [(base,'CLAW-Base-SE-Core-Candidate-20261030.zip'),(dist,'CLAW-Distribution-SE-Core-Candidate-20261030.zip')]:
        zip_tree(folder,out/name)
    report['archives']=[pin(p) for p in sorted(out.glob('*.zip'))]
    (out/'build-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--external-inputs',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    try:r=build(a.external_inputs,a.out)
    except (ValueError,OSError,KeyError,TypeError) as e:p.exit(1,'Core candidate rejected: '+str(e)+'\n')
    print(json.dumps({'baseFiles':len(r['base']),'distributionFiles':len(r['distribution']),'archives':r['archives']},indent=2))

if __name__=='__main__':main()
