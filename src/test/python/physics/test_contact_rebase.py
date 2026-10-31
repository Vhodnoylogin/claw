import importlib.util
from pathlib import Path
import unittest
import tempfile
import numpy as np
spec=importlib.util.spec_from_file_location('contact_rebase',(Path(__file__).resolve().parents[4] / 'src/main/python/physics')/'rebase-contact-inputs.py')
rebase=importlib.util.module_from_spec(spec);spec.loader.exec_module(rebase)

class ContactRebaseTests(unittest.TestCase):
    def test_model_and_helper_consumed_from_captured_bytes_mutations_fail_final_check(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);model=path/'model.json';helper=path/'helper.py'
            model.write_text('{"identity":"captured"}');helper.write_text('identity="captured"\n')
            captured=rebase.capture_inputs([model,helper])
            model.write_text('{"identity":"replaced"}');helper.write_text('identity="replaced"\n')
            self.assertEqual(rebase.captured_json(model,captured)['identity'],'captured')
            self.assertEqual(rebase.captured_module('claw_rebase_mutation_fixture',helper,captured).identity,'captured')
            with self.assertRaisesRegex(ValueError,'Input changed'):rebase.revalidate_inputs(captured)

    def test_rounded_bucket_boundary_cannot_hide_coincident_full_field_match(self):
        p=np.array([[.0004999,0,0],[1.0004999,0,0],[.0004999,1,0]]*2)
        before={'points':p.tolist(),'weightDeltas':[[0,0,0]]*3+[[1,0,0]]*3,'deltas':{},'faces':[[0,1,2],[3,4,5]]}
        q=p.copy();q[:3,0]+=2e-7
        after={**before,'points':q.tolist(),'faceReferences':[{'shape':'head','triangle':0},{'shape':'head','triangle':1}]}
        mapping,summary=rebase.match_region(before,after,[],1e-4)
        self.assertEqual([m['finalTriangle'] for m in mapping],[0,1])
        self.assertLess(summary['maximumRestCoordinateDifference'],1e-4)

    def test_coincident_faces_get_bijective_matching_when_greedy_choice_would_fail(self):
        p=[[0,0,0],[1,0,0],[0,1,0]]*2
        before={'points':p,'weightDeltas':[[0,0,0]]*3+[[-.00009,0,0]]*3,'deltas':{},'faces':[[0,1,2],[3,4,5]]}
        after={'points':p,'weightDeltas':[[0,0,0]]*3+[[.00009,0,0]]*3,'deltas':{},'faces':[[0,1,2],[3,4,5]],
            'faceReferences':[{'shape':'head','triangle':0},{'shape':'head','triangle':1}]}
        mapping,_=rebase.match_region(before,after,[],1e-4)
        self.assertEqual([m['finalTriangle'] for m in mapping],[1,0])

    def test_matches_actual_oriented_triangle_with_reordered_vertex_storage(self):
        before={'points':[[0,0,0],[1,0,0],[0,1,0]],'weightDeltas':[[1,0,0]]*3,
            'deltas':{'size':[[0,0,2]]*3},'faces':[[0,1,2]]}
        after={'points':[[0,1,0],[0,0,0],[1,0,0]],'weightDeltas':[[1,0,0]]*3,
            'deltas':{'size':[[0,0,2]]*3},'faces':[[0,1,2]],'faceReferences':[{'shape':'head_CLAWHead','triangle':37}]}
        mapping,summary=rebase.match_region(before,after,['size'],1e-4)
        self.assertEqual(mapping[0]['finalReference']['triangle'],37)
        self.assertTrue(summary['sameOrientedTrianglesAndFields'])
        self.assertEqual(summary['maximumCombinedCoordinateErrorBoundOverUnitInputBox'],0.)

    def test_rejects_changed_weight_field_absolute_tri_or_triangle_orientation(self):
        before={'points':[[0,0,0],[1,0,0],[0,1,0]],'weightDeltas':[[1,0,0]]*3,
            'deltas':{'size':[[0,0,2]]*3},'faces':[[0,1,2]]}
        for change in ('weight','tri','orientation'):
            import copy
            after=copy.deepcopy(before);after['faceReferences']=[{'shape':'head','triangle':0}]
            if change=='weight':after['weightDeltas'][0]=[1.1,0,0]
            elif change=='tri':after['deltas']['size'][0]=[0,0,2.1]
            else:after['faces']=[[0,2,1]]
            with self.subTest(change=change),self.assertRaises(ValueError):rebase.match_region(before,after,['size'],1e-4)

if __name__=='__main__':unittest.main()
