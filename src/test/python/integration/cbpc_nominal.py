"""Pure proposal: sampled CBPC-selective motion under repeated actor translation.

No tool calls or launches. Expected XP32 parentage is NOT directly observed.
Old pulse contracts are untouched. Input-motion statistics are not physical energy.
"""
from __future__ import annotations
import math
import statistics
import struct
import cbpc_probe as controls
import cbpc_pulse as hierarchy
import fsmp_probe as scene

PHASES = ("active", "stopped", "restarted")
QUIET = ("NPC Root [Root]", *scene.INTERMEDIATES)


def protocol(*, ai_disabled=False):
    require(type(ai_disabled) is bool, "Explicit AI protocol boolean required")
    result = {"id": "claw-cbpc-animated-nominal-proposal/1", "samples": 25, "maximumSeconds": 160.,
            "periodSeconds": .85, "maximumJitterSeconds": .15, "settleSeconds": 2.,
            "motionComparabilityFraction": .25, "amplitude": .5,
            "signalFloors": 4., "maximumOffRatio": .25,
            "float32UncertaintyMultiplier": 8.,
            "baseTranslationFloor": 1e-4, "baseRotationFloor": 1e-5}
    if ai_disabled:
        result.update(id="claw-cbpc-ai-off-translation-proposal/1", amplitude=20.,
                      aiEnabled=False, disableAIAfterNormalStart=True)
    return result


def automatic_protocol():
    """Prospective human-origin contract; no provider call before first window."""
    return {**protocol(), "id": "claw-cbpc-human-origin-automatic-nominal/1",
            "initialControlMode": "uncontrolled"}


def human_subject(reference, sex, provider_name):
    """Finite fixture policy, separate from unchanged transform calculations."""
    reference = scene.form(reference)
    require(sex in ("female", "male"), "Explicit human-origin sex required")
    local, base, weight, scale = ((0x900, "0x000A2C91", 50., 1.) if sex == "female" else
                                 (0x901, "0x000A2C90", struct.unpack("<f", bytes.fromhex("ffffef41"))[0], 1.13))
    require(int(reference, 16) >> 24 != 0xFF and int(reference, 16) & 0xFFFFFF == local,
            "Authored persistent lifecycle reference required")
    require(type(provider_name) is str and 0 < len(provider_name) <= 128 and
            all(c not in provider_name for c in "\r\n\0"), "Actual finite provider display name required")
    return {"schemaVersion": 1, "reference": reference, "sex": sex,
            "sourcePlugin": "test_CLAW - Physics Probe.esp", "localReference": f"0x{local:08X}",
            "baseForm": base, "originalRace": "0x00013746", "currentRace": "0x000CDD84",
            "rawNPCWeight": weight, "expectedUniformScale": scale, "providerActorName": provider_name}


def admit_human_origin(row, subject, *, numeric=True):
    expected = human_subject(subject["reference"], subject["sex"], subject["providerActorName"])
    require(subject == expected, "Changed finite human-origin fixture policy")
    actor, identity = row["guard"]["actor"], row["guard"]["identity"]
    require(type(actor.get("sex")) is int and actor["sex"] == (subject["sex"] == "female") and
            identity["form"].casefold() == subject["reference"].casefold() and
            identity.get("sourcePlugin") == subject["sourcePlugin"] and
            identity.get("localFormId", "").casefold() == subject["localReference"].casefold() and
            actor.get("baseForm", "").casefold() == subject["baseForm"].casefold() and
            actor.get("baseRace", "").casefold() == subject["currentRace"].casefold() and
            actor.get("race", "").casefold() == subject["currentRace"].casefold(),
            "Original-human base/current wolf identity differs")
    if numeric:
        scale = subject["expectedUniformScale"]
        require(actor["weight"]["rawNPCWeight"] == subject["rawNPCWeight"], "Original NPC weight changed")
        require(abs(row["root"]["scale"] - scale) <= 1e-5 and abs(row["guard"]["scale"] - scale) <= 1e-5,
                "Declared human-origin actor/root scale differs")
        require(all(abs(node["local"]["scale"] - 1.) <= 1e-5 and
                    abs(node["world"]["scale"] - scale) <= 1e-5 for node in row["nodes"].values()),
                "Declared local/world node scale differs")


