"""Capture the adaptive TailBone02 case inside an already owned VR session."""

import json
from pathlib import Path
import time

from prepare_tail_refit_contrast import read_pinned
from tail_refit_morph import UnconfirmedMutation, run_states
from verify_tail_refit import (
    CBPC, CHANNEL, EVENTS, MARGIN, MAX_GAP_NS, MIN_HOLD, NANO, NATIVE, NODE,
    POSE, PROFILE_SHA, PROOF_SHA, QPC, SLOT_IDS, STATES,
    bank_gap, f32, inspect_frame, positive_int, require, verify,
)


def signed_bits(value):
    return value - 0x100000000 if value >= 0x80000000 else value


class IndexedCapture:
    """Match operations to the owning executor's original append-only ledger."""

    def __init__(self, call, ledger_path, *, deadline, clock=time):
        self.call = call
        self.ledger_path = Path(ledger_path)
        self.deadline, self.clock = deadline, clock
        self.ledger_offset = 0
        self.ledger_count = 0
        self.waiting_on = None

    def ledger(self):
        return [json.loads(line) for line in self.ledger_path.read_bytes().splitlines()]

    def drain(self):
        with self.ledger_path.open("rb") as stream:
            require(stream.seek(0, 2) >= self.ledger_offset, "Executor ledger regressed during the owned capture")
            stream.seek(self.ledger_offset)
            data = stream.read()
        require(not data or data.endswith(b"\n"), "Executor ledger append was incomplete")
        rows = data.splitlines()
        start = self.ledger_count
        self.ledger_offset += len(data)
        self.ledger_count += len(rows)
        return start, rows

    def record(self, name, packet):
        remaining = self.deadline - self.clock.monotonic()
        require(remaining > 0, "The owned capture window expired")
        self.drain()
        result = self.call(name, packet, timeout=min(2.6, remaining), deadline=self.deadline)
        start, rows = self.drain()
        matches = [index for index, row in enumerate(map(json.loads, rows), start) if row.get("kind") == "tool"
                   and row.get("tool") == name and row.get("args") == packet and row.get("result") == result]
        require(len(matches) == 1, "Executor did not retain exactly one matching raw step")
        return matches[0], result

    def pap(self, script, function, args, kind):
        packet = {"action": "call", "script": script, "function": function, "args": args,
                  "timeoutMs": 2200}
        index, reply = self.record("papyrus", packet)
        require(reply.get("called") is True and str(reply.get("returnedType", "")).casefold() == kind
                and "returned" in reply and not (reply.get("error") or reply.get("isError")),
                f"Expected typed completion of {script}.{function}")
        value = reply["returned"]
        require(kind != "none" or value is None, f"Expected confirmed void completion of {function}")
        return index, value

    def write(self, script, function, args, kind="bool"):
        require(self.waiting_on is None, "Prior native mutation remains unresolved")
        self.waiting_on = function
        try:
            index, result = self.pap(script, function, args, kind)
        except Exception as error:
            raise UnconfirmedMutation(f"Unconfirmed {script}.{function}") from error
        self.waiting_on = None
        require(kind != "bool" or result is True, f"Native operation refused: {function}")
        return index, result

    def json_pap(self, script, function, args):
        index, value = self.pap(script, function, args, "string")
        return index, json.loads(value)


