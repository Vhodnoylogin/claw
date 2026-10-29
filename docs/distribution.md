# Linked human and werewolf morphs

Historical offline prototype, 11 October 2026. Its seeded traits and proposed
`CLAW.Link` key below do not describe the current native runtime. The supported
development direction is [human-to-werewolf morph linkage](transformation.md):
human coefficients determine a neutral beast vector without separate wolf presets.
The current coordinator uses its own scoped `CLAW.Distribution` key. See
[the native module](../distribution/README.md) for its actual API and lifecycle.
The published 0.6.2.0 resource package has no controller. `scripts/distribution.py`
is an executable **offline reference core**, not an installed game integration.

The owner clarified26October that linkage is **morph to morph**. Presets supply
the human values; their names do not select the wolf shape. See
[transformation.md](transformation.md) for the current runtime bridge. The older
explicit preset-pair planner remains a separate legacy experiment, not the
chosen transformation mechanism. The equations below remain unqualified
hypotheses. Reference cores must not run as a second live writer beside
`CLAW.Distribution`; the native coordinator owns the composed beast vector.

## One actor, two forms

Keep the actor's OBody human preset assignment and its morph contributions intact.
Derive beast proportions using an explicit CBBE or HIMBO mapping under the separate
`CLAW.Link` key. Human slider names do not occur in CLAW's TRI. The future adapter
must never clear all body morphs or reassign a human preset merely to transform.
On return to human form it clears only `CLAW.Link` and updates the loaded model.
Other mods' CLAW contributions must also remain intact.

The prototype links torso, belly, chest, arms and calves to **already applied,
weight-interpolated NiOverride coefficients**. Input values are not BodySlide XML
percentages or un-interpolated low/high slider endpoints. OBody already computes
`min + (max-min) * actorWeight / 100`; applying weight again would distort the link.
The selected body family is explicit, never inferred from sex or preset name.
Initial maps use slider names present in the installed Common Guy HIMBO and Common
Lass CBBE/3BA presets. Their geometric correspondence and numeric ranges remain
proposals requiring visual qualification; they are not universal body-family maps.

Ears, muzzle and tail are stable individual traits derived from a SHA-256 seed.
Changing the human preset changes linked proportions, but does not reroll those
traits. Native beasts without a human source get deterministic body variation too.
Identity must be a **save-stable actor reference identity** including save namespace;
an actor base ID would give every spawned copy the same body. Runtime temporary
references need an assigned persistent identity, not a volatile raw FormID alone.
Versioned saved state records the source coefficients and computed beast traits.
There is no dependency on Python's process-randomized hash or random traversal order.

Breast size stays neutral in this prototype pending shape/rig repair. No adult
morph is distributed. Recipe caps are illustrative development parameters, not
tested safe limits for combinations, collisions or animation.

## Race and model lifecycle

The adapter observes **current `Actor.GetRace()`**, not the actor base race, after
`OnRaceSwitchComplete`. It observes transformations and never invokes `SetRace`.
It also refreshes after loaded 3D changes and OBody's actual morph application.
OBody's `OnActorGenerated(Actor, String)` can precede actual application; upstream
`Obody_ApplyMorph` fires after it, with actor as event sender. Confirm this event in
the deployed VR runtime before wiring a controller.

The offline core increments a per-actor generation on each event. An unloaded
actor produces no write actions. A loaded beast produces clear-own-key, set-own-
coefficients, model-update actions; a loaded human produces only scoped cleanup
and model update. Every result remains pending until actual writes/update/readback
succeed. Before executing a queued plan, the adapter must recheck generation,
current race, selected body sex and loaded 3D. A transformation back supersedes a
queued beast update. Load/new-game events must restore saved state and refresh
subscriptions; no success is inferred from a queued action.
The runtime adapter must serialize updates per actor. Two concurrent calls with
the same previous state would otherwise receive the same generation; the pure
reference core does not provide a lock or asynchronous execution scheduler.
Human-return cleanup does not depend on the continued availability of the human
body provider or valid incoming source coefficients; it retains the last valid
beast/source snapshot and clears the owned key even after provider loss.

This module does not implement those hooks, effective morph aggregation, native
save serialization, action execution, acknowledgment, actor discovery or runtime
collider updates. Those belong to the next controller implementation. Keep the
optional OBody adapter separate from the core so a different distribution provider
can supply the same actor snapshot. A human-derived shape and an independent beast
override can be future selectable policies; override UI is not implemented.

## Run the reference core

Create a local JSON snapshot:

```json
{
  "identity": "example-save|persistent-reference-123",
  "sex": "female",
  "bodyFamily": "CBBE",
  "humanMorphs": {"BigTorso": 0.6, "ChubbyWaist": 0.3, "Belly": 0.2},
  "isBeast": true,
  "loaded": true
}
```

```powershell
python scripts/distribution.py 'D:/local/actor-snapshot.json'
python -m unittest discover -s tests -p test_distribution.py -v
```

For a native beast use `bodyFamily: null` and `humanMorphs: {}`. To simulate the
next event, provide the returned `state` as `previous`. The program only reads a
snapshot/recipe and prints a plan. It neither connects to Skyrim nor changes files.

## Verified integration sources

- Installed OBody NG 4.4.3 `OBodyNative.psc`: `GetPresetAssignedToActor`,
  `AssignPresetToActor`, `RegisterForOBodyEvent`; the quest source marks legacy
  StorageUtil preset assignment obsolete.
- [OBody Body.cpp](https://github.com/Aietos/OBody-NG/blob/main/src/Body/Body.cpp):
  current upstream base-race selection, weight interpolation and applied-morph event.
- [OBody PresetManager.cpp](https://github.com/Aietos/OBody-NG/blob/main/src/PresetManager/PresetManager.cpp):
  male preset classifier recognizes existing human body-family names. Plain CLAW
  male preset XML is not a drop-in solution; do not disguise it as HIMBO.
- [NiOverride bindings](https://github.com/expired6978/SKSE64Plugins/blob/master/skee64/PapyrusNiOverride.cpp)
  and [serialization](https://github.com/expired6978/SKSE64Plugins/blob/master/skee64/BodyMorphInterface.cpp):
  actor-reference/key ownership and saved morph contributions. Engine aggregation
  must be verified rather than assumed to be a sum of all external keys.
- Installed SKSEVR `Actor.psc`: `GetRace`, `OnRaceSwitchComplete`; `Form.psc`:
  mod-event callback signature `(String, String, Float, Form)`.

Next runtime acceptance: native male/female beast diversity, human->beast->human
cycles, OBody preset changes before/during transformation, save/load, delayed 3D,
duplicate events and multiple mods' keys. VR then uses the established full-body
`1stperson_werewolf_hands.nif` entry point with the same CLAW TRI; test transformation,
sex, VRIK/IK and interaction stack separately. See the
[Werewolf Body for VR author's implementation](https://www.nexusmods.com/skyrimspecialedition/mods/56394).
