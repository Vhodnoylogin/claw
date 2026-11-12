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
a=p.parse_args(args)
if a.out.exists():raise ValueError('Use a new visibility receipt')
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
a.out.write_text(json.dumps(result,indent=2)+'\n')
print('NEUTRAL_VISIBILITY|'+json.dumps({k:result[k] for k in ('bodyParityInside','bodyParityOutside','tubeOutside','ballsOutside','fullyOutsideTriangles')}))
