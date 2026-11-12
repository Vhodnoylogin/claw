"""Independent binary and typed artifact checks; no game/manager/install operation."""
from pathlib import Path
import argparse,copy,hashlib,json,struct,zlib,yaml,difflib
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def walk(blob,start=0,end=None):
    end=len(blob) if end is None else end
    while start<end:
        if start+24>end:raise ValueError('Truncated record')
        kind=blob[start:start+4];size,flags,fid=struct.unpack_from('<III',blob,start+4)
        stop=start+size if kind==b'GRUP' else start+24+size
        if stop>end or stop<=start:raise ValueError('Invalid container')
        if kind==b'GRUP':yield from walk(blob,start+24,stop)
        else:
            raw=blob[start+24:stop]
            if flags&0x40000:raw=zlib.decompress(raw[4:])
            yield kind,fid,flags,blob[start:start+24],raw
        start=stop

def fields(blob):
    out=[];pos=0
    while pos<len(blob):
        tag=blob[pos:pos+4];size=struct.unpack_from('<H',blob,pos+4)[0];pos+=6
        if tag==b'XXXX':raise ValueError('Unexpected extended field in this exact small race')
        out.append((tag,blob[pos:pos+size]));pos+=size
    if pos!=len(blob):raise ValueError('Bad field endpoint')
    return out

def compare_race(source,candidate):
    a=fields(source[4]);b=fields(candidate[4]);assert len(a)==len(b)==173
    delta=[i for i,(x,y) in enumerate(zip(a,b)) if x!=y]
    assert delta==[67,70],delta
    for i in delta:assert a[i]==(b'MODL',b'Actors\\WerewolfBeast\\WerewolfBeastProject.hkx\0') and b[i]==(b'MODL',b'\0')
    assert source[0:3]==candidate[0:3] and source[3][:4]+source[3][8:]==candidate[3][:4]+candidate[3][8:]
    assert source[2]==candidate[2]==0
    return delta

