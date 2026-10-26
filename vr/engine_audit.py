"""Resolve declared werewolf skin records offline; refuse unproved VR dispatch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import struct

import body_resource
from record_reader import DeclaredLoadOrder, FormKey, PluginFile, zstring

ROOT = body_resource.ROOT
RACE = FormKey('Skyrim.esm', 0xCDD84)
PLAYER = FormKey('Skyrim.esm', 7)
SLOT_NAMES = ['Head', 'Hair', 'Body', 'Hands', 'Forearms', 'Amulet', 'Ring', 'Feet',
              'Calves', 'Shield', 'Tail', 'LongHair', 'Circlet', 'Ears']


def slot_summary(record):
    a, b = record.one('BODT', False), record.one('BOD2', False)
    if (a is None) == (b is None):
        raise ValueError('Expected one BODT or BOD2 slot structure')
    raw, tag = (a, 'BODT') if a is not None else (b, 'BOD2')
    if len(raw) != (12 if tag == 'BODT' else 8):
        raise ValueError('Unexpected biped slot structure length')
    mask = struct.unpack_from('<I', raw)[0]
    return {'subrecord': tag, 'rawHex': raw.hex(), 'mask': mask,
            'slots': [{'number': 30 + bit, 'name': SLOT_NAMES[bit] if bit < len(SLOT_NAMES) else 'Custom'}
                      for bit in range(32) if mask & (1 << bit)],
            'interpretation': 'Biped slot mask; Spriggit BodyTemplate.FirstPersonFlags, not proof of native first-person model selection'}


def arma_summary(record):
    data = record.one('DNAM')
    if len(data) != 12:
        raise ValueError('Expected the checked 12-byte ARMA DNAM layout')
    return {**record.provenance(), 'race': record.ref('RNAM').text(),
            'biped': slot_summary(record), 'dnamHex': data.hex(),
            'weightSliderEnabled': {'male': bool(data[2] & 2), 'female': bool(data[3] & 2)},
            'weightFlagBytes': {'male': data[2], 'female': data[3]},
            'worldModels': {'male': zstring(record.one('MOD2')), 'female': zstring(record.one('MOD3'))},
            'firstPersonRecordModels': {'male': zstring(record.one('MOD4')), 'female': zstring(record.one('MOD5'))},
            'engineSelectedFirstPersonModels': None}


def skin_chain(order, race_key=RACE):
    race = order.winner(race_key, 'RACE')
    skin_key = race.ref('WNAM')
    if skin_key is None:
        raise ValueError('Race has no explicit skin armor')
    skin = order.winner(skin_key, 'ARMO')
    addons = []
    for value in skin.values('MODL'):
        if len(value) != 4:
            raise ValueError('ARMO addon reference must be four bytes')
        key = skin.source.form_key(struct.unpack('<I', value)[0])
        record = order.winner(key, 'ARMA')
        # An armor-parent-race implementation is outside this narrow werewolf audit.
        # Refuse instead of silently dropping an applicable inherited addon.
        if record.ref('RNAM') != race_key:
            raise ValueError('Addon uses another race; inherited/additional-race selection needs a separate resolver')
        addons.append(arma_summary(record))
    if not addons:
        raise ValueError('Skin armor has no declared addons')
    race_slots, skin_slots = slot_summary(race), slot_summary(skin)
    mask = race_slots['mask'] & skin_slots['mask']
    overlap = [mask & a['biped']['mask'] for a in addons]
    return {'race': {**race.provenance(), 'skin': skin_key.text(), 'biped': race_slots,
                     'skeletonRecordPaths': [zstring(x) for x in race.values('ANAM')]},
            'skinArmor': {**skin.provenance(), 'race': skin.ref('RNAM').text(), 'biped': skin_slots},
            'addons': addons, 'slotIntersectionMasks': overlap,
            'bodySlot32PresentInEveryStage': bool(mask & 4) and all(a['biped']['mask'] & 4 for a in addons),
            'scope': 'Declared record chain only; no transformed player or loaded graph observed'}


def player_record(order):
    player = order.winner(PLAYER, 'NPC_')
    acbs = player.one('ACBS')
    if len(acbs) < 4:
        raise ValueError('Truncated NPC ACBS')
    race, skin = player.ref('RNAM'), player.ref('WNAM', False)
    return {**player.provenance(), 'staticRace': race.text(),
            'explicitStaticSkin': skin.text() if skin else None,
            'staticFemaleFlag': bool(struct.unpack_from('<I', acbs)[0] & 1),
            'transformedRace': None, 'runtimeSex': None,
            'scope': 'Static player base is not a snapshot of the transformed player; NPC skin override and template rules must be checked at runtime'}


def resource_pins(resource_root, contract):
    directory = Path(resource_root).resolve(strict=True)
    profile = body_resource.load_profile(Path(__file__).with_name('profile.json'))
    result = {}
    for sex, expected in contract['resourceNifSha256'].items():
        nif = directory / sex / 'face-hidden-resource.nif'
        tri = directory / sex / profile['bodies'][sex]['tri']
        if body_resource.sha256(nif) != expected or body_resource.sha256(tri) != profile['bodies'][sex]['triSha256']:
            raise ValueError('Only the exact five-byte corrected published resource candidate is admitted: ' + sex)
        result[sex] = {'nif': str(nif), 'nifSha256': expected, 'tri': str(tri),
                       'triSha256': profile['bodies'][sex]['triSha256'],
                       'status': 'offline face-only resource; mixed head retained, camera clearance unqualified'}
    return result


def report(master, claw, resources, overrides=(), reference=None):
    contract_path = Path(__file__).with_name('engine-contract.json')
    contract = body_resource.read_json(contract_path)
    if contract.get('schemaVersion') != 1 or contract.get('nativeSelectionEstablished') is not False:
        raise ValueError('Native dispatch has no implemented proof/admission path in this auditor')
    master, claw = Path(master).resolve(strict=True), Path(claw).resolve(strict=True)
    if master.name.casefold() != 'skyrim.esm' or body_resource.sha256(master) != contract['skyrimMasterSha256']:
        raise ValueError('Unsupported exact Skyrim VR master baseline')
    if claw.name.casefold() != 'claw.esp' or body_resource.sha256(claw) != contract['clawPluginSha256']:
        raise ValueError('Unsupported exact published CLAW plugin baseline')
    pinned = resource_pins(resources, contract)
    paths = [master, claw, *[Path(p).resolve(strict=True) for p in overrides]]
    reference_path = Path(reference).resolve(strict=True) if reference else None
    inputs = list(dict.fromkeys([*paths, *([reference_path] if reference_path else [])]))
    hashes = {str(p): body_resource.sha256(p) for p in inputs}
    opened = []
    try:
        by_path = {}
        for path in inputs:
            plugin = PluginFile(path)
            opened.append(plugin)
            by_path[path] = plugin
        vanilla_order = DeclaredLoadOrder([by_path[master]])
        declared = DeclaredLoadOrder([by_path[p] for p in paths])
        vanilla = skin_chain(vanilla_order)
        effective = skin_chain(declared)
        reference_chain = skin_chain(DeclaredLoadOrder([by_path[master], by_path[reference_path]])) if reference_path else None
        addon_keys = [a['formKey'] for a in effective['addons']]
        history = {}
        for key in [RACE, by_path[master].form_key(0xCDD86), by_path[master].form_key(0xCDD87)]:
            history[key.text()] = [r.provenance() for r in declared.history(key)]
        outcome = {'schemaVersion': 1, 'status': 'refused-unresolved-native-first-person-dispatch',
                   'installable': False, 'pluginGenerated': False, 'installLayoutGenerated': False,
                   'manualGate': False, 'declaredInputOrder': [str(p) for p in paths],
                   'activeGameLoadOrderObserved': False, 'inputSha256': hashes,
                   'sourceSha256': {p.name: body_resource.sha256(p) for p in [Path(__file__), Path(__file__).with_name('record_reader.py'), contract_path]},
                   'vanilla': vanilla, 'declaredEffective': effective,
                   'declaredOverrideHistory': history, 'staticPlayerBase': player_record(declared),
                   'referenceOnlyComparison': reference_chain, 'resourceCandidates': pinned,
                   'nativeSelection': {'established': False, 'missingBranch': contract['missingNativeBranch'],
                                       'knownStringObservation': contract['nativeStringObservation'],
                                       'sourceBoundary': 'CommonLib InitWornArmorAddon and InitWornArmor delegate to native engine functions; VRIK consumes already-loaded first/third-person graphs.'},
                   'patchRefusal': {'reason': 'Record MOD4/MOD5 paths do not prove control of the native VR beast hands path or weight interpolation.',
                                    'requiredProof': ['Native beast path selection with per-sex weight bit enabled',
                                                      'Slot32 eligibility and loaded first-person graph relation',
                                                      'Per-sex and _0/_1 filename behavior without changing world models/weight flags'],
                                    'unchangedPolicy': 'No armor slots, records, world models, weight flags, skeletons, actor morphs or live files are changed.'}}
        if not addon_keys:
            raise ValueError('No resolved werewolf addon')
        if any(body_resource.sha256(p) != hashes[str(p)] for p in inputs):
            raise ValueError('Input changed during record audit')
        return outcome
    finally:
        for plugin in reversed(opened):
            plugin.close()


def write_report(master, claw, resources, output, overrides=(), reference=None):
    paths = [master, claw, *overrides, *([reference] if reference else [])]
    # Block output inside the body candidate too; its binary evidence is immutable.
    out = body_resource.safe_output(output, [*paths, Path(resources) / 'vr-body-report.json'])
    outcome = report(master, claw, resources, overrides, reference)
    out.mkdir(parents=True, exist_ok=False)
    (out / 'NO_PLUGIN_GENERATED.txt').write_text(outcome['patchRefusal']['reason'] + '\n' + outcome['nativeSelection']['missingBranch'] + '\n', encoding='utf-8')
    (out / 'engine-record-audit.json').write_text(json.dumps(outcome, indent=2) + '\n', encoding='utf-8')
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--master', required=True, type=Path)
    parser.add_argument('--claw-plugin', type=Path, default=ROOT / 'assets/release/0.6.2.0/base/CLAW.esp')
    parser.add_argument('--resources', required=True, type=Path)
    parser.add_argument('--out-dir', required=True, type=Path)
    parser.add_argument('--override', action='append', default=[], type=Path, help='Explicit later override; supplied order is not an observed active profile')
    parser.add_argument('--reference-plugin', type=Path, help='Compare with Skyrim baseline separately; not part of the declared override chain')
    args = parser.parse_args()
    try:
        result = write_report(args.master, args.claw_plugin, args.resources, args.out_dir, args.override, args.reference_plugin)
    except (ValueError, OSError, KeyError, struct.error, UnicodeError) as exc:
        parser.exit(1, 'VR_ENGINE|invalid-input: %s\n' % exc)
    print('VR_ENGINE|' + result['status'] + '|no-plugin|manualGate=false|' + str(args.out_dir))
    return 2  # Expected useful refusal, distinct from malformed/missing input (1).


if __name__ == '__main__':
    raise SystemExit(main())
