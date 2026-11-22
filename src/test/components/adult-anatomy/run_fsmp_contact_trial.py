"""Run an owned, reversible FSMP probe trial inside an admitted SE Autotest session."""

from dataclasses import dataclass
import json
import math
import os
import time

import numpy as np

from fsmp_contact_pose import MIN_MARGIN, NAMES, PELVIS
from fsmp_contact_windows import PHASES, SCRIPT, native_form, require, verify
from fsmp_probe import OBSERVATION, form, numbers, transform
from owned_anchors import completed_native, fixture_quarantined, quarantine_fixture


PROBE_PLUGIN = "test_CLAW - FSMP Contact Peer.esp"
SIGNATURES = {
    SCRIPT: ("globalFunctions", {
        "Arm": (["actor", "armoraddon", "actor", "armoraddon", "int", "int", "int"], "bool"),
        "Describe": (["int"], "string"), "Read": (["int", "int"], "string"), "Cancel": (["int"], "bool"),
    }),
    "DynamicHDT": ("globalFunctions", {
        "QueryCurrentPhysicsFile": (["actor", "armoraddon", "bool"], "string"),
        "ReloadPhysicsFile": (["actor", "armoraddon", "string", "bool", "bool"], "bool"),
    }),
    "Game": ("globalFunctions", {"GetFormFromFile": (["int", "string"], "form")}),
    "ObjectReference": ("memberFunctions", {"SetPosition": (["float"] * 3, "none")}),
}


@dataclass(frozen=True)
class Subjects:
    surface_ref: str
    surface_base: str
    probe_ref: str
    probe_base: str

    def specs(self):
        return [{"reference": form(ref), "base": form(base)} for ref, base in
                ((self.surface_ref, self.surface_base), (self.probe_ref, self.probe_base))]


def qualifier(script, descriptor):
    from skyrim_autotest.api_contract import validate_description

    scope, methods = SIGNATURES[script]
    checked = validate_description(script, descriptor, scope, {name: params for name, (params, _) in methods.items()})
    require(all(row["native"] is True and str(row["returnType"]).casefold() == methods[row["function"]][1]
                for row in checked), "Live native return contract differs: " + script)


def observe(raw, specs, morph_names):
    """Admit a single fresh third-person pair sample with the needed SKEE aggregates."""
    require(raw.get("ok") is True and raw.get("quality") == "complete" and raw.get("schemaVersion") == 1
            and raw.get("phase") == "skse_main_thread_task" and raw.get("units") == "skyrim_engine_units"
            and raw.get("space") == "world" and raw.get("coherence") == OBSERVATION
            and type(raw.get("sessionId")) is str and raw["sessionId"]
            and all(type(raw.get(k)) is int and raw[k] > 0 for k in ("sampleId", "producerMonotonicNs", "loadGeneration"))
            and len(raw["refs"]) == 2 and len(raw["nodes"]) == len(NAMES) + 1 and len(raw["skee"]) == 1,
            "Incomplete allocated-pair World Observer sample")
    keys, bodies = [], []
    for spec, race, names in zip(specs, ("0x000CDD84", "0x00013746"), (NAMES, (PELVIS,)), strict=True):
        row, = [row for row in raw["refs"] if form(row["identity"]["form"]) == spec["reference"]]
        actor, identity, root = row["actor"], row["identity"], row["rootIdentity"]
        require(row.get("status") == actor.get("status") == actor.get("raceStatus") == "available"
                and row.get("loaded3D") is True and row.get("deleted") is False and row.get("disabled") is False
                and form(row["baseForm"]) == form(actor["baseForm"]) == spec["base"]
                and form(actor["race"]) == race and type(actor["sex"]) is int and actor["sex"] == 0
                and identity.get("loadGeneration") == raw["loadGeneration"]
                and type(identity.get("runtimeHandle")) is int and identity["runtimeHandle"] > 0
                and root.get("firstPerson") is False and type(root.get("sampledRootToken")) is int
                and root["sampledRootToken"] > 0 and root.get("identityBasis") ==
                "sampled_pointer_and_handle_changes_no_object_retention", "Observed actor or root identity differs")
        keys.append([identity, root, row["baseForm"], actor["race"], actor["sex"], row["cellForm"]])
        nodes = {}
        for node in raw["nodes"]:
            if form(node["form"]) != spec["reference"]:
                continue
            name = node["name"]
            require(name in names and name not in nodes and node.get("status") == "available"
                    and node.get("firstPerson") is False and node.get("identity") == identity
                    and node.get("rootIdentity") == root, "Owned node is missing or from a different root")
            nodes[name] = transform(node["world"])
        require(set(nodes) == set(names), "Exact posed node catalog required")
        bodies.append({"position": numbers(row["position"], 3), "root": transform(row["sceneTransform"]), "nodes": nodes})

    require(keys[0][0]["runtimeHandle"] != keys[1][0]["runtimeHandle"]
            and keys[0][1] != keys[1][1] and keys[0][-1] == keys[1][-1], "Expected two roots in one live cell")
    skee, = raw["skee"]
    provider = skee["provider"]
    require(skee["identity"] == keys[0][0] and skee.get("status") == provider.get("status") == "available"
            and provider["interfaceVersion"] == 5 and type(provider["interfaceEpoch"]) is int
            and provider["interfaceEpoch"] > 0, "SKEE provenance does not identify the observed surface actor")
    rows = skee["morphs"]
    require(len(rows) == len(morph_names) and {row["name"] for row in rows} == set(morph_names),
            "Missing or duplicate collision-surface morph")
    require(all(row.get("status") == row["aggregate"].get("status") == "available"
                and type(row["aggregate"]["value"]) in (int, float) and row["aggregate"]["value"] == 0
                for row in rows), "The contact trial requires the six neutral surface morphs")
    return {"identity": [raw["sessionId"], raw["loadGeneration"], provider["interfaceEpoch"], keys],
            "sample": raw["sampleId"], "clock": raw["producerMonotonicNs"], "actors": bodies}


