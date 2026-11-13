"""Finite persistent-human lifecycle before the separate CBPC collector.

No provider calls, actor/base weight writes, FF creation or general executor.
Caller owns the frozen Session, phase deadline, save mapping and game disposal.
"""
import copy
import json
import math
import time

import cbpc_nominal as nominal
from skyrim_autotest.api_contract import validate_description

CONTRACTS = {
    "Game": ("globalFunctions", {"GetFormFromFile": (["int", "string"], "form"),
                                "GetCurrentCrosshairRef": ([], "objectreference")}),
    "Actor": ("memberFunctions", {"SetRace": (["race"], "none"), "QueueNiNodeUpdate": ([], "none"),
        "EnableAI": (["bool"], "none"), "SetRestrained": (["bool"], "none"), "SetHeadTracking": (["bool"], "none"),
        "UnequipAll": ([], "none")}),
    "ObjectReference": ("memberFunctions", {"Enable": (["bool"], "none"), "Disable": (["bool"], "none"),
        "SetPosition": (["float"] * 3, "none"), "GetDisplayName": ([], "string")}),
    "CLAWDistributionNative": ("globalFunctions", {"Refresh": (["actor"], "bool"),
        "GetStatus": (["actor"], "int"), "GetLastError": (["actor"], "string"),
        "GetAppearanceStatus": (["actor"], "string"), "GetCoatPattern": (["actor"], "string")}),
}


