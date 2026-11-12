"""Explicit flat/VR authoring composition; fitting and host ownership stay shared.

These are rest-surface enclosure profiles, not Havok/HIGGS/PLANCK integration.
One process selects one model and uses the existing single 128-index owner.
"""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
PHYSICS = ROOT / 'src/main/python/physics'
RESOURCES = Path(__file__).resolve().parents[1] / 'resources'


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fit = load_module('claw_contact_profile_fitter', PHYSICS / 'fit-capsules.py')
host = load_module('claw_contact_profile_host', PHYSICS / 'build.py')
settings = fit._settings_module
PROFILES = {'flat': ('flat-coarse.json', settings.FLAT_PROFILE, 52),
            'vr': ('vr-detailed.json', settings.VR_PROFILE, 128)}


def pin(path):
    raw = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}


def validate_recipes(recipes):
    if set(recipes) != set(PROFILES):
        raise ValueError('Exactly one flat and one VR profile are required')
    regions = {}
    for edition, (_, profile, budget) in PROFILES.items():
        value = recipes[edition]
        if (value.get('schemaVersion') != 1 or value.get('supportProfile') != profile
                or value.get('skinShapes') != ['body', 'head', 'claws']
                or value.get('contactPasses') != 0 or value.get('partitionMethod') != 'compact'
                or value.get('weightDomain') != [0., 1.] or value.get('morphDomain') != [0., 1.]
                or value.get('runtimeQualified') is not False or value.get('surfaceFitAccepted') is not False
                or value.get('requireDistinctWeightEndpoints') is not False
                or value.get('capsuleBudget') != budget):
            raise ValueError('Unsupported explicit contact profile contract')
        rows = settings.support_regions(value['supportRegions'])
        if sum(row['count'] for row in rows) != budget:
            raise ValueError('Profile allocation differs from its one-ledger budget')
        regions[edition] = {row['node']: row for row in rows}
    if set(regions['flat']) != set(regions['vr']):
        raise ValueError('Both profiles must retain the same whole-body attachments')
    for node, coarse in regions['flat'].items():
        detailed = regions['vr'][node]
        if detailed['sexMask'] != coarse['sexMask'] or detailed['count'] <= coarse['count']:
            raise ValueError('VR attachments must have finer allocation with the same sex ownership')
    return recipes


def read_recipes():
    return validate_recipes({edition: json.loads((RESOURCES / row[0]).read_bytes())
                             for edition, row in PROFILES.items()})


def read_vr_contact_recipe():
    """One explicit trial delta reuses the VR allocation without copying its budget."""
    delta = json.loads((RESOURCES / 'vr-contact-trial.json').read_bytes())
    if (set(delta) != {'schemaVersion', 'baseRecipe', 'name', 'supportProfile', 'contactPasses', 'fixtureSet', 'scope'}
            or delta['schemaVersion'] != 1 or delta['baseRecipe'] != 'vr-detailed.json'
            or delta['supportProfile'] != settings.VR_CONTACT_PROFILE
            or delta['contactPasses'] != 3 or delta['fixtureSet'] != 'compact'):
        raise ValueError('Unsupported explicit VR contact trial')
    value = read_recipes()['vr']
    value.update({key: delta[key] for key in ('name', 'supportProfile', 'contactPasses', 'fixtureSet', 'scope')})
    return value


def validate_models(models, *, vr_contact_trial=False):
    if type(vr_contact_trial) is not bool:
        raise ValueError('VR contact trial selection must be explicit')
    recipes = read_recipes()
    if vr_contact_trial:
        recipes['vr'] = read_vr_contact_recipe()
    if set(models) != set(PROFILES):
        raise ValueError('Both explicit runtime models are required')
    for edition, model in models.items():
        host.validate_fitted_model(model)
        recipe = recipes[edition]
        declared = [{key: row[key] for key in ('node', 'count', 'sexMask')}
                    for row in model['supportDeclaration']['regions']]
        if (model.get('supportProfile') != recipe['supportProfile']
                or model.get('coveredShapes') != recipe['skinShapes']
                or declared != recipe['supportRegions'] or len(model['slots']) != recipe['capsuleBudget']
                or model.get('runtimeQualified') is not False or model.get('surfaceFitAccepted') is not False):
            raise ValueError('Generated model differs from its explicit profile allocation')
    if models['flat']['modelIdentity'] == models['vr']['modelIdentity']:
        raise ValueError('Two different profile allocations require different model identities')
    if models['flat']['morphs'] != models['vr']['morphs']:
        raise ValueError('Both profiles must consume the same current body vector')


def write_pair_header(models, directory, *, vr_contact_trial=False):
    """Bind two existing emitter results; do not duplicate fitting arithmetic."""
    validate_models(models, vr_contact_trial=vr_contact_trial)
    texts = []
    for edition, function in (('flat', 'CompiledFlatContactModel'), ('vr', 'CompiledVRContactModel')):
        path = directory / (edition + '-profile-model.h')
        fit.write_cpp_model(models[edition], path, function_name=function)
        texts.append(path.read_text(encoding='utf-8').removeprefix('#pragma once\n'))
    output = directory / 'physics-fit-model.h'
    output.write_text('#pragma once\n#define CLAW_PHYSICS_RUNTIME_PROFILES 1\n' + '\n'.join(texts) + '''
namespace claw::physics {
enum class ContactRuntimeEdition { flat, vr };
inline const Model& CompiledModel(bool female, ContactRuntimeEdition edition) {
    switch (edition) {
    case ContactRuntimeEdition::flat: return CompiledFlatContactModel(female);
    case ContactRuntimeEdition::vr: return CompiledVRContactModel(female);
    }
    throw std::invalid_argument("Unknown contact runtime edition");
}
}
''', encoding='utf-8')
    return output
