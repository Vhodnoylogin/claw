"""One owned stock left-ear CBPC comparison. Uses no saved or shared player."""
import json
from math import dist
import time

import numpy as np
from cbpc_event_readback import Audience, score_player
from cbpc_vr_geometry import _sphere
from pose_contact_driver import (CalibratedWand, MovementLimits, PROBE_METRES, acknowledges,
                                 moved_frame, newer, public_frame, same_room, tracking_xyz)
from stock_ear_fit import NODE, SCHEMA, SLOT, fit_stock_ear
from verify_pose_contact_window import hold_ticks
from verify_tail_refit import DRIFT, MARGIN, MIN_HOLD, QPC, Subject, bank_gap, inspect_frame, require


EVENTS = 'CLAWVRPlayerCBPCEvents'
EAR = 'CLAWVRStockEarContactPose'
CBPC = 'CBPCPluginScript'
CBPC_SCHEMA = 'claw-vr-cbpc-stock-split-ear-events/1'
NONCE = 24112431
ENTRY = 0x434C0000 + SLOT


class StockEarWand(CalibratedWand):
    """Measure contact on the player's own ears with neutral, virtual controls."""
    def reachable(self, points, frame):
        require(same_room(self.reference, frame), 'The admitted controller room basis changed')
        xyz = self.tracking(points)
        return (np.isfinite(xyz).all(axis=1)
                & (np.linalg.norm(xyz - self.reference_xyz, axis=1) <= self.limits.travel)
                & (xyz[:, 1] >= self.limits.minimum_height))


