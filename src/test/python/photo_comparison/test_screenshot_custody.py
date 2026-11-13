from pathlib import Path
import hashlib,json,tempfile,unittest,sys
from PIL import Image
import os
HERE=Path(__file__).resolve().parent
sys.path.insert(0,os.environ.get("CLAW_PHOTO_HELPER_ROOT",str(HERE)))
import screenshot_custody as subject
from test_support import temporary

class ScreenshotTests(unittest.TestCase):
 def test_only_ascii_case_variants_of_literal_prefix_match(self):
  self.assertTrue(subject.literal_basename('Screenshot','ScreenShot'))
  self.assertTrue(subject.literal_basename('SCREENSHOT','ScreenShot'))
  for value in ('Other','ScreenShotMore','../ScreenShot','ScreenShot/','C:\\ScreenShot',' ScreenShot','ScreenShot\0','Screenſhot'):
   self.assertFalse(subject.literal_basename(value,'ScreenShot'),value)
 @unittest.skipUnless(os.name=="nt","Same-opened-file deletion contract requires Windows")
 def test_actual_case_equivalent_new_basename_has_same_guarded_cleanup_receipt(self):
  with temporary() as folder:
   root,game,receipt,inventory,retained,source=self.fixture(folder)
   result=subject.remove_verified_new_source({'sourcePath':str(source)},retained,inventory,'ScreenShot136130600',game,receipt)
   self.assertTrue(result['sourceStemMatchedWindowsCasefold']);self.assertEqual(result['expectedStem'],'ScreenShot136130600')
   self.assertFalse(source.exists());self.assertTrue(subject.original_eight(receipt)['allEightHashesExact'])
 def test_injected_ini_author_changes_only_declared_setting(self):
  data=b'[Display]\r\r\niScreenShotIndex=42\r\nfDefaultWorldFOV=75\r\n[Other]\r\nx=1\r\n'
  def write(text,section,key,value):return text.replace('iScreenShotIndex=42','iScreenShotIndex='+value)
  after=subject.reserve_ini(data,136130600,set_ini=write)
  self.assertEqual(subject.ini_index(after),136130600);self.assertIn(b'x=1',after)
  def bad(text,section,key,value):return write(text,section,key,value).replace('x=1','x=2')
  with self.assertRaisesRegex(ValueError,'unrelated INI'):subject.reserve_ini(data,136130600,set_ini=bad)
 def fixture(self,folder):
  root=Path(folder);game=root/'OwnedGame.exe';rows=[]
  for i in range(8):
   p=root/('ScreenShot'+str(i)+'.png');b=root/('old-backup'+str(i));p.write_bytes(b'old-'+bytes([i]));b.write_bytes(p.read_bytes())
   rows.append({'path':str(p),'backup':str(b),'sha256':subject.sha(p)})
  receipt=root/'custody.json';receipt.write_text(json.dumps({'rows':rows}))
  inventory={'files':[r['path'] for r in rows]}
  retained=root/'retained.png';Image.new('RGB',(1920,1080),(22,33,44)).save(retained)
  source=root/'Screenshot136130600.png';source.write_bytes(retained.read_bytes())
  return root,game,receipt,inventory,retained,source
 @unittest.skipUnless(os.name=="nt","Same-opened-file deletion contract requires Windows")
 def test_new_exact_copy_deleted_by_its_opened_file_only_after_durable_proof_callback(self):
  with temporary() as folder:
   root,game,receipt,inventory,retained,source=self.fixture(folder);proofs=[]
   result=subject.remove_verified_new_source({'sourcePath':str(source)},retained,inventory,source.stem,game,receipt,lambda p:proofs.append(p))
   self.assertEqual(len(proofs),1);self.assertEqual(proofs[0]['sha256'],subject.sha(retained))
   self.assertTrue(result['sourceAbsentAfterClose']);self.assertFalse(source.exists());self.assertTrue(retained.exists())
   self.assertTrue(subject.original_eight(receipt)['allEightHashesExact'])
 @unittest.skipUnless(os.name=="nt","Same-opened-file deletion contract requires Windows")
 def test_preexisting_or_wrong_basename_is_never_deleted(self):
  with temporary() as folder:
   root,game,receipt,inventory,retained,source=self.fixture(folder)
   for seen,stem in ((inventory, 'ScreenShot0'),({'files':inventory['files']+[str(source)]},source.stem)):
    with self.assertRaises(ValueError):subject.remove_verified_new_source({'sourcePath':str(source)},retained,seen,stem,game,receipt)
    self.assertTrue(source.exists())
 def test_reserved_preexisting_basename_refuses_before_capture_can_be_queued(self):
  with self.assertRaisesRegex(ValueError,'never queue'):
   subject.reserved_absent({'files':['D:/owned/screenshot136130600.PNG']},['ScreenShot136130600'])
 @unittest.skipUnless(os.name=="nt","Same-opened-file deletion contract requires Windows")
 def test_mismatched_copy_or_changed_old_original_refuses_deletion(self):
  with temporary() as folder:
   root,game,receipt,inventory,retained,source=self.fixture(folder)
   source.write_bytes(b'not the retained image')
   with self.assertRaises(ValueError):subject.remove_verified_new_source({'sourcePath':str(source)},retained,inventory,source.stem,game,receipt)
   self.assertTrue(source.exists());source.write_bytes(retained.read_bytes());(root/'ScreenShot0.png').write_bytes(b'changed old')
   with self.assertRaisesRegex(ValueError,'Protected original'):subject.remove_verified_new_source({'sourcePath':str(source)},retained,inventory,source.stem,game,receipt)
   self.assertTrue(source.exists())

if __name__=='__main__':unittest.main()