def admit_human_lifecycle(evidence, subject, final):
    """Original ancestry is captured evidence; SetRace changes both race fields."""
    require(evidence.get("completed") is True and evidence.get("unknown") is False and evidence.get("providerCalls") == [],
            "Completed provider-untouched lifecycle evidence required")
    labels = ["place-disabled", "enable-human", "restrain-human", "unequip-owned-outfit", "enable-human-ai", "first-wolf", "refresh", "human-return", "second-wolf", "node-update", "owned-save", "owned-load", "head-tracking-off"]
    require([r.get("label") for r in evidence.get("writes", [])] == labels and
            all(r.get("status") == "returned" for r in evidence["writes"]), "Known lifecycle completion sequence differs")
    binding = evidence.get("firstTransformBinding", {})
    require(binding.get("allDeclaredNodes") is True and binding.get("subject") == subject and
            binding.get("providerControlsBeforeThisPrefix") == [] and
            set(binding.get("ledger", {})) == set(scene.drivers(subject["sex"])) and
            all(type(r.get("insertions")) is int and r["insertions"] >= 1 and
                type(r.get("updates")) is int and r["updates"] >= 1 for r in binding["ledger"].values()),
            "First-transform binding diagnostics missing")
    source = evidence.get("humanSource", {})
    require(type(source.get("linkStatus")) is int and source["linkStatus"] in (0, 5) and type(source.get("appearanceStatus")) is str and
            (source["appearanceStatus"] == "human colours captured" or source["appearanceStatus"].startswith("record-hair-fallback:")),
            "Observed human source/status missing")
    witnesses = evidence.get("phaseWitnesses", {})
    names = ("initial-human", "enabled-human", "first-wolf", "refresh", "human-return", "second-wolf", "post-load")
    require(set(witnesses) == set(names), "Complete actual lifecycle phase witnesses required")
    previous = None
    for name in names:
        raw = witnesses[name]
        require(raw.get("ok") is True and raw.get("quality") == "complete" and len(raw.get("refs", [])) == 1,
                "Lifecycle witness incomplete")
        ref = raw["refs"][0]
        actor, identity = ref["actor"], ref["identity"]
        race = subject["originalRace"] if name in ("initial-human", "enabled-human", "human-return") else subject["currentRace"]
        require(identity.get("form", "").casefold() == subject["reference"].casefold() and
                identity.get("sourcePlugin") == subject["sourcePlugin"] and
                identity.get("localFormId", "").casefold() == subject["localReference"].casefold() and
                ref.get("baseForm", "").casefold() == subject["baseForm"].casefold() and actor.get("baseForm") == ref["baseForm"] and
                actor.get("race", "").casefold() == race.casefold() and actor.get("baseRace", "").casefold() == race.casefold() and
                type(actor.get("sex")) is int and actor["sex"] == (subject["sex"] == "female") and
                actor.get("weight", {}).get("rawNPCWeight") == subject["rawNPCWeight"],
                "Actual lifecycle base/sex/weight/current/base-race transition differs")
        require(ref.get("disabled") is (name == "initial-human") and
                ref.get("loaded3D") is (name != "initial-human"), "Lifecycle enabled/loaded boundary differs")
        if previous is not None:
            require(raw["sessionId"] == previous["sessionId"] and raw["producerMonotonicNs"] > previous["producerMonotonicNs"] and
                    (raw["loadGeneration"] > previous["loadGeneration"] if name == "post-load" else
                     raw["loadGeneration"] == previous["loadGeneration"] and raw["sampleId"] > previous["sampleId"]),
                    "Lifecycle witness replay/process change")
        previous = raw
    initial, loaded = witnesses["initial-human"], witnesses["post-load"]
    require(loaded["loadGeneration"] > initial["loadGeneration"] and
            loaded["loadGeneration"] == final["guard"]["generation"] and
            loaded["sessionId"] == final["guard"]["session"] and
            loaded["refs"][0]["identity"] == final["guard"]["identity"] and
            loaded["refs"][0]["rootIdentity"] == final["guard"]["root"] and
            loaded["sampleId"] < final["sample"] and loaded["producerMonotonicNs"] < final["time"],
            "Fresh postload root/epoch not reacquired")