class Capture(IndexedCapture):
    """Use only the provided executor, existing VFS/actor custody and a fixed controller."""

    def __init__(self, call, ledger_path, subject, profile, basis, *, deadline, clock=time):
        super().__init__(call, ledger_path, deadline=deadline, clock=clock)
        self.subject, self.profile, self.basis = subject, profile, basis
        self.nonce = subject.generation
        self.token = 0
        self.session_token = None
        self.sequence = 0
        self.owner = None
        self.morph_receipts = []
        self.banks = [[[*cap["p1"], *cap["p2"], cap["radius"]] for cap in bank]
                      for bank in basis["capsulesByPhase"]]
        self.manifest = {"schema": "claw-vr-tail02-refit-reads/2", "subject": vars(subject),
                         "phases": [], "capture": {}, "morph": {}}

    @classmethod
    def from_files(cls, call, ledger_path, subject, profile_path, basis_path, *, deadline):
        profile = json.loads(read_pinned(Path(profile_path), PROFILE_SHA))
        basis = json.loads(read_pinned(Path(basis_path), PROOF_SHA))
        return cls(call, ledger_path, subject, profile, basis, deadline=deadline)

    def observe(self):
        actor = self.subject.form["form"]
        index, raw = self.record("inspect", {
            "kind": "world_observer", "action": "snapshot", "refs": ["0x00000014", actor], "timeoutMs": 1500,
            "nodes": [{"ref": actor, "name": node, "firstPerson": False} for node in (NODE, "NPC Root [Root]")],
        })
        frame = inspect_frame([{"tool": "inspect", "args": {"kind": "world_observer", "action": "snapshot"},
                               "result": raw}], 0, self.subject)
        identity = frame["actor"][0]
        current = (frame["session"], frame["epoch"], identity["runtimeHandle"])
        require(self.owner is None or self.owner == current, "Lost the original loaded actor or world")
        require(all(gap >= MARGIN for gap in (bank_gap(frame, self.banks[0]), -bank_gap(frame, self.banks[1]))),
                "Fixed controller fails the neutral/morphed contrast")
        self.owner = current
        return index, frame

    def hold(self):
        start = None
        samples = []
        for _ in range(8):
            index, frame = self.observe()
            sample_ns = frame["ns"]
            start = sample_ns if start is None else start
            require(not samples or 0 < sample_ns - samples[-1][1] <= MAX_GAP_NS, "Unstable World Observer cadence")
            samples.append((index, sample_ns))
            if (sample_ns - start) * QPC >= (MIN_HOLD + 2) * NANO:
                return [row[0] for row in samples]
            self.clock.sleep(.48)
        raise ValueError("Observed hold did not reach the minimum duration")

    def wait(self, read, seconds=1.):
        until = min(self.deadline, self.clock.monotonic() + seconds)
        while self.clock.monotonic() < until:
            index, reply = read()
            status = reply.get("status")
            if status in ("ready", "ended"):
                return index, reply
            require(status in ("pending", "retiring"), "Native witness refused: " + str(reply.get("reason")))
            self.clock.sleep(max(0., min(.12, until - self.clock.monotonic())))
        raise ValueError("Native witness never reported a current result")

    def pose(self):
        args = [self.nonce, self.sequence]
        self.write(POSE, "SampleNpc", args, "string")
        index, reply = self.wait(lambda: self.json_pap(POSE, "ReadNpc", args))
        require(reply["status"] == "ready" and reply["sequence"] == self.sequence, "Pose sequence differs")
        self.sequence += 1
        return index

    def morph_call(self, script, function, args, kind):
        handler = self.pap if kind != "none" else self.write
        index, value = handler(script, function, args, kind)
        self.morph_receipts.append(index)
        return value

    def describe(self, script):
        index, raw = self.record("papyrus", {"action": "describe", "script": script})
        self.manifest["morph"]["describe"] = index
        return raw

    def capture_phase(self, name):
        number = len(self.manifest["phases"])
        require(name == ("neutral", "morphed", "returned")[number], "Unexpected refit phase")
        self.manifest["morph"][("initial", "apply", "restore")[number]] = self.morph_receipts[:]
        self.morph_receipts.clear()
        # Distribution can need two 2-second main-task scans before the fit worker publishes.
        index, event = self.wait(lambda: self.json_pap(POSE, "ReadPhysicsSnapshot", [self.nonce, self.token]),
                                 seconds=6.)
        token = event["snapshotToken"]
        require(type(token) is int and self.token < token < 0x01000000
                and event["actor"] == self.subject.actor and event["runtimeHandle"] == self.owner[2],
                "Snapshot event belongs to a different tail actor or generation")
        self.token = token
        args = [self.subject.form, self.subject.generation, self.token]
        phase = {"event": index, "token": token}

        def read_native(method, kind, key):
            phase[key], value = self.pap(NATIVE, method, args, kind)
            return value

        require(read_native("SnapshotCurrent", "bool", "begin") is True, "Refit snapshot already stale")
        expected = [STATES[number] if morph == CHANNEL else 0. for morph in self.profile["morphs"]]
        require(read_native("GetValues", "float[]", "values") == expected
                and read_native("GetWeight", "float", "weight") == .5, "Native snapshot has a different morph vector")
        phase["capsules"], phase["attach"], phase["detach"] = [], [], []
        capsules = []
        for slot, reference in zip(SLOT_IDS, self.banks[number], strict=True):
            index, shape = self.pap(NATIVE, "GetCapsule", [*args, slot], "float[]")
            require(len(shape) == 7 and f32(shape) == f32(reference), "Provider capsule differs from exact fitted bank")
            phase["capsules"].append(index)
            capsules.append(shape)
        for slot, shape in zip(SLOT_IDS, capsules, strict=True):
            index, _ = self.write(CBPC, "AttachColliderCapsule", [self.subject.form, NODE, shape[:3],
                                  shape[6], shape[3:6], shape[6], 0., 0x434C0000 + slot, True])
            phase["attach"].append(index)
        phase["poseBefore"] = self.pose()
        phase["hold"] = self.hold()
        phase["poseAfter"] = self.pose()
        require(read_native("SnapshotCurrent", "bool", "end") is True, "Refit bank changed during contact hold")
        for slot in SLOT_IDS:
            index, _ = self.write(CBPC, "DetachCollider", [self.subject.form, NODE, 1, 0x434C0000 + slot, True])
            phase["detach"].append(index)
        self.manifest["phases"].append(phase)

    def run(self, evidence):
        """Caller has verified loaded modules, fixture identity and disabled population host."""
        subject = self.subject
        require(0xFF000000 <= subject.actor < 0xFFFFFFFF and positive_int(self.nonce)
                and subject.cell == 0x0A01A5C6 and type(evidence) is str and 0 < len(evidence) <= 1024,
                "An admitted disposable VR actor and qualification record are required")
        self.observe()
        model_index, model = self.pap(NATIVE, "GetModelIdentity", [], "string")
        require(model == self.profile["modelIdentity"] == self.basis["model"], "Different native fit loaded")
        self.manifest["modelRead"] = model_index
        capture = self.manifest["capture"]
        capture["idle"], idle = self.json_pap(EVENTS, "GetCaptureState", [])
        require(idle.get("status") == "idle" and idle.get("pid") == subject.pid
                and idle.get("sinkRegistered") is True, "Callback witness was not idle and ready")
        generation = idle["generation"]
        capture["arm"], _ = self.write(EVENTS, "Arm", [self.nonce, generation, signed_bits(subject.actor), subject.cell])
        self.manifest["unattached"] = self.hold()
        _, self.session_token = self.write(NATIVE, "BeginSessionToken", [], "string")
        require(self.session_token, "Unable to open isolated native refit session")
        _, opened = self.write(POSE, "BeginNpcContact", [
            self.nonce, signed_bits(subject.actor), signed_bits(subject.base), signed_bits(self.owner[2]),
            signed_bits(subject.cell), 0xCDD87, self.profile["morphs"],
        ], "string")
        require(json.loads(opened)["status"] in ("pending", "ready"), "Pose witness did not accept the owned actor")
        # Arm the listener with sample zero. Evidence samples follow each event.
        _, ready = self.wait(lambda: self.json_pap(POSE, "ReadNpc", [self.nonce, 0]))
        require(ready["status"] == "ready", "Pose listener did not become ready")
        self.sequence = 1
        self.write(NATIVE, "RegisterQualifiedActor", [subject.form, subject.generation, self.profile["morphs"],
                                                     model, evidence, self.session_token])
        run_states(self.morph_call, self.describe, self.observe, self.capture_phase, subject.actor)
        self.write(NATIVE, "UnregisterActor", [subject.form, False, self.session_token], "none")
        require(self.pap(NATIVE, "ActorCurrent", [subject.form], "bool")[1] is False,
                "Native test actor is still registered after cleanup")
        _, retired = self.write(NATIVE, "EndSession", [self.session_token], "string")
        require(retired and retired != self.session_token, "Native test session did not retire")
        self.write(POSE, "EndNpc", [self.nonce], "string")
        _, ended = self.wait(lambda: self.json_pap(POSE, "ReadNpc", [self.nonce, self.sequence - 1]))
        require(ended["status"] == "ended", "Owned pose witness did not retire")
        self.manifest["detached"] = self.hold()
        capture["seal"], _ = self.write(EVENTS, "Seal", [self.nonce, generation])
        capture["read"], _ = self.json_pap(EVENTS, "Read", [self.nonce, generation])
        result = verify(self.manifest, self.ledger(), self.profile, self.basis)
        return self.manifest, result
