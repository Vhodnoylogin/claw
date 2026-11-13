"""One exact reserved screenshot: prove copy, then delete that opened file only."""
from pathlib import Path
import ctypes,hashlib,json,os,stat
from ctypes import wintypes
from PIL import Image
import configparser

def require(value,message):
 if not value:raise ValueError(message)
def literal_basename(value,wanted):
 return type(value) is str and value.isascii() and value.casefold()==wanted.casefold()
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def original_eight(receipt):
 rows=json.loads(Path(receipt).read_text(encoding='utf-8-sig'))['rows']
 require(len(rows)==8,'Exactly eight protected originals required')
 require(all(sha(r['path'])==sha(r['backup'])==r['sha256'] for r in rows),'Protected original screenshot changed')
 return {'originals':8,'allEightHashesExact':True}
def identity(s):return {'device':s.st_dev,'inode':s.st_ino,'size':s.st_size,'mtimeNs':s.st_mtime_ns}

def reserved_absent(inventory,stems):
 wanted={s.casefold() for s in stems}
 require(not any(Path(p).stem.casefold() in wanted for p in inventory['files']),
         'Reserved screenshot basename already exists; never queue an overwrite')

def ini_index(data):
 parser=configparser.ConfigParser(interpolation=None,strict=True);parser.optionxform=str
 parser.read_string(data.decode('utf-8-sig'))
 return parser.getint('Display','iScreenShotIndex')

def reserve_ini(data,index,*,set_ini):
 # Explicit authoring callback; no dependency on an executor checkout.
 def parsed(value):
  p=configparser.ConfigParser(interpolation=None,strict=True);p.optionxform=str;p.read_string(value.decode('utf-8-sig'))
  return {s:dict(p[s]) for s in p.sections()}
 before=parsed(data);require('Display' in before,'Owned SkyrimPrefs Display section unavailable')
 wanted={s:dict(v) for s,v in before.items()};wanted['Display']['iScreenShotIndex']=str(index)
 # Match the executor's read_text universal-newline behavior, including this
 # actual closed template's CRCRLF headers, before its existing set_ini helper.
 text=data.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
 after=set_ini(text,'Display','iScreenShotIndex',str(index)).encode('utf8')
 require(parsed(after)==wanted and ini_index(after)==index,'Reserved index altered unrelated INI semantics')
 return after

def remove_verified_new_source(receipt,retained,inventory,expected_stem,game_path,custody_receipt,before_delete=None):
 source=Path(receipt['sourcePath']);root=Path(game_path).parent.resolve();retained=Path(retained)
 require(source.resolve().parent==root and literal_basename(source.stem,expected_stem) and
         source.suffix.casefold() in ('.png','.bmp','.jpg','.jpeg','.dds'), 'Unexpected reserved native source path')
 require(str(source.resolve()) not in inventory['files'],'Never remove a preexisting native source')
 require(not root.lstat().st_file_attributes & 0x400 and source.is_file() and
         not source.lstat().st_file_attributes & 0x400,'Native source containment/reparse guard')
 original_eight(custody_receipt)
 retained_hash=sha(retained)
 with Image.open(retained) as image:
  image.load();require(image.size==(1920,1080),'Retained original is incomplete/nonFHD')
 # Exclusive read+delete handle prevents replacement/write races. Deletion is
 # applied to this proved opened file, not a later object at the same pathname.
 kernel=ctypes.WinDLL('kernel32',use_last_error=True)
 create=kernel.CreateFileW;create.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE];create.restype=wintypes.HANDLE
 close=kernel.CloseHandle;close.argtypes=[wintypes.HANDLE];close.restype=wintypes.BOOL
 handle=create(str(source.resolve()),0x80000000|0x00010000,0,None,3,0x00200000,None)
 require(handle not in (None,ctypes.c_void_p(-1).value),'Could not exclusively open exact native source for custody')
 import msvcrt
 fd=None
 try:
  fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
  with os.fdopen(fd,'rb',closefd=True) as stream:
   fd=None;before=os.fstat(stream.fileno());require(stat.S_ISREG(before.st_mode),'Source is not a regular opened file')
   source_hash=hashlib.file_digest(stream,'sha256').hexdigest();after=os.fstat(stream.fileno())
   require(identity(before)==identity(after)==identity(source.stat()),'Native source identity changed during copy proof')
   require(source_hash==retained_hash and after.st_size==retained.stat().st_size,'Native/retained original bytes differ')
   original_eight(custody_receipt)
   if before_delete:before_delete({'sourcePath':str(source.resolve()),'expectedStem':expected_stem,
      'sha256':source_hash,'retainedPath':str(retained),'retainedByteCopyEqual':True,'openedIdentity':identity(after),
      'oldEightHashesExact':True})
   class Disposition(ctypes.Structure):_fields_=[('DeleteFile',wintypes.BOOL)]
   disposition=Disposition(True);set_info=kernel.SetFileInformationByHandle
   set_info.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD];set_info.restype=wintypes.BOOL
   require(bool(set_info(msvcrt.get_osfhandle(stream.fileno()),4,ctypes.byref(disposition),ctypes.sizeof(disposition))),
           'Exact opened source deletion was not acknowledged')
  require(not os.path.lexists(source),'Native source remains after its owned handle closed')
 finally:
  if fd is not None:os.close(fd)
  if handle not in (None,ctypes.c_void_p(-1).value):close(handle)
 original_eight(custody_receipt)
 return {'provedNewOwnedSource':True,'sourcePath':str(source.resolve()),'expectedStem':expected_stem,
         'retainedPath':str(retained),'sha256':source_hash,'retainedByteCopyEqual':True,
         'openedIdentityBefore':identity(before),'openedIdentityAfter':identity(after),
         'deleteSameOpenedFileAcknowledged':True,'sourceAbsentAfterClose':True,'oldEightHashesExactAfterCleanup':True,
         'sourceStemMatchedWindowsCasefold':True,
         'cleanupDuringCapture':False,'cleanupAfterNativeReceipt':True}
