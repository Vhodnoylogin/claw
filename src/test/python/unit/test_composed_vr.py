import json
import os
from pathlib import Path
import sys
import unittest
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'src/main/python/build-tools'))
import chest_attachment as chest
import breast_rig as rig
import composed_vr


class ComposedTests(unittest.TestCase):
    def test_root_pair_uses_common_normalized_delta(self):
        old=np.array([[.25,.25,.5],[.75,.125,.125]])
        actual=chest.transfer_pair(old,[0,1],0,.3125,0,1)
        np.testing.assert_array_equal(actual[:,1],[.3125,.1875])
        np.testing.assert_array_equal(actual.sum(1),old.sum(1))
        np.testing.assert_array_equal(actual[:,2],old[:,2])

    def test_root_pair_keeps_p1_and_saturated_tip(self):
        old=np.array([[.5,.25,.25,0.,0.],[.25,0.,.25,.25,.25]])
        actual=chest.transfer_pair(old,[0,1],0,.3125,0,1)
        np.testing.assert_array_equal(actual[1],old[1])
        np.testing.assert_array_equal(actual[:,2:],old[:,2:])
        self.assertLessEqual((actual>0).sum(1).max(),4)

    def test_actual_composed_weight_endpoints_and_bounds(self):
        root=os.environ.get('CLAW_COMPOSED_NATIVE')
        if not root:self.skipTest('Set CLAW_COMPOSED_NATIVE to the completed composed candidate')
        root=Path(root);report=json.loads((root/'composed-vr-report.json').read_text())
        self.assertEqual(report['status'],'verified-offline-composed-body-resources-runtime-and-appearance-pending')
        api,_,_=rig.load_pynifly(None)
        for sex,body in report['bodies'].items():
            self.assertEqual(rig.sha256(body['nif']),body['nifSha256']);self.assertEqual(rig.sha256(body['highNif']),body['highNifSha256'])
            self.assertNotEqual(body['nifSha256'],body['highNifSha256'])
            low={s.name:s for s in api.NifFile(body['nif']).shapes};high={s.name:s for s in api.NifFile(body['highNif']).shapes}
            self.assertEqual(set(low),set(high));self.assertIn('head_CLAWHead',low)
            self.assertNotEqual(low['head'].textures,low['body'].textures)
            self.assertEqual(low['head'].textures,low['head_CLAWHead'].textures)
            moved=0
            for name,a in low.items():
                b=high[name];self.assertEqual(a.tris,b.tris);self.assertEqual(a.uvs,b.uvs);self.assertEqual(a.bone_weights,b.bone_weights)
                self.assertEqual(a.textures,b.textures)
                moved+=int(np.any(np.asarray(a.verts)!=np.asarray(b.verts),axis=1).sum())
                for bone in a.bone_weights:np.testing.assert_array_equal(rig.matrix(a.get_shape_skin_to_bone(bone)),rig.matrix(b.get_shape_skin_to_bone(bone)))
            self.assertGreater(moved,0)
            bound=json.loads(Path(body['boundsReport']).read_text())
            self.assertTrue(all(row['allDeclaredPoseMorphBoxesCovered'] for row in bound['poseReadback'].values()))
            self.assertTrue(all(row['ok'] for row in bound['publicStaticReadbackAfterPoseWrite']))
            self.assertTrue(all(row['ok'] for row in bound['highEndpointPublicReadback']))
            self.assertTrue(all(x['perTriangleOriginalMaterialAndUvPreserved'] for x in body['readback']['shapes'].values()))
            self.assertTrue(all(x['perTriangleOriginalMaterialAndUvPreserved'] for x in body['highReadback']['shapes'].values()))
            self.assertEqual(body['readback']['controlledHeadPoses']['maximumExteriorError'],0.)
            self.assertEqual(body['highReadback']['controlledHeadPoses']['maximumExteriorError'],0.)


if __name__=='__main__':unittest.main()