def matching_near(control, reciprocal):
    for index, (a, b) in enumerate(zip(control, reciprocal, strict=True)):
        tolerance = min(.08, .25 * min(a["marginGU"], b["marginGU"]))
        for key in (("probePoints", "targetTriangle") if index == 0 else ("probePoints",)):
            require(np.linalg.norm(np.asarray(a[key]) - np.asarray(b[key]), axis=-1).max() <= tolerance,
                    "Tag and reciprocal near windows used different observed geometry")
        require(abs(a["probeRadiusGU"] - b["probeRadiusGU"]) <= tolerance,
                "Tag and reciprocal near windows used different observed radius")


class Trial:
    def __init__(self, session, subjects, geometry, guard, maximum_seconds, nonce, frames, sleep, cancelled):
        require(session.state.get("gameEdition") == "se", "The trial requires the SE World Observer SKEE contract")
        self.session, self.geometry, self.guard = session, geometry, guard
        self.specs = subjects.specs()
        donor, probe = (int(spec["reference"], 16) for spec in self.specs)
        require(0xFF000000 <= donor < 0xFFFFFFFF and 0xFF000000 <= probe < 0xFFFFFFFF and donor != probe,
                "Two distinct disposable references are required")
        require(type(nonce) is int and 0 < nonce <= 0x7FFFFFFC and type(frames) is int and 1 <= frames <= 120
                and type(maximum_seconds) in (int, float) and 45 <= maximum_seconds <= 180,
                "Invalid bounded contact trial parameters")
        self.game = dict(session.state["game"])
        self.sleep, self.cancelled = sleep, cancelled
        self.end = time.monotonic() + maximum_seconds
        self.work_end = self.end - 20.
        self.pair = {"surfaceRef": donor, "surfaceAddon": 0xCDD87, "probeRef": probe}
        self.nonce, self.frames = nonce, frames
        self.output = session.dir / "fsmp-pair-contact"
        self.output.mkdir()
        self.ledger, self.windows, self.brackets = [], {}, {}
        self.state = {"reference": self.specs[1]["reference"], "identities": self.specs, "intent": None}
        self.previous, self.baseline = None, None
        self.armed = None
        self.mode_changed = self.moved = self.cleaning = False

    def save(self, name, value):
        temporary = self.output / (name + ".tmp")
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.output / name)

    def deadline(self):
        require(not self.cancelled() and not fixture_quarantined(self.session)
                and self.session.state["game"] == self.game, "Owned session or cancellation custody changed")
        deadline = self.end if self.cleaning else self.work_end
        require(time.monotonic() < deadline, "Bounded contact trial deadline exhausted")
        return deadline

    def check_ownership(self):
        for spec in self.specs:
            self.guard(self.session, spec, self.deadline())

    def call(self, tool, args):
        deadline = self.deadline()
        result = self.session.tool(tool, args, timeout=min(6, deadline - time.monotonic()), deadline=deadline)
        row = {"tool": tool, "args": args, "result": result}
        with (self.output / "steps.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.ledger.append(row)
        return len(self.ledger) - 1, result

    def pap(self, script, function, args, kind, *, target=None, mutate=False):
        packet = {"action": "call", "script": script, "function": function, "args": list(args), "timeoutMs": 5000}
        if target:
            packet["self"] = {"form": target}
        if mutate:
            self.check_ownership()
            self.state["intent"] = packet
            self.save("journal.json", self.state)
        try:
            index, result = self.call("papyrus", packet)
            require(completed_native(result, kind), "Typed native completion unavailable: " + function)
            if mutate:
                self.state["intent"] = None
                self.save("journal.json", self.state)
            return index, result["returned"]
        except BaseException as error:
            if mutate:
                quarantine_fixture(self.session, self.state, error)
            raise

    def sample(self):
        subjects = [row["reference"] for row in self.specs]
        index, raw = self.call("inspect", {"kind": "world_observer", "refs": subjects, "actors": True,
                                          "nodes": [{"ref": ref, "name": name, "firstPerson": False}
                                                    for ref, names in zip(subjects, (NAMES, (PELVIS,)), strict=True)
                                                    for name in names],
                                          "skee": {"refs": subjects[:1], "morphs": list(self.geometry.morphs)}})
        value = observe(raw, self.specs, self.geometry.morphs)
        if self.previous is not None:
            require(value["identity"] == self.baseline["identity"] and value["sample"] > self.previous["sample"]
                    and value["clock"] > self.previous["clock"], "Sample replay or owned scene changed")
        else:
            self.baseline = value
        self.previous = value
        return index, value

    def path(self, role):
        ref, addon = self.native_pair()[2:] if role == "probe" else self.native_pair()[:2]
        _, value = self.pap("DynamicHDT", "QueryCurrentPhysicsFile", [ref, addon, False], "string")
        require(type(value) is str, "No provider binding path")
        return value.replace("\\", "/")

    def native_pair(self):
        return [native_form(self.pair[key]) for key in ("surfaceRef", "surfaceAddon", "probeRef", "probeAddon")]

    def swap(self, path):
        self.mode_changed = True
        _, value = self.pap("DynamicHDT", "ReloadPhysicsFile", [*self.native_pair()[2:], path, False, False],
                            "bool", mutate=True)
        require(value is True and self.path("probe") == path, "Probe XML was not replaced as declared")

    def place(self, position):
        self.moved = True
        self.pap("ObjectReference", "SetPosition", list(map(float, position)), "none",
                 target=self.specs[1]["reference"], mutate=True)

    def posed(self, sample):
        surface, probe = sample["actors"]
        original = self.baseline["actors"][0]["root"]
        require(math.dist(surface["root"]["translation"], original["translation"]) <= MIN_MARGIN
                and np.max(np.abs(np.asarray(surface["root"]["rotationRowMajor"]) -
                                  original["rotationRowMajor"])) <= .001
                and surface["root"]["scale"] == original["scale"], "Stationary surface root moved")
        return surface["nodes"], probe["nodes"][PELVIS]

    def bracket(self, near):
        index, value = self.sample()
        result = self.geometry.bracket(*self.posed(value), near)
        return {"index": index, "producerMonotonicNs": value["clock"], **result}, value["actors"][1]

    def wait_bracket(self, near, position, *, seconds=6.):
        end = min(self.deadline(), time.monotonic() + seconds)
        for _ in range(32):
            frame, probe = self.bracket(near)
            if frame["valid"] and math.dist(probe["position"], position) <= MIN_MARGIN:
                return frame
            if time.monotonic() >= end:
                break
            self.sleep(.12)
        raise ValueError("Requested probe pose was not observed with the required clearance")

    def window(self, phase, number, position):
        near = phase in ("tag_control", "reciprocal_near")
        mode = self.geometry.control_path if phase == "tag_control" else self.geometry.probe_path
        require(self.path("surface") == self.geometry.target_path and self.path("probe") == mode,
                "Native registration changed before contact capture")
        before = self.wait_bracket(near, position)
        nonce = self.nonce + number
        epoch = self.baseline["identity"][1]
        index, accepted = self.pap(SCRIPT, "Arm", [*self.native_pair(), nonce, epoch, self.frames], "bool", mutate=True)
        require(accepted is True, "Provider refused the exact armed pair")
        self.armed = nonce
        stop = min(self.deadline(), time.monotonic() + 12.)
        for _ in range(48):
            described, content = self.pap(SCRIPT, "Describe", [nonce], "string")
            head = json.loads(content)
            if head.get("status") == "complete":
                self.armed = None
                break
            require(head.get("status") == "armed" and head.get("nonce") == nonce and time.monotonic() < stop,
                    "Contact window refused, changed, or exceeded its deadline")
            self.sleep(.1)
        else:
            raise ValueError("Contact capture polling bound exceeded")

        after, probe = self.bracket(near)
        require(after["valid"] and math.dist(probe["position"], position) <= MIN_MARGIN,
                "Contact window ended outside the observed held pose")
        frequency, first, last = (head[key] for key in ("qpcFrequency", "firstQpc", "lastQpc"))
        require(all(type(value) is int and value > 0 for value in (frequency, first, last))
                and before["producerMonotonicNs"] * frequency <= first * 1_000_000_000
                and last * 1_000_000_000 <= after["producerMonotonicNs"] * frequency,
                "World Observer frames do not bracket the provider QPC window")
        count = head["contactRows"]
        require(type(count) is int and 0 <= count <= 384, "Invalid bounded contact row count")
        pages = [self.pap(SCRIPT, "Read", [nonce, offset], "string")[0]
                 for offset in range(0, max(count, 1), 12)]
        self.windows[phase] = {"nonce": nonce, "arm": index, "describe": described, "pages": pages}
        self.brackets[phase] = [before, after]
        self.save("pose-brackets.json", self.brackets)

    def execute(self):
        for script in SIGNATURES:
            qualifier(script, self.call("papyrus", {"action": "describe", "script": script})[1])
        self.check_ownership()
        resolved = self.pap("Game", "GetFormFromFile", [0x800, PROBE_PLUGIN], "form")[1]
        self.pair["probeAddon"] = int(form(resolved["formId"]), 16)
        require(self.pair["probeAddon"] < 0xFE000000 and self.pair["probeAddon"] & 0xFFFFFF == 0x800,
                "Probe ARMA did not resolve to the declared full-plugin record")
        _, initial = self.sample()
        require(self.path("surface") == self.geometry.target_path and self.path("probe") == self.geometry.probe_path,
                "The two pre-equipped test actors do not own the original FSMP bindings")
        near, far = self.geometry.aims(*self.posed(initial))
        probe = initial["actors"][1]
        offset = np.asarray(probe["position"]) - probe["nodes"][PELVIS]["translation"]
        near, far = near + offset, far + offset
        require(max(np.linalg.norm(near - probe["position"]), np.linalg.norm(far - probe["position"])) <= 150,
                "Probe actors were not prepared near one another in the owned room")
        self.place(far)
        self.window(PHASES[0], 0, far)
        self.swap(self.geometry.control_path)
        self.place(near)
        self.window(PHASES[1], 1, near)
        self.place(far)
        self.wait_bracket(False, far)
        self.swap(self.geometry.probe_path)
        self.place(near)
        self.window(PHASES[2], 2, near)
        self.place(far)
        self.window(PHASES[3], 3, far)
        matching_near(self.brackets[PHASES[1]], self.brackets[PHASES[2]])
        index = {"schema": "claw-fsmp-pair-contact-reads/1", "pair": self.pair, "pid": self.game["pid"],
                 "callerEpoch": initial["identity"][1], "frames": self.frames,
                 "targetDriver": self.geometry.driver, "windows": self.windows}
        self.save("contact-index.json", index)
        result = verify(index, self.ledger)
        return {**result, "poseBracketsVerified": True, "geometry": self.geometry.identity}

    def cleanup(self):
        self.cleaning = True
        if fixture_quarantined(self.session):
            return False
        try:
            if self.armed is not None:
                _, stopped = self.pap(SCRIPT, "Cancel", [self.armed], "bool", mutate=True)
                if stopped is not True:
                    _, content = self.pap(SCRIPT, "Describe", [self.armed], "string")
                    require(json.loads(content).get("status") in ("refused", "complete"),
                            "Uncertain armed contact trial cleanup")
            if self.moved:
                original = self.baseline["actors"][1]["position"]
                self.place(original)
                for _ in range(15):
                    _, current = self.sample()
                    probe = current["actors"][1]
                    if math.dist(probe["position"], original) <= MIN_MARGIN and math.dist(
                            probe["root"]["translation"], self.baseline["actors"][1]["root"]["translation"]) <= MIN_MARGIN:
                        break
                    self.sleep(.12)
                else:
                    raise ValueError("Original probe position and model root did not return")
            if self.mode_changed and self.path("probe") != self.geometry.probe_path:
                self.swap(self.geometry.probe_path)
            if self.mode_changed:
                require(self.path("probe") == self.geometry.probe_path, "Probe's original XML did not return")
            self.save("cleanup.json", {"restored": True, "mutations": self.moved or self.mode_changed})
            return True
        except BaseException as error:
            quarantine_fixture(self.session, self.state, error)
            self.save("cleanup.json", {"restored": False, "error": str(error)})
            return False


def run(session, subjects, geometry, fixture_policy, *, nonce, frames=24, maximum_seconds=125,
        sleep=time.sleep, cancelled=lambda: False):
    """Run after the ordinary isolated fixture creation, equipment and native startup gates."""
    from skyrim_autotest.fixture_actors import guard

    trial = Trial(session, subjects, geometry, lambda s, spec, end: guard(s, spec, end, fixture_policy),
                  maximum_seconds, nonce, frames, sleep, cancelled)
    try:
        result = trial.execute()
    finally:
        clean = trial.cleanup()
        if not clean:
            session.save()
    require(clean, "Contact trial cleanup unverified; owned session teardown is required")
    trial.save("result.json", result)
    return result
