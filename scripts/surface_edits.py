"""Replay explicit authored surface edits on the pinned published CLAW base.

This is baked authoring data, not a procedural reconstruction of every sculpt
experiment. NIF edits are restricted to vertices, skin weights and spheres;
TRIP edits address named shape/morph records. All other bytes stay protected.
"""
from pathlib import Path
import hashlib
import json
import struct
import numpy as np
from head_split import Nif, Reader, encode


def sha(data):
    return hashlib.sha256(data).hexdigest()


class PackedPartitions:
    """Reviewed SSE packed VB and one or more mapped skin partitions."""
    def __init__(self, data):
        r = Reader(data)
        count, size, stride, desc = r.unpack('<IIIQ')
        if not 0 < count < 256 or stride != 40 or size % stride:
            raise ValueError('Unsupported packed vertex layout')
        self.header = data[:20]
        self.vertices = np.frombuffer(r.take(size), np.uint8).reshape(-1,40).copy()
        self.parts = []
        for _ in range(count):
            nv, nt, nb, ns, nw = r.unpack('<5H')
            if ns or nw != 4:
                raise ValueError('Unsupported partition influence layout')
            prefix = encode('<5H', nv, nt, nb, ns, nw) + r.take(nb*2)
            if r.take(1) != b'\1':
                raise ValueError('Missing vertex map')
            prefix += b'\1' + r.take(nv*2)
            if r.take(1) != b'\1':
                raise ValueError('Missing partition weights')
            weights = np.frombuffer(r.take(nv*16), np.uint8).reshape(nv,16).copy()
            if r.take(1) != b'\1':
                raise ValueError('Missing partition triangles')
            middle = b'\1' + r.take(nt*6)
            if r.take(1) != b'\1':
                raise ValueError('Missing partition indices')
            indices = np.frombuffer(r.take(nv*4), np.uint8).reshape(nv,4).copy()
            tail = r.take(10+nt*6)
            self.parts.append([prefix, weights, middle, indices, tail])
        r.done()

    def bytes(self):
        return self.header + self.vertices.tobytes() + b''.join(
            a+b'\1'+w.tobytes()+m+b'\1'+ix.tobytes()+t for a,w,m,ix,t in self.parts)


def skin_data(data):
    r = Reader(data)
    frame = r.take(52)
    count, has = r.unpack('<IB')
    if has != 1:
        raise ValueError('Expected vertex weights')
    bones = []
    for _ in range(count):
        fixed = r.take(68)
        weights = [list(r.unpack('<Hf')) for _ in range(r.unpack('<H')[0])]
        bones.append([fixed, weights])
    r.done()
    return frame, bones


def write_skin(frame, bones):
    return (frame + encode('<IB', len(bones), 1) + b''.join(
        fixed + encode('<H', len(weights)) + b''.join(encode('<Hf', *row) for row in weights)
        for fixed, weights in bones))


def trip_records(data):
    r = Reader(data)
    magic = r.take(4)
    if magic not in (b'PIRT', b'\0IRT'):
        raise ValueError('Unsupported TRI')
    def name():
        return r.take(r.unpack('<B')[0]).decode('iso-8859-15')
    shapes = []
    for _ in range(r.unpack('<H')[0]):
        shape = name()
        records = []
        for _ in range(r.unpack('<H')[0]):
            morph = name()
            scale, count = r.unpack('<fH')
            rows = [list(r.unpack('<H3h')) for _ in range(count)]
            if not np.isfinite(scale) or scale <= 0 or len({x[0] for x in rows}) != count:
                raise ValueError('Invalid TRI record')
            records.append([morph, scale, rows])
        if len({x[0] for x in records}) != len(records):
            raise ValueError('Duplicate morph')
        shapes.append([shape, records])
    r.done()
    if len({x[0] for x in shapes}) != len(shapes):
        raise ValueError('Duplicate shape')
    return magic, shapes


def write_trip(magic, shapes):
    def name(value):
        b = value.encode('iso-8859-15')
        return encode('<B', len(b)) + b
    return magic + encode('<H', len(shapes)) + b''.join(
        name(shape) + encode('<H', len(records)) + b''.join(
            name(morph) + encode('<fH', scale, len(rows)) +
            b''.join(encode('<H3h', *row) for row in rows)
            for morph, scale, rows in records) for shape, records in shapes)


