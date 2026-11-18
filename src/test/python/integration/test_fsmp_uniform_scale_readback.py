"""Portable symbolic scale discrimination; never a scaled runtime positive."""
from pathlib import Path
import copy,sys,unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import fsmp_uniform_scale_readback as scale
import test_fsmp_joint_limit_readback as fixtures


def symbolic_scaled(s=1.1,world_lower=None):
    value=fixtures.symbolic_fixture()
    for raw in (value['worldA'],value['worldB']):
        raw['refs'][0]['scale']=s;raw['refs'][0]['sceneTransform']['scale']=s
        raw['refs'][0]['rootIdentity']['sampledRootToken']+=1
        for node in raw['nodes']:
            node['rootIdentity']['sampledRootToken']=raw['refs'][0]['rootIdentity']['sampledRootToken']
            node['world']['scale']=s;node['world']['translation']=[s*x for x in node['world']['translation']]
    for native in (value['witnessA'],value['witnessB'],value['finalWitness']):
        native['sample'].update(mainFreezeNextFrame=False,engineMultiplier=1,timerPauseCount=0)
        for obj in native['sample']['objectWindow']['objects']:
            for stage in scale.STAGES:
                obj[stage]['world'][9:]=[s*x for x in obj[stage]['world'][9:]]
                if obj[stage]['inverseMass']>0:obj[stage]['inverseMass']=20/s**3
            for key in ('minimumPostWorld','maximumPostWorld'):obj[key][9:]=[s*x for x in obj[key][9:]]
    if world_lower is not None:
        # Independent forward displacement corruption, preserving raw alignment.
        old=.05*s;delta=world_lower-old
        for raw in (value['worldA'],value['worldB']):
            next(n for n in raw['nodes'] if n['name']==scale.DRIVERS[0])['world']['translation'][0]+=delta
        base=fixtures.associate(fixtures.symbolic_fixture());token=base['A']['tokens'][scale.DRIVERS[0]]
        for native in (value['witnessA'],value['witnessB'],value['finalWitness']):
            obj=next(o for o in native['sample']['objectWindow']['objects'] if o['token']==token)
            for stage in scale.STAGES:obj[stage]['world'][9]+=delta
            for key in ('minimumPostWorld','maximumPostWorld'):obj[key][9]+=delta
    return value


def associated(value,getter=1.1):
    return scale.pair(value['worldA'],value['worldB'],value['witnessA'],value['witnessB'],
                      reference=fixtures.REFERENCE,base=fixtures.BASE,rest_local=value['restLocal'],getter_a=getter,getter_b=getter)


def score(value):return scale.score_case(associated(value),value['finalWitness'],value['restLocal'])


def parsed(raw):return scale.probe.snapshot(raw,fixtures.REFERENCE,'female')


