"""Assemble the adaptive VR diagnostic inputs in detached staging."""

import argparse
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import shutil

from posed_contact import observed_geometry, read_pinned_asset
from prepare_tail_refit_contrast import PROFILE_SHA, read_pinned
from verify_tail_refit import PROOF_SHA


ROOT = Path(__file__).resolve().parents[4]
MESH = 'Meshes/Actors/WerewolfBeast/Character Assets/'
CARRIER = {'low': MESH + 'malebodywerewolf_0.nif', 'high': MESH + 'malebodywerewolf_1.nif',
           'tri': MESH + 'malebodywerewolf.tri'}
SKEE = 'SKSE/Plugins/skeevr.dll'
RETAINED = ('SKSE/Plugins/cbp.dll', 'Scripts/CBPCPluginScript.pex',
            'SKSE/Plugins/CLAWVRCBPCEvents.dll', 'Scripts/CLAWVRCBPCEvents.pex',
            'test_CLAW - VR CBPC Contact Fixture.esp')
STOCK_VFS_SHA = '878bea9552d3bf43d6cd9572a5b34de006f96d027154ef405d05e0016af6e0ec'
STOCK_CONTEXT_SHA = 'd11e45cbc30683668adc7ad020a06dc0379cc39219fb5baf8adbe0d6a1460632'
WAYPOINT_SHA = '51a54ba4196c666e5521291b2798dfe0dff76fb062f60282653bccde29784966'
DISTRIBUTION_BUILD_SHA = '675b6a16dbadb696b9fce4869733c7c0908c5b211d8e4b1db046445f5f5ef37f'
WITNESS_BUILD_SHA = 'fd649f8b2cf73368de4cc84d17c97f58d5304848e4b6217f2a68e8f8d0ca1d46'
TAIL_REFIT_WITNESS_BUILD_SHA = 'b7aa1e0738b185628221e982fb5745492cc09ac6c91c6bd125e177d823de72d2'
PRIOR_STAGE_SHA = '268a6a5ad9086f8c37b136811ec3832c0b60155701d9797deba57a6ceac2182e'
RACEMENU = {'RaceMenu.esp': '15e009b7f219b1e95bd78a31cdf8be2d3b45a38b784dd04f34a71a4ab6f76602',
            'RaceMenuPlugin.esp': 'e0737c5629b67afe2272ad83d5d5555d9be08be66a998c76287c0d224a40b180',
            'RaceMenu.bsa': '2e4a47aefa8a12dad1b3d3dfa58f3b39e9672b24e66e4d0a3c2b0b7ddcc6c6ab'}
FACADES = ('Scripts/CLAWPhysicsNative.pex', 'Scripts/CLAWDistributionNative.pex')


def pin(path):
    raw = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(raw), 'sha256': sha256(raw).hexdigest()}


def same_bytes(source, expected):
    for field in ('bytes', 'sha256'):
        if source[field] != expected[field]:
            raise ValueError('Pinned bytes differ: ' + source['path'])


def write_member(destination, source):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source['path'], destination)
    same_bytes(pin(destination), source)


