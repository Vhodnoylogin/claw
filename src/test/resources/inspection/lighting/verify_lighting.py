"""Independent Spriggit parse/rebuild/readback and package inventory."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import build_lighting as b

root=Path(sys.argv[1]).resolve()
exe=Path(sys.argv[2]).resolve()
assert root.is_dir() and not (root/'independent-verification.json').exists()
plugin=root/'payload'/b.NAME
(root/'roundtrip').mkdir()
calls=[]
for name,args in [
    ('serialize',['serialize','-i',str(plugin),'-o',str(root/'spriggit-source'),'-g','SkyrimSE','-p','Spriggit.Yaml.Skyrim','-v','0.41','-d',str(root/'payload')]),
    ('deserialize',['deserialize','-i',str(root/'spriggit-source'),'-o',str(root/'roundtrip'/b.NAME),'-p','Spriggit.Yaml.Skyrim','-v','0.41']),
    ('readback',['serialize','-i',str(root/'roundtrip'/b.NAME),'-o',str(root/'roundtrip-source'),'-g','SkyrimSE','-p','Spriggit.Yaml.Skyrim','-v','0.41','-d',str(root/'roundtrip')])]:
    done=subprocess.run([str(exe),*args],capture_output=True,text=True,encoding='utf-8',errors='replace')
    (root/(name+'.stdout.log')).write_text(done.stdout,encoding='utf-8')
    (root/(name+'.stderr.log')).write_text(done.stderr,encoding='utf-8')
    calls.append({'argv':[str(exe),*args],'exitCode':done.returncode})
    assert done.returncode==0,done.stderr
def inventory(folder):
    return {f.relative_to(folder).as_posix():f.read_bytes() for f in folder.rglob('*') if f.is_file()}
left=inventory(root/'spriggit-source');right=inventory(root/'roundtrip-source')
assert left==right
light=(root/'spriggit-source'/'Lights'/'test_CLAWInspectionNeutralFill - 000800_test_CLAWInspectionLighting.esp.yaml').read_text(encoding='utf-8-sig')
assert 'Radius: 450' in light and 'FadeValue: 1' in light and 'Color: \'#00DCE1E6\'' in light
assert 'Value:' not in light.replace('FadeValue:','') and 'Weight:' not in light and 'Flags:' not in light
cell=(root/'spriggit-source'/'Cells'/'1'/'9'/'QASmoke - 032AE7_Skyrim.esm'/'RecordData.yaml').read_text(encoding='utf-8-sig')
assert cell.count('Language: ')==10 and 'String: Editor Smoke Test Cell' in cell
assert all(f'EditorID: test_CLAWInspectionFill{i}' in cell for i in (1,2,3))
payload=inventory(root/'payload')
assert len(payload)==10
report={'passed':True,'runtimeTested':False,'spriggitTextRoundtripEqual':True,
    'textSourceFiles':len(left),'calls':calls,
    'tool':{'path':str(exe),'sha256':b.sha(exe.read_bytes())},
    'payload':[{'path':k,'bytes':len(v),'sha256':b.sha(v)} for k,v in sorted(payload.items())],
    'recordSource':str(root/'spriggit-source'),
    'scope':'Complete original CELL preserved; independent parser/rebuilder verifies48-byte LIGH, localized names, references and placements. No rendered acceptance.'}
(root/'independent-verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'passed':True,'payloadFiles':10,'textFiles':len(left),'pluginSha256':b.sha(plugin.read_bytes()),'runtimeTested':False}))
