# CLAW Distribution development companion

This optional native SKSE companion writes only the `CLAW.Distribution` morph
key. Its independent mode reads third-party **CLAW** presets and assigns them to
currently loaded werewolves. Explicit human morph linkage instead derives the
whole owned coefficient vector from a neutral baseline and applied human morphs;
it requires no beast preset files. The preserved first compiled candidate targets
**Skyrim VR 1.4.15**. A separate **Skyrim SE 1.7.104.0** development build is now the
flat-game test target.
It does not fork
OBody, rename beast presets to human families, or change OBody's human assignments.
The earlier SE mechanics candidate at `f42e0f2` completed a first bounded game run:
21 checks passed, one assertion mismatched with ambiguous timing and 46 checks
were not run. Those results do not accept this direct linked-mode revision or
rendered geometry. The current linked revision is not game-tested. Compilation
is not runtime acceptance.
The SE build requires **SKSE 2.3.1**, the matching **Address Library v13** data,
and a RaceMenu/SKEE build qualified for that runtime. RaceMenu/SKEE runtime
compatibility remains a separate gate; the pinned interface header alone does
not establish it. Other SE/AE game versions are rejected rather than inferred
compatible from their executable name. This exact-version bound describes the
current SE test candidate, not a permanent limit on the Distribution mod. The
actor/preset/state logic is shared; runtime DLL variants remain part of one
Distribution mod. Older SE/AE variants require their SDK/API review and dependency
qualification, and untested AE is not reported as a game pass.

## Preset contract

This catalog is required only for independent beast assignment. Linked actors
bypass catalog validity, selection and interpolation entirely.

Install standalone XML beneath:

```
Data/CalienteTools/BodySlide/SliderPresets/CLAW/<author>/<presets>.xml
```

The optional author subdirectory is recursive. Keep these presets nested beneath
`CLAW`: stock OBody 4.4.3 scans the top level, while BodySlide supports recursive
preset discovery. Never place CLAW beast XML in OBody's top-level preset directory.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<SliderPresets version="1">
  <Preset name="Author - Broad male" set="CLAW Male">
    <Group name="CLAW"/>
    <SetSlider name="CLAWTorsoGirth" size="small" value="15"/>
    <SetSlider name="CLAWTorsoGirth" size="big" value="65"/>
  </Preset>
