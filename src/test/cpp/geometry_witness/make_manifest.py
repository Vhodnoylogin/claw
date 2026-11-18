"""Read pinned private NIF/TRI inputs and emit a new external sealed header only."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
sys.dont_write_bytecode=True
PINS={'baseline':'e5a9d6b5572dfeb101afe149e79cf1961f73614ce108b23f98b4237c3a2e1212',
      'candidate':'74a068f397b824d61d0aa7ba117ada7359973624b5ded8e4ba82a86cb13f0ac4',
      'tri':'34744d5599531026f53a36e5438b39be3f880cd2cb7d9a0056b00bf343d05192'}
def pin(p):
 b=p.read_bytes();return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def topology(faces):
 rows=[]
 for face in faces:
  f=list(face);i=f.index(min(f));rows.append(tuple(f[i:]+f[:i]))
 h=14695981039346656037
 for f in sorted(rows):
  for value in f:
   for b in struct.pack('<H',value):h=((h^b)*1099511628211)&((1<<64)-1)
 return h
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--tri',type=Path,required=True);p.add_argument('--pynifly',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 out=a.out.resolve();repo=Path(__file__).resolve().parents[5]
 if out.exists() or repo==out or repo in out.parents or any(x.casefold() in {'mods','profiles','overwrite','skyrim special edition','skyrimvr'} for x in out.parts):raise ValueError('New external output only')
 pins={name:pin(getattr(a,name).resolve()) for name in PINS}
 for name,value in pins.items():
  if value['sha256']!=PINS[name]:raise ValueError('Exact approved input differs: '+name)
 sys.path.insert(0,str(a.pynifly.resolve()));from pyn import pynifly
 pynifly.NifFile.Load(str(a.pynifly/'NiflyDLL.dll'))
 nifs={name:pynifly.NifFile(value['path']) for name,value in pins.items() if name!='tri'};shapes=[]
 for role,points in [('fur_belly',[577,578,579,580,581,582]),('head',[779,1676,1677])]:
  chosen={name:next(s for s in n.shapes if s.name==role) for name,n in nifs.items()};s=chosen['baseline'];t=chosen['candidate']
  assert s.blockname==t.blockname=='BSTriShape' and s.bone_names==t.bone_names and s.tris==t.tris and len(s.verts)==len(t.verts)
  assert len(s.bone_names)<=128 and len(s.tris)<=32768
  rows={}
  for variant,shape in chosen.items():
   rows[variant]=[]
   for point in points:
    weights=[sum(v for i,v in shape.bone_weights.get(bone,[]) if i==point) for bone in shape.bone_names]
    rows[variant].append([struct.unpack('<H',struct.pack('<e',v))[0] for v in weights])
  shapes.append({'role':role,'vertices':len(s.verts),'triangles':len(s.tris),'pointCount':len(points),'points':points,'bones':len(s.bone_names),'boneNames':s.bone_names,'topologyHash':topology(s.tris),**rows})
 text='#pragma once\n#include <array>\n#include <cstdint>\nnamespace sealed {\n'
 text+='struct Shape {const char* role;unsigned vertices,triangles,pointCount;std::array<unsigned,6> points;unsigned bones;std::array<const char*,128> boneNames;std::uint64_t topologyHash;std::array<std::array<std::uint16_t,128>,6> baseline,candidate;};\n'
 for name in PINS:text+=f'inline constexpr const char* {name}Sha="{PINS[name]}";\n'
 text+='inline const std::array<Shape,2> shapes{{\n'
 for s in shapes:
  ar=lambda values:'{'+','.join(map(str,values))+'}'
  names='{'+','.join(json.dumps(v) for v in s['boneNames'])+'}'
  weights=lambda name:'{{'+','.join(ar(row) for row in s[name])+'}}'
  text+='Shape{'+','.join([json.dumps(s['role']),str(s['vertices']),str(s['triangles']),str(s['pointCount']),ar(s['points']),str(s['bones']),names,str(s['topologyHash'])+'ull',weights('baseline'),weights('candidate')])+'},\n'
 text+='}};\n}\n';out.mkdir(parents=True)
 (out/'SealedManifest.h').write_text(text,encoding='utf-8')
 receipt={'schema':'claw-geometry-sealed-input/1','status':'OFFLINE_NONSHIPPING_ONLY','inputs':pins,'shapes':shapes,'header':pin(out/'SealedManifest.h'),
          'readerFiles':[pin(x) for x in sorted((a.pynifly/'pyn').glob('*.py'))]+[pin(a.pynifly/'NiflyDLL.dll')],'generator':pin(Path(__file__).resolve())}
 (out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':receipt['status'],'out':str(out),'shapes':[(s['role'],s['vertices'],s['triangles']) for s in shapes]}))
if __name__=='__main__':main()
