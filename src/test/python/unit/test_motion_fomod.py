"""Actual serialized motion selections and independent resource admission checks."""
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

import test_source_package as base

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/main/python/physics'))
import fsmp_motion


def body_fixture(sex, marker=b'', geometry_tri=False):
    """Synthetic opaque geometry; actual existing producer adds the hook."""
    types = ['NiNode', 'NiStringExtraData', 'BSTriShape', 'BSShaderTextureSet']
    strings = [b'Scene Root', b'BODYTRI', ('Actors/WerewolfBeast/Character Assets/' + sex + 'bodywerewolf.tri').encode()]
    root = struct.pack('<II', 0, 0) if geometry_tri else struct.pack('<III', 0, 1, 1)
    geometry = struct.pack('<III', 0, 1, 1) + b'original geometry/skin' + marker if geometry_tri else b'original geometry/skin' + marker
    blocks = [root + b'original opaque root tail', struct.pack('<II', 1, 2), geometry]
    indices = [0, 1, 2]
    for name in sorted(fsmp_motion.materials.DIFFUSES):
        slots = [(fsmp_motion.materials.BASE + name).encode(), b'shared-normal', *([b''] * 7)]
        blocks.append(struct.pack('<I', 9) + b''.join(struct.pack('<I', len(s)) + s for s in slots)); indices.append(3)
    sized = lambda data: struct.pack('<I', len(data)) + data
    return (b'Gamebryo File Format, Version 20.2.0.7\n' + struct.pack('<IBIII', 0x14020007, 1, 12, len(blocks), 100) + b'\0\0\0'
            + struct.pack('<H', len(types)) + b''.join(sized(t.encode()) for t in types)
            + struct.pack('<' + str(len(indices)) + 'H', *indices) + struct.pack('<' + str(len(blocks)) + 'I', *map(len, blocks))
            + struct.pack('<II', len(strings), max(map(len, strings))) + b''.join(sized(s) for s in strings)
            + struct.pack('<I', 0) + b''.join(blocks) + struct.pack('<II', 1, 0))


