"""Pure current-source admission/scoring. No native math, storage write or transport."""
from __future__ import annotations
import copy,hashlib,json,math,struct

MORPH = "Breasts"
TARGET = "CLAWTorsoBreastSize"
OWN = "CLAW.Distribution"
TAGS = ("CLAWTestMixedCBBE", "CLAWTestMixedBHUNP")
FAMILIES = {TAGS[0]: "CLAW.CBBE.2.0.3.Geometry1", TAGS[1]: "CLAW.BHUNP.3.34.AdvancedV4"}


def require(value, message):
    if not value: raise AssertionError(message)


def bits(value):
    require(type(value) in (int,float) and math.isfinite(value), "Finite numeric coefficient required")
    try: return struct.pack("<f",value)
    except (OverflowError,struct.error): raise AssertionError("Finite float32 coefficient required") from None


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def rows(record):
    require(record.get("available") is True and type(record.get("present")) is bool and type(record.get("keys")) is list,
            "Complete observed morph row required")
    bits(record["value"])
    result={}
    for row in record["keys"]:
        key=row.get("key")
        require(type(key) is str and key and row.get("available") is True and row.get("present") is True,
                "Available individual keyed coefficient required")
        folded=key.casefold()
        require(folded not in result,"Case-insensitive key collision")
        bits(row["value"]);result[folded]=(key,bits(row["value"]))
    require(not result or record["present"] is True,"Absent name cannot have enumerated keys")
    return result


def keys_for_run(run_id):
    require(type(run_id) is str and run_id and all(32<ord(c)<127 for c in run_id),"Printable owned run ID required")
    keys={role:f"CLAW.Test.NonzeroMixed.{run_id}.{role}" for role in ("Source","Foreign")}
    require(all(len(k)<=128 for k in keys.values()) and len({k.casefold() for k in keys.values()})==2,
            "Two bounded distinct test keys required")
    return keys


def collision_check(measured,keys):
    require(len({k.casefold() for k in keys.values()})==2 and OWN.casefold() not in {k.casefold() for k in keys.values()},
            "Owned keys overlap")
    for record in measured.values():
        require(not set(rows(record)) & {k.casefold() for k in keys.values()},"Test key already exists or aliases existing key")


def _preserve_record(name,current,initial,keys,expected_owned,*,is_source,is_target):
    measured={name:current};allowed={k.casefold() for k in keys.values()}
    a,b=rows(measured[name]),rows(initial)
    ignored=allowed | ({OWN.casefold()} if is_target else set())
    require({k:v for k,v in a.items() if k not in ignored}=={k:v for k,v in b.items() if k not in ignored},
            "Foreign key changed: "+name)
    test={k:v for k,v in a.items() if k in allowed}
    expected={keys[role].casefold():(keys[role],bits(value)) for role,value in expected_owned.items()} if name==MORPH else {}
    require(test==expected,"Owned pair/value/presence differs: "+name)
    if is_source:
        # Additive mode is pinned; the aggregate is nevertheless independently observed.
        expected_value=initial["value"]+sum(expected_owned.values()) if name==MORPH else initial["value"]
        require(bits(measured[name]["value"])==bits(expected_value),"Observed source aggregate differs: "+name)
        if name!=MORPH: require(measured[name]["present"]==initial["present"],"Source presence changed")
    return True


def preserve_pair(current,initial,keys,expected_owned):
    """Only the Breasts storage row; this does not prove other morphs unchanged."""
    return _preserve_record(MORPH,current,initial,keys,expected_owned,is_source=True,is_target=False)


def preserve(measured,original,keys,expected_owned,source_names,targets):
    """Allow only two exact test pairs on Breasts and CLAW-owned target changes."""
    require(set(measured)==set(original)==set(source_names)|set(targets),"Full source/31-target catalog required")
    require(len(targets)==len(set(targets))==31,"Exactly31 public targets required")
    for name,initial in original.items():
        _preserve_record(name,measured[name],initial,keys,expected_owned,is_source=name in source_names,is_target=name in targets)
    return True


