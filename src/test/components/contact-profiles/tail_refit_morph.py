"""Owned CLAW test stimulus for the RaceMenu tail channel."""

import math

from prepare_tail_refit_contrast import CHANNEL


MORPH_SCRIPT = "NiOverride"
TEST_KEY = "CLAWTest.TailRefit"
PARAMETERS = ("objectreference", "string", "string")
FUNCTIONS = {
    "HasBodyMorph": ("bool", PARAMETERS),
    "GetBodyMorph": ("float", PARAMETERS),
    "SetBodyMorph": ("none", (*PARAMETERS, "float")),
    "ClearBodyMorph": ("none", PARAMETERS),
    "UpdateModelWeight": ("none", PARAMETERS[:1]),
}


class UnconfirmedMutation(RuntimeError):
    """The owned game session must be retired without saving or replaying a write."""


def check_registry(description):
    if str(description.get("name", "")).casefold() != MORPH_SCRIPT.casefold():
        raise ValueError("RaceMenu registry script identity differs")
    entries = description.get("globalFunctions", [])
    for method, (returns, params) in FUNCTIONS.items():
        matches = [entry for entry in entries if entry.get("name") == method]
        if len(matches) != 1:
            raise ValueError("Missing or ambiguous RaceMenu function: " + method)
        entry, = matches
        if (entry.get("native") is not True or str(entry.get("returnType", "")).casefold() != returns
                or tuple(str(param.get("type", "")).casefold() for param in entry.get("params", [])) != params):
            raise ValueError("Typed RaceMenu contract differs: " + method)


def key_value(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Test morph key must return a finite float")
    return float(value)


def run_states(call, describe, guard, phase, ref):
    """Run 0/1/0 on one owned fixture and clear only the reserved test key.

    call accepts (script, method, args, expected_type) and verifies exact
    completion. guard rechecks ownership of the same dynamic actor and its
    original attached body. phase records each native hold and must detach its
    owned capsules before returning. The caller preflights the actor and owns
    process retirement when a mutation's outcome is unknown.
    """
    if type(ref) is not int or not 0xFF000000 <= ref < 0xFFFFFFFF:
        raise ValueError("An owned dynamic NPC reference is required")
    check_registry(describe(MORPH_SCRIPT))
    form = {"form": f"0x{ref:08X}"}
    args = [form, CHANNEL, TEST_KEY]

    def read(expected):
        guard()
        present = call(MORPH_SCRIPT, "HasBodyMorph", args, "bool")
        value = key_value(call(MORPH_SCRIPT, "GetBodyMorph", args, "float"))
        guard()
        if present is not (expected != 0.) or value != expected:
            raise ValueError("Unexpected stored tail test key value")

    def change(method, params):
        guard()
        try:
            result = call(MORPH_SCRIPT, method, params, "none")
            if result is not None:
                raise ValueError("Expected confirmed native void completion")
            guard()
        except Exception as error:
            raise UnconfirmedMutation("Could not confirm " + method + " on the original actor") from error

    read(0.)
    phase("neutral")
    change("SetBodyMorph", [*args, 1.])
    try:
        change("UpdateModelWeight", [form])
        read(1.)
        phase("morphed")
    except UnconfirmedMutation:
        raise
    except Exception:
        change("ClearBodyMorph", args)
        change("UpdateModelWeight", [form])
        read(0.)
        raise
    change("ClearBodyMorph", args)
    change("UpdateModelWeight", [form])
    read(0.)
    phase("returned")
