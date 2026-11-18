"""Offline native candidate using an explicit verified existing compiler/SDK recipe."""
from pathlib import Path
import argparse,hashlib,json,os,subprocess,sys,time
sys.dont_write_bytecode=True
SRC=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pin(p):p=Path(p);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--previous',type=Path,required=True);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--papyrus',type=Path,required=True);a=p.parse_args()
 out=a.out.resolve();repo=SRC.parents[4]
 if out.exists() or repo==out or repo in out.parents or any(v.casefold() in {'mods','profiles','overwrite','skyrim special edition','skyrimvr'} for v in out.parts):raise ValueError('New external build only')
 manifest=read(a.manifest/'manifest.json');assert pin(a.manifest/'SealedManifest.h')==manifest['header']
 deps=read(a.previous/'verified-dependencies.json');verified=[]
 for path,digest in deps['files'].items():
  if 'mo2 test' in path.lower() or '/steamapps/' in path.replace('\\','/').lower():raise ValueError('Unexpected live dependency path')
  if sha(path)!=digest:raise ValueError('Verified dependency differs: '+path)
  verified.append(pin(path))
 out.mkdir(parents=True);(out/'obj').mkdir();(out/'Release').mkdir();(out/'Scripts').mkdir()
 def write(name,value):(out/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
 write('verified-inputs.json',{'previous':pin(a.previous/'verified-dependencies.json'),'files':verified,'manifest':pin(a.manifest/'manifest.json')})
 sourcePins=[pin(x) for x in SRC.iterdir() if x.is_file()]
 script=out/'capture-environment.cmd';script.write_bytes((a.previous/'capture-environment.cmd').read_bytes())
 raw=subprocess.run(['cmd.exe','/d','/c',str(script)],capture_output=True,text=True,check=True);env=os.environ.copy()
 for line in raw.stdout.splitlines():
  if '=' in line:
   key,value=line.split('=',1)
   if key.upper() in ('PATH','INCLUDE','LIB','LIBPATH','VCTOOLSINSTALLDIR','WINDOWSSDKDIR'):env[key]=value
 prior=read(a.previous/'actual-commands.json');commands=[]
 def run(argv,log):
  commands.append(argv);r=subprocess.run(argv,cwd=out,env=env,capture_output=True,text=True);(out/log).write_text(r.stdout+r.stderr,encoding='utf-8');write('commands.json',commands)
  if r.returncode:raise RuntimeError(log+' failed\n'+r.stdout[-6000:]+r.stderr[-1000:])
 cl=prior[0][0];args=[];old=prior[0][1:];i=0
 while i<len(old):
  arg=old[i];low=arg.lower()
  if low in ('/sourcedependencies',):i+=2;continue
  if low=='/d' and i+1<len(old) and old[i+1].startswith('ENABLE_SKYRIM_VR='):i+=2;continue
  if low.startswith('/denable_skyrim_vr=') or low.endswith('.cpp') or low.startswith(('/fo','/fd')):i+=1;continue
  if low.startswith(('/i','/external:i')) and any(x in low for x in ('bullet','hdt','fsmp','fsmp_step_witness')):i+=1;continue
  args.append(arg);i+=1
 run([cl,*args,'/I'+str(SRC),'/I'+str(a.manifest),'/Fo'+str(out/'obj/Plugin.obj'),str(SRC/'Plugin.cpp'),'/sourceDependencies',str(out/'compiler-dependencies.json')],'compile.log')
 link=prior[1][0];linkargs=[v for v in prior[1][1:] if not v.lower().startswith(('/out:','/pdb:','/implib:')) and not v.lower().endswith('.obj')]
 run([link,*linkargs,'/OUT:'+str(out/'Release/CLAWGeometryWitness.dll'),'/PDB:'+str(out/'Release/CLAWGeometryWitness.pdb'),'/IMPLIB:'+str(out/'Release/CLAWGeometryWitness.lib'),str(out/'obj/Plugin.obj')],'link.log')
 run([cl,'/nologo','/EHsc','/std:c++20','/MD','/UNDEBUG','/W4','/permissive-',str(SRC/'GeometryTests.cpp'),'/Fo'+str(out/'obj/GeometryTests.obj'),'/Fe'+str(out/'GeometryTests.exe')],'pure-compile.log')
 run([str(out/'GeometryTests.exe')],'pure-tests.log')
 run([str(Path(cl).with_name('dumpbin.exe')),'/exports',str(out/'Release/CLAWGeometryWitness.dll')],'exports.log')
 assert sha(a.papyrus)=='32281080fd8c8382ced212cd9a3d0debca811954d8929cdf1a971d06b1d861a3'
 run([str(a.papyrus),str(SRC/'CLAWGeometryWitness.psc'),'-o='+str(out/'Scripts'),'-i='+str(SRC)],'papyrus.log')
 for row in sourcePins:assert pin(row['path'])==row
 includes=read(out/'compiler-dependencies.json')['Data']['Includes']
 write('consumed-include-pins.json',[pin(Path(path)) for path in includes])
 receipt={'schema':'claw-geometry-witness-build/1','status':'BUILT_OFFLINE_NOT_INSTALLED_NOT_GAME_QUALIFIED','sources':sourcePins,'inputs':pin(out/'verified-inputs.json'),
  'manifest':pin(a.manifest/'manifest.json'),'header':pin(a.manifest/'SealedManifest.h'),'consumedIncludes':pin(out/'consumed-include-pins.json'),'compiler':pin(cl),'linker':pin(link),'papyrusCompiler':pin(a.papyrus),
  'dll':pin(out/'Release/CLAWGeometryWitness.dll'),'pex':pin(out/'Scripts/CLAWGeometryWitness.pex'),'pureTestsPassed':True,
  'sdkLayout':'EXCLUSIVE_SKYRIM_FLAT translation unit; SDK typed lock member and sizeof0x88 asserted; unchanged verified multi-runtime CommonLib static library',
  'runtimeABIQualified':False,'gpuReadsOrWrites':False,'worldWrites':False,'installed':False,'gameStarted':False,'finishedUtcEpoch':time.time()}
 write('build-receipt.json',receipt);print(json.dumps({'status':receipt['status'],'dll':receipt['dll'],'pex':receipt['pex']}))
if __name__=='__main__':main()
