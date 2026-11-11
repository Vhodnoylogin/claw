"""Check actual material paths, source preservation and the shipped WASM oracle."""
from pathlib import Path
import hashlib
import json
import struct
import subprocess
import argparse

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("report", type=Path)
parser.add_argument("--evaluator", type=Path, required=True, help="Built CLAW Morphbench evaluator CLI")
parser.add_argument("--output", type=Path, required=True)
arguments = parser.parse_args()
path = arguments.report
report = json.loads(path.read_bytes())
assert report['result'] == 'passed' and report['restored'] is True and not report['restoreErrors']
rows = {row['name']: row['observation'] for row in report['checks']}

def value(name):
    return rows[name]['returned']

def audit(name):
    result = json.loads(''.join(value(name)))
    assert result['leaseRootCurrent'] is True
    return result

def body(sample):
    return next(surface for surface in sample['surfaces'] if surface['name'].casefold() == 'body')

before = audit('coat-before-external')
external = audit('coat-after-external')
refreshed = audit('coat-after-forced-recomposition')
loaded = audit('coat-after-new-root')
assert 'diverseelegantwerewolves\\black\\body.dds' in body(before)['diffusePath'].casefold()
assert 'actors\\wolf\\wolfblack.dds' in body(external)['diffusePath'].casefold()
assert body(external)['diffusePath'] == body(refreshed)['diffusePath']
assert before['modelGeneration'] == external['modelGeneration'] == refreshed['modelGeneration']
assert loaded['modelGeneration'] != refreshed['modelGeneration']
assert 'diverseelegantwerewolves\\black\\body.dds' in body(loaded)['diffusePath'].casefold()
assert set(value('joint-effective-human-source-keys')) == {'LivingPhysique.Morphs', 'CLAWLPRegression.Foreign'}

f32 = lambda number: struct.unpack('<f', struct.pack('<f', number))[0]
source = value('joint-lp-source')
assert abs(value('joint-wolf-lp-source-preserved') - source) <= 1e-7
assert abs(value('joint-after-load-lp-source') - source) <= 1e-7
assert abs(rows['joint-human-return-lp-source']['morph']['value'] - source) <= 1e-7
assert abs(value('joint-human-return-condition') - source / .2) <= 1e-5
request = {'profileId': 'CLAW.HIMBO.5.8.Geometry1', 'actorWeight': 1.0,
    'humanValues': {'ArmsBiceps': f32(source + value('joint-human-foreign-source')),
        'TorsoVLine': .5, 'TorsoBackObliques': .5, 'TorsoBackDefinition': .5, 'LegsGlutes': .5}, 'humanTraits': {}}
evaluator = arguments.evaluator
result = subprocess.run(['node', str(evaluator)], input=json.dumps(request), capture_output=True, text=True, check=True)
expected = json.loads(result.stdout)['values']
numbers = {}
for target in ('CLAWArmBiceps', 'CLAWArmLean', 'CLAWTorsoWaistNarrow', 'CLAWTorsoBackWide', 'CLAWLegThighGirth'):
    actual = value('joint-wolf-' + target)
    restored = value('joint-after-load-wolf-' + target)
    assert actual == restored == expected[target], (target, actual, restored, expected[target])
    numbers[target] = {'game': actual, 'afterLoad': restored, 'wasm': expected[target]}

summary = {'run': report['id'], 'result': 'passed', 'restored': True,
    'report': str(path), 'reportSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    'externalMaterialPreserved': True, 'sameModelGeneration': before['modelGeneration'],
    'newModelGeneration': loaded['modelGeneration'], 'baseCoatReappliedAfterLoad': True,
    'lpHumanSource': source, 'wolfSourceRetained': value('joint-wolf-lp-source-preserved'),
    'returnedHumanCondition': value('joint-human-return-condition'),
    'input': request, 'exactNativeWasmMorphs': numbers}
arguments.output.write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
