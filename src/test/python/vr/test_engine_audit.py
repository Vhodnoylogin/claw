"""Independent synthetic records plus opt-in actual installed record evidence."""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str((Path(__file__).resolve().parents[4] / 'src/main/python/vr')))
import engine_audit as audit
from record_reader import DeclaredLoadOrder, FormKey, PluginFile, subrecords, zstring


def sub(tag, data):
    return tag.encode('ascii') + struct.pack('<H', len(data)) + data


def text(value):
    return value.encode() + b'\0'


def record(tag, fid, payload, flags=0):
    if flags & 0x40000:
        payload = struct.pack('<I', len(payload)) + zlib.compress(payload)
    return struct.pack('<4sIIIIHH', tag.encode(), len(payload), flags, fid, 0, 44, 0) + payload


def group(records, label=b'ARMA'):
    return struct.pack('<4sI4siHHHH', b'GRUP', 24 + len(records), label, 0, 0, 0, 0, 0) + records


def plugin(records=b'', masters=()):
    payload = sub('HEDR', struct.pack('<fII', 1.7, 1, 0x800))
    for master in masters:
        payload += sub('MAST', text(master)) + sub('DATA', bytes(8))
    return record('TES4', 0, payload) + records


def armor_addon(*, female='FemaleWolf_1.nif', male_weight=False, female_weight=False, race=0xCDD84, flags=0):
    data = bytes([0, 0, 2 if male_weight else 0, 2 if female_weight else 0, 2, 0, 0, 23]) + bytes(4)
    body = sub('EDID', text('NakedTorsoWerewolfBeast')) + sub('RNAM', struct.pack('<I', race))
    body += sub('BODT', struct.pack('<III', 4, 0, 2)) + sub('DNAM', data)
    for tag, value in [('MOD2', 'MaleWolf_1.nif'), ('MOD3', female),
                       ('MOD4', '1stPersonMaleBody_1.NIF'), ('MOD5', '1stPersonFemaleBody_1.nif')]:
        body += sub(tag, text(value))
    return record('ARMA', 0xCDD87, body, flags)


def master_records():
    race = sub('EDID', text('WerewolfBeastRace')) + sub('WNAM', struct.pack('<I', 0xCDD86))
    race += sub('BOD2', struct.pack('<II', 4, 2)) + sub('ANAM', text('skeleton.nif')) * 2
    skin = sub('EDID', text('SkinNakedWerewolfBeast')) + sub('RNAM', struct.pack('<I', 0xCDD84))
    skin += sub('BOD2', struct.pack('<II', 4, 2)) + sub('MODL', struct.pack('<I', 0xCDD87))
    player = sub('EDID', text('Player')) + sub('RNAM', struct.pack('<I', 0x13746)) + sub('ACBS', bytes(24))
    return group(record('RACE', 0xCDD84, race), b'RACE') + group(record('ARMO', 0xCDD86, skin), b'ARMO') + group(armor_addon()) + group(record('NPC_', 7, player), b'NPC_')


