"""Exact hidden/visible anatomy separation; no renderer or game acceptance."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
FILE = ROOT/'src/main/components/adult-anatomy/python/visual_variants.py'
SPEC = importlib.util.spec_from_file_location('claw_test_anatomy_visual_variants', FILE)
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


def cube():
    vertices = np.array([[-2,-2,-2],[2,-2,-2],[2,2,-2],[-2,2,-2],
                         [-2,-2,2],[2,-2,2],[2,2,2],[-2,2,2]], dtype=float)
    triangles = np.array([[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],
                          [1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]])
    return vertices, triangles


class LocalTopologyTests(unittest.TestCase):
    def test_exact_uv_seam_weld_does_not_create_a_local_hole(self):
        vertices, triangles = cube()
        # Give every triangle its own vertex indices, as authored UV seams do.
        duplicated = vertices[triangles].reshape(-1, 3)
        separate = np.arange(len(duplicated)).reshape(-1, 3)
        proof = v.closure_audit(duplicated, separate, [[-.5,-.5,-.5],[.5,.5,.5]])
        self.assertTrue(proof['localClosurePassed'])
        self.assertEqual(proof['localBoundaryEdges'], 0)

    def test_actual_missing_face_and_nonmanifold_patch_are_not_accepted(self):
        vertices, triangles = cube()
        for altered in (triangles[2:], np.r_[triangles, triangles[:1]]):
            proof = v.closure_audit(vertices, altered, [[-.5,-.5,-.5],[.5,.5,.5]])
            self.assertFalse(proof['localClosurePassed'])
            self.assertGreater(proof['localBoundaryEdges']+proof['localNonManifoldEdges'], 0)

    def test_no_epsilon_weld_can_hide_a_real_seam_gap(self):
        vertices, triangles = cube()
        duplicated = vertices[triangles].reshape(-1, 3)
        duplicated[0, 0] += 1e-6
        proof = v.closure_audit(duplicated, np.arange(len(duplicated)).reshape(-1, 3), [[0,0,0]])
        self.assertFalse(proof['localClosurePassed'])

    def test_pure_byte_api_refuses_unknown_or_already_changed_sources(self):
        with self.assertRaisesRegex(ValueError, 'exact reviewed'):
            v.hide_anatomy(b'unknown native geometry')
        with self.assertRaisesRegex(ValueError, 'ledger'):
            v.restore_anatomy(b'unknown native geometry', {})


class ActualVisualVariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected = os.environ.get('CLAW_ANATOMY_VISUAL_VARIANTS')
        if selected is None:
            raise unittest.SkipTest('Select an actual completed visual-variants directory')
        cls.root = Path(selected)
        cls.report = json.loads((cls.root/'visual-variants-report.json').read_text())
        if cls.report['status'] != 'verified-offline-hidden-base-and-exact-visible-addon-local-closure-passed':
            raise AssertionError('Selected native visibility candidate is incomplete')

    def test_all_four_families_and_both_endpoints_restore_exactly(self):
        self.assertEqual(set(self.report['families']), set(v.SOURCES))
        self.assertTrue(self.report['geometryRemainsEmbedded'])
        self.assertFalse(self.report['runtimeRenderingQualified'])
        self.assertFalse(self.report['appearanceQualified'])
        for family, rows in self.report['families'].items():
            self.assertTrue(rows['strictEndpointByteEquivalence'])
            for row in rows['endpoints']:
                base, addon = (Path(row[k]['path']).read_bytes() for k in ('base', 'addon'))
                hidden, ledger = v.hide_anatomy(addon)
                self.assertEqual((hidden, ledger), (base, row['ledger']))
                self.assertEqual(v.restore_anatomy(base, ledger), addon)
                self.assertEqual(v.sha(addon), v.SOURCES[family][0])
                self.assertEqual(sum(a != b for a, b in zip(base, addon)), 1)
                self.assertEqual(row['readback']['fsmpHook'], v.SOURCES[family][1])
                closure = row['readback']['localBodyClosure']
                self.assertTrue(closure['localClosurePassed'])
                self.assertEqual(closure['localBoundaryEdges'], 0)
                self.assertEqual(closure['localNonManifoldEdges'], 0)
                self.assertGreater(closure['localBodyTriangles'], 0)

    def test_independent_native_readback_keeps_body_and_hook_fields(self):
        dependency_paths = [Path(path) for path in self.report['dependencies']]
        addon = next(path.parent for path in dependency_paths if path.name == 'NiflyDLL.dll')
        morphbench = next(path.parent.parent for path in dependency_paths if path.name == 'nifpatch.py')
        api, Patch, Trip, _ = v._resource.dependencies(addon, morphbench)
        sys.path.insert(0, str(v.TOOLS))
        import breast_rig as rig
        skeleton = next(Path(path) for path, pin in self.report['resourceInputs'].items() if pin == v.SKELETON_SHA)
        for family, rows in self.report['families'].items():
            # The first test independently proves the second endpoint byte-equal.
            row = rows['endpoints'][0]
            actual = v.verify_native_pair(Path(row['base']['path']), Path(row['addon']['path']),
                Path(self.report['sharedTri']['path']), skeleton, api, Patch, Trip, rig)
            self.assertEqual(actual, row['readback'])

    def test_changed_base_or_restore_ledger_cannot_expose_other_geometry(self):
        row = self.report['families']['static']['endpoints'][0]
        base = Path(row['base']['path']).read_bytes()
        changed = bytearray(base); changed[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'pin changed'):
            v.restore_anatomy(bytes(changed), row['ledger'])
        ledger = copy.deepcopy(row['ledger']); ledger['edit']['offset'] += 4
        with self.assertRaisesRegex(ValueError, 'offset changed'):
            v.restore_anatomy(base, ledger)
        with self.assertRaisesRegex(ValueError, 'exact reviewed'):
            v.hide_anatomy(base)


if __name__ == '__main__':
    unittest.main(verbosity=2)
