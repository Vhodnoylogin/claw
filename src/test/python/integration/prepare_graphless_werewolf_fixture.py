"""Offline-only RACE override builder. Owner supplies installed plugins; no manager/game API."""
from pathlib import Path
import argparse,hashlib,json,struct,subprocess,zlib,shutil
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
PLUGIN='test_CLAW - Graphless Werewolf Feasibility.esp'
def records(data,start=0,end=None):
    end=len(data) if end is None else end;pos=start
    while pos<end:
        if pos+24>end:raise ValueError('Truncated TES container')
        typ=data[pos:pos+4];size,flags,form=struct.unpack_from('<III',data,pos+4)
        if typ==b'GRUP':
            if size<24 or pos+size>end:raise ValueError('Invalid group span')
            yield from records(data,pos+24,pos+size);pos+=size;continue
        if pos+24+size>end:raise ValueError('Invalid record span')
        packed=data[pos+24:pos+24+size];raw=zlib.decompress(packed[4:]) if flags&0x40000 else packed
        yield {'type':typ,'flags':flags,'form':form,'header':data[pos:pos+24],'packed':packed,'raw':raw}
        pos+=24+size
    if pos!=end:raise ValueError('Unconsumed container bytes')
def subs(raw):
    pos=0;extended=None;out=[]
    while pos<len(raw):
        if pos+6>len(raw):raise ValueError('Truncated subrecord')
        typ=raw[pos:pos+4];size=struct.unpack_from('<H',raw,pos+4)[0];pos+=6
        if typ==b'XXXX':
            if size!=4:raise ValueError('Bad extended size')
            extended=struct.unpack_from('<I',raw,pos)[0];pos+=4;continue
        if extended is not None:size=extended;extended=None
        if pos+size>len(raw):raise ValueError('Bad subrecord span')
        out.append((typ,raw[pos:pos+size]));pos+=size
    return out
text=lambda b:b.rstrip(b'\0').decode('utf8')
def sub(typ,payload):return typ+struct.pack('<H',len(payload))+payload
def record(typ,form,raw,flags=0):return struct.pack('<4sIIIIHH',typ,len(raw),flags,form,0,44,0)+raw
def read_plugin(path):
    data=Path(path).read_bytes();rows=list(records(data));header=rows[0]
    if header['type']!=b'TES4':raise ValueError('No TES4 header')
    masters=[text(v) for k,v in subs(header['raw']) if k==b'MAST']
    return rows,masters
def form_key(form,masters,own):
    index=form>>24
    if index>len(masters):raise ValueError('Unresolved master index')
    return (masters[index] if index<len(masters) else own).casefold(),form&0xFFFFFF