def current_inputs(sources,baseline,source_names):
    require(set(sources)==set(source_names),"Complete fresh source map required")
    values={name:sources[name]["value"] for name in source_names}
    for record in sources.values(): rows(record)
    require(baseline["stage"]=="human", "Original human baseline required")
    require(all(row.get("available") is True for row in baseline["traits"].values()),"Complete retained human traits required")
    values.update({name:row["value"] for name,row in baseline["traits"].items()})
    for value in values.values():bits(value)
    bits(baseline["weightRaw"])
    return {"values":values,"weightRaw":baseline["weightRaw"],"humanBaselineSha256":digest(baseline),
            "sourceRowsSha256":digest(sources),"basis":"fresh independently observed SKEE source aggregates + immutable original human traits/weight"}


def target_comparison(measured,prediction,targets,stage):
    require(set(prediction["outputs"])==set(targets) and len(targets)==31,"Native prediction must cover all31 targets")
    result={}
    for name in targets:
        actual=rows(measured[name]);own=actual.get(OWN.casefold());expected=prediction["outputs"][name] if stage=="beast" else 0.0
        value=struct.unpack("<f",own[1])[0] if own else 0.0
        result[name]={"expected":expected,"ownValue":value,"ownKeyPresent":own is not None,
                      "float32Exact":bits(value)==bits(expected),"zeroKeyAbsent":expected!=0 or own is None}
    mismatches=sum(not(row["float32Exact"] and row["zeroKeyAbsent"]) for row in result.values())
    return {"publicTargetCount":31,"targets":result,"mismatchCount":mismatches,"matches":mismatches==0}


def score(measured,prediction,inputs,targets,stage):
    comparison=target_comparison(measured,prediction,targets,stage)
    return {"basis":inputs["basis"],"inputs":copy.deepcopy(inputs),"nativePrediction":copy.deepcopy(prediction),
            "stage":stage,**comparison,"symbolicOrCounterfactual":False,"renderedVertexClaim":False}


def marker_inputs(fresh_breasts,baseline,source_names):
    """Conditional provisional inputs; never claim a freshly observed full source vector."""
    require(MORPH in source_names and set(baseline["sources"])==set(source_names),"Complete retained human source baseline required")
    rows(fresh_breasts)
    retained={name:baseline["sources"][name] for name in source_names if name!=MORPH}
    for record in retained.values():rows(record)
    values={name:record["value"] for name,record in retained.items()};values[MORPH]=fresh_breasts["value"]
    require(baseline["stage"]=="human","Original human baseline required")
    require(all(row.get("available") is True for row in baseline["traits"].values()),"Complete retained human traits required")
    values.update({name:row["value"] for name,row in baseline["traits"].items()})
    for value in values.values():bits(value)
    bits(baseline["weightRaw"])
    return {"classification":"PROVISIONAL","fullSourceVectorFresh":False,"freshSourceNames":[MORPH],
            "retainedSourceNames":list(retained),"values":values,"weightRaw":baseline["weightRaw"],
            "humanBaselineSha256":digest(baseline),"retainedSourceRowsSha256":digest(retained),"freshBreastsRowSha256":digest(fresh_breasts),
            "basis":"PROVISIONAL fresh Breasts + immutable retained other human sources/traits/weight; full-source audit pending"}


def marker_score(measured,original,keys,expected_owned,prediction,inputs,targets,stage):
    require(inputs.get("classification")=="PROVISIONAL" and inputs.get("fullSourceVectorFresh") is False,"Explicit provisional marker inputs required")
    require(set(measured)=={MORPH}|set(targets) and len(targets)==31,"Exact32-row marker required")
    preserve_pair(measured[MORPH],original[MORPH],keys,expected_owned)
    for name in targets:_preserve_record(name,measured[name],original[name],keys,expected_owned,is_source=False,is_target=True)
    comparison=target_comparison(measured,prediction,targets,stage)
    return {"classification":"PROVISIONAL","fullSourceVectorFresh":False,"fullAuditRequiredBeforeNextPlannedMutation":True,
            "basis":inputs["basis"],"inputs":copy.deepcopy(inputs),"nativePrediction":copy.deepcopy(prediction),
            "stage":stage,**comparison,"renderedVertexClaim":False}


def compare_vectors(a,b,targets,*,equal):
    changed=[name for name in targets if bits(a["outputs"][name])!=bits(b["outputs"][name])]
    require((not changed) if equal else changed==[TARGET],"Unexpected changed target vector")
    return changed


