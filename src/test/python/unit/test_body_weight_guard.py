import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'src/main/python/build-tools'))
import male_weight_guard as guard
import breast_rig as rig
spec=importlib.util.spec_from_file_location('test_continuous_guard_path',ROOT/'src/main/python/build-tools/check-weight-pose-path.py')
path=importlib.util.module_from_spec(spec);spec.loader.exec_module(path)


class GuardTests(unittest.TestCase):
    def test_continuous_collapse_is_distinct_from_normal_turn(self):
        base=np.array([[[0.,0,0],[1.,0,0],[0.,1,0]]])
        collapse=base.copy();collapse[0,2]=[0.,-1,0]
        report=path.critical(base,collapse)
        self.assertEqual(report['continuousAreaCollapseTriangles'],[0])
        turn=base.copy();turn[0,2]=[0.,-.5,1.]
        report=path.critical(base,turn)
        self.assertEqual(report['continuousAreaCollapseTriangles'],[])
        self.assertEqual(report['negativeOwnPose0NormalDotTriangles'],[0])

    def test_geodesic_guard_shares_coincident_uv_vertices(self):
        vertices=np.array([[0.,0,0],[1.,0,0],[0.,1,0],[0.,0,0],[1.,0,0],[0.,-1,0]])
        faces=np.array([[0,1,2],[3,4,5]])
        distance=guard.distances(vertices,faces,[0],3.)
        self.assertEqual(distance[0],distance[3]);self.assertEqual(distance[1],distance[4]);self.assertEqual(distance[3],0.)

    def test_actual_guard_keeps_low_and_contact_fields(self):
        root=os.environ.get('CLAW_COMPOSED_NATIVE')
        if not root:self.skipTest('Set CLAW_COMPOSED_NATIVE to final guarded composition')
        root=Path(root);file=root/'male-weight-guard-report.json'
        if not file.exists():self.skipTest('Selected composition predates the male weight repair')
        report=json.loads(file.read_text());self.assertEqual(report['status'],'verified-local-male-weight-repair-original-low-and-contact-fields-preserved')
        self.assertEqual(report['selectedFade'],2.5)
        manifest=json.loads((root/'final-resource-manifest.json').read_text())
        self.assertEqual(rig.sha256(manifest['files']['malebodywerewolf_1.nif']['path']),report['newMaleHighSha256'])
        for shapes in report['serializedContinuousPoseChecks'].values():
            for rows in shapes.values():
                self.assertEqual(len(rows),151)
                self.assertTrue(all(not r['continuousAreaCollapseTriangles'] and not r['negativeOwnPose0NormalDotTriangles'] for r in rows))
        self.assertTrue(report['exactFinalContactFieldProof'])
        self.assertTrue(all(row['exactP0'] and row['exactIndependentWeightDelta'] and row['exactAbsoluteTriFields'] for row in report['exactFinalContactFieldProof']))


if __name__=='__main__':unittest.main()