</SliderPresets>
```

Use exactly `CLAW Male` or `CLAW Female` as `set`; no name-based sex inference.
`Group` is optional. Endpoints are finite percentages in **0..100**, divided by
100 and interpolated once using the actor NPC weight in **0..100**. BodySlide's
omitted endpoint semantics apply: an omitted small or big endpoint is zero, and
an entirely omitted morph contributes zero. A typed preset with no `SetSlider`
elements is accepted as the neutral body, and readback checks all 25 owned public
morphs, including zeros for every omitted morph. This candidate intentionally rejects
negative/extrapolated values. Different values are not certified safe geometry.

The allowlist matches the published 0.6.2.0 base resource contract: 24 shared
morphs plus female-only `CLAWTorsoBreastSize`. Adult and unknown morphs, wrong-sex
morphs, unknown tags/attributes, malformed XML, duplicate preset names across files
or families, duplicate endpoints and unreadable files are errors. A catalog with
**any** such error is unavailable, with diagnostics in `CLAWDistribution.log`;
it does not silently use a partially accepted population. XML is limited to 1 MiB
per file and the catalog to 4,096 presets/files. DTD/entities are unsupported.
Input is strict UTF-8 (an initial BOM is allowed). Preset names are nonempty,
at most 160 UTF-8 bytes, without ASCII surrounding whitespace or control/DEL
characters. Unexpected XML attributes, duplicate attributes and substantive text
are rejected.

Example XML and the Python authoring/export workflow are owned outside this
directory by the main CLAW project. This parser is usable without the game:

```
claw-preset-tool validate <CLAW-preset-directory>
claw-preset-tool interpolate <directory> "Author - Broad male" male 50
```

## Runtime and saved state

Only `Actor.GetRace() == WerewolfBeastRace` qualifies, with readable NPC sex and
loaded 3D. The actor base race is never used for eligibility. The player and
high-process actors are discovered, with existing assignments also revisited.
Race completion, object load, SKSE node updates and OBody's `Obody_ApplyMorph`
event schedule refreshes. A coalesced two-second scan provides a fallback and
detects 3D root or weight changes and lost own-key values. A timer thread only
queues SKSE tasks; engine access and every SKEE read/write occur in those tasks.
The preset directory is resolved relative to the actual game executable, not
the launcher's working directory. After new-game/post-load readiness a task emits
the `CLAWDistribution_Loaded` mod event for the optional menu bootstrap.

Each actor reference gets an identity inside a randomized save namespace. A
stable FNV-1a selector in independent mode chooses among sorted presets of the
correct sex; the actual assignment is saved, so adding presets never rerolls
existing actors. Linked mode never invokes that selector. SKSE
serialization records namespace, identity, selected name, family, suppression,
VM deletion identity and verified coefficient cache. `ResolveFormID` and
`ResolveHandle` remap actor references/VM identities on load,
including saved dynamic references supported by SKSE. Identity is never the NPC
base ID. After load, records are unbound until a main task checks their resolved
nonempty VM deletion identity and binds the current actor. Failed/missing VM
handle remaps, a changed VM identity or a conflicting runtime object quarantine
the saved assignment; they never silently become a fresh assignment. The saved
identity is retained. Diagnostics appear in the log, and a manual request for a
quarantined record reports an error. Recovery is not guessed from a reused ID.
Dynamic
references that the game does not preserve cannot be promised persistence.

Manual assign/clear/refresh requests pin the exact Actor object and check that it
still owns its FormID and is not deleted before main-task work. Request serial,
runtime owner and world epoch guard every completion/error; a stale request cannot
erase or change a newer actor's pending request. Repeated pending commands use
the latest request. Cached getters expose only the matching bound actor/request.
Refresh keeps the pinned pointer rather than looking its ID up a second time.

A bounded pool (8,192 distinct Actor objects) shares one intrusive reference pin
across callbacks, pending requests and tasks. Pool entries are released
only by main-task collection when no other owner remains, including after world
change. This also handles a task completing before its native callback returns.
State owns a weak ActorHandle, never a strong reference that could delay normal
actor reclamation. Its handle is created/resolved only in main tasks. While it
resolves to the same current registered actor and the VM identity matches, normal
3D unload/reload preserves the assignment. An expired/mismatching handle is
quarantined instead of guessed to be the same reference. The pool and state bounds
fail closed when full. Pins, weak handles, pointers and runtime serials are never
saved. A 3D-root change on the same reference does not mint a new identity. The
pool container deliberately has process lifetime, so unqualified DLL/static
teardown never releases engine pins; normal reclamation happens through main tasks.

Deletion callbacks capture the existing runtime owner, then main-task cleanup
checks that same state/runtime witness and deletion or registry displacement.
A late receipt cannot erase a live current actor just because its VM handle matches, nor erase
a different owner's pending request. A receipt for an unbound restored record
quarantines it. Completed errors release their pending pin. A normal bound State
retains only the latest request token/runtime serial, keeping its terminal error
visible after pool collection and automatic refresh, until another accepted
request or world reset supersedes it. Errors without a validated runtime witness
remain in the log rather than being exposed to a later ID owner.
No uniqueness/reuse format or notification ordering of engine VM handles, or
formal generation guarantees of ActorHandle, are asserted. Save/load, 3D reload,
physical reference reconstruction,
deletion ordering and pool lifetime still require qualification in the selected
game runtime.

Returning to human form clears only known base morphs under this companion's key,
retaining the independent assignment or explicit linked profile for later beast form. Human OBody assignments and other
morph keys are left intact. Explicit `ClearOwn` also saves a suppression flag,
so periodic automatic assignment stays off until `AssignPreset` or an explicit
valid `ConfigureMorphLink` request is called.
Missing saved presets produce an error instead of choosing another preset.

The official RaceMenu/SKEE `BodyMorph` interface is acquired through its SKSE
message exchange. Applying clears this companion's own known contributions,
sets the selected/interpolated coefficients, requests an immediate body-morph
update and reads its own values back. A failed readback remains an error. This
does not prove that the rendered body, every mesh's morph path or physics changed.

OBody 4.4.3's non-respectful application can clear all actor morphs. Its applied
event and the readback scan restore this companion's own values when the actor
is currently a beast; race-return cleanup remains scoped. For older versions
without the applied event, respectful mode is recommended. The readback scan is
a recovery mechanism, not permission for this plugin to modify OBody settings.

## Papyrus API

`papyrus/CLAWDistributionNative.psc` is the declaration source. Compile it with
the project's Papyrus tooling; it is not a quest, MCM or automatic menu installer.
The coordinator owns the user menu and optional human OBody route.

| Function | Result |
|---|---|
| `GetPresetNames(female)` | Sorted valid catalog names for that family |
| `AssignPreset(actor, name)` | False if invalid/unavailable; true means queued |
| `GetAssigned(actor)` | Saved independent name, or empty in linked mode; does not imply application |
| `GetStatus(actor)` | Enum below; queued native requests report pending immediately |
| `GetLastError(actor)` | Most recent application/request error |
| `GetOwnMorph(actor, name)` | Last verified own coefficient, zero unless status is applied |
| `ClearOwn(actor)` | Queued scoped cleanup; saved suppression until explicit assign/configure |
| `Refresh(actor)` | Queued lifecycle/readback refresh |
| `ConfigureMorphLink(actor, profile, sources[], targets[], gains[], caps[])` | Queued explicit morph-to-morph profile, 1..32 rules; actual SKEE source coefficients, no preset-name pairs |
| `DisableMorphLink(actor)` | Queued return to the retained independent preset |

Status values: **0** unknown, **1** pending, **2** own coefficients read back and
model update requested, **3** unloaded, **4** error, **5** human/own key cleared,
**6** explicitly cleared, **7** SKEE unavailable. A queued assignment can still
fail because race/sex/reference/3D changed. `GetOwnMorph` is a cached readback, not
the aggregate across mods. Inspect status before interpreting zero.
Explicit refresh immediately marks the request pending and hides its previous
coefficient cache until queued work completes or reports an error.

The optional [morph-to-morph bridge](../docs/transformation.md) reads actual
applied signed human coefficients through SKEE in main-thread tasks. It sums
configured source values times gains, clamps each target sum once to 0..1 and
multiplies by its configured cap; it never reapplies actor weight to those human
values. Linked output starts with all public own morphs neutral for the actor's
sex; every unmapped trait, including ears and tail, stays zero. Female breast
stays zero pending shape qualification. No independent preset, catalog or actor
weight contributes, even if an older independent assignment is retained for
`DisableMorphLink`. `GetAssigned` is empty while linkage is enabled. The profile is explicit;
there is no universally calibrated default or automatic body-family detection.
Normal `AssignPreset` disables linkage. `ClearOwn` retains the mapping while
suppressing distribution; a valid explicit configuration resumes it. Disabling
linkage does not clear suppression. The existing
single own key is retained. Actor record v2 stores the mapping/source snapshot;
v1 migrates independent. The v2 layout is unchanged, and its linked records use
the direct neutral-baseline semantics after refresh. Real source aggregation and actual
save/load/transform behavior require separate acceptance evidence. The API queues
work: wait for the previous request to complete before submitting the next one.

## Build without installation

Use CMake 3.25+, x64 MSVC with C++23 support and an **external** configured
CommonLibSSE-NG checkout. The verified source baseline is official
[CommonLibSSE-NG v3.7.0](https://github.com/CharmedBaryon/CommonLibSSE-NG/tree/c4ab853d095e81e3390b282d7ba01ab2f24ebf25).
That historical baseline is for the preserved VR candidate, not SE 1.7.104.
The SE target requires a current external SDK with explicit
`SKSE::RUNTIME_SSE_1_7_104`, 1.7 layouts and Address Library format-5 support.
The selected current source baseline is CommonLibSSE-NG 9.1.0 at
`a898f469851c464d05137bb74b069dd234897643`, plus the owner's isolated TypeInfo
object-array mask correction `0c95630c29ff98f64caeea83c29ca373cf93e58b` (its direct
child). The actual source is staged outside Git with the exact official OpenVR
submodule; the canonical checkout is not modified. The SE DLL and offline tools
compile against that source; all 23 core cases and the four example presets pass.
PE inspection confirms the expected metadata without loading the DLL, and the
positive build-helper check leaves the DLL hash unchanged. Runtime dependency
and engine qualification remain separate from these offline results.
Do not unlock the old 3.7.0 SDK by changing only the runtime constant.
No machine path is hardcoded in the source.

Download the official external
[SKEE API header](https://raw.githubusercontent.com/expired6978/SKSE64Plugins/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/IPluginInterface.h)
as `IPluginInterface.h`; its SHA-256 is enforced by CMake. `dependencies.json`
records upstream revisions/archive hashes. Pugixml, fmt, spdlog and rapidcsv are
fetched with pinned hashes into the external build directory, or supplied using
CMake `FETCHCONTENT_SOURCE_DIR_<NAME>` variables. Dependency sources are not copied
into the CLAW repository. Retain their licenses in any future distributed bundle.
Those fmt/spdlog/rapidcsv pins belong to the VR build. SE resolves spdlog,
rapidcsv and the current SDK's DirectXTK dependency from the caller's external
dependency prefix/toolchain instead. Supply only the pinned pugixml source through
`-FetchSources` for that branch. CLAW uses no trampolines, so the SE configuration
disables the SDK's optional patch decoder instead of downloading it.

```powershell
./distribution/build.ps1 -BuildDir '<external-build>' `
  -CommonLibDir '<external-commonlib-checkout>' `
  -SkeeHeader '<external-dependencies>/IPluginInterface.h'