def prepare_seed(out,evidence,game,mods,spriggit):
    if out.exists():raise FileExistsError('Use a fresh external build directory')
    cfg=json.loads((evidence/'config.json').read_bytes());pins=json.loads((evidence/'vfs-pins.json').read_bytes())
    archived=evidence/'runtime/runs/20261112-122338-305f7d/test-profile'
    modlist=archived/'modlist.txt';enabled=[line[1:] for line in modlist.read_text(encoding='utf-8-sig').splitlines() if line.startswith('+')]
    requested=cfg['copied_profile_mods']['enabledPlugins'];sources=[];winners={};templates={}
    for name in requested:
        candidates=[mods/mod/name for mod in enabled if (mods/mod/name).is_file()]
        if (mods.parent/'overwrite'/name).exists():raise ValueError('Unaccounted plugin overwrite: '+name)
        source=candidates[0] if candidates else game/'Data'/name
        if not source.is_file():raise FileNotFoundError(source)
        retained=next((r for r in pins if r['path'].casefold()==name.casefold()),None)
        if retained and (source.resolve()!=Path(retained['source']).resolve() or SHA(source)!=retained['sha256']):raise ValueError('Retained VFS plugin mismatch: '+name)
        rows,masters=read_plugin(source);hits=[]
        for row in rows:
            if row['type'] not in (b'RACE',b'ARMO',b'ARMA'):continue
            key=form_key(row['form'],masters,name)
            if key[0]!='skyrim.esm' or key[1] not in (0xCDD84,0xCDD86,0xCDD87):continue
            summary={'record':row['type'].decode(),'formKey':f'{key[1]:06X}:Skyrim.esm','source':str(source),'plugin':name,'sourceSha256':SHA(source),'masterList':masters,'recordFlags':row['flags'],'payloadSha256':hashlib.sha256(row['raw']).hexdigest()}
            hits.append(summary);winners[(row['type'],key[1])]=summary;templates[(row['type'],key[1])]=(row,masters,source)
        sources.append({'plugin':name,'source':str(source),'sha256':SHA(source),'masters':masters,'relevantRecords':hits,'sourceResolution':'Explicit retained native test mod priority; exact retained VFS pin where supplied; no new native resolver claim'})
    winning,masters,source=templates[(b'RACE',0xCDD84)]
    assert source.name=='Dawnguard.esm',source
    fields=subs(winning['raw']);graphs=[(i,text(v)) for i,(k,v) in enumerate(fields) if k==b'MODL' and v.lower().endswith(b'.hkx\0')]
    assert len(graphs)==2 and all(v.lower()=='actors\\werewolfbeast\\werewolfbeastproject.hkx' for i,v in graphs)
    out.mkdir(parents=True);seed=out/'winning-source'/PLUGIN;seed.parent.mkdir()
    allmasters=masters+[source.name]
    header=sub(b'HEDR',struct.pack('<fII',1.7,1,0x800))+sub(b'CNAM',b'CLAW test-only fixture\0')+sub(b'SNAM',b'External winning-race source seed; not installed\0')
    for master in allmasters:header+=sub(b'MAST',master.encode()+b'\0')+sub(b'DATA',struct.pack('<Q',0))
    race=winning['header']+winning['packed']
    group=struct.pack('<4sI4sIHHHH',b'GRUP',24+len(race),b'RACE',0,0,0,0,0)+race
    seed.write_bytes(record(b'TES4',0,header,flags=0x80)+group)
    support=extract_dawnguard_tables(seed.parent,game/'Data/Skyrim - Interface.bsa')
    (out/'localized-source-support.json').write_text(json.dumps(support,indent=2)+'\n',encoding='utf8')
    proof={'declaredProfile':'CLAW CBPC Passive Binding Diagnostic','historicalNativeRun':'20261112-122338-305f7d','archivedModlist':str(modlist),'archivedModlistSha256':SHA(modlist),'config':str(evidence/'config.json'),'configSha256':SHA(evidence/'config.json'),'activePlugins':requested,'sources':sources,'winningRace':winners[(b'RACE',0xCDD84)],'winningSkin':winners[(b'ARMO',0xCDD86)],'winningAddon':winners[(b'ARMA',0xCDD87)],'graphFields':[{'subrecordIndex':i,'oldValue':v} for i,v in graphs],'seedMasters':allmasters,'seedSha256':SHA(seed),'runtimeAdmissionRequired':True}
    (out/'winning-race-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8')
    result=subprocess.run([str(spriggit),'serialize','--InputPath',str(seed),'--OutputPath',str(out/'winning-readback'),'--GameRelease','SkyrimSE','--PackageName','Spriggit.Yaml','--PackageVersion','0.41.0','--Threads','1','--ErrorOnUnknown','true'],capture_output=True,text=True,timeout=90)
    (out/'winning-serialize.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    if result.returncode:raise RuntimeError('Spriggit winning source readback failed; see log')
    print(json.dumps({'winningRace':str(source),'scannedPlugins':len(sources),'seed':str(seed),'graphs':graphs}))
def extract_dawnguard_tables(destination,archive):
    """Only Dawnguard .strings, renamed to this fixture namespace; local test inputs."""
    import lz4.block
    blob=archive.read_bytes();ver,offset,aflags,nfolders,nfiles,folder_bytes,name_bytes,fileflags=struct.unpack_from('<8I',blob,4)
    assert blob[:4]==b'BSA\0' and ver==105
    folders=[];pos=offset
    for _ in range(nfolders):
        h,count,pad,begin=struct.unpack_from('<QIIQ',blob,pos);pos+=24;folders.append((count,begin))
    entries=[];name_start=pos
    for count,begin in folders:
        pos=begin-name_bytes;length=blob[pos];folder=blob[pos+1:pos+1+length].rstrip(b'\0').decode();pos+=1+length
        for _ in range(count):
            h,size,begin=struct.unpack_from('<QII',blob,pos);pos+=16;entries.append((folder,size,begin))
        name_start=max(name_start,pos)
    pos=name_start;tables=[];(destination/'Strings').mkdir()
    for folder,size,begin in entries:
        end=blob.index(b'\0',pos);name=blob[pos:end].decode();pos=end+1
        if folder.lower()!='strings' or not name.lower().startswith('dawnguard_') or not name.lower().endswith('.strings'):continue
        payload=blob[begin:begin+(size&0x3fffffff)]
        if aflags&0x100:payload=payload[1+payload[0]:]
        if bool(aflags&4)^bool(size&0x40000000):payload=lz4.block.decompress(payload[4:],uncompressed_size=struct.unpack_from('<I',payload)[0])
        target=destination/'Strings'/name.replace('dawnguard',Path(PLUGIN).stem,1);target.write_bytes(payload)
        tables.append({'archivePath':folder+'/'+name,'path':str(target),'sha256':SHA(target),'bytes':len(payload)})
    assert len(tables)==9
    return {'archive':str(archive),'archiveSha256':SHA(archive),'tables':tables}
def run_spriggit(out,spriggit,label,args):
    result=subprocess.run([str(spriggit),*args],capture_output=True,text=True,timeout=90)
    (out/(label+'.log')).write_text(result.stdout+'\n'+result.stderr,encoding='utf8')
    if result.returncode:raise RuntimeError(label+' failed; see external log')
def raw_two_path_payload(original):
    fields=subs(original);indices=[i for i,(k,v) in enumerate(fields) if k==b'MODL' and v.lower()==b'actors\\werewolfbeast\\werewolfbeastproject.hkx\0']
    if indices!=[67,70]:raise ValueError('Expected exact pinned male/female graph positions')
    edited=[(k,b'\0' if i in indices else v) for i,(k,v) in enumerate(fields)]
    payload=b''.join(sub(k,v) for k,v in edited)
    assert [(i,a,b) for i,(a,b) in enumerate(zip(fields,subs(payload))) if a!=b]==[(i,fields[i],(b'MODL',b'\0')) for i in indices]
    return payload,indices

def build_raw_candidate(out,game,spriggit):
    """Final is exact winning raw record, not the serializer-normalized intermediate."""
    final=out/'raw-two-path-candidate'
    if final.exists():raise FileExistsError('No overwrite of final fixture')
    proof=json.loads((out/'winning-race-proof.json').read_bytes());winner=proof['winningRace'];source=Path(winner['source'])
    if SHA(source)!=winner['sourceSha256']:raise ValueError('Winning source changed')
    rows,masters=read_plugin(source);race=next(r for r in rows if r['type']==b'RACE' and form_key(r['form'],masters,source.name)==('skyrim.esm',0xCDD84))
    assert race['flags']==0
    raw,indices=raw_two_path_payload(race['raw']);header=bytearray(race['header']);struct.pack_into('<I',header,4,len(raw));race_bytes=bytes(header)+raw
    allmasters=masters+[source.name]
    tes4=sub(b'HEDR',struct.pack('<fII',1.7,1,0x800))+sub(b'CNAM',b'CLAW test-only feasibility fixture\0')+sub(b'SNAM',b'TEST ONLY: empty two werewolf behavior project paths; engine feasibility UNKNOWN\0')
    for master in allmasters:tes4+=sub(b'MAST',master.encode()+b'\0')+sub(b'DATA',struct.pack('<Q',0))
    group=struct.pack('<4sI4sIHHHH',b'GRUP',24+len(race_bytes),b'RACE',0,0,0,0,0)+race_bytes
    final.mkdir();(final/PLUGIN).write_bytes(record(b'TES4',0,tes4,flags=0x80)+group)
    support=extract_dawnguard_tables(final,game/'Data/Skyrim - Interface.bsa')
    (out/'raw-localization-support.json').write_text(json.dumps(support,indent=2)+'\n',encoding='utf8')
    # Produce a correctly localized source readback for the independent semantic comparison.
    comparison=out/'raw-winning-comparison';comparison.mkdir()
    src_tes4=record(b'TES4',0,tes4,flags=0x80)
    source_race=race['header']+race['packed'];source_group=struct.pack('<4sI4sIHHHH',b'GRUP',24+len(source_race),b'RACE',0,0,0,0,0)+source_race
    (comparison/PLUGIN).write_bytes(src_tes4+source_group);shutil.copytree(final/'Strings',comparison/'Strings')
    for label,sourcepath,target in (('raw-winning-readback',comparison/PLUGIN,out/'raw-winning-readback'),('raw-candidate-readback',final/PLUGIN,out/'raw-candidate-readback')):
        run_spriggit(out,spriggit,label,['serialize','--InputPath',str(sourcepath),'--OutputPath',str(target),'--GameRelease','SkyrimSE','--PackageName','Spriggit.Yaml','--PackageVersion','0.41.0','--Threads','1','--ErrorOnUnknown','true'])
    run_spriggit(out,spriggit,'raw-normalized-roundtrip-build',['deserialize','--InputPath',str(out/'raw-candidate-readback'),'--OutputPath',str(out/'raw-normalized-roundtrip'/PLUGIN),'--PackageName','Spriggit.Yaml','--PackageVersion','0.41.0'])
    run_spriggit(out,spriggit,'raw-normalized-roundtrip-readback',['serialize','--InputPath',str(out/'raw-normalized-roundtrip'/PLUGIN),'--OutputPath',str(out/'raw-normalized-roundtrip-readback'),'--GameRelease','SkyrimSE','--PackageName','Spriggit.Yaml','--PackageVersion','0.41.0','--Threads','1','--ErrorOnUnknown','true'])
    print(json.dumps({'candidate':str(final/PLUGIN),'sha256':SHA(final/PLUGIN),'bytes':(final/PLUGIN).stat().st_size,'strings':len(support['tables']),'rawEditedSubrecordIndices':indices,'normalizedRoundtripIsReadbackEvidenceOnly':True}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--stage',choices=('all','seed','raw'),default='all');ap.add_argument('--output',type=Path,required=True);ap.add_argument('--evidence',type=Path);ap.add_argument('--game',type=Path,required=True);ap.add_argument('--mods',type=Path);ap.add_argument('--spriggit',type=Path,required=True);a=ap.parse_args()
    if a.stage in ('all','seed'):
        if not all((a.evidence,a.mods)):ap.error('Seed requires evidence/mods')
        prepare_seed(a.output,a.evidence,a.game,a.mods,a.spriggit)
    if a.stage in ('all','raw'):build_raw_candidate(a.output,a.game,a.spriggit)