class RecordReaderTests(unittest.TestCase):
    def test_extended_subrecord_and_truncation(self):
        data = b'x' * 70000
        raw = sub('XXXX', struct.pack('<I', len(data))) + b'MODL\0\0' + data
        self.assertEqual([('MODL', data)], subrecords(raw))
        for damaged in [raw[:-1], b'EDID\x02', sub('XXXX', struct.pack('<I', 3)),
                        sub('XXXX', struct.pack('<I', 3)) + sub('XXXX', struct.pack('<I', 3)),
                        sub('XXXX', b'xx')]:
            with self.subTest(damaged=damaged[:15]), self.assertRaises(ValueError):
                subrecords(damaged)

    def test_zstring_cannot_hide_embedded_null_or_missing_terminator(self):
        self.assertEqual('model.nif', zstring(b'model.nif\0'))
        for value in [b'model.nif', b'model\0ignored\0', b'']:
            with self.assertRaises(ValueError):
                zstring(value)

    def test_master_local_and_self_form_id_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Patch.esp'
            path.write_bytes(plugin(masters=['Skyrim.esm', 'Other.esm']))
            p = PluginFile(path)
            try:
                self.assertEqual(FormKey('skyrim.ESM', 0xCDD87), p.form_key(0xCDD87))
                self.assertEqual(FormKey('Other.esm', 0x123), p.form_key(0x01000123))
                self.assertEqual(FormKey('Patch.esp', 0x800), p.form_key(0x02000800))
                with self.assertRaises(ValueError):
                    p.form_key(0x03000800)
            finally:
                p.close()
    def test_compressed_payload_and_nested_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Skyrim.esm'
            path.write_bytes(plugin(group(group(armor_addon(flags=0x40000)))))
            p = PluginFile(path)
            try:
                r = DeclaredLoadOrder([p]).winner(FormKey('Skyrim.esm', 0xCDD87), 'ARMA')
                self.assertEqual('NakedTorsoWerewolfBeast', zstring(r.one('EDID')))
                self.assertFalse(audit.arma_summary(r)['weightSliderEnabled']['female'])
            finally:
                p.close()

    def test_bad_group_record_and_compression_bound_are_rejected(self):
        malformed = [b'TES4', plugin() + b'GRUP' + struct.pack('<I', 0) + bytes(16),
                     plugin() + record('ARMA', 0xCDD87, sub('EDID', text('x')))[:-1]]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Skyrim.esm'
            for raw in malformed:
                path.write_bytes(raw)
                with self.subTest(size=len(raw)), self.assertRaises(ValueError):
                    PluginFile(path)
            raw = record('ARMA', 0xCDD87, bytes(4), 0x40000)
            # Corrupt the claimed uncompressed size without constructing a large payload.
            raw = raw[:24] + struct.pack('<I', 0xFFFFFFFF) + raw[28:]
            path.write_bytes(plugin(group(raw)))
            p = PluginFile(path)
            try:
                with self.assertRaisesRegex(ValueError, 'exceeds audit bound'):
                    next(iter(p.records.values())).fields()
            finally:
                p.close()
            corrupt = struct.pack('<4sIIIIHH', b'ARMA', 9, 0x40000, 0xCDD87, 0, 44, 0)
            corrupt += struct.pack('<I', 4) + b'bad!!'
            path.write_bytes(plugin(group(corrupt)))
            p = PluginFile(path)
            try:
                with self.assertRaisesRegex(ValueError, 'Invalid compressed record stream'):
                    next(iter(p.records.values())).fields()
            finally:
                p.close()

    def test_duplicate_record_and_master_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Skyrim.esm'
            for raw in [plugin(group(armor_addon() * 2)), plugin(masters=['Other.esm', 'other.esm'])]:
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    PluginFile(path)


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        directory = Path(self.temp.name) / 'inputs'
        directory.mkdir()
        self.master = directory / 'Skyrim.esm'
        self.patch = directory / 'CLAW.esp'
        self.master.write_bytes(plugin(master_records()))
        self.patch.write_bytes(plugin(group(armor_addon(male_weight=True, female_weight=True)), ['Skyrim.esm']))
        self.base, self.override = PluginFile(self.master), PluginFile(self.patch)

    def tearDown(self):
        self.override.close()
        self.base.close()
        self.temp.cleanup()

    def test_record_chain_slots_and_declared_override(self):
        order = DeclaredLoadOrder([self.base, self.override])
        result = audit.skin_chain(order)
        addon = result['addons'][0]
        self.assertEqual('0CDD86:skyrim.esm', result['race']['skin'])
        self.assertEqual('0CDD87:skyrim.esm', addon['formKey'])
        self.assertTrue(result['bodySlot32PresentInEveryStage'])
        self.assertEqual([4], result['slotIntersectionMasks'])
        self.assertEqual([{'number': 32, 'name': 'Body'}], addon['biped']['slots'])
        self.assertEqual({'male': True, 'female': True}, addon['weightSliderEnabled'])
        self.assertEqual(2, len(order.history(FormKey('Skyrim.esm', 0xCDD87))))
        self.assertIsNone(addon['engineSelectedFirstPersonModels'])

    def test_vanilla_weight_flags_and_sex_models_stay_distinct(self):
        result = audit.skin_chain(DeclaredLoadOrder([self.base]))['addons'][0]
        self.assertEqual({'male': False, 'female': False}, result['weightSliderEnabled'])
        self.assertEqual('FemaleWolf_1.nif', result['worldModels']['female'])
        self.assertEqual('1stPersonFemaleBody_1.nif', result['firstPersonRecordModels']['female'])

    def test_static_player_is_not_transformed_snapshot(self):
        result = audit.player_record(DeclaredLoadOrder([self.base]))
        self.assertEqual('013746:skyrim.esm', result['staticRace'])
        self.assertIsNone(result['explicitStaticSkin'])
        self.assertIsNone(result['transformedRace'])
        self.assertIsNone(result['runtimeSex'])

    def test_missing_master_and_duplicate_input_refused(self):
        for plugins in [[self.override], [self.base, self.base]]:
            with self.assertRaises(ValueError):
                DeclaredLoadOrder(plugins)

    def test_deleted_override_does_not_fall_back(self):
        r = self.override.records[FormKey('Skyrim.esm', 0xCDD87)]
        r.flags |= 0x20
        with self.assertRaisesRegex(ValueError, 'deleted/ignored'):
            audit.skin_chain(DeclaredLoadOrder([self.base, self.override]))

    def test_inherited_race_is_explicitly_outside_resolver_scope(self):
        self.override.close()
        self.patch.write_bytes(plugin(group(armor_addon(race=0x13746)), ['Skyrim.esm']))
        self.override = PluginFile(self.patch)
        with self.assertRaisesRegex(ValueError, 'another race'):
            audit.skin_chain(DeclaredLoadOrder([self.base, self.override]))

    def test_rejected_resource_pins_and_baseline_create_no_output(self):
        contract = audit.body_resource.read_json(Path(audit.__file__).with_name('engine-contract.json'))
        with self.assertRaises((ValueError, OSError)):
            audit.resource_pins(self.temp.name, contract)
        output = Path(self.temp.name) / 'new-audit'
        with self.assertRaisesRegex(ValueError, 'Unsupported exact Skyrim VR master'):
            audit.write_report(self.master, self.patch, Path(self.temp.name) / 'resources', output)
        self.assertFalse(output.exists())


