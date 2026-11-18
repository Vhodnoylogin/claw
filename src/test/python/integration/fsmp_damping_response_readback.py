"""Pure exploratory damping contrast; the first actual case FAILED its gates.
Extrema enclosures are not a trajectory or runtime qualification."""
import math,struct
if __package__:
    from . import fsmp_joint_limit_readback as joint
else:
    import fsmp_joint_limit_readback as joint

PARENTS, DRIVERS = joint.PARENTS, joint.DRIVERS
require = joint.require
EPS = .005
STEP = .1
MIN_POST_HELD_PAIRS = 240
DT_BAND = tuple(struct.unpack('<f',struct.pack('<f',v))[0] for v in (1/240,1/20))


def exact_f32_vector(actual,expected):
    if type(actual) is not list or len(actual)!=len(expected):return False
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in actual):return False
    try:return b''.join(struct.pack('<f',v) for v in actual)==b''.join(struct.pack('<f',v) for v in expected)
    except (OverflowError,struct.error):return False


def dot(a,b): return sum(x*y for x,y in zip(a,b))


def pivot(rest):
    r, t = rest['rotationRowMajor'], rest['translation']
    return [sum(r[j*3+i]*t[j] for j in range(3)) for i in range(3)]


def peak_bounds(record, anchor, rest, epsilon=EPS):
    """Enclose max_t [u·(pB-RB*R0^T*t0-pAheld)] over actual post-step samples.

    Independent component extrema need not occur together. For any component's
    maximizing extremum, the other components remain in their full ranges.
    That gives a lower bound on the maximum; full interval arithmetic gives an
    upper bound. No value is labelled the actual amplitude or time of a peak.
    """
    a = joint.pose_transform(anchor)
    u = [a['rotationRowMajor'][i*3] for i in range(3)]
    v = pivot(rest)
    coefficients = [-u[i]*v[j] for i in range(3) for j in range(3)] + u
    lo, hi = record['minimumPostWorld'], record['maximumPostWorld']
    require(len(lo)==len(hi)==12 and all(type(x) in (int,float) and math.isfinite(x) for x in lo+hi),
            'Finite actual WORLD extrema required')
    require(all(x<=y for x,y in zip(lo,hi)), 'Reversed WORLD extrema')
    terms = [(min(c*l,c*h),max(c*l,c*h)) for c,l,h in zip(coefficients,lo,hi)]
    low = -dot(u,a['translation']) + sum(t[0] for t in terms)
    high = -dot(u,a['translation']) + sum(t[1] for t in terms)
    return {'lower':low+max(b-a for a,b in terms)-epsilon,'upper':high+epsilon,
            'inflation':epsilon,'scope':'enclosure of max projection within this exact900-post-step window; not a co-temporal extrema pose/peak value/time'}


def baseline(associated, native):
    require(associated['expectedInverseMass']==dict.fromkeys(DRIVERS,20.), 'Original20/20 masses required')
    for mark in ('A','B'):
        for coords in associated[mark]['jointCoordinates'].values():
            require(all(abs(v)<=EPS for xyz in coords.values() for v in xyz), 'Unshifted quiet joint baseline required')
    w = native['sample']['objectWindow']
    require(w['status']=='collecting' and 20<w['pairedSteps']<300, 'Early collecting baseline window required')
    require(DT_BAND[0]<=w['lastTimeStep']<=DT_BAND[1], 'Observed baseline dt outside screening band')
    objects={o['token']:o for o in w['objects']}
    for driver in DRIVERS:
        o=objects[associated['A']['tokens'][driver]]
        require(max(b-a for a,b in zip(o['minimumPostWorld'][9:],o['maximumPostWorld'][9:]))<=EPS,
                'Initial driver envelope was not quiet')
    return {**associated,'responseBaselineValidated':True,'baselinePairedSteps':w['pairedSteps'],
            'baselineFirstPreQpc':w['firstPreQpc'],
            'baselineObservedDt':w['lastTimeStep'],
            'initialObjectPoses':{str(o['token']):o['initialPre'] for o in w['objects']}}


