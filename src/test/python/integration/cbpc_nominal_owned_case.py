"""Unlaunched proposal: thin nominal callback inside an already owned SE Session.

The outer case owns fixture/VFS/provider admission, process exit and file restore.
No launcher, node writes, provider-state getter, binding claim or parent getter.
An uncertain/cancelled dispatch forbids every further callback mutation, including
cleanup; the owning Session must tear down that disposable world instead.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import time

from skyrim_autotest.api_contract import validate_description
import cbpc_nominal as nominal
import cbpc_probe as controls
import cbpc_stock_role as role
import fsmp_probe as scene
import fsmp_pulse


RESERVE = 32.
SETTLE_AFTER_POSITION = .2
CONTRACTS = {
    "CBPCPluginScript": ("globalFunctions", {
        "StartPhysics": (["actor", "string"], "none"),
        "StopPhysics": (["actor", "string"], "none")}),
    "Actor": ("memberFunctions", {
        "EnableAI": (["bool"], "none"), "SetRestrained": (["bool"], "none")}),
    "ObjectReference": ("memberFunctions", {
        "SetPosition": (["float"]*3, "none"), "Disable": (["bool"], "none")}),
    "Game": ("globalFunctions", {"GetCurrentCrosshairRef": ([], "objectreference")}),
}


class Cancelled(RuntimeError):
    pass


def validate_contract(script, raw):
    scope, methods = CONTRACTS[script]
    checked = validate_description(script, raw, scope, {n: v[0] for n, v in methods.items()})
    for row in checked:
        scene.require(row["native"] is True and str(row["returnType"]).casefold() == methods[row["function"]][1],
                      "Changed native return contract: " + script + "." + row["function"])
    return checked


def verify_sources(pins, stock_expected):
    """Reuse the declared helper/proof sources; this does not qualify live VFS."""
    modules = {"cbpc_probe.py": controls, "cbpc_pulse.py": nominal.hierarchy,
               "fsmp_probe.py": scene, "fsmp_pulse.py": fsmp_pulse}
    for name, module in modules.items():
        expected = pins["helperSources"][name]
        scene.require(hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() == expected["sha256"],
                      "Declared helper source changed: " + name)
    proof = [p for p in pins["stockConfigurationAndRoleProof"]
             if Path(p["path"]).name == "stock-graph-expected.json"]
    scene.require(len(proof) == 1, "Unique pinned stock-role proof required")
    raw = Path(proof[0]["path"]).read_bytes()
    scene.require(hashlib.sha256(raw).hexdigest() == proof[0]["sha256"] and
                  json.loads(raw) == stock_expected, "Stock expected-role source changed")
    scene.require(pins["xp32Sha256"] == nominal.hierarchy.XP32_SHA256, "Changed expected XP32 skeleton")


def packet(reference, script, function, args):
    return {"action": "call", "script": script, "function": function,
            "self": {"form": reference}, "args": args, "timeoutMs": 8000}


def run(session, reference, sex, *, admitted, subject_pins, stock_expected,
        sleep=time.sleep, monotonic=time.monotonic, clock=time.perf_counter,
        cancelled=lambda: False):
    """Collect the separate nominal protocol; never launch or install anything.

    `admitted` is the outer case's fresh disposable-fixture observation. The outer
    case still independently verifies actual VFS winners/loaded modules, distance,
    ownership and source pins. A local cancellation callable is an executor input,
    not a newly invented Session/game API. KeyboardInterrupt is also contained.
    """
    reference = scene.form(reference)  # Refuse the player before files or tools.
    scene.require(sex == "female", "This declared eleven-driver nominal case is female only")
    scene.require(session.state.get("configuration", {}).get("game_edition") == "se",
                  "Pinned CBPC nominal callback requires the owned SE Session")
    expected = scene.snapshot(admitted, reference, sex)
    verify_sources(subject_pins, stock_expected)
    scene.require(stock_expected["query"].get("refs") == [reference], "Pinned stock query is for another fixture")
    spec, plan = nominal.protocol(), controls.prepare(reference, sex)
    end = monotonic() + spec["maximumSeconds"]
    output = session.dir / "cbpc-nominal"
    output.mkdir(exist_ok=False)
    observations = output / "observations"
    observations.mkdir()
    state = {"schemaVersion": 1, "reference": reference, "sex": sex,
             "protocol": spec, "subjectPins": copy.deepcopy(subject_pins),
             "skeletonSha256": nominal.hierarchy.XP32_SHA256,
             "expectedParents": {n: p[0] for n, p in nominal.hierarchy.parent_paths(sex).items()},
             "setupReceipts": [], "receipts": {}, "positionReceipts": {}, "windows": {},
             "intent": None, "uncertain": False, "cancelled": False,
             "quarantined": False, "providerState": "unknown", "providerRestorationClaimed": False,
             "actualParentIdentityObserved": False, "apiContracts": {}}
    baseline = graph = None
    graph_qualified = False
    previous = expected
    cleaning = False
    sequence = 0

    def save_raw(full=False):
        session.state["cbpcNominal"] = {"directory": str(output), "intent": copy.deepcopy(state["intent"]),
                                       "quarantined": state["quarantined"], "uncertain": state["uncertain"]}
        journal = {k: state[k] for k in ("protocol", "reference", "sex", "intent", "uncertain",
                   "cancelled", "quarantined", "providerState", "providerRestorationClaimed")}
        journal.update(receiptCounts={k: len(v) for k, v in state["receipts"].items()},
                       positionCounts={k: len(v) for k, v in state["positionReceipts"].items()},
                       primaryError=state.get("primaryError"), cleanup=state.get("cleanup"))
        (output / "journal.json").write_text(json.dumps(journal, indent=2), encoding="utf-8")
        if full:
            (output / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
        session.save()

    def save(full=False):
        try:
            save_raw(full)
        except BaseException as error:
            state["quarantined"] = True
            if isinstance(error, Cancelled) or not isinstance(error, Exception):
                state["cancelled"] = True
            raise

    def save_after_error():
        try:
            save_raw(full=True)
        except BaseException as error:
            state["quarantined"] = True
            if isinstance(error, Cancelled) or not isinstance(error, Exception):
                state["cancelled"] = True
            state.setdefault("persistenceErrors", []).append({"type": type(error).__name__, "message": str(error)})
            session.state.setdefault("cbpcNominal", {}).update(quarantined=True, uncertain=state["uncertain"])

    def checkpoint():
        if cancelled():
            state["cancelled"] = state["quarantined"] = True
            raise Cancelled("Nominal callback cancelled; no further world mutation")
        scene.require(not state["quarantined"], "Nominal callback quarantined; owned Session teardown required")

    def call(label, tool, args):
        checkpoint()
        deadline = end if cleaning else end - RESERVE
        remaining = deadline - monotonic()
        scene.require(remaining > 0, "Nominal callback deadline/cleanup reserve exhausted")
        try:
            session.phase("cbpc-nominal: " + label, min(remaining, 12.) + 1.)
            return session.tool(tool, args, timeout=min(remaining, 10.), deadline=deadline)
        except BaseException:
            state["quarantined"] = True  # No new call after any unresolved transport.
            raise

    def wait_until(at):
        while clock() < at:
            checkpoint()
            scene.require(monotonic() < (end if cleaning else end-RESERVE), "Nominal wait deadline exhausted")
            sleep(max(0., min(.05, at-clock())))
        checkpoint()

    def observe(label):
        nonlocal previous, sequence
        raw = call(label, "inspect", plan["query"])
        try:
            sequence += 1
            (observations / f"{sequence:04d}-{label}.json").write_text(json.dumps(raw, indent=2), encoding="utf-8")
            row = scene.snapshot(raw, reference, sex)
            scene.require(row["guard"] == expected["guard"], "Owned actor/root/source continuity lost")
            scene.require(row["sample"] > previous["sample"] and row["time"] > previous["time"],
                          "Replayed/nonadvancing nominal observation")
            if graph is not None:
                role.require_same_root(raw, graph)
        except BaseException:
            state["quarantined"] = True
            raise
        previous = row
        return raw

    def mutate(label, request, before):
        checkpoint()
        scene.require(state["intent"] is None, "Previous mutation completion unresolved")
        intent = {"label": label, "request": copy.deepcopy(request), "beforeSample": before["sampleId"]}
        try:
            state["intent"] = intent
            save()  # Durable intent before exactly one dispatch.
            result = call(label, "papyrus", request)
            receipt = {"request": copy.deepcopy(request), "nativeResult": result, "before": before}
            intent["nativeResult"] = result  # Actual received reply only, still unvalidated.
            save()
            controls.completed(receipt, request)
            state["intent"] = None
            save()  # Completion is durable before another world mutation.
        except BaseException:
            state["intent"] = intent
            state["uncertain"] = state["quarantined"] = True
            save_after_error()  # Never replace the dispatch/persistence failure.
            raise
        checkpoint()
        return receipt

    def transition(action):
        scene.require(action not in state["receipts"], "No provider transition replay")
        rows = state["receipts"][action] = []
        for index, request in enumerate(plan["calls"][action]):
            label = action + "-" + str(index)
            before = observe(label + "-before")
            receipt = mutate(label, request, before)
            receipt["after"] = observe(label + "-after")
            rows.append(receipt)
            save()

    def cleanup():
        result = state["cleanup"] = {"providerState": "unknown", "providerRestorationClaimed": False,
            "providerCleanupCalls": [], "fixtureCleanupScope": "origin-and-disabled-only-in-pure-scorer",
            "outerSessionExitAndPreimagesRequired": True, "crosshairReleasedVerified": False}
        before = observe("cleanup-origin-before")
        receipt = mutate("cleanup-origin", packet(reference, "ObjectReference", "SetPosition", baseline["position"]), before)
        wait_until(clock() + SETTLE_AFTER_POSITION)
        receipt["after"] = observe("cleanup-origin-after")
        scene.require(scene.max_delta(previous["position"], baseline["position"]) <= .025,
                      "Owned actor origin restoration not observed")
        result["restoreReference"] = receipt
        before = observe("cleanup-disable-before")
        receipt = mutate("cleanup-disable", packet(reference, "ObjectReference", "Disable", [False]), before)
        result["disposeFixture"] = receipt
        while monotonic() < end:
            raw = call("cleanup-disabled-readback", "inspect", {"kind": "world_observer", "refs": [reference], "actors": True})
            refs = raw.get("refs", [])
            scene.require(raw.get("ok") is True and raw.get("quality") == "complete" and len(refs) == 1 and
                          raw.get("sessionId") == expected["guard"]["session"] and
                          raw.get("loadGeneration") == expected["guard"]["generation"] and
                          raw.get("sampleId", 0) > previous["sample"] and raw.get("producerMonotonicNs", 0) > previous["time"] and
                          refs[0].get("identity") == expected["guard"]["identity"] and
                          refs[0].get("baseForm") == expected["guard"]["actor"]["baseForm"] and refs[0].get("deleted") is False,
                          "Disposal readback identity/epoch unavailable")
            receipt["after"] = raw
            previous.update(sample=raw["sampleId"], time=raw["producerMonotonicNs"])
            crosshair = call("cleanup-crosshair", "papyrus", {"action": "call", "script": "Game",
                "function": "GetCurrentCrosshairRef", "args": [], "timeoutMs": 8000})
            result.setdefault("crosshairObservations", []).append({"world": raw, "nativeResult": crosshair})
            scene.require(crosshair.get("called") is True and "returned" in crosshair and
                          not crosshair.get("error") and not crosshair.get("isError"), "Crosshair readback unavailable")
            if crosshair["returned"] is None:
                scene.require(crosshair.get("returnedType") == "none", "Null crosshair type unavailable")
                if refs[0].get("disabled") is True:
                    result["crosshairReleasedVerified"] = True
                    save()
                    return
            wait_until(clock() + .1)
        raise ValueError("Owned fixture disabled/null-crosshair readback not observed")

    primary = cleanup_error = None
    try:
        for script in CONTRACTS:
            raw = call("describe-" + script, "papyrus", {"action": "describe", "script": script})
            state["apiContracts"][script] = {"raw": raw, "checked": validate_contract(script, raw)}
        raw = observe("baseline")
        baseline = scene.snapshot(raw, reference, sex)
        actor = baseline["guard"]["actor"]
        scene.require(all(actor.get(k, "").lower() == "0x000cdd84" for k in ("race", "baseRace")),
                      "Fresh disposable born-beast fixture required")
        state["baseline"] = raw
        graph = call("stock-role-admission", "inspect", stock_expected["query"])
        state["stockRoleRaw"] = graph
        state["stockRoleAdmission"] = role.qualify(graph, raw, stock_expected)
        graph_qualified = True
        previous.update(sample=graph["sampleId"], time=graph["producerMonotonicNs"])
        for function in ("EnableAI", "SetRestrained"):
            before = observe(function + "-before")
            receipt = mutate(function, packet(reference, "Actor", function, [True]), before)
            receipt["after"] = observe(function + "-after")
            state["setupReceipts"].append(receipt)
        save()
        points = nominal.trajectory(baseline["position"])
        for phase, action in zip(nominal.PHASES, ("start", "stop", "restart")):
            transition(action)
            wait_until(clock() + spec["settleSeconds"])
            rows, receipts = [], []
            state["windows"][phase], state["positionReceipts"][phase] = rows, receipts
            started = clock()
            for index, wanted in enumerate(points):  # Exactly 25 points, 24 measured intervals.
                wait_until(started + index*spec["periodSeconds"])
                label = phase + "-position-" + str(index)
                before = observe(label + "-before")
                receipt = mutate(label, packet(reference, "ObjectReference", "SetPosition", wanted), before)
                wait_until(clock() + SETTLE_AFTER_POSITION)
                receipt["after"] = raw = observe(label + "-after")
                scene.reference_excitation(previous, baseline, wanted)
                if rows:
                    gap = (raw["producerMonotonicNs"]-rows[-1]["producerMonotonicNs"])/1e9
                    scene.require(abs(gap-spec["periodSeconds"]) <= spec["maximumJitterSeconds"],
                                  "Actual observed cadence outside nominal declaration")
                rows.append(raw)
                receipts.append(receipt)
                save()
    except BaseException as error:
        primary = error
        state["primaryError"] = {"type": type(error).__name__, "message": str(error)}
        if isinstance(error, Cancelled) or not isinstance(error, Exception):
            state["cancelled"] = state["quarantined"] = True
    finally:
        cleaning = True
        try:
            checkpoint()
            if baseline is not None and graph_qualified:
                cleanup()
        except BaseException as error:
            cleanup_error = error
            if isinstance(error, Cancelled) or not isinstance(error, Exception):
                state["cancelled"] = state["quarantined"] = True
            state.setdefault("cleanup", {}).update(error={"type": type(error).__name__, "message": str(error)},
                callbackFurtherMutationsForbidden=state["quarantined"], outerOwnedSessionTeardownRequired=True)
        try:
            save(full=True)
        except BaseException as error:
            state["finalPersistenceError"] = {"type": type(error).__name__, "message": str(error)}
            if primary is None and cleanup_error is None:
                cleanup_error = error
            save_after_error()  # Preserve the earlier primary/cleanup exception.
    if primary is not None:
        raise primary
    if cleanup_error is not None:
        raise cleanup_error
    diagnostic = nominal.score(state, subject_pins)
    appended_check = None
    try:
        (output / "diagnostic.json").write_text(json.dumps(diagnostic, indent=2), encoding="utf-8")
        scene.require(diagnostic["status"] == "sampled-provider-selective-motion" and not diagnostic["missingDrivers"],
                      "Nominal selective response unconfirmed; no runtime qualification")
        appended_check = {"name": spec["id"], "result": "passed", "observation": diagnostic,
            "scope": "sampled nominal technical contrast only; actual parent identity and runtime qualification unobserved"}
        session.state.setdefault("checks", []).append(appended_check)
        session.save()
    except BaseException as error:
        state["quarantined"] = True
        if isinstance(error, Cancelled) or not isinstance(error, Exception):
            state["cancelled"] = True
        state["terminalError"] = {"type": type(error).__name__, "message": str(error)}
        if appended_check is not None:
            checks = session.state.get("checks", [])
            for index, check in enumerate(checks):
                if check is appended_check:
                    del checks[index]  # Preserve every preexisting/unrelated check.
                    break
        save_after_error()
        raise
    return diagnostic
