"""Bounded collision registration contracts; no contact or solver test claims."""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
FILE = ROOT/'src/main/components/adult-anatomy/python/collision_candidate.py'
SPEC = importlib.util.spec_from_file_location('claw_test_anatomy_collision', FILE)
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


def row(bone, weight):
    return [(bone, weight), (c.PELVIS, 0.), (c.PELVIS, 0.), (c.PELVIS, 0.)]


class SourcePolicyTests(unittest.TestCase):
    def test_strict_equality_excludes_exact_pelvis_one_and_includes_one_mobile_corner(self):
        rows = [row(c.PELVIS, 1.), row(c.PELVIS, 1.), row(c.PELVIS, 1.),
                *(row(name, .125) for name in c.ANATOMY_DRIVERS)]
        proof = c.retained_support(rows, [(0, 1, 2), (0, 1, 3), (1, 2, 4), (0, 2, 5)])
        self.assertEqual(proof['excludedPelvisOnlyTriangles'], 1)
        self.assertEqual(proof['retainedTriangles'], 3)
        self.assertEqual(proof['retainedDynamicVertices'], 3)
        self.assertEqual(set(proof['positivePackedDriverRows'].values()), {1})

    def test_epsilon_equality_and_missing_actual_support_do_not_pass(self):
        rows = [row(c.PELVIS, 1.), row(c.PELVIS, 1.), row(c.PELVIS, 1.)]
        for suffix in ([], [row(name, 2**-23) for name in c.ANATOMY_DRIVERS]):
            with self.assertRaisesRegex(ValueError, 'actual dynamic driver'):
                c.retained_support(rows+suffix, [(0, 1, 2)])
        for rows in ([], [row('unknown bone', .2)]):
            with self.assertRaises(ValueError): c.retained_support(rows, [(0, 1, 2)])

    def test_reciprocal_tags_external_skeleton_and_skinned_peer_required(self):
        self.assertTrue(c.eligible_pair({c.PEER_TAG}, {c.SURFACE_TAG}))
        for tags, whitelist, options in [
            (set(), {c.SURFACE_TAG}, {}), ({c.PEER_TAG}, set(), {}),
            ({c.PEER_TAG}, {c.SURFACE_TAG}, {'same_skeleton': True}),
            ({c.PEER_TAG}, {c.SURFACE_TAG}, {'peer_skinned': False}),
            ({c.PEER_TAG}, {c.SURFACE_TAG}, {'both_kinematic': True}),
        ]:
            self.assertFalse(c.eligible_pair(tags, whitelist, **options))

    def test_peer_xml_contract_never_means_bound_or_working_contact(self):
        node = ET.Element('per-vertex-shape', {'name': 'existing_peer_mesh'})
        for tag, value in [('margin', '.125'), ('shared', 'external'),
                           ('tag', c.PEER_TAG), ('can-collide-with-tag', c.SURFACE_TAG)]:
            ET.SubElement(node, tag).text = value
        report = c.validate_peer_shape(ET.tostring(node))
        self.assertTrue(report['xmlContractPassed'])
        for key in ('nativeBindingVerified', 'distinctLiveSkeletonVerified', 'contactQualified'):
            self.assertFalse(report[key])
        for tag, bad in [('margin', '0'), ('margin', 'nan'), ('shared', 'internal'),
                         ('tag', 'foreign'), ('can-collide-with-tag', 'foreign')]:
            original = node.find(tag).text; node.find(tag).text = bad
            with self.assertRaises(ValueError): c.validate_peer_shape(ET.tostring(node))
            node.find(tag).text = original
        ET.SubElement(node, 'no-collide-with-tag').text = 'unused'
        with self.assertRaises(ValueError): c.validate_peer_shape(ET.tostring(node))

    def test_unknown_inputs_and_incomplete_provider_source_fail_closed(self):
        with self.assertRaises(ValueError): c.bind_candidate(b'unknown mesh', 'anatomy3')
        with self.assertRaises(ValueError): c.collision_xml(b'<system/>', 'anatomy3')
        with self.assertRaises(ValueError): c.provider_contract(b'unknown source', {})


class ActualCollisionInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.environ.get('CLAW_ANATOMY_COLLISION')
        if selected is None:
            raise unittest.SkipTest('Select an actual completed offline collision candidate')
        cls.root = Path(selected)
        cls.report = json.loads((cls.root/'collision-report.json').read_text())
        if cls.report['status'] != 'verified-offline-surface-binding-and-source-eligibility-only':
            raise AssertionError('Actual candidate is incomplete')

    def test_actual_written_files_and_both_endpoints_keep_exact_source_graph(self):
        for rel, expected in self.report['files'].items():
            self.assertEqual(c.sha((self.root/rel).read_bytes()), expected)
        for family, value in self.report['families'].items():
            source_key = 'anatomy' if family == 'anatomy3' else 'combined'
            original = (Path(self.report['invocation'][source_key])/c.FAMILIES[family][2]).read_bytes()
            xml = Path(value['xml']['path']).read_bytes()
            self.assertTrue(c.inspect_collision_xml(xml, original, family)['noPeerBound'])
            broken = ET.fromstring(xml)
            broken.find("per-triangle-shape/weight-threshold[@bone='NPC Pelvis [Pelv]']").text = '0'
            with self.assertRaises(ValueError): c.inspect_collision_xml(ET.tostring(broken), original, family)
            broken = ET.fromstring(xml)
            broken.find('bone/mass').text = '999'
            with self.assertRaises(ValueError): c.inspect_collision_xml(ET.tostring(broken), original, family)
            # The existing strict motion-only parser must continue rejecting a
            # collision extension instead of quietly broadening normal graphs.
            drivers = c.ANATOMY_DRIVERS+(c.CORE_DRIVERS if family == 'combined12' else ())
            anchors = ('WWD 1',)+(('NPC Head [Head]', 'Tails') if family == 'combined12' else ())
            with self.assertRaises(ValueError): c._motion.inspect_xml(xml, drivers, anchors)
            self.assertTrue(value['strictEndpointByteEquivalence'])
            self.assertEqual(value['endpoints'][0]['sha256'], value['endpoints'][1]['sha256'])
            for endpoint in value['endpoints']:
                proof = endpoint['proof']
                self.assertTrue(proof['allOtherBlocksExact'])
                self.assertTrue(proof['nativeReadback']['morphbenchBlockReadback'])
                self.assertTrue(proof['nativeReadback']['packedPartitionOrientedTriangleOrderExact'])
                support = proof['nativeReadback']['packedProviderSupport']
                self.assertEqual(support['sourceTriangleCount'], 1760)
                self.assertGreater(support['retainedTriangles'], 0)
                self.assertGreater(support['excludedPelvisOnlyTriangles'], 0)
                self.assertFalse(proof['nativeReadback']['contactQualified'])

    def test_actual_provider_inputs_and_explicit_unqualified_limits(self):
        archive = Path(self.report['invocation']['provider_archive']).read_bytes()
        source = Path(self.report['invocation']['provider_source'])
        evidence = c.provider_contract(archive, {name: (source/name).read_bytes() for name in c.PROVIDER_FILES})
        self.assertTrue(evidence['selectedFilesExactToReleaseArchive'])
        self.assertFalse(evidence['installedBinaryEquivalenceProved'])
        for key in ('contactQualified', 'motionRuntimeQualified', 'peerAssetsSupplied', 'installed', 'gameStarted'):
            self.assertFalse(self.report[key])
        peer = json.loads((self.root/'peer-contract.json').read_text())
        self.assertTrue(all(peer['eligibilityControls'].values()))
        self.assertFalse(peer['genericHavokHiggsPlanckContactSupported'])
        self.assertTrue(peer['missing'])


if __name__ == '__main__':
    unittest.main()