def run(session, reference, sex, *, position, end, first_binding_witness,
        monotonic=time.monotonic, sleep=time.sleep):
    """Leave a freshly reacquired wolf for collection, or dispose known failure.

    `end` is the separate lifecycle deadline, already reserving collection/exit.
    The Session's existing platform owned-save policy provides save/load proof.
    """
    scene = nominal.scene
    cleanup_end, end = end, end - 8.
    subject = nominal.human_subject(reference, sex, "pending-actual-display-name")
    scene.require(type(position) is list and len(position) == 3 and
                  all(type(v) in (int, float) and math.isfinite(v) for v in position), "Finite declared scene position required")
    output = session.dir / "cbpc-human-lifecycle"
    output.mkdir(exist_ok=False)
    state = {"schemaVersion": 1, "reference": reference, "sex": sex, "writes": [], "observations": [],
             "unknown": False, "enabled": False, "completed": False, "providerCalls": [],
             "authority": None, "expectedRace": subject["originalRace"], "contracts": {}, "phaseWitnesses": {}}
    def persist():
        session.state["cbpcHumanLifecycle"] = {k: copy.deepcopy(state[k]) for k in
            ("reference", "unknown", "enabled", "completed", "authority")}
        (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        session.save()
    def persist_error():
        try:
            persist()
        except BaseException as error:
            state.setdefault("persistenceErrors", []).append({"type": type(error).__name__, "message": str(error)})
    def tool(name, args):
        scene.require(not state["unknown"] and monotonic() < end, "Lifecycle quarantined/deadline exhausted")
        try:
            remaining = end-monotonic()
            owned_transition = (name == "platform" and args.get("operation") == "input.perform" and
                                args.get("request", {}).get("action") in ("save_game", "load_game"))
            session.phase("cbpc-human-lifecycle", remaining if owned_transition else min(12., remaining))
            return session.tool(name, args, timeout=remaining if owned_transition else min(10., remaining), deadline=end)
        except BaseException:
            state["unknown"] = True
            persist_error()
            raise
    def pap(script, function, args, self_ref=None, returned="none"):
        request = {"action": "call", "script": script, "function": function, "args": args, "timeoutMs": 8000}
        if self_ref is not None:
            request["self"] = {"form": self_ref}
        raw = tool("papyrus", request)
        scene.require(raw.get("called") is True and raw.get("returnedType", "").casefold() == returned and
                      "returned" in raw and not raw.get("error") and not raw.get("isError"), "Lifecycle native completion unavailable")
        value = raw["returned"]
        valid = ((returned == "none" and value is None) or (returned == "bool" and type(value) is bool) or
                 (returned == "int" and type(value) is int) or (returned == "string" and type(value) is str) or
                 (returned == "form" and isinstance(value, dict) and type(value.get("formId")) is str))
        scene.require(valid, "Lifecycle native return primitive differs")
        return value
    def observe(*, loaded=True, reset=False, race_choices=None):
        raw = tool("inspect", {"kind": "world_observer", "refs": [reference], "actors": True})
        try:
            scene.require(raw.get("ok") is True and raw.get("quality") == "complete" and len(raw.get("refs", [])) == 1,
                          "Complete persistent reference observation required")
            scene.require(raw.get("schemaVersion") == 1 and raw.get("phase") == "skse_main_thread_task" and
                          raw.get("units") == "skyrim_engine_units" and raw.get("space") == "world" and
                          raw.get("coherence") == scene.OBSERVATION and type(raw.get("sessionId")) is str and raw["sessionId"],
                          "Persistent observer contract changed")
            ref = raw["refs"][0]
            identity, actor = ref["identity"], ref["actor"]
            races = race_choices or (state["expectedRace"],)
            scene.require(ref.get("status") == "available" and actor.get("status") == "available" and
                actor.get("raceStatus") == "available" and ref.get("disabled") is (not state["enabled"]) and
                identity["form"].casefold() == reference.casefold() and
                identity.get("sourcePlugin") == subject["sourcePlugin"] and
                identity.get("localFormId", "").casefold() == subject["localReference"].casefold() and
                ref.get("baseForm", "").casefold() == subject["baseForm"].casefold() and
                actor.get("baseForm") == ref["baseForm"] and actor.get("baseRace", "").casefold() in {r.casefold() for r in races} and
                actor.get("race", "").casefold() in {r.casefold() for r in races} and
                actor.get("baseRace", "").casefold() == actor.get("race", "").casefold() and
                type(actor.get("sex")) is int and actor["sex"] == (sex == "female") and
                actor.get("weight", {}).get("rawNPCWeight") == subject["rawNPCWeight"] and
                ref.get("deleted") is False, "Persistent original-human identity/race/weight differs")
            authority = {"sessionId": raw["sessionId"], "generation": raw["loadGeneration"], "identity": identity}
            scene.require(type(raw["sampleId"]) is int and raw["sampleId"] > 0 and type(raw["producerMonotonicNs"]) is int and
                          raw["producerMonotonicNs"] > 0 and type(raw["loadGeneration"]) is int and raw["loadGeneration"] > 0,
                          "Persistent observer time/epoch missing")
            if state["observations"]:
                prior = state["observations"][-1]
                scene.require(raw["producerMonotonicNs"] > prior["producerMonotonicNs"] and
                              (reset or raw["sampleId"] > prior["sampleId"]), "Replayed lifecycle observation")
            if state["authority"] is not None and not reset:
                scene.require(authority == state["authority"], "Persistent actor incarnation/epoch changed")
            if loaded:
                scene.require(ref.get("disabled") is False and ref.get("loaded3D") is True and
                              type(ref.get("rootIdentity", {}).get("sampledRootToken")) is int and
                              ref["rootIdentity"]["sampledRootToken"] > 0 and ref["rootIdentity"].get("firstPerson") is False and
                              ref["rootIdentity"].get("identityBasis") == "sampled_pointer_and_handle_changes_no_object_retention",
                              "Loaded current root missing")
                scene.transform(ref["sceneTransform"])
            state["authority"] = copy.deepcopy(authority)
            state["observations"].append(raw)
            persist()
            return raw
        except BaseException:
            state["unknown"] = True  # Never dispose against missing/changed identity.
            persist_error()
            raise
    def mutate(label, operation, *, guard=True):
        if guard:
            observe(loaded=state["enabled"])
        row = {"label": label, "status": "intent"}
        state["writes"].append(row)
        persist()
        try:
            value = operation()
            row.update(status="returned", result=copy.deepcopy(value))
            persist()
            return value
        except BaseException:
            row["status"] = "unknown"
            state["unknown"] = True
            persist_error()
            raise
    def read_native(function, returned):
        observe()
        value = pap("CLAWDistributionNative", function, [{"form": reference}], returned=returned)
        state.setdefault("nativeReadbacks", []).append({"function": function, "value": value})
        persist()
        return value
    def wait_applied():
        while monotonic() < end:
            if read_native("GetStatus", "int") == 2:
                scene.require(read_native("GetLastError", "string") == "", "CLAW application has an error")
                return
            sleep(.1)
        raise ValueError("Applied CLAW state not observed")
    def race(target, label):
        previous_race = state["expectedRace"]
        mutate(label, lambda: pap("Actor", "SetRace", [{"form": target}], reference))
        state["pendingRace"] = target
        persist()
        # Only this predeclared transition may temporarily retain the old race
        # or unload its model. No additional mutation occurs while waiting.
        while monotonic() < end:
            row = observe(loaded=False, race_choices=(previous_race, target))["refs"][0]
            if row["actor"]["race"].casefold() == target.casefold() and row.get("loaded3D") is True and row.get("rootIdentity", {}).get("sampledRootToken", 0) > 0:
                state["expectedRace"] = target
                state["pendingRace"] = None
                state["phaseWitnesses"][label] = observe()
                return
            sleep(.1)
        state["unknown"] = True
        persist()
        raise ValueError("Declared race/model transition not resolved")
    def owned_action(action):
        result = tool("platform", {"operation": "input.perform", "request": {
            "action": action, "saveTag": "cbpc-human-lifecycle", "scope": "owned-disposable-profile"}})
        if action == "save_game":
            scene.require(result.get("save", {}).get("completed") is True and result["save"].get("ownedByAttempt") is True,
                          "Owned save completion not verified")
        else:
            evidence = result.get("lifecycle", {})
            scene.require(evidence.get("worldReady") is True and evidence.get("pidChanged") is False and
                          evidence.get("generationChanged") is True and evidence.get("oldReferenceTagsInvalidated") is True,
                          "Same-process owned load/epoch completion missing")
        return result
    primary = None
    try:
        for script, (scope, methods) in CONTRACTS.items():
            raw = tool("papyrus", {"action": "describe", "script": script})
            checked = validate_description(script, raw, scope, {n: p for n, (p, _) in methods.items()})
            scene.require(all(r["native"] is True and r["returnType"].casefold() == methods[r["function"]][1]
                              for r in checked), "Lifecycle API contract differs")
            state["contracts"][script] = {"raw": raw, "checked": checked}
        resolved = pap("Game", "GetFormFromFile", [int(subject["localReference"], 16), subject["sourcePlugin"]], returned="form")
        scene.require(resolved["formId"].casefold() == reference.casefold(), "Actual persistent fixture resolution differs")
        initial = observe(loaded=False)
        scene.require(initial["refs"][0].get("disabled") is True and initial["refs"][0].get("loaded3D") is False,
                      "Fresh initially-disabled/unloaded human reference required")
        state["phaseWitnesses"]["initial-human"] = initial
        mutate("place-disabled", lambda: pap("ObjectReference", "SetPosition", position, reference))
        mutate("enable-human", lambda: pap("ObjectReference", "Enable", [False], reference))
        state["enabled"] = True
        # Enable is known returned; await its human model without another write.
        while monotonic() < end:
            row = observe(loaded=False)["refs"][0]
            if row.get("loaded3D") is True and row.get("rootIdentity", {}).get("sampledRootToken", 0) > 0:
                break
            sleep(.1)
        observe()
        mutate("restrain-human", lambda: pap("Actor", "SetRestrained", [True], reference))
        before_outfit = observe()
        mutate("unequip-owned-outfit", lambda: pap("Actor", "UnequipAll", [], reference))
        after_outfit = observe()
        state["outfitRootRebind"] = {"before": before_outfit, "after": after_outfit,
                                    "scope": "Known own UnequipAll and current-root re-admission; no base outfit/inventory deletion"}
        mutate("enable-human-ai", lambda: pap("Actor", "EnableAI", [True], reference))
        human_until = monotonic() + nominal.protocol()["settleSeconds"]
        while monotonic() < human_until:
            scene.require(monotonic() < end, "Normal human update opportunity deadline exhausted")
            sleep(min(.1, human_until-monotonic()))
        status = ""
        while monotonic() < end:
            status = read_native("GetAppearanceStatus", "string")
            if status == "human colours captured" or status.startswith("record-hair-fallback:"):
                break
            sleep(.1)
        scene.require(status == "human colours captured" or status.startswith("record-hair-fallback:"), "Human appearance source not captured")
        state["humanSource"] = {"appearanceStatus": status, "linkStatus": read_native("GetStatus", "int"),
                                "scope": "Actual human appearance/source status; link0 is unknown, not body-matrix success"}
        scene.require(state["humanSource"]["linkStatus"] in (0, 5), "Fresh human link has an unexpected status")
        state["phaseWitnesses"]["enabled-human"] = observe()
        provider_name = pap("ObjectReference", "GetDisplayName", [], reference, returned="string")
        subject = nominal.human_subject(reference, sex, provider_name)
        race(subject["currentRace"], "first-wolf")
        wait_applied()
        until = monotonic() + nominal.protocol()["settleSeconds"]
        while monotonic() < until:
            scene.require(monotonic() < end, "First-transform settling deadline exhausted")
            sleep(min(.1, until-monotonic()))
        first_nodes = tool("inspect", nominal.controls.prepare(reference, sex)["query"])
        nominal.admit_human_origin(scene.snapshot(first_nodes, reference, sex), subject)
        state["phaseWitnesses"]["first-wolf"] = first_nodes
        state["firstTransformBinding"] = first_binding_witness(subject, output)
        persist()
        pattern = read_native("GetCoatPattern", "string")
        scene.require(mutate("refresh", lambda: pap("CLAWDistributionNative", "Refresh", [{"form": reference}], returned="bool")) is True,
                      "CLAW Refresh was not queued")
        wait_applied()
        state["phaseWitnesses"]["refresh"] = observe()
        race(subject["originalRace"], "human-return")
        while monotonic() < end and read_native("GetStatus", "int") != 5:
            sleep(.1)
        scene.require(read_native("GetStatus", "int") == 5, "Human return/own-key-cleared status missing")
        race(subject["currentRace"], "second-wolf")
        wait_applied()
        mutate("node-update", lambda: pap("Actor", "QueueNiNodeUpdate", [], reference))
        observe()
        old_epoch = copy.deepcopy(state["authority"])
        mutate("owned-save", lambda: owned_action("save_game"))
        mutate("owned-load", lambda: owned_action("load_game"))
        resolved = pap("Game", "GetFormFromFile", [int(subject["localReference"], 16), subject["sourcePlugin"]], returned="form")
        scene.require(resolved["formId"].casefold() == reference.casefold(), "Postload authored reference resolution differs")
        fresh = observe(reset=True)
        scene.require(fresh["loadGeneration"] > old_epoch["generation"], "Fresh observer load generation missing")
        wait_applied()
        mutate("head-tracking-off", lambda: pap("Actor", "SetHeadTracking", [False], reference))
        scene.require(read_native("GetCoatPattern", "string") == pattern, "Automatic selection changed across lifecycle")
        fresh = observe()
        state["phaseWitnesses"]["post-load"] = fresh
        state.update(completed=True, humanOrigin=subject, finalRoot=fresh["refs"][0]["rootIdentity"],
                     queueNodeUpdateClaim="Known queued call and current-root observation; no forced recreation inferred")
        persist()
        query = nominal.controls.prepare(reference, sex)["query"]
        admitted = tool("inspect", query)
        return subject, admitted, state
    except BaseException as error:
        primary = error
        state["primaryError"] = {"type": type(error).__name__, "message": str(error)}
        persist_error()
        raise
    finally:
        end = cleanup_end
        if not state["completed"] and state["enabled"] and not state["unknown"]:
            try:
                mutate("failed-lifecycle-dispose", lambda: pap("ObjectReference", "Disable", [False], reference))
                state["enabled"] = False
                disposed = observe(loaded=False)
                scene.require(disposed["refs"][0].get("disabled") is True and disposed["refs"][0].get("loaded3D") is False and
                              disposed["refs"][0].get("rootIdentity", {}).get("sampledRootToken") in (None, 0),
                              "Known lifecycle disposal/unloaded state not observed")
                crosshair = tool("papyrus", {"action": "call", "script": "Game", "function": "GetCurrentCrosshairRef", "args": [], "timeoutMs": 8000})
                scene.require(crosshair.get("called") is True and crosshair.get("returnedType") == "none" and
                              "returned" in crosshair and crosshair["returned"] is None and not crosshair.get("error") and not crosshair.get("isError"),
                              "Known lifecycle null-crosshair cleanup not observed")
            except BaseException as error:
                state["cleanupError"] = {"type": type(error).__name__, "message": str(error)}
                persist_error()
                if primary is None:
                    raise
            finally:
                persist_error()