def verify(directory):
    proof=json.loads((directory/'winning-race-proof.json').read_bytes());source=Path(proof['winningRace']['source'])
    assert sha(source)==proof['winningRace']['sourceSha256']
    for row in proof['sources']:assert sha(row['source'])==row['sha256']
    original=next(r for r in walk(source.read_bytes()) if r[0]==b'RACE' and r[1]==0xCDD84)
    plugin=directory/'raw-two-path-candidate/test_CLAW - Graphless Werewolf Feasibility.esp';rows=list(walk(plugin.read_bytes()))
    assert [r[0] for r in rows]==[b'TES4',b'RACE'] and rows[0][2]==0x80
    masters=[v.rstrip(b'\0').decode() for k,v in fields(rows[0][4]) if k==b'MAST'];assert masters==['Skyrim.esm','Update.esm','Dawnguard.esm']
    assert proof['winningRace']['masterList']==masters[:-1]
    delta=compare_race(original,rows[1]);a=fields(original[4]);b=fields(rows[1][4])
    assert next(v for k,v in a if k==b'FULL')==next(v for k,v in b if k==b'FULL')==struct.pack('<I',0x29D0)
    assert next(v for k,v in a if k==b'DESC')==next(v for k,v in b if k==b'DESC')==bytes(4)
    name='Races/WerewolfBeastRace - 0CDD84_Skyrim.esm.yaml'
    winning=yaml.safe_load((directory/'raw-winning-readback'/name).read_bytes());actual=yaml.safe_load((directory/'raw-candidate-readback'/name).read_bytes());expected=copy.deepcopy(winning)
    for sex in ('Male','Female'):expected['BehaviorGraph'][sex]['File']=''
    assert actual==expected
    roundtrip=yaml.safe_load((directory/'raw-normalized-roundtrip-readback'/name).read_bytes());assert roundtrip==actual
    original_tables=json.loads((directory/'localized-source-support.json').read_bytes())['tables']
    support=json.loads((directory/'raw-localization-support.json').read_bytes());assert len(support['tables'])==9
    assert sha(support['archive'])==support['archiveSha256']
    before={r['archivePath']:r['sha256'] for r in original_tables}
    for row in support['tables']:assert sha(row['path'])==row['sha256']==before[row['archivePath']]
    languages={row['Language']:row['String'] for row in actual['Name']['Values']};assert languages['Russian']=='\u0412\u0435\u0440\u0432\u043e\u043b\u044c\u0444' and languages['English']=='Werewolf' and len(languages)==9
    for row in support['tables']:
        data=Path(row['path']).read_bytes();count,n=struct.unpack_from('<II',data);lookup=dict(struct.unpack_from('<II',data,8+i*8) for i in range(count));off=8+count*8+lookup[0x29D0];end=data.index(b'\0',off)
        assert data[off:end].decode('utf8')==languages[Path(row['path']).stem.split('_')[-1].title()]
    counterexamples=[]
    for field,description in ((b'WNAM','skin change'),(b'DATA','race data change')):
        bad=copy.deepcopy(rows[1]);parts=fields(bad[4]);j=next(i for i,(tag,v) in enumerate(parts) if tag==field);tag,value=parts[j];parts[j]=(tag,bytes([value[0]^1])+value[1:]);raw=b''.join(k+struct.pack('<H',len(v))+v for k,v in parts);bad=(*bad[:4],raw)
        try:compare_race(original,bad)
        except AssertionError:counterexamples.append(description+' rejected')
        else:raise AssertionError('Unrelated delta accepted')
    out={'status':'artifact-fidelity-passed-engine-feasibility-UNKNOWN','candidate':str(plugin),'candidateSha256':sha(plugin),'candidateBytes':plugin.stat().st_size,'raceFormKey':'0CDD84:Skyrim.esm','winningPlugin':'Dawnguard.esm','scannedExplicitPlugins':21,'masters':masters,'masterIndexSpacePreserved':'Source indices0/1=masters; original source own2=Dawnguard now explicit master2; unchanged raw FormIDs retain meanings',
      'raceSubrecords':173,'unchangedSubrecords':171,'changedSubrecordIndices':delta,'onlyRawFieldChanges':['BehaviorGraph.Male.MODL: project path -> empty NUL string','BehaviorGraph.Female.MODL: project path -> empty NUL string'],'raceHeaderExactExceptRequiredPayloadLength':True,'sourceOrderingExact':True,'skinSkeletonFlagsOtherFieldsExact':True,'localizedFlag':True,'nameStringIdUnchanged':'000029D0','descriptionStringIdUnchanged':'00000000','stringTables':support['tables'],'all9LocaleNamesPreserved':True,'activeDeclaredTestLocale':'RUSSIAN','typedSpriggitOnlyTwoFieldDeltas':True,'normalizedRoundtripTypedEquivalent':True,'normalizedRoundtripIsNOTFinalCandidate':True,'actualArtifactCounterexamples':counterexamples,'failedUnlocalizedIntermediatePreserved':str(directory/'test_CLAW - Graphless Werewolf Feasibility.esp') if (directory/'test_CLAW - Graphless Werewolf Feasibility.esp').exists() else None,'gameTested':False,'installed':False,'livePreparationAuthorized':False,'launchAllowed':False}
    (directory/'raw-fixture-validation.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
    x=(directory/'raw-winning-readback'/name).read_text(encoding='utf8');y=(directory/'raw-candidate-readback'/name).read_text(encoding='utf8');(directory/'raw-two-field-typed.patch').write_text(''.join(difflib.unified_diff(x.splitlines(True),y.splitlines(True),fromfile='winning-localized/RACE',tofile='raw-candidate/RACE')),encoding='utf8')
    print(json.dumps({'status':out['status'],'candidateSha256':out['candidateSha256'],'unchangedSubrecords':171,'typedRoundtrip':True,'stringTables':9,'counterexamples':counterexamples}))
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);a=ap.parse_args();verify(a.directory)