class ScaleMath(unittest.TestCase):
    def test_symbolic_complete_scaled_mass_and_limit(self):
        value=symbolic_scaled();before=copy.deepcopy(value)
        with patch.object(scale.cached,'module_admission',side_effect=AssertionError('Historical module admission must not run')):
            result=score(value)
        self.assertEqual(value,before)
        row=result['completed900Coordinates']['lastPost'][scale.DRIVERS[0]]
        self.assertAlmostEqual(row['qWorld'][0],.055)
        self.assertAlmostEqual(row['qNominal'][0],.05)
        self.assertAlmostEqual(row['actualInverseMass'],20/1.1**3)
        self.assertEqual(row['observedWorldScale'],1.1)
    def test_unscaled_mass_and_unscaled_limit_refused(self):
        value=symbolic_scaled();token=associated(value)['A']['tokens'][scale.DRIVERS[0]]
        for native in (value['witnessA'],value['witnessB']):
            obj=next(o for o in native['sample']['objectWindow']['objects'] if o['token']==token)
            for stage in scale.STAGES:obj[stage]['inverseMass']=20.
        with self.assertRaisesRegex(ValueError,'inverse mass'):associated(value)
        with self.assertRaisesRegex(ValueError,'Scaled positive'):score(symbolic_scaled(world_lower=.05))
    def test_scaled_pivot_not_body_origin_only(self):
        rest=fixtures.transform((0.,1.,0.));a=fixtures.transform((100.,200.,300.));b=fixtures.transform((100.055,201.1,300.))
        self.assertAlmostEqual(scale.joint_world_frame(a,b,rest,1.1)['translation'][1],0.)
        self.assertAlmostEqual(scale.unit.joint_frame(a,b,rest)['translation'][1],.1)
    def test_observer_bridge_retains_raw_scale_and_uses_scaled_pivot(self):
        rest=fixtures.transform((0.,1.,0.));a=fixtures.transform((100.,200.,300.));b=fixtures.transform((100.055,201.1,300.))
        a['scale']=b['scale']=1.1;before=copy.deepcopy((a,b))
        frame=scale.observer_joint_world_frame(a,b,rest)
        self.assertEqual((a,b),before);self.assertEqual(frame['observedNiScale'],1.1)
        self.assertAlmostEqual(frame['translation'][0],.055);self.assertAlmostEqual(frame['translation'][1],0.)
    def test_getter_does_not_substitute_for_actual_world_scale(self):
        with self.assertRaisesRegex(ValueError,'independently observed'):
            scale.scale_context(parsed(fixtures.symbolic_fixture()['worldA']),1.1)
        with self.assertRaisesRegex(ValueError,'independently observed'):associated(symbolic_scaled(),getter=1.)
    def test_nonuniform_local_or_world_scale_refused(self):
        for space in ('local','world'):
            value=symbolic_scaled()
            next(n for n in value['worldB']['nodes'] if n['name']==scale.DRIVERS[0])[space]['scale']=1.05
            with self.subTest(space=space),self.assertRaises(ValueError):associated(value)
    def test_wrong_rest_pivot_alias_and_stale_pause_refused(self):
        value=symbolic_scaled();value['restLocal'][scale.DRIVERS[0]]['translation'][0]+=.05
        with self.assertRaisesRegex(ValueError,'pivot'):associated(value)
        value=symbolic_scaled();raw=value['worldB']
        next(n for n in raw['nodes'] if n['name']==scale.DRIVERS[1])['world']=copy.deepcopy(next(n for n in raw['nodes'] if n['name']==scale.DRIVERS[0])['world'])
        with self.assertRaises(ValueError):associated(value)
        value=symbolic_scaled();value['witnessB']['sample']['objectWindow']['lastPostQpc']+=1
        with self.assertRaisesRegex(ValueError,'pause'):associated(value)
    def test_unit_case_guards_stay_unit_only(self):
        value=symbolic_scaled()
        with self.assertRaisesRegex(ValueError,'unit actor'):
            scale.unit.pair(value['worldA'],value['worldB'],value['witnessA'],value['witnessB'],reference=fixtures.REFERENCE,base=fixtures.BASE,rest_local=value['restLocal'],expected_inverse_mass=dict.fromkeys(scale.DRIVERS,20.))
        value=fixtures.symbolic_fixture();scale.unit.score_limit(fixtures.associate(value))
    def test_same_completed_window_and_clock_required(self):
        for kind in ('nonce','pairs','clock'):
            value=symbolic_scaled();s=value['finalWitness']['sample']
            if kind=='nonce':s['objectWindow']['nonce']+=1
            elif kind=='pairs':s['objectWindow'].update(pairedSteps=899,status='collecting')
            else:s['engineMultiplier']=.5
            with self.subTest(kind=kind),self.assertRaises(ValueError):score(value)


class SetupTransition(unittest.TestCase):
    def context(self):
        initial=parsed(fixtures.symbolic_fixture()['worldA']);value=symbolic_scaled()
        value['worldA'].update(sampleId=2,producerMonotonicNs=1_300_000_000)
        value['worldB'].update(sampleId=3,producerMonotonicNs=1_600_000_000)
        return initial,parsed(value['worldA']),parsed(value['worldB'])
    def test_acknowledged_declared_scale_root_turnover_establishes_new_lease(self):
        initial,a,b=self.context();before=copy.deepcopy(initial)
        self.assertNotEqual(initial['guard']['root'],a['guard']['root'])
        lease=scale.establish_measurement(initial,a,1.1,b,1.1,acknowledged=True)
        self.assertEqual(lease['guard'],b['guard']);self.assertEqual(initial,before)
        self.assertEqual(lease['scaleContext']['roles'][scale.DRIVERS[0]]['world'],1.1)
    def test_unknown_ack_cannot_rebind(self):
        initial,a,b=self.context()
        with self.assertRaisesRegex(ValueError,'ACK'):scale.establish_measurement(initial,a,1.1,b,1.1,acknowledged=False)
    def test_foreign_base_world_or_incarnation_cannot_rebind(self):
        for field in ('actor','generation','identity'):
            initial,a,b=self.context()
            if field=='actor':b['guard'][field]['baseForm']='0x00000007'
            elif field=='identity':b['guard'][field]['runtimeHandle']+=1
            else:b['guard'][field]+=1
            with self.subTest(field=field),self.assertRaises(ValueError):scale.establish_measurement(initial,a,1.1,b,1.1,acknowledged=True)
    def test_measurement_requires_two_fresh_stable_root_samples(self):
        for kind in ('root','sample','time'):
            initial,a,b=self.context()
            if kind=='root':b['guard']['root']['sampledRootToken']+=1
            elif kind=='sample':b['sample']=a['sample']
            else:b['time']=a['time']
            with self.subTest(kind=kind),self.assertRaises(ValueError):scale.establish_measurement(initial,a,1.1,b,1.1,acknowledged=True)
    def test_intermediate_known_setup_is_pending_not_faked_ready(self):
        _,a,_=self.context();a['root']['scale']=1.
        self.assertFalse(scale.transition_context(a,1.1)['ready'])
        a['root']['scale']=1.2
        with self.assertRaises(ValueError):scale.transition_context(a,1.1)


if __name__=='__main__':unittest.main(verbosity=2)