class MotionFomodTests(unittest.TestCase):
    def setUp(self):
        # Reuse the existing packaging fixture without inheriting/rerunning its suites.
        self.fixture = base.SourcePackageTests()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.f, self.package = self.fixture, base.package
        for name in self.package.MOTION_SOURCES:
            self.f.write(name, (ROOT / name).read_bytes())
        subprocess.run(['git', '-C', str(self.f.root), 'add', '--all'], check=True)
        for sex in ('male', 'female'):
            for weight in (0, 1): self.f.write('target/bodies/' + sex + 'bodywerewolf_' + str(weight) + '.nif', body_fixture(sex))
        self.receipts = self.prepare_motion()

    def pin(self, path):
        data = Path(path).read_bytes()
        return {'path': str(path), 'bytes': len(data), 'sha256': self.package.sha(data)}

    def prepare_motion(self):
        resources = {sex + str(weight): self.pin(self.f.bodies / (sex + 'bodywerewolf_' + str(weight) + '.nif'))
                     for sex in ('male', 'female') for weight in (0, 1)}
        skeleton = self.f.write('target/motion-input/skeleton.nif', b'Synthetic pinned XP32 input, not an actual skeleton')
        resources['skeleton'] = self.pin(skeleton)
        sources = [self.pin(self.f.root / name) for name in sorted(self.package.MOTION_SOURCES)]
        result = {}
        for provider in ('cbpc', 'fsmp'):
            folder = self.f.root / ('target/motion-' + provider)
            files = {name: ('# original synthetic motion fixture ' + name + '\n').encode() for name in self.package.CBPC_FILES} if provider == 'cbpc' else {}
            if provider == 'fsmp':
                for sex in ('male', 'female'):
                    xml = self.package.MOTION_XML + sex.title() + '.xml'
                    files[xml] = fsmp_motion.render_xml(sex == 'female')
                    for weight in (0, 1):
                        raw = (self.f.bodies / (sex + 'bodywerewolf_' + str(weight) + '.nif')).read_bytes()
                        adapted, _ = fsmp_motion.materials.adapt_nif(raw)
                        hooked, _ = fsmp_motion.bind_nif(adapted, xml)
                        for route in ('bodywerewolf', 'PlayerWerewolf'):
                            files[self.package.MESH + '/' + sex + route + '_' + str(weight) + '.nif'] = hooked
            files['README.txt'] = b'Synthetic builder receipt; no actual provider/game qualification.'
            for name, data in files.items(): self.f.write(str((folder / 'package' / name).relative_to(self.f.root)), data)
            report = {'schemaVersion': 1, 'provider': provider,
                      'status': 'built-offline-motion-adapter-runtime-pending' if provider == 'cbpc' else 'built-offline-FSMP-motion-runtime-pending',
                      'collisionResponseEnabled': False, 'resources': copy.deepcopy(resources), 'sourceInputs': sources,
                      'runtimeQualified': False, 'files': [{'path': name, 'bytes': len(data), 'sha256': self.package.sha(data)} for name, data in files.items()]}
            path = folder / 'report.json'; path.write_bytes(self.package.encoded(report)); result[provider] = path
        return result

    def arguments(self, output='motion'):
        return dict(self.f.arguments(output=output), cbpc_motion_build=self.receipts['cbpc'], fsmp_motion_build=self.receipts['fsmp'])

    def mutate_report(self, provider, callback):
        path = self.receipts[provider]; report = json.loads(path.read_bytes()); callback(report)
        path.write_bytes(self.package.encoded(report))

    def test_sixty_actual_plans_are_exclusive_and_share_matrices_tris_native(self):
        self.assertEqual(self.package.CBPC_FILES, {'SKSE/Plugins/' + name for name in
                         ('CBPCMasterConfig_CLAWMotion.txt', 'CBPConfig_CLAWMotion.txt',
                          'CBPCMasterConfig_CLAWBreastMotion.txt', 'CBPConfig_CLAWBreastMotion.txt')})
        result = self.package.build(**self.arguments())
        self.assertEqual(len(result['selections']), 60)
        self.assertEqual({(r['maleFamily'], r['family'], r['obody'], r['physics']) for r in result['selections']},
                         {(m, f, o, p) for m in self.package.MALE_FAMILIES for f in self.package.FEMALE_FAMILIES
                          for o in (False, True) for p in ('none', 'cbpc', 'fsmp')})
        entries = self.package.read_zip(Path(result['archive']).read_bytes())
        expected_counts = {'none': 18, 'cbpc': 22, 'fsmp': 20}
        grouped = {}
        for row in result['selections']:
            self.assertEqual(row['runtimeFiles'], expected_counts[row['physics']] + 2 * row['obody'])
            selected = {v['path']: v for v in row['files']}
            self.assertEqual(len(selected), len(row['files']))
            for name, value in selected.items():
                self.assertEqual(value['sha256'], self.package.sha(entries[value['source']]))
                if name.endswith('.nif'):
                    self.assertEqual(value['source'].startswith('40 Motion/FSMP/'), row['physics'] == 'fsmp')
            self.assertEqual(set(selected) & self.package.CBPC_FILES, self.package.CBPC_FILES if row['physics'] == 'cbpc' else set())
            common = {n: v['sha256'] for n, v in selected.items() if not n.endswith('.nif') and n not in self.package.CBPC_FILES
                      and not n.startswith(self.package.MOTION_XML)}
            key = row['maleFamily'], row['family'], row['obody']
            self.assertEqual(grouped.setdefault(key, common), common)
        self.assertEqual(sum(n.endswith('.nif') for n in entries), 4)  # two unhooked + two hooked; no route/weight copies.
        self.assertFalse(result['gameOrManagerExecuted'])
        for provider in ('cbpc', 'fsmp'):
            self.assertFalse(result['motionProviders'][provider]['runtimeQualified'])
            self.assertEqual(set(result['motionProviders'][provider]['sharedTriSha256']), {'male', 'female'})

    def test_mutual_exclusion_is_read_from_xml_not_payload_priority(self):
        result = self.package.build(**self.arguments())
        entries = self.package.read_zip(Path(result['archive']).read_bytes()); config = ET.fromstring(entries['fomod/ModuleConfig.xml'])
        choices = config.find(".//group[@name='One werewolf motion provider']")
        self.assertEqual(choices.get('type'), 'SelectExactlyOne')
        self.assertEqual([p.get('name') for p in choices.findall('plugins/plugin')], ['None', 'CBPC', 'FSMP'])
        self.assertEqual(choices.find('plugins/plugin/typeDescriptor/type').get('name'), 'Recommended')
        choices.set('type', 'SelectAny')
        altered = dict(entries); altered['fomod/ModuleConfig.xml'] = ET.tostring(config)
        with self.assertRaisesRegex(ValueError, 'mutually exclusive'): self.package.selection_audit(altered)
        choices.set('type', 'SelectExactlyOne')
        with self.assertRaisesRegex(ValueError, 'known provider'):
            base.reader.resolve_selection(config, entries, native=True, male_family='HIMBO', family='3BA', physics='both')
        mapped = config.find("conditionalFileInstalls/patterns/pattern/dependencies/flagDependency[@flag='physicsMode'][@value='fsmp']")
        parent = next(p for p in config.findall('conditionalFileInstalls/patterns/pattern') if p.find('dependencies/flagDependency') is mapped)
        parent.find('files').append(copy.deepcopy(parent.find('files/file')))
        with self.assertRaisesRegex(ValueError, 'Conflicting installed destination'):
            base.reader.resolve_selection(config, entries, native=True, male_family='HIMBO', family='3BA', physics='fsmp')

    def test_changed_payload_or_foreign_body_is_rejected(self):
        path = self.receipts['cbpc'].parent / 'package' / next(iter(self.package.CBPC_FILES)); path.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Changed motion payload'): self.package.build(**self.arguments())
        self.receipts = self.prepare_motion()
        foreign = self.f.write('target/foreign-body.nif', body_fixture('male', b'anatomy-or-VR'))
        self.mutate_report('fsmp', lambda r: r['resources'].update(male0=self.pin(foreign)))
        with self.assertRaisesRegex(ValueError, 'selected core endpoint'): self.package.build(**self.arguments())

    def test_unlisted_and_provider_or_test_payloads_are_rejected(self):
        for name in ('SKSE/Plugins/cbp.dll', 'Scripts/Test.pex', 'Textures/coat.dds', 'SKSE/Plugins/anatomy.xml'):
            with self.subTest(name=name):
                path = self.receipts['fsmp'].parent / 'package' / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b'foreign')
                with self.assertRaisesRegex(ValueError, 'Unlisted motion payload'): self.package.build(**self.arguments())
                path.unlink()

    def test_rehashed_anatomy_or_contact_xml_is_rejected(self):
        name = self.package.MOTION_XML + 'Male.xml'
        path = self.receipts['fsmp'].parent / 'package' / name
        original = path.read_bytes()
        for extra in (b'<bone name="WWD 2"><mass>1</mass></bone>', b'<per-triangle-shape name="contact"/>'):
            with self.subTest(extra=extra):
                data = original.replace(b'</system>', extra + b'</system>'); path.write_bytes(data)
                self.mutate_report('fsmp', lambda r: next(v for v in r['files'] if v['path'] == name).update(bytes=len(data), sha256=self.package.sha(data)))
                with self.assertRaisesRegex(ValueError, 'FSMP motion system|motion scope'): self.package.build(**self.arguments())
        path.write_bytes(original)

    def test_distinct_endpoints_keep_their_own_routes(self):
        self.f.write('target/bodies/femalebodywerewolf_1.nif', body_fixture('female', b'distinct-weight1'))
        self.receipts = self.prepare_motion()
        result = self.package.build(**self.arguments())
        for row in result['selections']:
            selected = {v['path']: v['source'] for v in row['files']}
            zero = selected[self.package.MESH + '/femalebodywerewolf_0.nif']
            one = selected[self.package.MESH + '/femalebodywerewolf_1.nif']
            self.assertNotEqual(zero, one)
            self.assertEqual(one, selected[self.package.MESH + '/femalePlayerWerewolf_1.nif'])

    def test_geometry_attached_bodytri_does_not_require_root_extra(self):
        for sex in ('male', 'female'):
            for weight in (0, 1): self.f.write('target/bodies/' + sex + 'bodywerewolf_' + str(weight) + '.nif', body_fixture(sex, geometry_tri=True))
        self.receipts = self.prepare_motion()
        result = self.package.build(**self.arguments())
        self.assertEqual(len(result['selections']), 60)

    def test_rehashed_geometry_hook_and_tri_counterexamples_are_rejected(self):
        directory = self.receipts['fsmp'].parent / 'package'
        name = self.package.MESH + '/femalebodywerewolf_0.nif'
        original = (directory / name).read_bytes()
        for before, after in ((b'original geometry/skin', b'altered! geometry/skin'),
                              (b'CLAWMotionFemale.xml', b'TESTMotionFemale.xml')):
            with self.subTest(after=after):
                changed = original.replace(before, after); self.assertNotEqual(changed, original)
                for route in ('bodywerewolf', 'PlayerWerewolf'):
                    relative = self.package.MESH + '/female' + route + '_0.nif'; (directory / relative).write_bytes(changed)
                    self.mutate_report('fsmp', lambda r, relative=relative: next(v for v in r['files'] if v['path'] == relative).update(bytes=len(changed), sha256=self.package.sha(changed)))
                with self.assertRaisesRegex(ValueError, 'core geometry|root hook'): self.package.build(**self.arguments())
                self.receipts = self.prepare_motion()
        # A different shared TRI filename cannot be admitted just by updating receipt hashes.
        for weight in (0, 1):
            p = self.f.bodies / ('femalebodywerewolf_' + str(weight) + '.nif')
            p.write_bytes(p.read_bytes().replace(b'femalebodywerewolf.tri', b'femalebodywerewxxx.tri'))
        self.receipts = self.prepare_motion()
        with self.assertRaisesRegex(ValueError, 'mismatched BODYTRI'): self.package.build(**self.arguments())


if __name__ == '__main__':
    unittest.main()
