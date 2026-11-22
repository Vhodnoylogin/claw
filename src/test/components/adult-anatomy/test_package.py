"""Separate candidate selection contracts, with explicit actual assets opt-in."""
import collections
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[4]
PATH = REPO/'src/main/components/adult-anatomy/python/package.py'
SPEC = importlib.util.spec_from_file_location('claw_anatomy_candidate_package', PATH)
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


def helpers():
    names = ('package-source-build.py', 'build-unified-release.py')
    return tuple(p.load(p.TOOLS/name, (p.TOOLS/name).read_bytes()) for name in names)


def symbolic():
    entries = {p.GUIDE: p.RUNTIME_GUIDE, p.NOTICE: p.ASSET_NOTICE,
               'fomod/ModuleConfig.xml': p.installer(), 'fomod/info.xml': b'<fomod/>'}
    for folder, xml in p.VARIANTS.values():
        entries[folder+'/male.nif'] = b'synthetic opaque NIF, not game evidence'
        if xml:
            entries[folder+'/'+xml] = b'<system/>'
    return entries


class PackageSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package, cls.reader = helpers()

    def test_default_installs_static_appearance_for_either_core_mode(self):
        entries = symbolic()
        config = ET.fromstring(entries['fomod/ModuleConfig.xml'])
        recommended = [x.findtext('conditionFlags/flag') for x in config.findall('.//plugins/plugin')
                       if x.find('typeDescriptor/type').get('name') == 'Recommended']
        self.assertEqual(recommended, ['none', 'off'])
        for core in ('none', 'fsmp'):
            selected = p.selection(entries, 'off', self.reader, core_motion=core)
            self.assertEqual(set(selected), {*p.DESTINATIONS, p.GUIDE, p.NOTICE})
            folder = p.VARIANTS[core, 'off'][0]
            self.assertEqual({selected[name] for name in p.DESTINATIONS}, {folder + '/male.nif'})

    def test_both_male_routes_and_known_core_motion_choice_are_required(self):
        entries = symbolic()
        for core in ('none', 'fsmp'):
            selected = p.selection(entries, 'on', self.reader, core_motion=core)
            self.assertEqual(set(selected), {*p.DESTINATIONS, p.XML_ROOT+p.VARIANTS[core, 'on'][1], p.GUIDE, p.NOTICE})
            self.assertEqual(len({selected[name] for name in p.DESTINATIONS}), 1)
        with self.assertRaisesRegex(ValueError, 'Explicit known'):
            p.selection(entries, 'on', self.reader, core_motion='unknown')
        with self.assertRaisesRegex(ValueError, 'CLAW.esp'):
            p.selection(entries, 'off', self.reader, core_motion='fsmp', active=())

    def test_weakened_default_extra_female_mapping_and_foreign_payload_fail(self):
        for change in ('multiple', 'default', 'female'):
            entries = symbolic()
            xml = ET.fromstring(entries['fomod/ModuleConfig.xml'])
            if change == 'multiple':
                xml.find('.//group').set('type', 'SelectAny')
            elif change == 'default':
                xml.find('.//plugins/plugin/typeDescriptor/type').set('name', 'Optional')
            else:
                ET.SubElement(xml.find('.//pattern/files'), 'file', source='10 Static/male.nif',
                              destination=p.MESH+'femalebodywerewolf_0.nif')
            entries['fomod/ModuleConfig.xml'] = ET.tostring(xml)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'Installer changed'):
                p.selection(entries, 'off', self.reader, core_motion='fsmp')
        for name in ('Textures/foreign.dds', 'SKSE/Plugins/hdtSMP64.dll', 'Source/tool.py'):
            entries = symbolic(); entries[name] = b'foreign'
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'archive member'):
                p.audit(entries, {}, {}, self.package, self.reader)


class ActualCandidatePackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        paths = [os.environ.get(key) for key in ('CLAW_ANATOMY_CORE_ARCHIVE', 'CLAW_ANATOMY_NEUTRAL', 'CLAW_ANATOMY_COMBINED')]
        if all(path is None for path in paths):
            raise unittest.SkipTest('Explicit actual anatomy/core package inputs not selected')
        if not all(paths):
            raise AssertionError('Set all three actual anatomy/core package inputs')
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.report = p.build(core_archive=Path(paths[0]), neutral=Path(paths[1]), combined=Path(paths[2]),
                             out=Path(cls.temp.name)/'fresh-output')
        cls.package, cls.reader = helpers()
        cls.entries = cls.package.read_zip(Path(cls.report['archive']['path']).read_bytes())
        cls.base = cls.package.read_zip(Path(cls.report['baseArchive']['path']).read_bytes())
        cls.core = cls.package.read_zip(Path(paths[0]).read_bytes())

    def test_actual_pair_has_ten_overlay_members_and_120_verified_selections(self):
        self.assertEqual(self.report['archive']['members'], 10)
        self.assertEqual(self.report['planCount'], 120)
        self.assertEqual(collections.Counter(row['anatomy'] for row in self.report['plans']),
                         {'absent': 40, 'off': 40, 'on': 40})
        self.assertFalse(self.report['runtimeQualified'])
        self.assertFalse(self.report['contactQualified'])
        self.assertEqual(set(self.base), set(self.core))
        self.assertEqual(self.report['retainedMotionResult']['result'], 'failed')
        self.assertFalse(any(name.endswith(('.dll', '.pex', '.esp', '.tri', '.dds', '.py')) for name in self.entries))

    def test_static_default_restores_original_appearance_and_preserves_core_fsmp(self):
        selected = p.selection(self.entries, 'off', self.reader, core_motion='fsmp')
        # Equal core endpoints/armor routes share archive members. Read their
        # installed destinations from the actual serialized FOMOD mappings.
        paths = self.reader.resolve_selection(ET.fromstring(self.base['fomod/ModuleConfig.xml']), self.base,
            native=True, male_family='HIMBO', family='CBBE', physics='fsmp',
            additional_active=('HIMBO.esp', 'CBBE.esp'))
        original = {name: self.core[source] for name, source in paths.items()}
        baseline = {name: self.base[source] for name, source in paths.items()}
        self.assertEqual({name for name in baseline if baseline[name] != original[name]}, set(p.DESTINATIONS))
        overlay = {**baseline, **{name: self.entries[source] for name, source in selected.items()}}
        self.assertTrue(all(overlay[name] == data for name, data in original.items()))
        self.assertTrue(all(p.sha(overlay[name]) == p.CORE_FSMP_SHA for name in p.DESTINATIONS))
        self.assertEqual(p.sha(overlay[p.XML_ROOT+'CLAWMotionMale.xml']),
                         'b42bfa436a4e53baa48ff2249d4659718603798dabdb1e6b9427dc37efa0ea34')

    def test_modified_skin_or_xml_bytes_cannot_enter_a_rebuilt_candidate(self):
        for source in ('10 Static/male.nif', '30 Anatomy FSMP/male.nif', '40 Combined FSMP/CLAWMotionNeutralAnatomyMale.xml'):
            entries = dict(self.entries)
            changed = bytearray(entries[source]); changed[-1] ^= 1; entries[source] = bytes(changed)
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, 'Changed component payload'):
                p.audit(entries, self.base, self.core, self.package, self.reader)


if __name__ == '__main__':
    unittest.main(verbosity=2)
