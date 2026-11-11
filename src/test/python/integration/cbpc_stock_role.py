"""Pure loaded-root admission for the separately hash-qualified stock controller.

The caller first verifies the exact DLL/config and inspected skeleton pins. These
functions join that static role proof to fresh observations; they do not infer
provider binding, general ancestry, physics response or render synchronization.
"""

def _require(value, message):
    if not value:
        raise AssertionError(message)

def qualify(raw, admitted, expected):
    _require(raw.get('ok') is True and raw.get('schemaVersion') == 1, 'Stock controller graph admission failed')
    _require(raw.get('phase') == admitted['phase'] == 'skse_main_thread_task', 'Stock controller graph admission failed')
    _require(raw.get('coherence') == admitted['coherence'] and raw.get('observerVersion') == admitted['observerVersion'], 'Stock controller graph admission failed')
    _require(raw.get('sessionId') == admitted['sessionId'] and raw.get('loadGeneration') == admitted['loadGeneration'], 'Stock controller graph admission failed')
    _require(raw.get('sampleId', 0) > admitted['sampleId'] and raw.get('producerMonotonicNs', 0) > admitted['producerMonotonicNs'], 'Stock controller graph admission failed')
    _require(raw.get('quality') in ('complete', 'partial'), 'Stock controller graph admission failed')
    _require(len(raw.get('refs', [])) == 1, 'Stock controller graph admission failed')
    before, current = (admitted['refs'][0], raw['refs'][0])
    _require(current.get('status') == 'available' and current.get('loaded3D') is True and (current.get('disabled') is False) and (current.get('deleted') is False), 'Stock controller graph admission failed')
    for key in ('identity', 'rootIdentity', 'baseForm', 'actor'):
        _require(current.get(key) == before[key], 'Role read changed owned actor/root: ' + key)
    names = set(expected['protectedNames']) | set(expected['writeTargets'])
    rows = raw.get('nodes', [])
    _require(len(rows) == len(names) and {r.get('name') for r in rows} == names, 'Stock controller graph admission failed')
    missing = []
    for row in rows:
        _require(row.get('form') == before['identity']['form'] and row.get('firstPerson') is False, 'Stock controller graph admission failed')
        _require(row.get('identity') == before['identity'] and row.get('rootIdentity') == before['rootIdentity'], 'Stock controller graph admission failed')
        if row.get('status') == 'unavailable':
            _require(row.get('reason') == 'Node not found', 'Absence must be actual loaded-root name lookup')
            _require(row['name'] not in expected['requiredProbeNames'], 'Required motion/control node missing')
            missing.append(row['name'])
        else:
            _require(row.get('status') == 'available', 'Stock controller graph admission failed')
    absent_required = set(missing) & set(expected['missingAnyMeansEarlyReturn'])
    _require(absent_required, 'All required anatomy nodes may exist; stop before controls without actual ancestry proof')
    return {'qualifiedConditionalNoop': True, 'basis': 'exact binary special controller + same loaded-root missing prerequisite', 'actualMissingPrerequisites': sorted(absent_required), 'allFourTargetsRead': expected['writeTargets'], 'protectedNamesQueried': expected['protectedNames'], 'sourceParentPaths': expected['sourceParentPaths'], 'runtimeGenericParentageQualified': False, 'sampleId': raw['sampleId'], 'rootIdentity': before['rootIdentity'], 'qualityPreserved': raw['quality']}


def require_same_root(raw, qualified):
    _require(raw.get('ok') is True and raw.get('schemaVersion') == 1, 'Incomplete qualified-root observation')
    _require(raw.get('sessionId') == qualified['sessionId'] and raw.get('loadGeneration') == qualified['loadGeneration'], 'Qualified root epoch changed')
    _require(raw.get('observerVersion') == qualified['observerVersion'] and raw.get('coherence') == qualified['coherence'] and raw.get('phase') == qualified['phase'], 'Qualified root observation contract changed')
    _require(raw.get('sampleId', 0) > qualified['sampleId'] and raw.get('producerMonotonicNs', 0) > qualified['producerMonotonicNs'], 'Qualified root observation replayed')
    _require(len(raw.get('refs', [])) == 1, 'Qualified root reference missing')
    current, previous = raw['refs'][0], qualified['refs'][0]
    _require(current.get('status') == 'available' and current.get('loaded3D') is True and current.get('disabled') is False and current.get('deleted') is False, 'Qualified root unavailable')
    for key in ('identity', 'rootIdentity', 'baseForm', 'actor'):
        _require(current.get(key) == previous[key], 'Qualified stock root continuity lost: ' + key)
