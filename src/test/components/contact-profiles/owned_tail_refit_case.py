"""Bind the CLAW diagnostic to an existing executor-owned VR fixture."""

from copy import deepcopy
from pathlib import Path

from run_tail_refit import Capture
from tail_refit_morph import UnconfirmedMutation
from verify_tail_refit import Subject, fixture_creation, fixture_generation, positive_int, require


def bind_capture(session, *, tag, resolved_base, profile_path, basis_path, deadline):
    """Reuse the ordinary disposable fixture receipt and original executor ledger.

    The platform supplies the resolved plugin-local base, runtime asset
    verification, calibrated input and admission. This adapter never creates
    an actor, opens a session or launches a process.
    """
    from skyrim_autotest import native
    from skyrim_autotest.fixture_actors import require_fixture

    state = session.state
    run_id, game, world = state.get("id"), deepcopy(state.get("game")), state.get("ownedWorldGeneration")
    require(isinstance(run_id, str) and run_id and isinstance(game, dict)
            and positive_int(game.get("pid")) and positive_int(game.get("birth"))
            and isinstance(game.get("path"), str) and Path(game["path"]).name.casefold() == "skyrimvr.exe"
            and state.get("configuration", {}).get("game_edition") == "vr"
            and state.get("gameplayBootstrap", {}).get("completed") is True
            and state.get("testProfile") and positive_int(world), "Expected an admitted disposable Skyrim VR session")
    require(not state.get("ownedFixtureQuarantine") and native.alive(game), "Owned Skyrim VR process is unavailable")

    entry = state.get("interactiveActorFixtures", {}).get(tag)
    require(isinstance(entry, dict), "Expected the exact same-run fixture tag")
    record = require_fixture(session, {"reference": entry.get("reference"), "base": resolved_base})
    actor, incarnation = record["actor"], record["incarnation"]
    witness = record["creationWitness"]
    require(witness.get("forcePersist") is False and record.get("createdReference") == record["reference"]
            and "restorationWitness" not in record and actor.get("sex") == "male"
            and actor.get("race") == "0x000CDD84" and actor.get("weight") == 50 and actor.get("loaded3D") is True,
            "Expected the fresh, nonpersistent male werewolf diagnostic fixture")
    require(record == entry and record["base"] == resolved_base
            and int(resolved_base, 16) & 0xFFFFFF == 0x800, "Resolved fixture base differs from the admission")
    generation = fixture_generation(record["creationId"])
    subject = Subject(game["pid"], int(record["reference"], 16), int(resolved_base, 16), 0x0A01A5C6, generation)
    scope = {"tag": tag, "creationId": record["creationId"], "incarnation": deepcopy(incarnation)}

    def guarded_tool(name, args, **kwargs):
        current = session.state
        fixture = current.get("interactiveActorFixtures", {}).get(tag, {})
        if (current.get("id") != run_id or current.get("game") != game or current.get("ownedWorldGeneration") != world
                or current.get("ownedFixtureQuarantine") or fixture.get("status") != "created"
                or fixture.get("creationId") != scope["creationId"] or fixture.get("incarnation") != scope["incarnation"]
                or not native.alive(game)):
            raise UnconfirmedMutation("Original owned VR session or fixture world is no longer current")
        return session.tool(name, args, **kwargs)

    capture = Capture.from_files(guarded_tool, session.dir / "steps.jsonl", subject, profile_path,
                                 basis_path, deadline=deadline)
    ledger = capture.ledger()
    indices = [i for i, row in enumerate(ledger) if row.get("kind") == "interactive-fixture-created"
               and row.get("creationId") == scope["creationId"]]
    require(len(indices) == 1, "Missing or duplicated original fixture creation row")
    scope["index"], = indices
    capture.owner = fixture_creation(ledger, scope, subject)
    capture.manifest["fixtureCreation"] = scope
    return capture
