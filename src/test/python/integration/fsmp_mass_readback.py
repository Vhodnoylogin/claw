"""Pure paused WORLD/token/mass verification from externally selected game evidence.

No game, filesystem write, clock, transport or simulation occurs in these functions.
The caller must separately bind actual owned PID/window nonce and fresh fixture authority.
The sole native snapshot validator is src/test/cpp/fsmp_step_witness/validate_snapshot.py.
Math matches the frozen checker exercised by the18November parameter diagnostic;
module imports alone adapt it to the maintained test-source layout.
"""
from pathlib import Path
import importlib.util

if __package__:
    from . import fsmp_probe as probe, fsmp_cached_world as cached
else:
    import fsmp_probe as probe
    import fsmp_cached_world as cached

_validator = Path(__file__).resolve().parents[4] / "src/test/cpp/fsmp_step_witness/validate_snapshot.py"
_spec = importlib.util.spec_from_file_location("claw_fsmp_mass_witness_snapshot", _validator)
witness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(witness)

P1 = ("NPC L Breast P1", "NPC R Breast P1")

def one(raw, native, reference, base, expected_inverse_mass):
    if set(expected_inverse_mass) != set(P1):
        raise ValueError("Exact bilateral P1 expectation required")
    row = probe.snapshot(raw, reference, "female")
    actor = row["guard"]["actor"]
    cached.require(actor["baseForm"] == base and actor["race"] == "0x000CDD84" and
                   actor["baseRace"] == "0x000CDD84", "Actual female/base/wolf identity differs")
    cached.require(abs(row["guard"]["scale"]-1.) <= 1e-5 and abs(row["root"]["scale"]-1.) <= 1e-5 and
                   all(abs(v[s]["scale"]-1.) <= 1e-5 for v in row["nodes"].values() for s in ("local", "world")),
                   "Mass10/20 expectation requires actual unit actor/root/local/WORLD scales")
    cached.require(native["status"] == "ready", "Ready native snapshot required")
    witness.validate_window(native["sample"]["objectWindow"], native["sample"]["loadEpoch"])
    cached.paused_signature(native)
    window = native["sample"]["objectWindow"]
    match = cached.paused_match(row, window, "female")
    cached.require(match["status"] == "unique-paused-dynamic11-match", "Unique injective11-role WORLD mapping unavailable")
    objects = {v["token"]: v for v in window["objects"]}
    found = {}
    for item in match["dynamicBodies"]:
        if item["node"] not in P1:
            continue
        token = item["candidates"][0]["token"]
        obj = objects[token]
        poses = {key: obj[key] for key in ("initialPre", "lastPre", "lastPost")}
        expected = expected_inverse_mass[item["node"]]
        cached.require(type(expected) in (int, float) and expected in (10., 20.), "Explicit diagnostic mass expectation required")
        cached.require(all(p["rigidBody"] is True and p["flags"] & 3 == 0 and p["inverseMass"] == expected
                           for p in poses.values()), "Associated P1 inverse mass/flags differ")
        found[item["node"]] = {"token": token, "expectedInverseMass": expected,
                              "observedInverseMass": {k: p["inverseMass"] for k,p in poses.items()},
                              "worldMatch": item["candidates"][0]}
    cached.require(set(found) == set(P1), "Missing bilateral P1 readback")
    return row, {"p1": found, "mapping": match, "windowNonce": window["nonce"]}

def pair(world_a, world_b, native_a, native_b, *, reference, base, expected_inverse_mass):
    cached.require(cached.paused_signature(native_a) == cached.paused_signature(native_b),
                   "Paused counters/lastPost/object metadata changed")
    cached.require(native_a["pid"] == native_b["pid"] and native_a["qpcFrequency"] == native_b["qpcFrequency"] and
                   native_b["sample"]["sampledQpc"] > native_a["sample"]["sampledQpc"],
                   "Native process/clock progression unavailable")
    a, ma = one(world_a, native_a, reference, base, expected_inverse_mass)
    b, mb = one(world_b, native_b, reference, base, expected_inverse_mass)
    cached.require(a["guard"] == b["guard"] and b["sample"] > a["sample"] and b["time"]-a["time"] >= 200_000_000,
                   "Actor/root/world identity changed or producer progression below.2s")
    cached.require([ma["p1"][n]["token"] for n in P1] == [mb["p1"][n]["token"] for n in P1], "Bilateral tokens changed")
    return {"status": "two-paused-unit-scale-p1-mass-readbacks-matched", "reference": reference, "base": base,
            "expectedInverseMass": expected_inverse_mass, "A": ma, "B": mb,
            "normalMotionQualified": False, "contactQualified": False, "renderStrainQualified": False,
            "amplitudeRatioInferred": False, "originalUneditedPhysicsQualified": False}
