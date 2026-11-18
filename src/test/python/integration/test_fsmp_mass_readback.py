"""Optional explicit archived-game regression; no synthetic positive evidence.

Set CLAW_FSMP_MASS_READBACK_EVIDENCE to the archived paused-mass-writeback.json.
Set CLAW_FSMP_MASS_READBACK_REQUIRED=1 when this input is mandatory for the run.
An unset optional input skips visibly; an explicitly selected missing/changed input fails.
Negative tests deliberately corrupt copies of that actual evidence, never invent passes.
"""
from pathlib import Path
import copy,hashlib,json,os,sys,unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import fsmp_mass_readback as mass

ARCHIVED_EVIDENCE_SHA256 = '22cde932829d345636c93c57073e20728e20b2972a27ecf5f345fab5fe057c25'
EXPECTED = {"NPC L Breast P1":10., "NPC R Breast P1":20.}

class ExplicitActualMassReadback(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        selected=os.environ.get("CLAW_FSMP_MASS_READBACK_EVIDENCE")
        if not selected:
            if os.environ.get("CLAW_FSMP_MASS_READBACK_REQUIRED")=="1":
                raise AssertionError("Required actual mass evidence missing: set CLAW_FSMP_MASS_READBACK_EVIDENCE")
            raise unittest.SkipTest("Optional actual-game mass proof not selected; set CLAW_FSMP_MASS_READBACK_EVIDENCE (and REQUIRED=1 to enforce it)")
        cls.path=Path(selected).expanduser().resolve(strict=True)
        payload=cls.path.read_bytes()
        if hashlib.sha256(payload).hexdigest()!=ARCHIVED_EVIDENCE_SHA256:
            raise AssertionError("Explicit actual archived proof hash differs; new evidence requires its own reviewed contract")
        cls.actual=json.loads(payload)
        if not {"worldA","worldB","witnessA","witnessB","matches"}<=set(cls.actual):
            raise AssertionError("Complete actual paused pair required")
        cls.reference=cls.actual["worldA"]["refs"][0]["identity"]["form"]
        cls.base="0x0D000801"
    def check_pair(self,value=None,**kwargs):
        v=self.actual if value is None else value
        return mass.pair(v["worldA"],v["worldB"],v["witnessA"],v["witnessB"],
                         reference=self.reference,base=kwargs.get("base",self.base),expected_inverse_mass=EXPECTED)
    def test_actual_archived_positive_pair_replays_exactly(self):
        result=self.check_pair()
        self.assertEqual(result,self.actual["matches"])
        self.assertEqual(result["status"],"two-paused-unit-scale-p1-mass-readbacks-matched")
        for side in ("A","B"):
            self.assertEqual(len(result[side]["mapping"]["dynamicBodies"]),11)
            for name,value in EXPECTED.items():
                self.assertEqual(set(result[side]["p1"][name]["observedInverseMass"].values()),{value})
        self.assertFalse(result["normalMotionQualified"])
        self.assertFalse(result["renderStrainQualified"])
        self.assertFalse(result["contactQualified"])
        self.assertFalse(result["amplitudeRatioInferred"])
    def test_wrong_declared_base_rejects_actual_evidence(self):
        with self.assertRaises(ValueError):self.check_pair(base="0x0D000803")
    def test_old_mass_values_cannot_pass_new_parameter_case(self):
        value=copy.deepcopy(self.actual)
        for side in ("A","B"):
            token=value["matches"][side]["p1"]["NPC L Breast P1"]["token"]
            for obj in value["witness"+side]["sample"]["objectWindow"]["objects"]:
                if obj["token"]==token:
                    for key in ("initialPre","lastPre","lastPost"):obj[key]["inverseMass"]=20.
        with self.assertRaises(ValueError):self.check_pair(value)
    def test_missing_or_duplicate_body_cannot_be_invented(self):
        for action in ("missing","duplicate"):
            value=copy.deepcopy(self.actual);window=value["witnessB"]["sample"]["objectWindow"]
            if action=="missing":window["objects"].pop();window["objectCount"]-=1
            else:window["objects"][1]["token"]=window["objects"][0]["token"]
            with self.subTest(action=action),self.assertRaises(ValueError):self.check_pair(value)
    def test_one_dynamic_body_cannot_satisfy_two_bone_roles(self):
        value=copy.deepcopy(self.actual)
        for world in (value["worldA"],value["worldB"]):
            left=next(n for n in world["nodes"] if n["name"]=="NPC L Breast P1")
            right=next(n for n in world["nodes"] if n["name"]=="NPC R Breast P1")
            right["world"]=copy.deepcopy(left["world"])
        with self.assertRaises(ValueError):self.check_pair(value)
    def test_all_unit_scale_channels_are_required(self):
        for kind in ("actor","root","local","world"):
            value=copy.deepcopy(self.actual);world=value["worldB"]
            if kind=="actor":world["refs"][0]["scale"]=1.01
            elif kind=="root":world["refs"][0]["sceneTransform"]["scale"]=1.01
            else:world["nodes"][0][kind]["scale"]=1.01
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.check_pair(value)
    def test_changed_root_or_replayed_observation_rejects(self):
        for kind in ("root","sample","time"):
            value=copy.deepcopy(self.actual)
            if kind=="root":value["worldB"]["refs"][0]["rootIdentity"]["sampledRootToken"]+=1
            elif kind=="sample":value["worldB"]["sampleId"]=value["worldA"]["sampleId"]
            else:value["worldB"]["producerMonotonicNs"]=value["worldA"]["producerMonotonicNs"]
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.check_pair(value)
    def test_different_native_process_or_cache_rejects(self):
        for kind in ("pid","cache"):
            value=copy.deepcopy(self.actual)
            if kind=="pid":value["witnessB"]["pid"]+=1
            else:value["witnessB"]["sample"]["objectWindow"]["pairedSteps"]+=1
            with self.subTest(kind=kind),self.assertRaises(ValueError):self.check_pair(value)

if __name__=="__main__":unittest.main()