```

For SE, use a **new** build directory and the current configured SDK/dependencies:

```powershell
./distribution/build.ps1 -Runtime SE -BuildDir '<external-SE-build>' `
  -CommonLibDir '<external-current-commonlib-checkout>' `
  -SkeeHeader '<external-dependencies>/IPluginInterface.h' `
  -DependencyPrefix '<external-SDK-dependency-prefix>' -BuildTests
```

`-ToolchainFile` can supply an existing external dependency toolchain instead.
The equivalent CMake selector is `-DCLAW_RUNTIME=SE`; the default remains `VR`.
Targets are `CLAWDistributionSE` for SE and `CLAWDistribution` for VR. Each emits
`Release/CLAWDistribution.dll` in its own build tree; never combine their DLLs or
reuse one runtime's build tree for the other. The helper refuses legacy VR tree
reuse for SE, and CMake records the selected runtime for later configurations.

The SE DLL exports modern `SKSEPlugin_Version` data with an exact supported
runtime list, updated-struct and Address Library V5 metadata. It does not advertise
unrestricted Address Library version independence. Query and Load both check the
exact runtime, and Load rejects mismatches before SKSE initialization or engine
access. These entry checks do not prove every downstream engine call or SKEE
implementation is compatible.

The helper defaults to the installed VS2026 generator, accepts `-CMakeExe` and
`-Generator`, rejects source/live/archive output locations, and never installs or
runs anything. It produces `Release/CLAWDistribution.dll` and
`Release/claw-preset-tool.exe`. `-BuildTests` only compiles the optional test
executable. Core-only builds require pugixml but no SKSE/CommonLib/Windows:

```
cmake -S distribution -B <external-build> -DCLAW_BUILD_PLUGIN=OFF
cmake --build <external-build> --config Release
```

After the coordinator confirms testing readiness, explicitly configure
`CLAW_BUILD_TESTS=ON`, compile `claw-preset-tests` and run it or CTest. No post-build
command executes tests. Offline cases cover endpoints, sparse BodySlide exports,
typed families, exclusions, duplicate catalogs, bad input, stable selection,
nested third-party files and direct linked output with neutral unmapped traits
and no independent catalog/weight access. The SE DLL compiled and all 28 offline
contract cases passed for this direct linked revision. Runtime acceptance still
needs a separately authorized
game test: multiple male/female beasts, UI assignment, human key preservation,
transform/race events, delayed/reloaded 3D, external OBody updates, saved dynamic
references and save/load. The earlier bounded SE mechanics run described above
does not qualify this revised linked behavior.