def freeze(args):
    case, out = args.stock_case.resolve(strict=True), args.out.resolve()
    if any(part.casefold() in {'data', 'mods', 'overwrite', 'profiles'} for part in out.parts):
        raise ValueError('Choose a detached staging directory')
    stock = json.loads(read_pinned(case / 'poststage-vfs.expected.json', STOCK_VFS_SHA))
    scoped = json.loads(read_pinned(case / 'ROOT-CURRENT-VFS.json', STOCK_CONTEXT_SHA))
    old_overlay = {row['virtual']: row['actual'] for row in stock['resources']}
    old_winners = {row['virtual']: row['actual'] for row in scoped['resources']}
    model = json.loads(read_pinned(args.profile, PROFILE_SHA))
    geometry = observed_geometry(model, 'male', {k: old_winners[v] for k, v in CARRIER.items()}, args.pynifly)
    installed = {name: pin(Path(old_winners[name]['path'])) for name in (*CARRIER.values(), SKEE)}
    for name, current in installed.items():
        same_bytes(current, old_winners[name])
    skeleton_path = MESH + 'skeleton.nif'
    authored_skeleton, = [item for item in model['sourceInputs'] if Path(item['path']).name.lower() == 'skeleton.nif']
    installed[skeleton_path] = pin(args.skeleton)
    same_bytes(installed[skeleton_path], authored_skeleton)
    for name, digest in RACEMENU.items():
        installed[name] = pin(args.racemenu / name)
        if installed[name]['sha256'] != digest:
            raise ValueError('RaceMenu asset differs from the verified file: ' + name)

    distribution = json.loads(read_pinned(args.distribution_build, DISTRIBUTION_BUILD_SHA))
    witness = json.loads(read_pinned(args.witness_build, TAIL_REFIT_WITNESS_BUILD_SHA))
    prior = json.loads(read_pinned(args.prior_stage, PRIOR_STAGE_SHA))
    for record in (distribution['dll'], distribution['fitWitness'], witness['dll'], witness['pex']):
        read_pinned_asset(record)
    bank = json.loads(read_pinned(Path(distribution['fitWitness']['path']), PROOF_SHA))
    waypoint = json.loads(read_pinned(args.waypoint, WAYPOINT_SHA))
    if not model['modelIdentity'] == bank['model'] == waypoint['model']:
        raise ValueError('The native build references a different fit')
    members = {'SKSE/Plugins/CLAWDistribution.dll': distribution['dll'],
               'SKSE/Plugins/CLAWVRNpcPose.dll': witness['dll'],
               'Scripts/CLAWVRNpcPose.pex': witness['pex']}
    # The previously compiled facades match the retained Distribution build.
    same_bytes(distribution['dll'], prior['members']['SKSE/Plugins/CLAWDistribution.dll'])
    for name in FACADES:
        members[name] = prior['members'][name]
        read_pinned_asset(members[name])
    for virtual in (*stock['cbpcConfigInventory'], *RETAINED):
        member = case / 'contact-inputs' / PurePosixPath(virtual)
        members[virtual] = pin(member)
        same_bytes(members[virtual], old_overlay[virtual])

    out.mkdir(parents=True, exist_ok=False)
    subject = out / 'subject/Data'
    for name, source in members.items():
        write_member(subject / PurePosixPath(name), source)
    reference = out / 'references'
    for name, source in (('fitted-capsules.json', pin(args.profile)), ('TAIL02-FIXED-SPHERE.json', distribution['fitWitness']),
                         ('TAIL02-WAYPOINT-R03-040M-REPLAY.json', pin(args.waypoint))):
        write_member(reference / name, source)
    report = {
        'schema': 'claw-vr-tail-refit-subject-staging/1', 'model': model['modelIdentity'],
        'fixture': {'baseLocalId': '000800', 'race': 'Skyrim.esm|0CDD84', 'sex': 'male', 'weight': 50,
                    'cell': '0A01A5C6', 'node': 'TailBone02', 'slots': [108, 109, 110, 111]},
        'geometry': geometry, 'papyrusBuild': prior['papyrusBuild'], 'priorStage': pin(args.prior_stage),
        'nativeBuildReceipts': [pin(args.distribution_build), pin(args.witness_build)],
        'members': {p.relative_to(subject).as_posix(): pin(p) for p in sorted(subject.rglob('*')) if p.is_file()},
        'retainedOrigins': members, 'diskDependencies': installed,
        'references': [pin(p) for p in sorted(reference.iterdir())],
        'remaining': ['Admit a qualified semantic host and install through Polygon custody.',
                      'Verify current VFS winners, loaded modules, NiOverride signatures, and the sole fixture actor.',
                      'Qualify and read back the fixed controller pose and both geometry margins in the live session.',
                      'Record the native four-capsule refit, contact contrast, and cleanup in game.'],
        'installed': False, 'gameValidated': False,
    }
    target = out / 'subject-staging.json'
    target.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return pin(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('stock-case', 'distribution-build', 'witness-build', 'profile', 'pynifly', 'waypoint',
                 'skeleton', 'racemenu', 'prior-stage', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    print(json.dumps(freeze(parser.parse_args())))


if __name__ == '__main__':
    main()