def provider_ledger(data, nodes, subject):
    require(subject == human_subject(subject["reference"], subject["sex"], subject["providerActorName"]),
            "Changed finite provider-log subject")
    require(tuple(nodes) == scene.drivers(subject["sex"]), "Changed finite provider driver inventory")
    lines = data[:data.rfind(b"\n") + 1].decode("utf8", errors="strict").splitlines()
    base = subject["baseForm"][2:].lower()
    name = subject["providerActorName"] + " - " + subject["sex"].title() + " - Thing.update() "
    return {n: {"insertions": sum(x.startswith("Adding " + n + " to default list for " + base + " -> ") for x in lines),
                "updates": sum(x.startswith(name + n + " - Diff: ") for x in lines)} for n in nodes}


def selected_protocol(declared=None):
    """Immutable declared experiments; legacy remains the default."""
    if declared is None:
        return protocol()
    for expected in (protocol(), protocol(ai_disabled=True), automatic_protocol()):
        if (type(declared) is dict and declared.keys() == expected.keys() and
                all(type(declared[k]) is type(v) and declared[k] == v for k,v in expected.items())):
            return expected
    raise ValueError("Unknown or modified nominal protocol")


def require(value, message):
    if not value:
        raise ValueError(message)


def trajectory(origin, declared_protocol=None):
    spec = selected_protocol(declared_protocol)
    rows = [[origin[0] + spec["amplitude"]*math.sin(2*math.pi*i/12), origin[1], origin[2]] for i in range(spec["samples"])]
    rows[-1] = list(origin)
    return rows


def ulp32(value):
    require(math.isfinite(value), "Nonfinite transform component")
    if abs(value) < 2.0**-126:
        return 2.0**-149
    return 2.0**(math.frexp(abs(value))[1]-24)


def local_floor(transform, channel):
    base = protocol()["baseTranslationFloor" if channel == "translation" else "baseRotationFloor"]
    return max(base, 8*max(map(ulp32, transform[channel])))


def relative_floor(child, parent, channel):
    """Conservative quantization envelope; not calibrated sensor accuracy.

Inputs are copied native float32 transform fields. Sum rather than assume
cancellation; include rotation and parent-scale uncertainty in inverse transform.
"""
    scale = abs(parent["scale"])
    require(scale > 0, "Invalid parent scale")
    delta = [a-b for a,b in zip(child["translation"], parent["translation"])]
    if channel == "translation":
        errors = []
        for i in range(3):
            total = sum(abs(parent["rotationRowMajor"][j*3+i]) *
                        (ulp32(child["translation"][j])+ulp32(parent["translation"][j])) +
                        abs(delta[j])*ulp32(parent["rotationRowMajor"][j*3+i]) for j in range(3))/scale
            total += sum(abs(x) for x in delta)*ulp32(scale)/(scale*scale)
            errors.append(total)
        return max(1e-4, 8*max(errors))
    error = 3*(max(map(ulp32, child[channel])) + max(map(ulp32, parent[channel])))
    return max(1e-5, 8*error)


def stats(vectors):
    center = [statistics.mean(v[i] for v in vectors) for i in range(len(vectors[0]))]
    residual = [max(abs(x-y) for x,y in zip(v,center)) for v in vectors]
    return {"rms": math.sqrt(statistics.mean(x*x for x in residual)), "peak": max(residual)}