@unittest.skipUnless(os.environ.get('CLAW_VR_RECORD_MASTER') and os.environ.get('CLAW_VR_RESOURCE_ROOT'),
                     'Set CLAW_VR_RECORD_MASTER and CLAW_VR_RESOURCE_ROOT for actual pinned record evidence')
class InstalledRecordEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = audit.report(os.environ['CLAW_VR_RECORD_MASTER'],
                                  audit.ROOT / 'target/references/releases/0.6.2.0/base/CLAW.esp',
                                  os.environ['CLAW_VR_RESOURCE_ROOT'], reference=os.environ.get('CLAW_VR_REFERENCE_PLUGIN'))

    def test_actual_vanilla_chain_and_exact_record_offsets(self):
        vanilla = self.result['vanilla']
        self.assertEqual(876313, vanilla['race']['recordOffset'])
        self.assertEqual(4021391, vanilla['skinArmor']['recordOffset'])
        self.assertEqual(245179729, vanilla['addons'][0]['recordOffset'])
        self.assertTrue(vanilla['bodySlot32PresentInEveryStage'])
        self.assertEqual({'male': False, 'female': False}, vanilla['addons'][0]['weightSliderEnabled'])

    def test_actual_claw_flags_world_sex_and_human_first_person_fields(self):
        addon = self.result['declaredEffective']['addons'][0]
        self.assertEqual({'male': True, 'female': True}, addon['weightSliderEnabled'])
        self.assertIn('FemaleBodyWereWolf_1.NIF', addon['worldModels']['female'])
        self.assertIn('1stPersonMaleBody_1.NIF', addon['firstPersonRecordModels']['male'])
        self.assertIn('1stPersonFemaleBody_1.nif', addon['firstPersonRecordModels']['female'])
        self.assertIsNone(addon['engineSelectedFirstPersonModels'])

    def test_refusal_is_preserved_despite_correct_records_and_resources(self):
        self.assertFalse(self.result['pluginGenerated'])
        self.assertFalse(self.result['installLayoutGenerated'])
        self.assertFalse(self.result['manualGate'])
        self.assertFalse(self.result['activeGameLoadOrderObserved'])
        self.assertEqual('refused-unresolved-native-first-person-dispatch', self.result['status'])
        self.assertIn('DNAM', self.result['nativeSelection']['missingBranch'])

    def test_reference_is_comparison_and_retains_body_human_paths(self):
        reference = self.result['referenceOnlyComparison']
        if reference is None:
            self.skipTest('No explicit reference plugin supplied')
        self.assertTrue(reference['bodySlot32PresentInEveryStage'])
        addon = reference['addons'][0]
        self.assertEqual({'male': False, 'female': False}, addon['weightSliderEnabled'])
        self.assertEqual(self.result['vanilla']['addons'][0]['firstPersonRecordModels'], addon['firstPersonRecordModels'])
        self.assertEqual(2, len(self.result['declaredInputOrder']))


if __name__ == '__main__':
    unittest.main()
