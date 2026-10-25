# Human and beast preset pairing

Development reference,25October2026. `scripts/linked_presets.py` implements an
**offline** pairing and policy planner. The current native companion does not
consume its output. Nothing here transforms an actor, changes OBody assignments
or establishes game compatibility.

## Explicit pairs first

Human CBBE/3BA/HIMBO slider names are not a universal measurement system. The
installed CBBE and3BA projects even reference different shape datasets for shared
names, and ordinary presets contain legitimate negative coefficients. Guessing
wolf proportions from equal names or a sum of human sliders would lose meaning.

The first route is an author-defined pair from an exact human preset/profile to
an ordinary same-sex CLAW preset. The source profile identifies an explicitly
chosen body resource revision; it is never inferred from sex or preset substrings.
`recipes/linked-presets.json` intentionally contains no fabricated installed rules.
The numerical examples in `tests/fixtures/paired-link.json` are synthetic tests.

```json
{
  "schemaVersion": 1,
  "pairs": [{
    "id": "YourName/lean-female-v1",
    "sourceProfile": "Your explicitly versioned human body profile",
    "sourcePreset": "Exact human preset name",
    "sex": "female",
    "targetPreset": "Exact CLAW Female preset name",
    "bodyMorphs": ["CLAWTorsoGirth", "CLAWArmGirth"]
  }]
}
```

Only the listed body domain is replaced; target omissions mean zero there.
Saved individual traits, such as ears and tail, are composed separately and must
not overlap that domain. Target XML endpoints interpolate once at actor weight.
Female breast and adult morphs are excluded from automatic linked domains pending
their independent shape/rig qualification. Unknown properties, duplicate matches,
wrong-sex targets and overlapping domains are errors. Once bound, changed rule or
target fingerprints require an explicit rebind; no hidden reroll follows.

## One coordinator and one active key

Explicit modes are `independent`, `manual` and `linked`, with separate suppression.
Manual neutral is a valid full-body request. It is not an invitation to resume
automatic linking. Returning human clears only our two beast keys; OBody's human
assignment and foreign morph entries remain the provider's responsibility.

The future runtime coordinator must exclusively choose `CLAW.Distribution` or
`CLAW.Link`, clear the inactive owned key, replace the active vector and verify
all owned values including zeros. Do not run this planner or the older scalar
prototype as a second writer beside the current native distributor. SKEE's
aggregate across keys is not assumed to be an additive sum.

The caller supplies a save-stable reference identity, explicit mode, actual sex,
current race/loaded3D observations, saved independent/manual choices, saved traits
and a confirmed source assignment. Every plan increments generation and remains
pending. Human cleanup and unloaded deferral precede source/catalog validation.
Missing unconfirmed sources use the last resolved linked intent with a stale
diagnostic, or the saved independent preset if no link exists. Missing/changed
pinned targets cause an error without new writes. The planner's cached intent is
not a runtime acknowledgment; the adapter must retain a separate actual readback
receipt and recheck epoch/identity/generation/race/sex/3D before writing.

Source observations keep the existing three fields:

| Observation | Meaning |
|---|---|
| `{"profile":"explicit profile ID","preset":"Exact preset name","confirmed":true}` | Assigned; match an exact pair |
| `{"profile":"explicit profile ID","preset":null,"confirmed":true}` | Provider confirms no assignment |
| Missing source or `confirmed:false` | Provider unavailable/unconfirmed |

An empty preset string remains invalid. The future OBody adapter must convert a
successful empty assignment query into `preset:null`; it must not convert API
unavailability into a confirmed unassignment. OBody's native unassignment event
can carry the **previous** preset name when `PresetWasUnassigned` is set. Check
that flag and query current assignment instead of treating the payload as a new
assignment ([pinned OBody NG 4.4.3 API contract](https://github.com/Aietos/OBody-NG/blob/e33bbc151c38fbe6feae9f5b04558cd6c7528384/include/API/API.h#L549-L572)).

In linked mode, confirmed unassignment resolves the already selected independent
preset plus saved individual traits. Only after that fallback resolves successfully
does the new pending state remove `lastLink`. A later provider loss therefore
cannot resurrect the retired link. Failure to resolve the fallback retains the
previous link state and plans no writes. Manual, suppression, human cleanup and
unloaded deferral keep their precedence and do not retire a link as a side effect.
The CLI needs a catalog for this fallback, but neither loads nor requires a pairs
document for confirmed unassignment, even if `--pairs` names a missing file.

Existing native assignments do not record manual provenance. A future migration
must stay independent until an explicit mode selection opts into linkage. A
stored preset name alone cannot establish user intent.

## Offline interface and remaining work

`plan(snapshot, rules, normalized_catalog, allowed_morphs)` is dependency-free and
does not mutate its inputs. The CLI accepts `--pairs` and a typed XML `--presets`
subtree; snapshot fields are shown in the fixed fixture corpus. Output contains
policy, generation, active key, scoped clear keys, desired coefficients and
diagnostics. It is an execution intent, never a success receipt.

Actual source discovery, persistent policy migration, a single native writer,
race/model/OBody event integration and acknowledgment remain to implement and
test in game. Later calibrated scalar profiles must preserve signed human inputs
and avoid applying actor weight a second time. The older illustrative scalar
equations in [distribution.md](distribution.md) are not an accepted default.
