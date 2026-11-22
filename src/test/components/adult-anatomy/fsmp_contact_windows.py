"""Read direct contact diagnostics from four completed FSMP trial windows."""

import argparse
import json
import math
from pathlib import Path


SCRIPT = "CLAWFSMPPairContact"
PHASES = ("far_before", "tag_control", "reciprocal_near", "far_after")
DRIVERS = ("WWD 2", "WWLB 1", "WWRB 1")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def typed(ledger, index, function, args, result_type):
    require(type(index) is int and 0 <= index < len(ledger), "Missing provider receipt")
    row = ledger[index]
    packet, result = row["args"], row["result"]
    require(row.get("tool") == "papyrus" and packet.get("action") == "call"
            and packet.get("script") == SCRIPT and packet.get("function") == function
            and packet.get("args") == args and "self" not in packet
            and result.get("called") is True and str(result.get("returnedType", "")).casefold() == result_type
            and not (result.get("error") or result.get("isError")), "Typed FSMP receipt differs: " + function)
    return result["returned"]


def native_form(value):
    return {"form": f"0x{value:08X}"}


def finite_vector(vector):
    return (type(vector) is list and len(vector) == 3 and
            all(type(number) in (int, float) and math.isfinite(number) for number in vector))


def check_rows(head, pages, driver):
    offset, last_step = 0, 0
    accepted = 0
    for page in pages:
        rows = page["rows"]
        remaining = head["contactRows"] - offset
        require(page.get("status") == "complete" and page.get("nonce") == head["nonce"]
                and page.get("total") == head["contactRows"] and page.get("offset") == offset
                and type(rows) is list and len(rows) == min(12, remaining)
                and (remaining > 0 or offset == 0), "Incomplete or repeated contact-page receipt")
        for row in rows:
            depth, qpc, step = row["signedDepth"], row["qpc"], row["step"]
            normal = row["normalToSurface"]
            require(type(step) is int and max(1, last_step) <= step <= head["frames"]
                    and type(qpc) is int and head["firstQpc"] <= qpc <= head["lastQpc"]
                    and type(depth) in (int, float) and math.isfinite(depth) and depth < 0
                    and row["surfaceDriver"] in DRIVERS and finite_vector(normal)
                    and abs(sum(number * number for number in normal) - 1) <= .002001
                    and all(finite_vector(row[name]) for name in ("surfaceLocal", "probeLocal")),
                    "Invalid accepted point or source bone")
            last_step = step
            accepted += row["surfaceDriver"] == driver
        offset += len(rows)
    require(offset == head["contactRows"] and len(pages) == max(1, (offset + 11) // 12),
            "Missing direct contact data after the completed window")
    return accepted


def verify(manifest, ledger):
    require(manifest.get("schema") == "claw-fsmp-pair-contact-reads/1", "Unexpected capture manifest")
    pair = manifest["pair"]
    pair_fields = ("surfaceRef", "surfaceAddon", "probeRef", "probeAddon")
    require(set(pair) == set(pair_fields) and all(type(value) is int and 0 < value < 0xFFFFFFFF for value in pair.values())
            and pair["surfaceRef"] >= 0xFF000000 and pair["probeRef"] >= 0xFF000000
            and pair["surfaceRef"] != pair["probeRef"], "Expected two distinct disposable actors")
    fixture = [native_form(pair[field]) for field in pair_fields]
    pid, epoch, frames, driver = (manifest[k] for k in ("pid", "callerEpoch", "frames", "targetDriver"))
    require(all(type(value) is int and value > 0 for value in (pid, epoch, frames))
            and 1 <= frames <= 120 and driver in DRIVERS, "Invalid fixed trial settings")
    windows = manifest["windows"]
    require(set(windows) == set(PHASES), "All four controls are required")
    results, last_nonce, last_index, last_qpc, frequency = {}, 0, -1, 0, None
    for phase in PHASES:
        plan = windows[phase]
        nonce, indices = plan["nonce"], [plan["arm"], plan["describe"], *plan["pages"]]
        require(type(nonce) is int and last_nonce < nonce <= 0x7FFFFFFF
                and all(type(i) is int for i in indices) and indices == sorted(set(indices))
                and last_index < indices[0] and len(indices) >= 3, "Replayed or unordered window")
        require(typed(ledger, plan["arm"], "Arm", [*fixture, nonce, epoch, frames], "bool") is True,
                "Provider did not arm the exact pair")
        head = json.loads(typed(ledger, plan["describe"], "Describe", [nonce], "string"))
        mode = "tag_control" if phase == "tag_control" else "reciprocal"
        require(head.get("schema") == "claw-fsmp-pair-contact/1" and head.get("status") == "complete"
                and head.get("pid") == pid and head.get("nonce") == nonce and head.get("callerEpoch") == epoch
                and head.get("mode") == mode and head.get("measure") == "pre-solve accepted contact point"
                and head.get("frames") == frames and head.get("requiredFrames") == frames
                and all(head.get(k) == pair[k] for k in pair_fields)
                and all(type(head.get(k)) is int for k in ("qpcFrequency", "firstQpc", "lastQpc", "contactRows"))
                and head["qpcFrequency"] > 0 and (frequency is None or head["qpcFrequency"] == frequency)
                and last_qpc < head["firstQpc"] <= head["lastQpc"] and 0 <= head["contactRows"] <= 384,
                "Incomplete or foreign native FSMP window: " + phase)
        pages = [json.loads(typed(ledger, index, "Read", [nonce, offset * 12], "string"))
                 for offset, index in enumerate(plan["pages"])]
        accepted = check_rows(head, pages, driver)
        require(accepted > 0 if phase == "reciprocal_near" else head["contactRows"] == 0,
                "Direct contact does not distinguish the reciprocal near window: " + phase)
        results[phase] = {"pointCount": head["contactRows"], "targetDriverPointCount": accepted,
                          "beginQpc": head["firstQpc"], "endQpc": head["lastQpc"]}
        last_nonce, last_index, last_qpc, frequency = nonce, indices[-1], head["lastQpc"], head["qpcFrequency"]
    return {"status": "actor-bound-fsmp-contact-points-observed", "pair": pair, "targetDriver": driver,
            "windows": results, "qpcFrequency": frequency, "poseControlsVerified": False, "impulseVerified": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--steps", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = verify(json.loads(args.manifest.read_bytes()),
                        [json.loads(line) for line in args.steps.read_bytes().splitlines()])
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "unqualified-fsmp-contact-windows", "reason": str(error)}))
        raise SystemExit(2)
    print(json.dumps(result, allow_nan=False))
