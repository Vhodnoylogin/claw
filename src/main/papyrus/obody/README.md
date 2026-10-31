# Optional stock OBody source adapter

This development adapter lets a new, originally-beast actor obtain an ordinary
human preset through OBody itself. It does not introduce wolf presets, change
race keywords, fork OBody, or write SKEE source keys. The normal human-to-wolf
link remains in the Distribution native coordinator.

The inspected [OBody5.2 source](https://github.com/Aietos/OBody-NG/blob/13513609145313f721970c2ebe113290f6add6e8/src/Body/Event.cpp)
restricts ordinary actor processing to ActorTypeNPC. Its public `GenActor`
entry calls stock generation, which retains its processed checks, blacklist and
distribution rules. The adapter asks for that operation only for a fresh
automatically adopted beast with no observed human form and no configured
human source names, including zero-valued entries. An existing OBody assignment
is retained. Already processed/unassigned or blacklisted actors remain governed
by OBody. A historical unassignment before CLAW first observed the actor is not
distinguishable from absence through the public preset-name getter; the adapter
does not invent that history. This behavior needs installed-provider qualification.

The native adapter also negotiates the official versioned OBody API and waits
for its readiness callback **and a genuine internally generated actor event** in
the current provider epoch. DLL presence alone is insufficient. This additional
event witnesses the stock distribution path's initialization, including its
per-save distribution key. If all loaded humans were processed already, source
bootstrap waits until a real stock generation occurs. No hidden probe actor,
global key change, arbitrary delay or readiness bypass is used. The optional
auto-enabled host resumes once on the corresponding availability event.
`GetProviderStatus()` distinguishes this wait from an enabled provider.

Native candidate and ready events use a bounded exact integer token. The host
requests main-task revalidation, checks race/loaded state and OBody assignment
again, then atomically claims the cached token immediately before `GenActor`.
Restored CLAW states, manual, suppressed and quarantined states never gain automatic
eligibility. Human observation, a model/sex/resource/world change or a manual
request revokes it. Each new eligible state is advertised once; no retry loop
rerolls a refused actor. Calls to two separate providers cannot be made
transactional against unrelated mod writers; OBody's own generation guard remains
the final assignment decision.

`Enable()` admits an asynchronous native request; `GetLastResult()` is a delivery
diagnostic, not evidence of assignment, rendering or persistence. A nonempty
existing preset is respected even when every coefficient is zero. There are no
timer scans in this script. The native coordinator supplies bounded discovery
and independently observes the actual effective coefficients afterward.

Build with explicit existing Caprica, Spriggit, flags and script imports:

```powershell
python distribution/obody/build.py --out '<new external directory>' `
  --compiler '<Caprica.exe>' --spriggit '<Spriggit.CLI.exe>' `
  --flags '<TESV_Papyrus_Flags.flg>' --import-path '<Skyrim/SKSE script sources>' `
  --obody-declaration '<OBody5.2>/OBodyNative.psc' --enable-population
```

The explicit `--enable-population` install choice emits a start-enabled quest
with `IntegrationOptIn=true`. Without it the quest is stopped and opt-in is
false, for controlled preparation. Both packages depend on the matching native
Distribution companion and an explicitly declared human resource-family
configuration. No package is installed or game launched by this builder.
The output contains only the original host ESP/PEX/source and this guide;
third-party declarations stay in the external compiler closure.