# Archived replay adapters below do not implement the native matrix evaluator.
SUFFIXES = ("HumanNonzero", "WolfInitial", "WolfChanged", "LoadedWolf",
            "WolfDeletedControl", "ReturnedHuman", "CleanHuman")


def observed_rows(packets, identity, names):
    """Decode complete retained Observer packets without treating a projection as an RPC."""
    result = {}
    previous = -1
    for raw in packets:
        require(raw.get("quality") == "complete" and raw.get("phase") == "skse_main_thread_task",
                "Complete main-thread observation required")
        require(type(raw.get("sampleId")) is int and raw["sampleId"] > previous,
                "Fresh ordered provider samples required")
        previous = raw["sampleId"]
        require(len(raw["refs"]) == len(raw["skee"]) == 1, "Exactly one observed actor required")
        ref, sample = raw["refs"][0], raw["skee"][0]
        provider = sample["provider"]
        require(sample["status"] == provider["status"] == "available" and provider["interfaceVersion"] == 5,
                "Available SKEE interface5 required")
        coherence = {"sessionId": raw["sessionId"], "loadGeneration": raw["loadGeneration"],
                     "identity": ref["identity"], "rootIdentity": ref["rootIdentity"],
                     "actor": ref["actor"], "providerEpoch": provider["interfaceEpoch"]}
        require(coherence == identity and sample["identity"] == ref["identity"],
                "Provider actor/world/root identity differs")
        for item in sample["morphs"]:
            name = item["name"]
            require(name not in result, "Duplicate observed morph name")
            presence, aggregate, keys = item["namePresence"], item["aggregate"], item["keys"]
            require(item["status"] == presence["status"] == aggregate["status"] == keys["status"] == "available",
                    "Unavailable observed morph component")
            require(keys["providerTraversalCompleted"] is True and
                    all(keys[k] is False for k in ("truncated", "invalidKey", "nonFinite", "captureFailure")) and
                    keys["callbackCount"] == keys["retainedCount"] == len(keys["entries"]),
                    "Incomplete provider key traversal")
            records = []
            for row in keys["entries"]:
                require(row["status"] == "available", "Unavailable provider key")
                records.append({"key": row["key"], "available": True, "present": True, "value": row["value"]})
            result[name] = {"available": True, "present": presence["present"],
                            "value": aggregate["value"], "keys": records}
            rows(result[name])
    require(set(result) == set(names), "Exact observed source/target catalog required")
    return result


def expected_pair(tag, suffix):
    if suffix == "CleanHuman" or (tag == TAGS[0] and suffix in ("WolfDeletedControl", "ReturnedHuman")):
        return {}
    return {"Foreign": .0625, "Source": .375 if tag == TAGS[0] and suffix in ("WolfChanged", "LoadedWolf") else .125}


def _projected_inputs(rebuilt, recorded, original_digest):
    # Only machine paths in the original baseline were omitted by the bundle.
    # Its original digest is a retained reference, NOT recomputed from redaction.
    require(recorded["humanBaselineSha256"] == original_digest, "Original baseline digest reference differs")
    require({k: v for k, v in rebuilt.items() if k != "humanBaselineSha256"} ==
            {k: v for k, v in recorded.items() if k != "humanBaselineSha256"},
            "Rebuilt source inputs differ")
    return recorded


