"""Collect CLAW pose-contact receipts through an already admitted VR executor."""

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import time

from posed_contact import world_matrix
from prepare_pose_ack_contact import contrast, project
from run_tail_refit import IndexedCapture, signed_bits
from verify_pose_ack import selected_receipts, verify as verify_ack
from verify_pose_contact_window import CLOCK, CONTROL, cap_values, hold_ticks, verify
from verify_tail_refit import (
    EVENTS, MARGIN, MAX_GAP_NS, MIN_HOLD, NANO, NATIVE, POSE, QPC,
    bank_gap, inspect_frame, positive_int, require,
)


class PoseContactCapture(IndexedCapture):
    """Use the owner's existing driver and ledger; issue no process or profile operations."""

    def __init__(self, call, ledger_path, ack_log, subject, profile_path, position, *, deadline, clock=time):
        super().__init__(call, ledger_path, deadline=deadline, clock=clock)
        self.log = Path(ack_log)
        self.profile_bytes = Path(profile_path).read_bytes()
        self.profile = json.loads(self.profile_bytes)
        self.subject, self.position = subject, position
        self.sequence = 0
        self.owner = None

    def poll(self, read, done, pending, seconds):
        until = min(self.deadline, self.clock.monotonic() + seconds)
        while self.clock.monotonic() < until:
            result = read()
            if done(result):
                return result
            require(pending(result), "A scoped readback was refused or changed identity")
            self.clock.sleep(max(0., min(.12, until - self.clock.monotonic())))
        raise ValueError("The admitted witness did not become ready before its deadline")

    def observe(self):
        actor = self.subject.form["form"]
        packet = {"kind": "world_observer", "action": "snapshot", "refs": ["0x00000014", actor], "timeoutMs": 1500,
                  "nodes": [{"ref": actor, "name": node, "firstPerson": False} for node in (self.node, "NPC Root [Root]")]}
        index, raw = self.record("inspect", packet)
        frame = inspect_frame([{"tool": "inspect", "args": packet, "result": raw}], 0, self.subject, self.node)
        scope = (frame["session"], frame["epoch"], frame["actor"][0]["runtimeHandle"])
        require(self.owner is None or self.owner == scope, "The World Observer actor incarnation changed")
        self.owner = scope
        return index, frame, raw.get("durationUs")

    def hold(self, *, near=None, old=None, new=None):
        frames, durations, indices = [], [], []
        for _ in range(8):
            index, frame, duration = self.observe()
            require(type(duration) is int and 0 <= duration <= MAX_GAP_NS // 1000,
                    "Observer did not return a bounded task duration")
            require(not frames or 0 < frame["ns"] - frames[-1]["ns"] <= MAX_GAP_NS, "Unstable Observer cadence")
            if new is not None:
                new_gap = bank_gap(frame, new)
                require(new_gap <= -MARGIN if near else new_gap >= MARGIN,
                        "The measured hand missed the requested updated-bank margin")
            if old is not None:
                require(bank_gap(frame, old) >= MARGIN, "The measured hand intersects the previous bank")
            frames.append(frame)
            durations.append(duration)
            indices.append(index)
            first_complete = frames[0]["ns"] + (durations[0] + 1) * 1000
            if (frames[-1]["ns"] - first_complete) * QPC >= (MIN_HOLD + 2) * NANO:
                hold_ticks(frames, durations)
                return indices
            self.clock.sleep(.42)
        raise ValueError("The independently observed hand hold was too short")

    def move(self, phase, waypoint):
        require(self.waiting_on is None and self.clock.monotonic() < self.deadline, "Controller window is unavailable")
        self.waiting_on = "controller:" + phase
        require(self.position(phase, waypoint, deadline=self.deadline) is True, "Controller move was not confirmed")
        self.waiting_on = None

    def ack_lines(self):
        raw = self.log.read_bytes()
        complete = raw if raw.endswith(b"\n") else raw[:raw.rfind(b"\n") + 1]
        return complete.decode("utf-8-sig").splitlines()

    def current(self, token):
        return self.pap(NATIVE, "SnapshotCurrent", [self.subject.form, self.subject.generation, token], "bool")

    def choose_delta(self):
        previous_scan = 0
        until = min(self.deadline, self.clock.monotonic() + 12.)
        while self.clock.monotonic() < until:
            lines = self.ack_lines()
            rows = selected_receipts(lines, self.subject.actor, self.subject.generation)
            if len(rows) > 1 and rows[-1][0] != previous_scan:
                token, _, receipt, _ = rows[-1]
                previous_scan = token
                prior, bank = {}, {}
                for current, _, _, group in rows:
                    if current == token:
                        prior = bank.copy()
                    bank.update(group)
                slots = [slot for slot, (name, _) in bank.items() if name == self.node]
                if (receipt["application"] == "delta" and receipt["previousToken"] == rows[-2][0] and
                        set(slots).intersection(receipt["changedSlots"]) and self.current(token)[1] is True):
                    verify_ack(lines, actor=self.subject.actor, generation=self.subject.generation, profile=self.profile,
                               expected_tokens=(token,), require_delta=True)
                    _, frame, _ = self.observe()
                    old = [prior[slot][1] for slot in slots]
                    new = [bank[slot][1] for slot in slots]
                    transform = world_matrix(frame["targetPose"])[:3]
                    radius = 3. * frame["left"]["scale"]
                    candidate = contrast(project(old, transform, radius), project(new, transform, radius), MARGIN)
                    if candidate["meetsRequestedMargin"] and self.current(token)[1] is True:
                        # The projector used the observed absolute owner transform.
                        return token, candidate["sphereCenterRootRelativeGu"], cap_values(old), cap_values(new)
            self.clock.sleep(.12)
        raise ValueError("Natural idle yielded no current pose delta with a measured controller contrast")

    def read_pose(self, expected):
        return self.poll(lambda: self.json_pap(POSE, "ReadNpc", [self.nonce, self.sequence]),
                         lambda pair: pair[1].get("status") == expected,
                         lambda pair: pair[1].get("status") in ("pending", "retiring"), 1.6)[0]

    def sample(self):
        self.sequence += 1
        self.write(POSE, "SampleNpc", [self.nonce, self.sequence], "string")
        return self.read_pose("ready")

    def control(self, name, args, expected):
        index, actual = self.write(CONTROL, name, args, "bool" if type(expected) is bool else "int")
        require(type(actual) is type(expected) and actual == expected, f"Scoped host operation refused: {name}")
        return index

    def run(self, node, nonce, evidence):
        subject = self.subject
        require(node in {"TailBone02", "NPC EarL [EarL]Bone01"} and positive_int(nonce) and nonce < 0x80000000 and
                0xFF000000 <= subject.actor < 0xFFFFFFFF and subject.base & 0xFFFFFF == 0x800 and
                all(positive_int(value) for value in (subject.pid, subject.base, subject.cell)) and
                type(evidence) is str and 0 < len(evidence) <= 1024, "An admitted fixture and provider scope are required")
        self.node, self.nonce = node, nonce
        model_read, model = self.pap(NATIVE, "GetModelIdentity", [], "string")
        require(model == self.profile["modelIdentity"], "Loaded Distribution uses a different model")
        capture, holds = {}, {}
        capture["idle"], idle = self.json_pap(EVENTS, "GetCaptureState", [])
        generation = idle.get("generation")
        identity = {"schema": "claw-vr-cbpc-events/1", "pid": subject.pid, "generation": generation,
                    "sinkRegistered": True, "loading": False}
        require(positive_int(generation) and idle == {**identity, "status": "idle"}, "CBPC witness is unavailable")
        capture["arm"], _ = self.write(EVENTS, "Arm", [nonce, generation, signed_bits(subject.actor), signed_bits(subject.cell)])
        self.poll(lambda: self.json_pap(EVENTS, "GetCaptureState", []),
                  lambda pair: pair[1] == {**identity, "status": "armed"},
                  lambda pair: pair[1] in ({**identity, "status": "idle"}, {**identity, "status": "pending"}), 2.)
        self.move("far", None)
        holds["unattachedFar"] = {"frames": self.hold()}

        self.control("BeginSession", [True, evidence], True)
        self.control("RegisterActor", [0, subject.form], 0)
        _, slot_generation = self.pap(CONTROL, "GetGeneration", [0], "int")
        require(positive_int(slot_generation), "The host did not assign a generation to the owned actor")
        self.subject = replace(subject, generation=slot_generation)
        require(not selected_receipts(self.ack_lines(), subject.actor, slot_generation),
                "The new host generation already has pose ACK evidence")
        self.control("EnableAutomaticActor", [0, subject.form, evidence, True, True, True], 0)
        token, world_near, old, new = self.choose_delta()
        count_index, count = self.pap(CONTROL, "GetLedgerCount", [0], "int")
        require(count == sum(slot["sexMask"] in ("male", "both") for slot in self.profile["slots"]),
                "The complete slot bank was not accepted by the host")

        self.move("near", world_near)
        self.write(POSE, "BeginNpcContact", [nonce, signed_bits(subject.actor), signed_bits(subject.base),
                   signed_bits(self.owner[2]), signed_bits(subject.cell), 0xCDD87, self.profile["morphs"]], "string")
        self.read_pose("ready")
        for phase, near in (("nearBefore", True), ("far", False), ("nearAfter", True)):
            if phase != "nearBefore":
                self.move("near" if near else "far", world_near if near else None)
            first, active = self.current(token)
            require(active is True, "The selected pose token expired before the hold")
            before = self.sample()
            frames = self.hold(near=near, old=old, new=new)
            after = self.sample()
            last, active = self.current(token)
            require(active is True, "The selected pose token was superseded during the hold")
            holds[phase] = {"currentBefore": first, "poseBefore": before, "frames": frames,
                            "poseAfter": after, "currentAfter": last}

        self.write(POSE, "EndNpc", [nonce], "string")
        self.read_pose("ended")
        release = {"call": self.control("ReleaseActor", [0], 0)}
        release["count"], remaining = self.pap(CONTROL, "GetLedgerCount", [0], "int")
        release["actorCurrent"], active = self.pap(NATIVE, "ActorCurrent", [subject.form], "bool")
        require(type(remaining) is int and remaining == 0 and active is False, "Scoped host retirement is unproven")
        holds["nearDetached"] = {"frames": self.hold(near=True, new=new)}
        capture["seal"], _ = self.write(EVENTS, "Seal", [nonce, generation])
        self.poll(lambda: self.json_pap(EVENTS, "GetCaptureState", []),
                  lambda pair: pair[1] == {**identity, "status": "sealed"},
                  lambda pair: pair[1] == {**identity, "status": "armed"}, 2.)
        capture["read"], _ = self.json_pap(EVENTS, "Read", [nonce, generation])

        manifest = {"schema": "claw-vr-pose-contact-reads/1", "clock": CLOCK, "subject": vars(self.subject),
                    "node": node, "token": token, "modelRead": model_read, "ledgerCount": count_index,
                    "capture": capture, "holds": holds, "release": release}
        raw = {"steps": self.ledger_path.read_bytes(), "ack_log": self.log.read_bytes(), "profile": self.profile_bytes}
        require(all(raw[name].endswith(b"\n") for name in ("steps", "ack_log")), "Original receipts ended mid-record")
        manifest["sha256"] = {key: sha256(data).hexdigest() for key, data in raw.items()}
        verdict = verify(manifest, [json.loads(line) for line in raw["steps"].splitlines()],
                         raw["ack_log"].decode("utf-8-sig").splitlines(), self.profile)
        return manifest, raw, verdict