def changed_rows(a, b, dtype):
    x = np.frombuffer(a, dtype).reshape(len(a) // np.dtype(dtype).itemsize // 4, 4)
    y = np.frombuffer(b, dtype).reshape(x.shape)
    return [[int(i), *y[i].tolist()] for i in np.flatnonzero(np.any(x != y, axis=1))]


def nif_recipe(before, after):
    a, b = Nif(before), Nif(after)
    if (a.prefix, a.type_names, a.kinds, a.strings, a.footer) != (b.prefix, b.type_names, b.kinds, b.strings, b.footer):
        raise ValueError('NIF structure changed')
    edits = []
    for index, (x, y) in enumerate(zip(a.blocks, b.blocks)):
        if x == y:
            continue
        kind = a.kind(index)
        edit = {'block': index, 'kind': kind, 'before': sha(x), 'after': sha(y)}
        if kind == 'NiSkinData':
            af, ab = skin_data(x); bf, bb = skin_data(y)
            if af != bf or len(ab) != len(bb):
                raise ValueError('Skin frame or bone inventory changed')
            edit['bones'] = []
            for i, ((fixed, weights), (newfixed, newweights)) in enumerate(zip(ab, bb)):
                if fixed[:52] != newfixed[:52]:
                    raise ValueError('Bone bind changed')
                if fixed != newfixed or weights != newweights:
                    edit['bones'].append({'bone': i, 'sphere': list(struct.unpack('<4f', newfixed[52:])), 'weights': newweights})
        elif kind == 'NiSkinPartition':
            ap, bp = PackedPartitions(x), PackedPartitions(y)
            if ap.header != bp.header or len(ap.parts)!=len(bp.parts) or any((a[0],a[2],a[4])!=(b[0],b[2],b[4]) for a,b in zip(ap.parts,bp.parts)):
                raise ValueError('Partition topology changed')
            if ap.vertices.shape != bp.vertices.shape or not np.array_equal(ap.vertices[:,16:20], bp.vertices[:,16:20]):
                raise ValueError('Vertex inventory or UV changed')
            edit['vertices'] = []
            for i in np.flatnonzero(np.any(ap.vertices != bp.vertices, axis=1)):
                row = bp.vertices[i].tobytes()
                edit['vertices'].append([int(i), *struct.unpack('<4f', row[:16]), *row[20:28], *struct.unpack('<4H', row[28:36]), *row[36:40]])
            edit['partitionWeights'] = [[part,*row] for part,(aa,bb) in enumerate(zip(ap.parts,bp.parts)) for row in changed_rows(aa[1].tobytes(),bb[1].tobytes(),'<f4')]
            edit['partitionIndices'] = [[part,*row] for part,(aa,bb) in enumerate(zip(ap.parts,bp.parts)) for row in changed_rows(aa[3].tobytes(),bb[3].tobytes(),'u1')]
        elif kind == 'BSTriShape':
            extra = struct.unpack_from('<I', x, 4)[0]
            pos = 72 + extra*4
            if x[:pos] != y[:pos] or x[pos+16:] != y[pos+16:]:
                raise ValueError('Shape edit exceeds sphere')
            edit['sphere'] = list(struct.unpack_from('<4f', y, pos))
        else:
            raise ValueError('Unsupported authored block: ' + kind)
        edits.append(edit)
    recipe = {'before': sha(before), 'after': sha(after), 'blocks': edits}
    if apply_nif(before, recipe) != after:
        raise ValueError('Authored NIF replay failed')
    return recipe


def apply_nif(data, recipe):
    if sha(data) != recipe['before']:
        raise ValueError('NIF input drift')
    c = Nif(data)
    seen = set()
    for e in recipe['blocks']:
        i = e['block']
        if i in seen or c.kind(i) != e['kind'] or sha(c.blocks[i]) != e['before']:
            raise ValueError('Invalid block binding')
        seen.add(i)
        if e['kind'] == 'NiSkinData':
            frame, bones = skin_data(c.blocks[i])
            for row in e['bones']:
                j = row['bone']
                bones[j] = [bones[j][0][:52] + encode('<4f', *row['sphere']), row['weights']]
            out = write_skin(frame, bones)
        elif e['kind'] == 'NiSkinPartition':
            p = PackedPartitions(c.blocks[i])
            for row in e['vertices']:
                j = row[0]
                packed = encode('<4f', *row[1:5]) + p.vertices[j,16:20].tobytes() + bytes(row[5:13]) + encode('<4H', *row[13:17]) + bytes(row[17:21])
                p.vertices[j] = np.frombuffer(packed, np.uint8)
            for row in e['partitionWeights']:
                p.parts[row[0]][1][row[1]] = np.frombuffer(encode('<4f', *row[2:]), np.uint8)
            for row in e['partitionIndices']:
                p.parts[row[0]][3][row[1]] = row[2:]
            out = p.bytes()
        elif e['kind'] == 'BSTriShape':
            out = bytearray(c.blocks[i]); pos = 72 + struct.unpack_from('<I', out, 4)[0]*4
            struct.pack_into('<4f', out, pos, *e['sphere']); out = bytes(out)
        else:
            raise ValueError('Unsupported authored edit')
        if sha(out) != e['after']:
            raise ValueError('Authored block replay mismatch')
        c.blocks[i] = out
    out = c.bytes()
    if sha(out) != recipe['after']:
        raise ValueError('Authored NIF output mismatch')
    return out


def tri_recipe(before, after):
    am, a = trip_records(before); bm, b = trip_records(after)
    if am != bm or [x[0] for x in a] != [x[0] for x in b]:
        raise ValueError('TRI shape inventory changed')
    edits = []
    for (shape, old), (_, new) in zip(a, b):
        original = {r[0]: r for r in old}
        replacements = [r for r in new if original.get(r[0]) != r]
        removed = sorted(set(original)-{r[0] for r in new})
        if replacements or removed or [r[0] for r in old] != [r[0] for r in new]:
            edits.append({'shape': shape, 'order': [r[0] for r in new], 'removedRecords': removed, 'records': replacements})
    if {r[0] for _,rows in a for r in rows} != {r[0] for _,rows in b for r in rows}:
        raise ValueError('Public morph inventory changed')
    recipe = {'before': sha(before), 'after': sha(after), 'shapes': edits}
    if apply_tri(before, recipe) != after:
        raise ValueError('Authored TRI replay failed')
    return recipe


def apply_tri(data, recipe):
    if sha(data) != recipe['before']:
        raise ValueError('TRI input drift')
    magic, shapes = trip_records(data)
    edits = {e['shape']: e for e in recipe['shapes']}
    if len(edits) != len(recipe['shapes']) or not set(edits) <= {s for s,_ in shapes}:
        raise ValueError('Invalid TRI shape binding')
    for shape, records in shapes:
        if shape not in edits:
            continue
        e = edits[shape]; current = {r[0]: r for r in records}
        for name in e.get('removedRecords', []):
            if name not in current:
                raise ValueError('Missing explicitly removed TRI record')
            del current[name]
        current.update({r[0]: r for r in e['records']})
        if len(e['order']) != len(set(e['order'])) or set(e['order']) != set(current):
            raise ValueError('Invalid TRI order')
        records[:] = [current[name] for name in e['order']]
    out = write_trip(magic, shapes)
    if sha(out) != recipe['after']:
        raise ValueError('Authored TRI output mismatch')
    return out


def build(base, recipe_path, output):
    base, output = Path(base).resolve(), Path(output).resolve()
    if output.exists() or output == base or base in output.parents or output in base.parents:
        raise ValueError('New external output directory required')
    recipe = json.loads(Path(recipe_path).read_text(encoding='utf-8'))
    if recipe.get('schema') != 'claw-authored-surface-edits/1':
        raise ValueError('Unsupported surface edit schema')
    files = {}
    for sex in ('male','female'):
        for suffix in ('_0.nif','_1.nif','.tri'):
            name = sex+'bodywerewolf'+suffix
            e = recipe['files'][name]
            if 'alias' in e:
                if suffix != '_1.nif' or e['alias'] != sex+'bodywerewolf_0.nif':
                    raise ValueError('Only matching weight endpoint aliases supported')
                e = recipe['files'][e['alias']]
            original = (base/name).read_bytes()
            files[name] = (apply_tri if suffix=='.tri' else apply_nif)(original,e)
    output.mkdir(parents=True)
    for name, data in files.items():
        (output/name).write_bytes(data)
    return {name: sha(data) for name,data in files.items()}
