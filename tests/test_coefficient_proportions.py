import hashlib,importlib.util,json,math,unittest
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("refine",ROOT/"scripts/refine-morph-links.py");refine=importlib.util.module_from_spec(spec);spec.loader.exec_module(refine)


def rules(family):
 p=next(p for p in ET.parse(ROOT/"distribution/profiles/MorphLinks.xml").getroot().findall("Profile") if p.attrib["family"]==family)
 return [dict(r.attrib) for r in p.findall("Rule")]


def compose(family,sources):
 sums={};caps={}
 for r in rules(family):
  t=r['target'];sums[t]=sums.get(t,0)+sources.get(r['source'],0)*float(r['gain']);caps[t]=float(r['cap'])
 return {k:max(0,min(1,v))*caps[k] for k,v in sums.items()}


class ProportionsTests(unittest.TestCase):
 def test_reviewed_policy_requires_exact_baseline(self):
  source=b'<MorphLinkProfiles schemaVersion="1"><Profile family="HIMBO"><Rule source="A" target="CLAWTorsoGirth" gain="2" cap="1" /></Profile></MorphLinkProfiles>'
  policy={'schemaVersion':1,'baseSourceSha256':hashlib.sha256(source).hexdigest(),'families':{'HIMBO':{'targetMultipliers':{'CLAWTorsoGirth':.5},'addRules':[]}}}
  result=refine.refine(source,policy);self.assertEqual(result.find('Profile/Rule').attrib['gain'],'1.0')
  with self.assertRaises(ValueError):refine.refine(source+b' ',policy)

 def test_zero_remains_neutral_without_preset_or_actor_identity(self):
  for family in ['HIMBO','3BA','CBBE']:self.assertFalse(any(compose(family,{}).values()))

 def test_girth_quality_cap_preserves_subcap_slope_and_bounds_extremes(self):
  source=b'<MorphLinkProfiles schemaVersion="1"><Profile family="HIMBO"><Rule source="Bulk" target="CLAWTorsoGirth" gain="2" cap="1" /></Profile></MorphLinkProfiles>'
  policy={'schemaVersion':1,'baseSourceSha256':hashlib.sha256(source).hexdigest(),'families':{'HIMBO':{'targetMultipliers':{'CLAWTorsoGirth':.3},'targetCaps':{'CLAWTorsoGirth':.25},'addRules':[]}}}
  rule=refine.refine(source,policy).find('Profile/Rule').attrib
  output=lambda v:float(rule['cap'])*max(0,min(1,float(rule['gain'])*v))
  self.assertAlmostEqual(output(.1),.06)
  self.assertEqual(output(1),.25)
  for family in ['HIMBO','3BA','CBBE']:
   rr=rules(family);sample={r['source']:1e4 for r in rr if r['target']=='CLAWTorsoGirth' and float(r['gain'])>0}
   self.assertEqual(compose(family,sample)['CLAWTorsoGirth'],.25)

 def test_measured_male_roundness_preserves_more_range_than_live_saturation(self):
  actual={'BellyPot':.5,'BellyRounder':.2,'TorsoBelly':.6,'TorsoBellyChub':.35}
  value=compose('HIMBO',actual)['CLAWTorsoBellyRound'];self.assertAlmostEqual(value,.45503877,places=6)
  samples=[compose('HIMBO',{'BellyPot':v})['CLAWTorsoBellyRound'] for v in [-1,0,.1,.5,1]]
  self.assertEqual(samples,sorted(samples));self.assertEqual(samples[0],0);self.assertLess(samples[-1],1)

 def test_muscular_shoulders_and_human_chest_width_use_logical_sources(self):
  self.assertAlmostEqual(compose('HIMBO',{'TorsoShoulderInc':.2})['CLAWTorsoShoulderGirth'],.68191105)
  self.assertEqual(compose('3BA',{'ChestWidth':.9})['CLAWTorsoChestSize'],0)
  self.assertAlmostEqual(compose('3BA',{'ChestWidth':.9})['CLAWTorsoShoulderGirth'],.22995423)
  self.assertGreater(compose('HIMBO',{'TorsoWaistSize':.2})['CLAWTorsoWaistNarrow'],0)
  self.assertEqual(compose('HIMBO',{'TorsoWaistSize':-.4})['CLAWTorsoWaistNarrow'],0)

 def test_measured_muscle_bulk_counters_waist_shrink_across_independent_grid(self):
  # Independently serialized HIMBO _0 waist responses; the ratio was separately
  # confirmed equal at _1. These are source units, not six preset identities.
  for muscle in [0,.25,.5,.75,1]:
   for waist in [0,.25,.5,.75,1]:
    human_width=.02634494243768279*muscle-.021085090903294502*waist
    narrow=compose('HIMBO',{'Muscle':muscle,'TorsoWaistSize':waist})['CLAWTorsoWaistNarrow']
    if human_width>=0:self.assertEqual(narrow,0)
    else:self.assertGreater(narrow,0)
  self.assertEqual(compose('HIMBO',{'Muscle':.2,'TorsoWaistSize':.2})['CLAWTorsoWaistNarrow'],0)
  self.assertAlmostEqual(compose('HIMBO',{'TorsoWaistSize':.2})['CLAWTorsoWaistNarrow'],.76709574)

 def test_breast_coefficients_and_native_output_contract_are_preserved(self):
  self.assertAlmostEqual(compose('3BA',{'Breasts':.15})['CLAWTorsoBreastSize'],.53963454)
  for family in ['HIMBO','3BA','CBBE']:
   rr=rules(family);self.assertLessEqual(len(rr),128)
   self.assertTrue(all(0<float(r['cap'])<=1 and math.isfinite(float(r['gain'])) for r in rr))
   for seed in range(8):
    src={r['source']:((seed+i)%7-3)/3 for i,r in enumerate(rr)}
    self.assertTrue(all(0<=v<=1 for v in compose(family,src).values()))


if __name__=='__main__':unittest.main()