def held_inputs(associated, native, original_world, observed_world):
    sample=native['sample'];window=sample['objectWindow']
    joint.witness.validate_window(window,sample['loadEpoch'])
    require(native['pid']==associated['pid'] and sample['loadEpoch']==associated['loadEpoch']
            and window['nonce']==associated['nonce'] and window['status']=='collecting',
            'Same live input window required')
    require(not sample['mainFreezeTime'] and not sample['mainFreezeNextFrame'] and not sample['uiPaused']
            and sample['engineMultiplier']==1 and sample['timerPauseCount']==0, 'Normal input clock required')
    remaining=900-window['pairedSteps']
    require(remaining>=MIN_POST_HELD_PAIRS, 'Insufficient declared post-second-update pair headroom')
    require(DT_BAND[0]<=window['lastTimeStep']<=DT_BAND[1], 'Observed input dt outside declared screening band')
    original=joint.probe.snapshot(original_world,associated['reference'],'female')
    observed=joint.probe.snapshot(observed_world,associated['reference'],'female')
    require(original['guard']==observed['guard'], 'Input actor/root/world changed')
    objects={o['token']:o for o in window['objects']};result={}
    for parent in PARENTS:
        before=original['nodes'][parent]['world'];after=observed['nodes'][parent]['world']
        rel=joint.probe.relative(after,before)
        require(joint.probe.max_delta(rel['translation'],[STEP,0.,0.])<=.003
                and joint.probe.max_delta(rel['rotationRowMajor'],[1.,0.,0.,0.,1.,0.,0.,0.,1.])<=1e-5
                and abs(rel['scale']-1.)<=1e-5,'Actual pure held anchor step differs: '+parent)
        pose=objects[associated['A']['tokens'][parent]]['lastPost']
        require(joint.probe.max_delta(pose['world'][9:],after['translation'])<=.002
                and joint.probe.max_delta(pose['world'][:9],after['rotationRowMajor'])<=1e-5,
                'Native kinematic anchor has not independently reached its observed held step')
        result[parent]={'anchorPose':pose,'beforeWorld':before,'afterWorld':after,'actualStep':rel['translation'][0]}
    require(abs(result[PARENTS[0]]['actualStep']-result[PARENTS[1]]['actualStep'])<=.003,
            'Bilateral actual input amplitudes differ')
    return {'anchors':result,'pairedStepsAfterSecondKnownUpdate':window['pairedSteps'],
            'remainingPairedSteps':remaining,'observedInputDt':window['lastTimeStep'],
            'dtScope':'sampled dt/headroom only; not window-minimum dt or integrated simulation-time proof',
            'atomicInput':False}


def score(associated, inputs, final_native, rest):
    require(associated.get('responseBaselineValidated') is True,'Qualified quiet opening pair required')
    s=final_native['sample'];w=s['objectWindow']
    joint.witness.validate_window(w,s['loadEpoch'])
    require(final_native['status']=='ready' and final_native['pid']==associated['pid']
            and s['loadEpoch']==associated['loadEpoch'] and w['nonce']==associated['nonce']
            and w['status']=='complete' and w['pairedSteps']==900,'Same completed900 window required')
    require(w['firstPreQpc']==associated['baselineFirstPreQpc']
            and {str(o['token']):o['initialPre'] for o in w['objects']}==associated['initialObjectPoses'],
            'Final immutable window/catalogue preimage differs from opening')
    require(w['pairedSteps']-inputs['pairedStepsAfterSecondKnownUpdate']>=MIN_POST_HELD_PAIRS,
            'Actual recorded post-input pair floor absent')
    require(not s['mainFreezeTime'] and not s['mainFreezeNextFrame'] and not s['uiPaused']
            and s['engineMultiplier']==1 and s['timerPauseCount']==0,'Normal final clock required')
    require(DT_BAND[0]<=w['lastTimeStep']<=DT_BAND[1], 'Observed final dt outside screening band')
    objects={o['token']:o for o in w['objects']};bounds={}
    for parent,driver in zip(PARENTS,DRIVERS):
        a,b=objects[associated['A']['tokens'][parent]],objects[associated['A']['tokens'][driver]]
        for stage in joint.STAGES:
            require(a[stage]['inverseMass']==0 and a[stage]['flags']&3==2
                    and b[stage]['inverseMass']==20 and b[stage]['flags']&3==0,'Original mass/kinematic metadata changed')
        held=inputs['anchors'][parent]
        # Held endpoint and orientation must persist. Initial endpoint is intentionally different.
        for stage in ('lastPre','lastPost'):
            require(joint.probe.max_delta(a[stage]['world'][9:],held['anchorPose']['world'][9:])<=.002
                    and joint.probe.max_delta(a[stage]['world'][:9],held['anchorPose']['world'][:9])<=1e-5,
                    'Final held anchor drifted')
        for i in range(9):
            require(a['maximumPostWorld'][i]-a['minimumPostWorld'][i]<=1e-5,'Anchor rotated during response')
        # Every captured parent translation remains in the baseline-to-held segment box.
        initial=held['beforeWorld']['translation'];target=held['afterWorld']['translation']
        for i in range(3):
            require(a['minimumPostWorld'][9+i]>=min(initial[i],target[i])-.003
                    and a['maximumPostWorld'][9+i]<=max(initial[i],target[i])+.003,
                    'Anchor envelope exceeded its declared held-step input')
        bound=peak_bounds(b,held['anchorPose'],rest[driver]);d=held['actualStep']
        bound.update(step=d,lowerOverStep=bound['lower']/d,upperOverStep=bound['upper']/d)
        bounds[driver]=bound
    left,right=bounds[DRIVERS[0]],bounds[DRIVERS[1]]
    require(left['lowerOverStep']>=.5,'Reduced damping certified overshoot absent')
    require(right['lowerOverStep']>=-.1,'Unchanged right driver did not independently follow its input')
    require(right['upperOverStep']<=.4,'Unchanged right certified peak control exceeded')
    require(left['lowerOverStep']-right['upperOverStep']>=.2,'Independent bilateral peak-contrast margin absent')
    return {'status':'one-joint-damping-bounded-window-extrema-contrast-observed','bounds':bounds,
            'postSecondUpdatePairs':900-inputs['pairedStepsAfterSecondKnownUpdate'],
            'scope':'one edited joint damper functional WORLD response contrast; no direct coefficient getter/exact amplitude/peak time/curve/render/contacts/VR',
            'timeCoverageProven':False,'trajectoryRecovered':False,'atomicInput':False}