def run(session, invoke, handle, *, fitted_model, deadline):
    pid = session.state['game']['pid']
    subject = Subject(pid, 0x14, 7, 0x0A01A5C6, 0)
    folder = session.dir / 'stock-ear-contact'
    folder.mkdir()
    record = {}
    sample_serial = 0

    def save():
        (folder / 'summary.json').write_text(json.dumps(record, indent=2, allow_nan=False)+'\n', encoding='utf-8')

    def pap(name, function, args, kind):
        return invoke(name, function, args, kind)

    def read_pose(nonce):
        request = json.loads(pap(EAR, 'Capture', [nonce], 'string'))
        require((request['schema'], request['pid'], request['nonce']) == (SCHEMA, pid, nonce),
                'Pose request belongs to a different game')
        reply = request
        for _ in range(18):
            if reply['status'] != 'pending':
                break
            time.sleep(.12)
            reply = json.loads(pap(EAR, 'Read', [nonce], 'string'))
        (folder / f'pose-{nonce}.json').write_text(json.dumps({'request':request, 'reply':reply}, indent=2)+'\n',
                                                  encoding='utf-8')
        require(reply['status'] == 'ready', 'Ear pose refused: ' + str(reply.get('reason')))
        require(reply['epoch'] == request['worldGate']['generation'] and reply['sample']['phaseSequence'] > request['worldGate']['armedAfterPhase'],
                'Expected a fresh same-world post-VRIK/HIGGS ear pose')
        return reply

    def tool(name, args, end):
        now = time.monotonic()
        require(now + .1 < end and end <= deadline, 'Original contact tool deadline expired')
        return session.tool(name, args, timeout=min(3., end-now), deadline=end)

    def observe(end):
        nonlocal sample_serial
        form = subject.form['form']
        args = {'kind':'world_observer', 'action':'snapshot', 'timeoutMs':1200, 'refs':[form],
                'nodes':[{'ref':form, 'name':name, 'firstPerson':False} for name in (NODE, 'NPC Root [Root]')],
                'actorState':True}
        raw = tool('inspect', args, end)
        sample_serial += 1
        (folder / f'frame-{sample_serial:03}.json').write_text(json.dumps(raw, indent=2)+'\n', encoding='utf-8')
        frame = inspect_frame([{'tool':'inspect','args':args,'result':raw}], 0, subject, NODE, own_body=True)
        require(frame['player'][0]['runtimeHandle'] == handle, 'Player handle changed during hand measurement')
        frame['durationUs'] = raw['durationUs']
        return frame

    def publication(frame, old, end, driver):
        require(session.state['inputBackend']=='driver' and session.state['driverBackend']=='file'
                and session.state.get('focusInputPaused') is not True
                and session.state['hardwareFrame']['_publication']['command']==old['command'],
                'Contact driver or previous frame left case custody')
        result = tool('driver', {'action':'publish','frame':frame,'holdSeconds':7.}, end)
        current = result['publication']
        require(result['published'] is True and current['owner']==session.state['hardwareOwner'] and current['version']==2
                and current['sequence']>old['sequence'] and current['command']!=old['command'],
                'Missing owned controller publication')
        for _ in range(5):
            status = tool('driver', {'action':'status'}, end)
            if acknowledges(status, current, driver):
                require(public_frame(session.state['hardwareFrame'])==frame, 'Confirmed frame changed')
                return current
            time.sleep(.07)
        raise ValueError('Missing owned controller acknowledgement')

    # Qualify the solver producer and take the first native posed-skin sample
    # before altering the test actor's environment or publishing hand movement.
    first = read_pose(NONCE)
    save()
    idle = json.loads(pap(EVENTS, 'GetCaptureState', [], 'string'))
    require(idle == {'status':'idle','schema':CBPC_SCHEMA,'pid':pid,'generation':idle['generation'],
                     'sinkRegistered':True,'loading':False}, 'The stock ear event witness is not ready')
    model = fitted_model
    require(first['sample']['rawWeight'] == 75., 'Unexpected stock male transformation weight')
    fitted = fit_stock_ear(model, first, pid=pid, nonce=NONCE, handle=handle)
    record['initialFit'] = fitted
    save()

    snap = session.state['hardwareFrame']
    frame0, expected = public_frame(snap), snap['_publication']
    status = tool('driver', {'action':'status'}, deadline)
    driver = status['driverInstance']

    require(all(frame0[side]['controller']['pressed']==0 and frame0[side]['controller']['touched']==0
                and frame0[side]['controller']['axes']==[[0.,0.]]*5 for side in ('left','right')),
            'The virtual controllers must have neutral buttons')
    if not acknowledges(status, expected, driver):
        require(status.get('expired') is True, 'Original hardware frame lacks a current ACK')
        expected = publication(frame0, expected, deadline, driver)
    p0 = tracking_xyz(frame0)
    reference = observe(deadline)
    prior = reference
    probes = []
    for axis in range(3):
        change = moved_frame(frame0, p0 + PROBE_METRES * np.eye(3)[axis])
        expected = publication(change, expected, deadline, driver)
        for _ in range(5):
            moved = observe(deadline)
            require(newer(prior,moved) and same_room(reference,moved), 'The reference room or actor changed')
            prior = moved
            if dist(moved['source'],reference['source']) > .8:
                break
            time.sleep(.10)
        else:
            raise ValueError('The commanded calibration displacement did not arrive')
        expected = publication(frame0, expected, deadline, driver)
        for _ in range(5):
            returned = observe(deadline)
            require(newer(prior,returned) and same_room(reference,returned), 'The reference room or actor changed')
            prior = returned
            if dist(returned['source'],reference['source']) <= DRIFT:
                break
            time.sleep(.10)
        else:
            raise ValueError('The hand did not return to its calibration point')
        probes.append((change,moved,returned))

    wand = StockEarWand(session.tool, session.state, observe, frame0, reference, probes, driver, MovementLimits(.95,.7))
    observed = read_pose(NONCE+1)
    fitted = fit_stock_ear(model, observed, pid=pid, nonce=NONCE+1, handle=handle)
    bank = (fitted['geometry'],)
    reference = observe(deadline)
    target_pose = reference['targetPose']
    capsule = fitted['geometry']
    center, _ = _sphere(target_pose, [(capsule[i]+capsule[3+i])*.5 for i in range(3)], 1.)
    record.update(fitted=fitted, trackingColumns=wand.columns.tolist(),
                  neutralGap=bank_gap(reference,bank), nearPoint=center)
    save()
    require(record['neutralGap'] >= MARGIN, 'The neutral hand is already too close to the fitted ear')

    generation = idle['generation']
    keys = [NONCE, generation]
    attached = False
    window = {}

    def event_state():
        return json.loads(pap(EVENTS, 'GetCaptureState', [], 'string'))

    def wait_state(desired, allowed):
        for _ in range(10):
            current = event_state()
            require(current == {**idle, 'status':current['status']} and current['status'] in (desired, *allowed),
                    'The event witness changed scope or refused the trial')
            if current['status'] == desired:
                return
            time.sleep(.075)
        raise ValueError('The event witness did not reach ' + desired)

    def detach():
        pap(CBPC, 'DetachCollider', [subject.form, NODE, 1, ENTRY, True], 'none')

    def hold(label, near, end):
        before = wand.confirm(end)
        frames = []
        gaps = []
        for _ in range(11):
            frame = observe(end)
            require(same_room(reference,frame) and dist(frame['source'],wand.world(wand.xyz)) <= DRIFT,
                    'A hold escaped the confirmed controller or actor pose')
            gap = bank_gap(frame,bank)
            require(gap <= -MARGIN if near else gap >= MARGIN, 'The measured hand missed the ' + label + ' margin')
            frames.append(frame)
            gaps.append(gap)
            if len(frames)>=6 and frame['ns'] - frames[0]['ns'] >= 1_750_000_000:
                break
            time.sleep(.19)
        after = wand.confirm(end)
        require(before['command']==after['command'] and before['driverInstance']==after['driverInstance'],
                'Controller command changed inside a measured hold')
        start, end_qpc, _ = hold_ticks(frames,[f['durationUs'] for f in frames])
        window[label] = (start,end_qpc)
        record.setdefault('holds',{})[label] = {'qpc':window[label], 'gaps':gaps, 'ackBefore':before, 'ackAfter':after}
        save()

    # Refit once with the hand at the proposed near point, then keep pose
    # inputs and the physical anchor stable throughout the measured contrast.
    wand('near', center, deadline=deadline-14.)
    near_fit = read_pose(NONCE+2)
    fit_check = fit_stock_ear(model, near_fit, pid=pid, nonce=NONCE+2, handle=handle)
    require(fit_check['morphs']==fitted['morphs'] and max(abs(a-b) for a,b in zip(fit_check['geometry'],capsule)) <= .1,
            'The hand approach changed the fitted ear shape')
    end = min(deadline-12.,time.monotonic()+51.)
    require(end-time.monotonic()>=32., 'Insufficient independent time for the callback contrast')
    try:
        require(pap(EVENTS, 'Arm', keys+[subject.actor,subject.cell], 'bool') is True,
                'Unable to arm the stock ear callback witness')
        wait_state('armed',('pending',))
        hold('unattachedNear',True,end)
        record['pendingNative'] = 'AttachColliderCapsule'
        save()
        pap(CBPC, 'AttachColliderCapsule', [subject.form,NODE,list(capsule[:3]),capsule[6],
                                            list(capsule[3:6]),capsule[6],0.,ENTRY,True], 'none')
        attached = True
        record['pendingNative'] = None
        hold('nearBefore',True,end)
        wand('far',None,deadline=end)
        hold('far',False,end)
        wand('near',center,deadline=end)
        hold('nearAfter',True,end)
        record['pendingNative'] = 'DetachCollider'
        save()
        detach()
        attached = False
        record['pendingNative'] = None
        hold('nearDetached',True,end)
        require(pap(EVENTS, 'Seal', keys, 'bool') is True, 'Unable to seal the owned callback witness')
        wait_state('sealed',('armed',))
        events = json.loads(pap(EVENTS,'Read',keys,'string'))
        (folder/'events.json').write_text(json.dumps(events,indent=2)+'\n',encoding='utf-8')
        require(events['qpcFrequency']==QPC, 'Unexpected native callback clock')
        audience = Audience(pid,NONCE,generation,subject.actor,subject.base,subject.cell,'Male',NODE)
        record['outcome'] = score_player(events,idle,audience,window,body32=(0xCDD86,0xCDD87),
                                         runtime_handle=handle,minimum_hold_ticks=MIN_HOLD,stock_split_ear=True)
        save()
        require(record['outcome']['status']=='qualified-emission-contrast','No qualified VR left-ear contact contrast')
    finally:
        if attached and record['pendingNative'] is None:
            record['pendingNative'] = 'DetachCollider'
            save()
            detach()
            record['pendingNative'] = None
        if not wand.pending:
            wand.restore(deadline=deadline)
            record['restoredTracking'] = True
            save()
