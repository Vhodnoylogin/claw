import copy,json,unittest,sys,os,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,os.environ.get('CLAW_PHOTO_HELPER_ROOT',str(HERE)))
import numpy as np
import frame_registration as registration
from test_support import FIXTURES,temporary
from PIL import Image
class Registration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pattern=np.random.default_rng(260113).integers(0,256,(1080,1920),dtype=np.uint8)
        cls.policy=json.loads((FIXTURES/'registration-policy.json').read_bytes())
    def test_same_grid_passes_without_mutating_either_array(self):
        a=self.pattern.copy();b=self.pattern.copy();result=registration.estimate(a,b,self.policy)
        self.assertTrue(result['passed']);self.assertLess(result['maximumFhdCornerDisplacementPixels'],.001)
        self.assertFalse(result['imagesShiftedResampledOrWritten']);self.assertTrue(np.array_equal(a,self.pattern));self.assertTrue(np.array_equal(b,self.pattern))
    def test_one_pixel_shift_exceeds_unchanged_half_pixel_gate(self):
        shifted=np.roll(self.pattern,1,axis=1);before=shifted.copy();result=registration.estimate(self.pattern,shifted,self.policy)
        self.assertFalse(result['passed']);self.assertGreater(result['maximumFhdCornerDisplacementPixels'],.5);self.assertTrue(np.array_equal(shifted,before))
    def test_flat_or_wrong_resolution_is_unavailable(self):
        with self.assertRaisesRegex(ValueError,'insufficient distinctive'):registration.estimate(np.zeros_like(self.pattern),np.zeros_like(self.pattern),self.policy)
        with self.assertRaisesRegex(ValueError,'FHD'):registration.estimate(self.pattern[:100],self.pattern[:100],self.policy)

    def test_public_file_api_withholds_without_pixel_admission_and_preserves_bytes(self):
        with temporary() as directory:
            root=Path(directory);image=root/'original.png';Image.fromarray(self.pattern).save(image)
            before=image.read_bytes();digest=hashlib.sha256(before).hexdigest()
            case={'photos':[{'id':name,'path':str(image),'sha256':digest,'status':'captured'} for name in ['a','b']]}
            policy=copy.deepcopy(self.policy);policy['rootReview']={'baselineSha256':digest,'originalHashes':{'a':digest,'b':digest},'pixelAdmission':False}
            casefile=root/'case.json';roifile=root/'roi.json';casefile.write_text(json.dumps(case));roifile.write_text(json.dumps(policy))
            result=registration.run(casefile,roifile)
            self.assertEqual(result['status'],'COMPARE_WITHHELD');self.assertFalse(result['rootPixelAndRoiAdmission']);self.assertTrue(result['noImagesModified'])
            self.assertEqual(image.read_bytes(),before)
            policy['rootReview'].pop('pixelAdmission');roifile.write_text(json.dumps(policy))
            missing=registration.run(casefile,roifile)
            self.assertEqual(missing['status'],'COMPARE_WITHHELD')
            policy['rootReview'].update({key:True for key in registration.PIXEL_ADMISSION_FIELDS});roifile.write_text(json.dumps(policy))
            self.assertEqual(registration.run(casefile,roifile)['status'],'PASS_STATIC_BACKGROUND_REGISTRATION')
            self.assertEqual(image.read_bytes(),before)
            case['photos'][0]['sha256']='0'*64;casefile.write_text(json.dumps(case))
            with self.assertRaisesRegex(ValueError,'Original frame changed'):registration.run(casefile,roifile)
            self.assertEqual(image.read_bytes(),before)