def replay(bundle):
    """Replay storage/numeric projections against recorded native predictions.

    This does not execute native CLI math, re-admit modules, verify live file
    restoration, or observe CPU/GPU vertex deformation.
    """
    require(bundle["schema"] == "claw-actual-mixed-source-replay/1", "Reviewed mixed-source schema required")
    require(bundle["projection"]["wholeBaselineDigestRecomputed"] is False and
            bundle["projection"]["nativeEvaluatorReexecuted"] is False, "Explicit projection limits required")
    targets, sources = bundle["targets"], bundle["sources"]
    require(len(targets) == len(set(targets)) == 31 and MORPH in sources, "Complete target/source catalogs required")
    require(bundle["keys"] == keys_for_run(bundle["sourceRun"]), "Run-owned key names differ")
    keys = bundle["keys"]
    captures = bundle["captures"]
    require(len(captures) == 14 and {c["label"] for c in captures} ==
            {tag + suffix for tag in TAGS for suffix in SUFFIXES}, "All14 distinct full captures required")
    predictions, generations = {}, {}
    for tag in TAGS:
        baseline, original = bundle["baselines"][tag], bundle["originalRows"][tag]
        collision_check(original, keys)
        predictions[tag], generations[tag] = {}, {}
        for suffix in SUFFIXES:
            capture = next(c for c in captures if c["label"] == tag + suffix)
            actor, matrix, block = capture["actor"], capture["matrix"], capture["currentSourcePrediction"]
            stage = "human" if suffix in ("HumanNonzero", "ReturnedHuman", "CleanHuman") else "beast"
            require(capture["legacyFieldsUnmodified"] is True and capture["renderedVertexClaim"] is False,
                    "Separate current-source block and render limit required")
            require(matrix["selectedFamily"]["value"] == FAMILIES[tag] and
                    matrix["selectedFamily"]["matchesRequested"] is True, "Observed selected family differs")
            require(matrix["subjectDiagnostics"]["status"] == (5 if stage == "human" else 2) and
                    matrix["subjectDiagnostics"]["error"] == "", "Observed subject status/error differs")
            require(suffix == "HumanNonzero" or matrix["traitsPreserved"] is True and matrix["weightPreserved"] is True,
                    "Retained human traits/weight differ")
            identity = actor["identity"]
            require(identity["actor"]["baseForm"] == baseline["identity"]["actor"]["baseForm"] and
                    identity["sessionId"] == baseline["identity"]["sessionId"] and
                    identity["actor"]["sex"] == 1, "Actor/base/session identity differs")
            require(identity["actor"]["race"] == ("0x000CDD84" if stage == "beast" else baseline["identity"]["actor"]["race"]),
                    "Observed current race differs")
            require(bits(actor["weightRaw"]) == bits(baseline["weightRaw"]), "Actual weight changed")
            measured = {**matrix["sources"], **{name: {"available": True, "present": row["namePresent"],
                         "value": row["aggregate"], "keys": row["keys"]} for name, row in matrix["targets"].items()}}
            require(observed_rows(capture["providerObservations"], identity, set(sources) | set(targets)) == measured,
                    "Raw post-prediction provider rows differ from captured matrix rows")
            preserve(measured, original, keys, expected_pair(tag, suffix), sources, targets)
            inputs = _projected_inputs(current_inputs(matrix["sources"], baseline, sources), block["inputs"],
                                       bundle["originalBaselineDigests"][tag])
            rebuilt = score(measured, block["nativePrediction"], inputs, targets, stage)
            require(rebuilt == block and rebuilt["matches"] is True, "Full31 float32 capture differs")
            predictions[tag][suffix] = block["nativePrediction"]
            generations[tag][suffix] = identity["loadGeneration"]
        require(generations[tag]["LoadedWolf"] > generations[tag]["WolfChanged"] and
                generations[tag]["ReturnedHuman"] == generations[tag]["LoadedWolf"], "Save/load generation evidence differs")
        compare_vectors(predictions[tag]["WolfChanged"], predictions[tag]["LoadedWolf"], targets, equal=True)
    compare_vectors(predictions[TAGS[0]]["WolfInitial"], predictions[TAGS[0]]["WolfChanged"], targets, equal=False)
    compare_vectors(predictions[TAGS[1]]["WolfInitial"], predictions[TAGS[1]]["WolfChanged"], targets, equal=True)
    compare_vectors(predictions[TAGS[0]]["WolfDeletedControl"], predictions[TAGS[0]]["CleanHuman"], targets, equal=True)
    compare_vectors(predictions[TAGS[1]]["WolfChanged"], predictions[TAGS[1]]["WolfDeletedControl"], targets, equal=True)
    for name in ("automatic-changed", "automatic-empty"):
        interval, marker, ready = bundle["intervals"][name], bundle["markers"][name], bundle["fullReady"][name]
        require(abs(interval["deadlineMonotonic"] - interval["startedMonotonic"] - 30) < 1e-6 and
                marker["deadlineMonotonic"] == interval["deadlineMonotonic"], "Original30 reaction budget differs")
        require(marker["classification"] == "PROVISIONAL" and marker["fullSourceVectorFresh"] is False,
                "Provisional marker mislabeled as full proof")
        require(set(marker["actors"]) == set(ready["actors"]) == set(TAGS), "Both actor barriers required")
        for tag in TAGS:
            observation = marker["actors"][tag]
            require(len(observation["providerObservations"]) == 1, "Marker must retain its one32-row RPC")
            measured = observed_rows(observation["providerObservations"], observation["identity"], [MORPH, *targets])
            block, baseline = observation["provisionalMarker"], bundle["baselines"][tag]
            require("symbolicOrCounterfactual" not in block, "Full proof flag falsely attributed to marker")
            inputs = _projected_inputs(marker_inputs(measured[MORPH], baseline, sources), block["inputs"],
                                       bundle["originalBaselineDigests"][tag])
            owned = {} if name == "automatic-empty" and tag == TAGS[0] else {
                "Foreign": .0625, "Source": .375 if tag == TAGS[0] else .125}
            require(marker_score(measured, bundle["originalRows"][tag], keys, owned,
                    block["nativePrediction"], inputs, targets, "beast") == block and block["matches"] is True,
                    "Provisional32-row marker differs")
            full = ready["actors"][tag]
            require(full["identity"] == observation["identity"] and full["subject"] ==
                    {"status": 2, "error": "", "selectedFamily": FAMILIES[tag]},
                    "Full barrier identity/status/family differs")
            packets = full["providerObservations"]
            require(len(packets) == 8, "Both full118-row observations required")
            before = observed_rows(packets[:4], full["identity"], set(sources) | set(targets))
            after = observed_rows(packets[4:], full["identity"], set(sources) | set(targets))
            require(before == after, "Full source/target rows changed across prediction")
            preserve(after, bundle["originalRows"][tag], keys, owned, sources, targets)
            block = full["currentSourcePrediction"]
            inputs = _projected_inputs(current_inputs({s: after[s] for s in sources}, baseline, sources), block["inputs"],
                                       bundle["originalBaselineDigests"][tag])
            require(score(after, block["nativePrediction"], inputs, targets, "beast") == block and block["matches"] is True,
                    "Mandatory full current-source barrier differs")
    operations = bundle["operations"]
    labels = [row["label"] for row in operations]
    wanted = [f"{tag}:{role}:initial" for tag in TAGS for role in ("Foreign", "Source")]
    wanted += [TAGS[0] + ":Source:update", TAGS[0] + ":Source:clear", TAGS[0] + ":Foreign:clear",
               TAGS[1] + ":Source:clear", TAGS[1] + ":Foreign:clear"]
    require([label for label in labels if not label.startswith("semantic:")] == wanted,
            "Exactly nine ordered source operations required")
    require(labels.count("semantic:save-once") == labels.count("semantic:load-once") == 1,
            "One owned save/load required")
    require(labels[labels.index(TAGS[0] + ":Source:update") + 1] == "semantic:save-once" and
            labels[labels.index(TAGS[0] + ":Foreign:clear") + 1] == "semantic:" + TAGS[0] + "-human",
            "Unexpected mutation during automatic read-only interval")
    for row in operations:
        if row["label"].startswith("semantic:"): continue
        tag, role, action = row["label"].split(":")
        request = row["request"]
        require(request["bindingId"] == ("source_clear" if action == "clear" else "source_set") and
                request["args"][1:3] == [MORPH, keys[role]], "Unexpected source operation request")
        if action != "clear":
            require(bits(request["args"][3]) == bits(.375 if action == "update" else .0625 if role == "Foreign" else .125),
                    "Unexpected source operation value")
    for tag in TAGS:
        pair = bundle["intermediateClear"][tag]
        require(pair["expectedOwned"] == {"Foreign": .0625}, "Intermediate single remaining key evidence required")
        preserve_pair(pair["sourceRows"][MORPH], bundle["originalRows"][tag][MORPH], keys, pair["expectedOwned"])
    completion = bundle["completion"]
    require(completion["passed"] is True and completion["unknownMutation"] is False and completion["intent"] is None and
            completion["sourceMutationCount"] == 9 and all(not row for row in completion["ownedPairs"].values()),
            "Known completed operation ledger required")
    return {"status": "recorded-mixed-source-storage-and-numeric-replay-passed", "fullCaptures": 14,
            "targetsPerCapture": 31, "provisionalMarkers": 4, "mandatoryFullActorBarriers": 4,
            "sourceOperations": 9, "nativeEvaluatorReexecuted": False,
            "liveRestorationReverified": False, "renderedVertexClaim": False}
