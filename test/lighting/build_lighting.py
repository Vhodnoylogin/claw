"""Offline-only QASmoke inspection lights; no live installation writes."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib

NAME = 'test_CLAWInspectionLighting.esp'
CELL = 0x00032AE7
LIGHT = 0x03000800
POSITIONS = [(-2537.94482421875, y, 7106.4501953125) for y in (1200., 1550., 1900.)]

def sha(data): return hashlib.sha256(data).hexdigest()
def sub(kind, raw): return kind.encode('ascii')+struct.pack('<H', len(raw))+raw
def subs(raw):
    at = 0
    result = []
    while at < len(raw):
        kind, size = struct.unpack_from('<4sH', raw, at); at += 6
        if kind == b'XXXX':
            assert size == 4
            size = struct.unpack_from('<I', raw, at)[0]; at += 4
            kind = raw[at:at+4]; at += 6
        assert at+size <= len(raw)
        result.append((kind, raw[at:at+size])); at += size
    assert at == len(raw)
    return result

def records(data, start=0, end=None, ancestors=()):
    end = len(data) if end is None else end
    while start < end:
        assert start+24 <= end
        kind, size = struct.unpack_from('<4sI', data, start)
        limit = start+size if kind == b'GRUP' else start+24+size
        assert start < limit <= end
        if kind == b'GRUP':
            assert size >= 24
            yield from records(data, start+24, limit, ancestors+(data[start:start+24],))
        else:
            flags, form = struct.unpack_from('<II', data, start+8)
            raw = data[start+24:limit]
            if flags & 0x40000:
                count = struct.unpack_from('<I', raw)[0]; raw = zlib.decompress(raw[4:])
                assert len(raw) == count
            yield kind, form, flags, raw, data[start:limit], ancestors
        start = limit
    assert start == end

def rec(kind, form, payload, flags=0):
    return struct.pack('<4sIIIIHH', kind.encode('ascii'), len(payload), flags, form, 0, 44, 0)+payload
def grp(label, kind, payload, template=None):
    header = template or struct.pack('<4sI4siHHHH', b'GRUP', 0, label, kind, 0, 0, 0, 0)
    assert header[:4] == b'GRUP' and len(header) == 24
    return header[:4]+struct.pack('<I', 24+len(payload))+header[8:]+payload

def build(master, cell_source, strings_dir, output):
    source = master.read_bytes()
    cell_data=cell_source.read_bytes()
    source_rows=list(records(cell_data))
    source_masters=[v.rstrip(b'\0').decode() for k,v in subs(source_rows[0][3]) if k==b'MAST']
    assert source_masters==['Skyrim.esm','Update.esm'] and cell_source.name=='Dragonborn.esm'
    masters=[*source_masters,cell_source.name]
    cells = [r for r in source_rows if r[0] == b'CELL' and r[1] == CELL]
    assert len(cells) == 1
    cell = cells[0]
    fields = dict(subs(cell[3]))
    assert fields[b'EDID'] == b'QASmoke\0'
    assert set(fields)=={b'EDID',b'FULL',b'DATA',b'XCLL',b'LTMP',b'XCLW',b'XCIM'}
    assert fields[b'DATA']==b'\x03\0'
    assert fields[b'LTMP']==b'\0'*4 and fields[b'XCIM']==struct.pack('<I',0x13B32)
    assert len(cell[5]) == 3
    assert [struct.unpack_from('<i', h, 12)[0] for h in cell[5]] == [0, 2, 3]
    assert cell[5][0][8:12] == b'CELL'
    # Preserve the complete winning Dragonborn CELL byte-for-byte. No ambient/fog/water,
    # ownership, region, acoustic, template or existing reference is changed.
    # Existing master children remain inherited; only our three new refs are added.
    cell_bytes = cell[4]
    # The on-disk DATA appends TESValueForm/TESWeightForm to OBJ_LIGH.
    lighting = struct.pack('<iI4B I6fIf', -1, 450, 220, 225, 230, 0, 0,
                           1.0, 90.0, 1.0, 0.0, 0.0, 0.0, 0, 0.)
    assert len(lighting) == 48
    light = rec('LIGH', LIGHT, sub('EDID', b'test_CLAWInspectionNeutralFill\0')+
                sub('OBND', struct.pack('<6h', 0, 0, 0, 0, 0, 0))+
                sub('DATA', lighting)+sub('FNAM', struct.pack('<f', 1.0)))
    refs = b''
    for index, xyz in enumerate(POSITIONS, 1):
        refs += rec('REFR', LIGHT+index,
            sub('EDID', f'test_CLAWInspectionFill{index}'.encode()+b'\0')+
            sub('NAME', struct.pack('<I', LIGHT))+
            sub('DATA', struct.pack('<6f', *xyz, 0., 0., 0.)))
    children = grp(struct.pack('<I', CELL), 6,
                   grp(struct.pack('<I', CELL), 9, refs))
    cell_group = cell_bytes+children
    for template in reversed(cell[5]):
        cell_group = grp(template[8:12], struct.unpack_from('<i', template, 12)[0],
                         cell_group, template)
    # HEDR counts five non-header records plus six GRUP headers.
    header = rec('TES4', 0, sub('HEDR', struct.pack('<fII', 1.7, 11, 0x804))+
                 sub('CNAM', b'CLAW test scene\0')+
                 sub('SNAM', b'Test-only neutral fill lights. No gameplay or body changes.\0')+
                 b''.join(sub('MAST',m.encode()+b'\0')+sub('DATA',b'\0'*8) for m in masters), flags=0x80)
    plugin = header+grp(b'LIGH', 0, light)+cell_group
    output.mkdir(parents=True, exist_ok=False)
    package = output/'payload'; package.mkdir()
    (package/NAME).write_bytes(plugin)
    # Keep the vanilla localized FULL payload exactly unchanged. A localized ESP
    # must supply its own STRINGS lookup; master string IDs are not inherited.
    # Copy only this one cell-name entry per original language, never whole tables.
    string_id = struct.unpack('<I',fields[b'FULL'])[0]
    assert len(fields[b'FULL']) == 4
    tables = sorted(strings_dir.glob('dragonborn_*.strings'))
    assert len(tables) == 9
    target_strings=package/'Strings'; target_strings.mkdir()
    string_sources=[]
    for source_path in tables:
        source_bytes=source_path.read_bytes()
        count, data_size=struct.unpack_from('<II',source_bytes)
        assert len(source_bytes)==8+count*8+data_size
        entries=dict(struct.unpack_from('<II',source_bytes,8+i*8) for i in range(count))
        assert string_id in entries
        begin=8+count*8+entries[string_id]
        end=source_bytes.index(0,begin)+1
        value=source_bytes[begin:end]
        target_name=NAME[:-4]+source_path.name[len('dragonborn'):]
        tiny=struct.pack('<IIII',1,len(value),string_id,0)+value
        (target_strings/target_name).write_bytes(tiny)
        string_sources.append({'path':str(source_path.resolve()),'sha256':sha(source_bytes),
            'output':str(Path('Strings')/target_name),'entryId':f'{string_id:08X}',
            'entryBytes':value.hex(),'bytes':len(tiny),'sha256':sha(tiny)})
    result = validate(plugin, cell_bytes)
    result.update(master={'path':str(master.resolve()),'bytes':len(source),'sha256':sha(source)},
        winningCellSource={'path':str(cell_source.resolve()),'bytes':len(cell_data),'sha256':sha(cell_data)},
        output={'name':NAME,'bytes':len(plugin),'sha256':sha(plugin)},
        light={'form':'03000800','radiusGameUnits':450,'rgb':[220,225,230],
               'fade':1.0,'falloffExponent':1.0,'shadow':False,'flicker':False,
               'positionGameUnits':POSITIONS},
        cellAncestorHeaders=[h.hex() for h in cell[5]], localizedCellNameTables=string_sources,
        scope='Offline binary structural checks only; rendered lighting not yet qualified.')
    (output/'validation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    (output/'README.md').write_text('''# CLAW inspection lighting — test data only

Bundle `payload/test_CLAWInspectionLighting.esp` into the existing
`test_CLAW - Human and Werewolf Comparison` installation. Enable the ESP only in
the CLAW test profile. This is not a third production mod or release archive.

Three neutral static omni lights without shadows, flicker, sound or visible
models fill the accepted QASmoke actor rows. They use RGB220/225/230, radius450,
fade1, X=-2537.944824, Y=1200/1550/1900, Z=7106.450195. The existing complete
winning Dragonborn.esm QASmoke CELL record is carried unchanged; original ambient/fog and all
master reference children remain inherited. Only one own light definition and
three new temporary placed references are added. No scripts, quests, bodies,
textures, skeletons, save changes or external runtime dependencies are included.

Source: build_lighting.py and the exact local Skyrim.esm/Dragonborn.esm identified in
validation.json. The localized ESP includes nine tiny STRINGS tables containing
only the original QASmoke name in each master language, preserving the complete
CELL record bytes and name. LIGH DATA is the48-byte disk layout, including
Value/Weight. CommonLib TESObjectLIGH.h documents its first40bytes;
independent Spriggit parsing/round-trip checks are recorded separately.

After idle installation, start a fresh owned test session. Preserve all accepted
actor positions and Off AI/collision. Verify three light references at the exact
coordinates, then inspect front and side of both sexes, thin/muscular/heavy.
Check fur detail, neutral colour, no clipping/white skin highlights and no light
pop at camera changes. Reduce fade if skin is washed out; do not solve it by
changing production textures or adding unbounded overlapping lights. Compare
human/wolf frames under unchanged lighting. Rendered acceptance remains pending.
''',encoding='utf-8')
    return result

def validate(plugin, original_cell):
    rows=list(records(plugin)); kinds=[r[0] for r in rows]
    assert sorted(kinds) == sorted([b'TES4',b'LIGH',b'CELL',b'REFR',b'REFR',b'REFR'])
    header=dict(subs(rows[0][3])); assert [v for k,v in subs(rows[0][3]) if k==b'MAST']==[b'Skyrim.esm\0',b'Update.esm\0',b'Dragonborn.esm\0']
    assert struct.unpack('<fII', header[b'HEDR'])[1:] == (11,0x804)
    assert rows[0][2]==0x80
    cell=next(r for r in rows if r[0]==b'CELL'); assert cell[4]==original_cell and cell[1]==CELL
    light=next(r for r in rows if r[0]==b'LIGH'); assert light[1]==LIGHT and light[2]==0
    l=dict(subs(light[3])); assert len(l[b'DATA'])==48
    assert struct.unpack_from('<I',l[b'DATA'],12)[0]==0
    assert set(l)=={b'EDID',b'OBND',b'DATA',b'FNAM'}
    refs=[r for r in rows if r[0]==b'REFR']
    for index,(r,xyz) in enumerate(zip(refs,POSITIONS),1):
        assert r[1]==LIGHT+index and r[2]==0
        f=dict(subs(r[3])); assert struct.unpack('<I',f[b'NAME'])[0]==LIGHT
        assert struct.unpack('<6f',f[b'DATA'])==(*xyz,0.,0.,0.)
        assert [struct.unpack_from('<i',h,12)[0] for h in r[5]]==[0,2,3,6,9]
        assert all(struct.unpack_from('<I',h,8)[0]==CELL for h in r[5][-2:])
    assert len({r[1] for r in rows})==6
    return {'passed':True,'recordKinds':[k.decode() for k in kinds],
            'completeWinningCellByteIdentical':True,'ownRecords':4,
            'newPlacedReferences':3,'masterCount':3,'runtimeTested':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--master',type=Path,required=True);p.add_argument('--cell-source',type=Path,required=True);p.add_argument('--strings',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); print(json.dumps(build(a.master,a.cell_source,a.strings,a.output),indent=2))
