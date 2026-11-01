"""Pinned installer-only updater contracts; synthetic payloads never run in game."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
spec = importlib.util.spec_from_file_location('claw_fomod_update', ROOT/'src/main/python/build-tools/build-fomod-update.py')
update = importlib.util.module_from_spec(spec); spec.loader.exec_module(update)

def entries():
    config = ET.Element('config')
    ET.SubElement(config, 'moduleName').text = 'CLAW'
    dependencies = ET.SubElement(config, 'moduleDependencies', operator='And')
    for name in ('RaceMenu.esp', 'HIMBO.esp', 'CBBE.esp'):
        ET.SubElement(dependencies, 'fileDependency', file=name, state='Active')
    required = ET.SubElement(config, 'requiredInstallFiles'); files = {}
    for name in ('CLAW.esp', 'male_0.nif', 'male_1.nif', 'male.tri', 'female_0.nif', 'female_1.nif', 'female.tri'):
        source = '00 Base/'+name; ET.SubElement(required, 'file', source=source, destination=name)
        files[source] = ('synthetic '+name).encode()
    steps = ET.SubElement(config, 'installSteps', order='Explicit')
    for name, folders in (('Native', ['10 Native']), ('Combined bodies', list(update.FOLDERS.values())), ('OBody', ['30 OBody Source'])):
        step = ET.SubElement(steps, 'installStep', name=name)
        plugins = ET.SubElement(ET.SubElement(ET.SubElement(step, 'optionalFileGroups'), 'group'), 'plugins')
        for folder in folders:
            plugin = ET.SubElement(plugins, 'plugin', name=folder)
            ET.SubElement(plugin, 'description').text = 'Synthetic fixture'
            ET.SubElement(ET.SubElement(plugin, 'files'), 'folder', source=folder, destination='')
            ET.SubElement(ET.SubElement(plugin, 'typeDescriptor'), 'type', name='Optional')
    files.update({'10 Native/CLAWDistribution.dll': b'native fixture', '10 Native/CLAW.pex': b'script fixture',
                  '30 OBody Source/Host.esp': b'host fixture', '30 OBody Source/Host.pex': b'host script fixture',
                  'LICENSE.txt': b'unchanged notices'})
    for family, folder in update.FOLDERS.items(): files[folder+'/MorphLinks.xml'] = family.encode()
    files['fomod/ModuleConfig.xml'] = ET.tostring(config, encoding='utf-8', xml_declaration=True)
    files['fomod/info.xml'] = b"<?xml version='1.0' encoding='utf-8'?>\n<fomod><Name>CLAW</Name><Version MachineVersion='0.7.0.0'>0.7.0.0</Version></fomod>"
    return files

class FomodUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name); self.archive = self.root/'original.zip'
        self.original = entries()
        with zipfile.ZipFile(self.archive, 'x') as archive:
            for name, data in self.original.items(): archive.writestr(name, data)
        self.original_archive_bytes = self.archive.read_bytes()
        self.allowed = patch.object(update, 'ACCEPTED_INPUTS', {update.sha(self.original_archive_bytes)})
        self.allowed.start(); self.addCleanup(self.allowed.stop)

    def test_only_two_xml_members_change_and_all_four_payloads_are_preserved(self):
        result = update.build(self.archive, self.root/'output')
        self.assertEqual(len(result['selections']), 4)
        self.assertEqual([len(row['files']) for row in result['selections']], [10, 12, 10, 12])
        with zipfile.ZipFile(result['archive']['path']) as archive:
            actual = {name: archive.read(name) for name in archive.namelist()}
        self.assertEqual({name for name in actual if actual[name] != self.original[name]}, update.XML_MEMBERS)
        self.assertEqual(set(actual), set(self.original))
        info = ET.fromstring(actual['fomod/info.xml'])
        self.assertEqual(info.findtext('Version'), '0.7.1')
        self.assertEqual(info.find('Version').get('MachineVersion'), '0.7.1')
        for name in update.XML_MEMBERS:
            self.assertFalse(actual[name].startswith(b'<?xml'))
            self.assertEqual(ET.fromstring(b'\xfe\xff'+actual[name].decode().encode('utf-16-be')).tag,
                             ET.fromstring(actual[name]).tag)
        self.assertEqual(self.archive.read_bytes(), self.original_archive_bytes)

    def test_male_and_female_are_separate_pages_with_only_original_families(self):
        config = ET.fromstring(update.update_config(self.original['fomod/ModuleConfig.xml']))
        steps = config.findall('installSteps/installStep')
        self.assertEqual([step.get('name') for step in steps], ['Native', 'Male body', 'Female body', 'OBody'])
        male = steps[1].findall('.//plugin'); female = steps[2].findall('.//plugin')
        self.assertEqual([row.get('name') for row in male], ['HIMBO'])
        self.assertEqual([row.get('name') for row in female], ['CBBE', 'CBBE + 3BA'])
        self.assertEqual(male[0].find('typeDescriptor/type').get('name'), 'Required')
        for row in female:
            kinds = {node.get('name') for node in row.findall('.//defaultType')+row.findall('.//type')}
            self.assertLessEqual(kinds, {'Optional', 'Recommended'})
        self.assertEqual([node.get('file') for node in config.find('moduleDependencies')], ['RaceMenu.esp'])

    def test_unapproved_archive_refused_before_creating_output(self):
        with patch.object(update, 'ACCEPTED_INPUTS', set()):
            with self.assertRaisesRegex(ValueError, 'exact approved'):
                update.build(self.archive, self.root/'output')
        self.assertFalse((self.root/'output').exists())

    def test_existing_output_is_not_overwritten(self):
        output = self.root/'output'; output.mkdir(); marker = output/'owner.txt'; marker.write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'new output directory'):
            update.build(self.archive, output)
        self.assertEqual(marker.read_text(), 'preserve')

    def test_unknown_installer_structure_is_rejected(self):
        config = ET.fromstring(self.original['fomod/ModuleConfig.xml'])
        config.find('installSteps').remove(config.find('installSteps')[1])
        with self.assertRaisesRegex(ValueError, 'published 0.7 combined'):
            update.update_config(ET.tostring(config))

if __name__ == '__main__': unittest.main()