def motion_index(rows, name, channel):
    """Mean squared sampled component velocity; no mass/force/work interpretation."""
    terms = []
    for a,b in zip(rows,rows[1:]):
        dt=(b["time"]-a["time"])/1e9
        terms.append(sum(((y-x)/dt)**2 for x,y in zip(
            a["nodes"][name]["world"][channel], b["nodes"][name]["world"][channel])))
    return math.sqrt(statistics.mean(terms))


def score(document, expected_subject_pins, *, declared_protocol=None, human_origin=None):
    spec=selected_protocol(declared_protocol)
    require(document.get("schemaVersion")==1 and document.get("protocol")==spec, "Changed nominal contract")
    require(document.get("subjectPins")==expected_subject_pins and bool(expected_subject_pins), "Subject source/provider pins differ")
    require(document.get("skeletonSha256")==hierarchy.XP32_SHA256, "Wrong XP32 skeleton")
    reference,sex=scene.form(document["reference"]),document["sex"]
    parents={n:p[0] for n,p in hierarchy.parent_paths(sex).items()}
    require(document.get("expectedParents")==parents, "Changed pinned expected parent paths")
    baseline=previous=scene.snapshot(document["baseline"],reference,sex)
    automatic = spec == automatic_protocol()
    if automatic:
        require(human_origin is not None and document.get("humanOrigin") == human_origin,
                "Explicit original-human subject contract required")
        admit_human_origin(baseline, human_origin)
        admit_human_lifecycle(document.get("humanLifecycle", {}), human_origin, baseline)
        require(document.get("providerControlBeforeInitial") == [] and
                set(document["receipts"]) == {"stop", "restart"}, "No initial provider control is permitted")
    else:
        require(human_origin is None, "Legacy contract cannot adopt a human-origin subject")
        require(all(baseline["guard"]["actor"].get(k,"").lower()=="0x000cdd84" for k in ("race","baseRace")), "Born-beast fixture required")
        require(abs(baseline["root"]["scale"]-1.)<=1e-5 and abs(baseline["guard"]["scale"]-1.)<=1e-5, "Nominal unit scale required")
    origin=baseline["position"]
    root_offset=[x-y for x,y in zip(baseline["root"]["translation"],origin)]

    def consume(raw):
        nonlocal previous
        row=scene.snapshot(raw,reference,sex)
        require(row["guard"]==baseline["guard"], "Actor/root/source incarnation changed")
        require(row["sample"]>previous["sample"] and row["time"]>previous["time"], "Nonadvancing observation")
        require(scene.max_delta(row["angles"],baseline["angles"])<=1e-5, "Unexpected actor rotation")
        require(scene.max_delta(row["root"]["rotationRowMajor"],baseline["root"]["rotationRowMajor"])<=1e-5 and
                abs(row["root"]["scale"]-baseline["root"]["scale"])<=1e-5, "Unexpected root rotation/scale")
        require(scene.max_delta([x-y for x,y in zip(row["root"]["translation"],row["position"])],root_offset)<=.025,
                "Reference and root trajectories disagree")
        for name in scene.node_names(sex):
            for space in ("local","world"):
                require(abs(row["nodes"][name][space]["scale"]-baseline["nodes"][name][space]["scale"])<=1e-5,
                        "Node scale changed")
        for name in scene.node_names(sex):
            for space in ("local","world"):
                for value in (*row["nodes"][name][space]["translation"], *row["nodes"][name][space]["rotationRowMajor"]):
                    require(struct.unpack("<f",struct.pack("<f",value))[0]==value,
                            "Transform precision differs from declared native float32 fields")
        previous=row
        return row

    # Completed setup calls are evidence of requests, not an unavailable AI-state getter.
    setup=document["setupReceipts"]
    require(len(setup)==2, "Missing setup receipts")
    for receipt,function in zip(setup,("EnableAI","SetRestrained")):
        request={"action":"call","script":"Actor","function":function,
                 "self":{"form":reference},"args":[True],"timeoutMs":8000}
        controls.completed(receipt,request)

    plan=controls.prepare(reference,sex)
    windows={};cadence={};composition={}
    for phase,action in zip(PHASES,((None if automatic else "start"),"stop","restart")):
        receipts=document["receipts"][action] if action is not None else []
        require(len(receipts)==(len(plan["calls"][action]) if action is not None else 0), "Missing driver control receipt")
        for receipt,request in zip(receipts,plan["calls"][action] if action is not None else []):
            consume(receipt["before"]);controls.completed(receipt,request);consume(receipt["after"])
        if phase=="active" and spec.get("disableAIAfterNormalStart"):
            freeze=document["aiFreezeReceipt"]
            normal_start_after=previous["time"]
            freeze_before=consume(freeze["before"])
            require((freeze_before["time"]-normal_start_after)/1e9>=spec["settleSeconds"],
                    "Normal AI-on settle before AI-off not observed")
            controls.completed(freeze,{"action":"call","script":"Actor","function":"EnableAI",
                "self":{"form":reference},"args":[False],"timeoutMs":8000})
            consume(freeze["after"])
        raw=document["windows"][phase]
        require(len(raw)==25, "Exactly25 samples required")
        require((raw[0]["producerMonotonicNs"]-previous["time"])/1e9>=spec["settleSeconds"], "Phase settle not observed")
        moves=document["positionReceipts"][phase]
        require(type(moves) is list and len(moves)==len(raw), "Missing actor-position receipts")
        rows=[]
        for receipt,item,wanted in zip(moves,raw,trajectory(origin,spec)):
            consume(receipt["before"])
            controls.completed(receipt,{"action":"call","script":"ObjectReference","function":"SetPosition",
                "self":{"form":reference},"args":wanted,"timeoutMs":8000})
            require(receipt.get("after")==item, "Window is not the position receipt readback")
            rows.append(consume(item))
        windows[phase]=rows
        for row,wanted in zip(rows,trajectory(origin,spec)):
            require(scene.max_delta(row["position"],wanted)<=.025, "Actual trajectory differs from declaration")
        gaps=[(b["time"]-a["time"])/1e9 for a,b in zip(rows,rows[1:])]
        require(all(abs(g-.85)<=.15 for g in gaps), "Nominal sample cadence outside declaration")
        cadence[phase]={"mean":statistics.mean(gaps),"span":sum(gaps)}
        for name,parent in parents.items():
            for row in rows:
                own=row["nodes"][name];par=row["nodes"][parent]
                rel=scene.relative(own["world"],par["world"])
                for channel in scene.FLOORS:
                    bound=max(relative_floor(own["world"],par["world"],channel),local_floor(own["local"],channel))
                    error=scene.max_delta(rel[channel],own["local"][channel])
                    require(error<=bound, "Expected-parent transform composition inconsistent: "+name)
                    composition[name]=max(composition.get(name,0.),error/bound)

    means=[cadence[p]["mean"] for p in PHASES]
    require(max(means)-min(means)<=.25*min(means), "Unequal phase sampling cadence")
    all_rows=[r for p in PHASES for r in windows[p]]
    for name in QUIET:
        for channel in scene.FLOORS:
            bound=max(local_floor(r["nodes"][name]["local"],channel) for r in all_rows)
            require(stats([r["nodes"][name]["local"][channel] for r in all_rows])["peak"]<=bound,
                    "Independent own-local control changed: "+name)

    inputs={}
    for name in dict.fromkeys(scene.anchors(sex).values()):
        inputs[name]={}
        for channel in scene.FLOORS:
            energies=[motion_index(windows[p],name,channel) for p in PHASES]
            # Translation provides declared excitation; rotation may be consistently quiet.
            floor=max(local_floor(r["nodes"][name]["world"],channel) for r in all_rows)/.7
            if max(energies)>4*floor:
                require(min(energies)>0 and max(energies)-min(energies)<=.25*min(energies),
                        "Incomparable actual kinematic input: "+name)
            elif channel=="translation":
                raise ValueError("Insufficient measured kinematic input: "+name)
            inputs[name][channel]=dict(zip(PHASES,energies))

    channels={};missing=[]
    for name,parent in parents.items():
        passes=[];evidence={}
        for channel in scene.FLOORS:
            evidence[channel]={}
            for space in ("local","expectedParentWorld"):
                values={};floor=0.
                for phase in PHASES:
                    vectors=[]
                    for row in windows[phase]:
                        own,par=row["nodes"][name],row["nodes"][parent]
                        if space=="local":
                            vectors.append(own["local"][channel]);floor=max(floor,local_floor(own["local"],channel))
                        else:
                            vectors.append(scene.relative(own["world"],par["world"])[channel])
                            floor=max(floor,relative_floor(own["world"],par["world"],channel))
                    values[phase]=stats(vectors)
                on=min(values[p]["rms"] for p in ("active","restarted"))
                passed=on>4*floor and values["stopped"]["peak"]<=floor and values["stopped"]["rms"]<=.25*on
                evidence[channel][space]={"floor":floor,"phases":values,"passed":passed}
            if all(evidence[channel][s]["passed"] for s in ("local","expectedParentWorld")):passes.append(channel)
        channels[name]={"expectedParent":parent,"passingChannels":passes,"evidence":evidence}
        if not passes:missing.append(name)
    cleanup=document["cleanup"]
    require(cleanup.get("providerState")=="unknown" and cleanup.get("providerRestorationClaimed") is False,
            "Unknown provider state must not be claimed restored")
    restored=cleanup["restoreReference"]
    consume(restored["before"])
    controls.completed(restored,{"action":"call","script":"ObjectReference","function":"SetPosition",
                                "self":{"form":reference},"args":origin,"timeoutMs":8000})
    after=consume(restored["after"])
    require(scene.max_delta(after["position"],origin)<=.025, "Owned reference origin not restored")
    disposal=cleanup["disposeFixture"]
    consume(disposal["before"])
    controls.completed(disposal,{"action":"call","script":"ObjectReference","function":"Disable",
                                "self":{"form":reference},"args":[False],"timeoutMs":8000})
    raw=disposal["after"];refs=raw.get("refs",[])
    require(raw.get("ok") is True and raw.get("quality")=="complete" and len(refs)==1 and
            raw.get("sessionId")==baseline["guard"]["session"] and
            raw.get("loadGeneration")==baseline["guard"]["generation"] and
            raw.get("sampleId",0)>previous["sample"] and raw.get("producerMonotonicNs",0)>previous["time"],
            "Disposal observation unavailable or stale")
    require((raw["producerMonotonicNs"]-baseline["time"])/1e9<=spec["maximumSeconds"], "Aggregate nominal deadline exceeded")
    require(refs[0].get("identity")==baseline["guard"]["identity"] and refs[0].get("disabled") is True and
            refs[0].get("deleted") is False and refs[0].get("baseForm")==baseline["guard"]["actor"]["baseForm"],
            "Owned fixture disabled readback missing/wrong")
    return {"status":"sampled-provider-selective-motion" if not missing else "unconfirmed",
            "missingDrivers":missing,"channels":channels,"cadence":cadence,"inputMotionIndex":inputs,
            "maximumCompositionErrorInFloors":composition,"actualParentIdentityObserved":False,
            "fixtureCleanupVerified":True,"fixtureCleanupScope":"origin-and-disabled-only; crosshair/exit/preimages are outer transport/Session gates",
            "providerStateRestored":False,"bindingInventoryObserved":False,"physicsPhaseObserved":False,"runtimeQualified":False,
            "claim":"Pinned-expected-parent-relative sampled nominal operability only"}
