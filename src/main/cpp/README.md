# CLAW Distribution development companion

The native source now lives in `src/main/cpp`; its independent regression tests
live in `src/test/cpp`. The repository-root CMake entry point delegates here.
Use a fresh `target/native` or external build directory. Generated DLLs, object
files, executables and reports are not source resources and are not tracked.
The runtime implementation has not changed as part of this layout migration.

The current released source is CLAW 0.7.0.0. Its actual SE mechanism and textured
inspection results are recorded in [the final verification](../docs/verification-20261031.md).
The detailed sections below retain earlier companion-development history;
historical pending acceptance and exact-SE build notes do not supersede that
release record or expand the documented runtime coverage.

The current matrix candidate adds a matching coefficient C and function F for
every human-to-wolf edge. One portable implementation in
`shared/MatrixKernel.cpp` compiles into this DLL and the Morphbench plugin's
WebAssembly module. The [matrix contract](../docs/matrix-contract.md) defines
linear, positive/negative, smoothstep, bounded integer power and human-independent
constant edges, ordered arithmetic and strict parameters. No expressions execute.
Current profiles retain the family IDs, append four authored lean targets and use
`authored-opposed-matrix1`; the frozen 30 October release remains unchanged.
Linked targets are now opaque morph identifiers with preserved authored spelling;
the loaded model must actually provide them. SKEE interns names without ASCII
case distinctions, so case-only aliases and source/output overlaps are rejected
using deterministic ASCII identity. Bound morph names use printable ASCII; no
locale-dependent case conversion or arbitrary-prefix inference is performed.
The legacy 28 shared names plus female breast
remain neutral coefficient metadata, while up to 64 active target names enter
the shared kernel. Independent preset validation retains its original allowlist.

Gains are float32 before the shared inclusive `abs(gain) <= 1e-6F` omission rule.
Inactive edges are removed before duplicate/cap checks, source capture and save
output; their other fields must still be well formed and finite. Empty linked
profiles remain neutral linked policies. Exact active source/output collisions
are rejected, and capture also refuses sources overlapping existing own-key
outputs. No prefix is assumed to identify a human or wolf morph.

Actor records now write v5 with every function and parameter. Readers retain
v1..v4 support; old rules initialize to the original exact linear evaluation.
Saved matrices remain authoritative, so existing actors adopt revised XML only
through an explicit ConfigureMorphFamily request. All-constant profiles capture
no human values and cannot depend on an OBody source bootstrap. Fresh game,
existing-save refresh and rendered geometry still require runtime acceptance.
The wire record remains v5. Loading removes now-inactive saved edges and their
declared source values without substituting an installed profile; undeclared,
missing active or nonfinite source snapshots still fail. Runtime cleanup visits
all names under the exact `CLAW.Distribution` key before mutation, including stale
custom names. Other providers' keys are preserved. Neutral outputs are not stored
as zero-valued SKEE keys, although coefficient readback still reports their zeros.

This optional native SKSE companion writes only the `CLAW.Distribution` morph
key. Its independent mode reads third-party **CLAW** presets and assigns them to
currently loaded werewolves. Explicit human morph linkage instead derives the
whole owned coefficient vector from a neutral baseline and applied human morphs;
it requires no beast preset files. The historical first compiled candidate targeted **Skyrim VR 1.4.15**; the
30 October frozen release used a separate **Skyrim SE 1.7.104.0** binary. Current
source instead builds one universal candidate for SE, AE and VR as detailed below.
It does not fork
OBody, rename beast presets to human families, or change OBody's human assignments.
The earlier SE mechanics candidate at `f42e0f2` completed a first bounded game run:
21 checks passed, one assertion mismatched with ambiguous timing and 46 checks
were not run. Those results do not accept this direct linked-mode revision or
rendered geometry. Later SE core117 and born33 checks exercised six human actors,
roundtrips, source preservation, mixed-state persistence and two initially-wolf
actors. The repaired-surface trial then passed 82 action checks and six one-way
transformations. Final textured visual acceptance remains pending. The minimal
linked release candidate is built by `src/main/python/build-tools/build-core-candidate.py`; the older
independent-preset/menu packager below is not its installation contract.
The frozen exact-SE build required **SKSE 2.3.1**, matching **Address Library v13** data,
and a RaceMenu/SKEE build qualified for that runtime. RaceMenu/SKEE runtime
compatibility remains a separate gate; the pinned interface header alone does
not establish it. That historical build rejected other SE/AE versions. The new universal source
uses the explicit candidate boundaries below and still requires the correct
per-runtime dependencies. Untested AE is not reported as a game pass.

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
elements is accepted as the neutral body, and readback checks all 29 owned public
morphs, including zeros for every omitted morph. This candidate intentionally rejects
negative/extrapolated values. Different values are not certified safe geometry.

The allowlist matches the published 0.6.2.0 base resource contract: 28 shared
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

`../papyrus/claw/CLAWDistributionNative.psc` is the declaration source. Compile it with
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
| `ConfigureMorphLink(actor, profile, sources[], targets[], gains[], caps[])` | Queued explicit morph-to-morph profile, 0..128 structural rules; actual SKEE source coefficients, no preset-name pairs |
| `GetMorphFamilies(female)` / `ConfigureMorphFamily(actor, profileId)` | Enumerate and bind a validated body-resource mapping; setup must declare the actual installed family |
| `GetHumanWeight(actor)` / `GetBeastWeight(actor)` | Last observed normalized NPC weight in each form; -1 means unavailable, and neither getter sets weight |
| `DisableMorphLink(actor)` | Queued return to the retained independent preset |

Status values: **0** unknown, **1** pending, **2** own coefficients read back and
model update requested, **3** unloaded, **4** error, **5** human/own key cleared,
**6** explicitly cleared, **7** SKEE unavailable. A queued assignment can still
fail because race/sex/reference/3D changed. `GetOwnMorph` is a cached readback, not
the aggregate across mods. Inspect status before interpreting zero.
Explicit refresh immediately marks the request pending and hides its previous
coefficient cache until queued work completes or reports an error.

The optional [morph-to-morph bridge](../docs/transformation.md) reads actual
applied signed human coefficients through SKEE in main-thread tasks. It evaluates each configured function and sums its output times the gain,
clamps each target sum once to 0..1 and
multiplies by its configured cap; it never reapplies actor weight to those human
values. Linked output starts with all public own morphs neutral for the actor's
sex; every unmapped trait, including ears and tail, stays zero. Female breast
mapping is available in the matching measured female resource profiles; its
appearance still needs acceptance. No independent preset, catalog or actor
weight contributes, even if an older independent assignment is retained for
`DisableMorphLink`. `GetAssigned` is empty while linkage is enabled. The profile is explicit;
there is no universally calibrated default or automatic body-family detection.
Normal `AssignPreset` disables linkage. `ClearOwn` retains the mapping while
suppressing distribution; a valid explicit configuration resumes it. Disabling
linkage does not clear suppression. The existing
single own key is retained. Actor co-save v5 stores the mapping, functions and parameters, captured source
values and optional actual weight observations. Readers retain v1/v2/v3/v4 support;
v2 retains its 32-row budget, while v3/v4/v5 allow 128 rows. Version1 migrates to
independent mode. Linked records use the direct neutral baseline after refresh.
Real source aggregation and actual
save/load/transform behavior require separate acceptance evidence. The API queues
work: wait for the previous request to complete before submitting the next one.

## Build without installation

The current source builds one `CLAWDistribution.dll` through CommonLib's SE,
AE and VR runtime dispatch. The [universal runtime contract](../docs/universal-runtime.md)
lists its exact candidate versions and per-runtime SKSE minima. Candidate loading
is distinct from game qualification: SE and VR need fresh checks of this binary;
AE currently has structural review and offline build/policy checks only.
The frozen 30 October exact-SE and historical legacy-VR outputs are unchanged.

Use CMake 3.25+, x64 MSVC with C++23 support and an **external** configured
CommonLibSSE-NG SDK. The current pinned source is 9.1.0 at
`a898f469851c464d05137bb74b069dd234897643`, plus the owner's TypeInfo correction
`0c95630c29ff98f64caeea83c29ca373cf93e58b`. This SDK supplies explicit 1.7.104
layouts, both pre/post629 layouts, SE/AE/VR relocations and Papyrus bindings.
Its exact official OpenVR submodule remains external. The legacy 3.7.0 SDK is
insufficient for the universal build. No machine path is embedded in the source.

Download the pinned official external
[SKEE API header](https://raw.githubusercontent.com/expired6978/SKSE64Plugins/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/IPluginInterface.h)
as `IPluginInterface.h`; its SHA-256 is enforced by CMake. `dependencies.json`
records the SDK and upstream revisions. Pugixml is fetched with a pinned hash or
supplied through `FETCHCONTENT_SOURCE_DIR_PUGIXML`; modern SDK dependencies come
from the caller's external dependency prefix/toolchain. No vendor source is copied
into CLAW. Retain all dependency licenses in any corresponding-source package.
CLAW uses no trampolines, so the optional patch decoder is disabled.

```powershell
./src/main/cpp/build.ps1 -BuildDir './target/native' `
  -CommonLibDir '<external-current-commonlib-checkout>' `
  -SkeeHeader '<external-dependencies>/IPluginInterface.h' `
  -DependencyPrefix '<external-SDK-dependency-prefix>' -BuildTests
```

`-ToolchainFile` can supply a dependency toolchain instead. `UNIVERSAL` is the
only current runtime selector and the default; CMake accepts
`-DCLAW_RUNTIME=UNIVERSAL`. The one native target is `CLAWDistribution` and emits
`src/main/cpp/Release/CLAWDistribution.dll` beneath the selected build directory
for all three engine families. The helper rejects
older SE/VR build trees rather than replacing their historical binaries.

Both modern `SKSEPlugin_Version` and legacy `SKSEPlugin_Query` exports are
present. Version metadata and Query/Load share one exact candidate list; Load
checks the matching SKSE minimum and confirms CommonLib's actual detected
runtime family. Address Library V5 capability and CommonLib's variable-struct
compatibility declaration describe mechanisms, not completed game acceptance.
No unrestricted future-version promise is made.

The helper defaults to the installed VS2026 generator, accepts `-CMakeExe` and
`-Generator`, rejects source/live/archive output locations, and never installs or
runs tests or the game. It produces `src/main/cpp/Release/CLAWDistribution.dll`
and `src/main/cpp/Release/claw-preset-tool.exe` beneath the selected build directory.
`-BuildTests` only compiles the six optional test executables. Run them explicitly
with `ctest --test-dir target/native -C Release --output-on-failure`.
Core-only builds require pugixml but no SKSE/CommonLib/Windows:

```
cmake -S . -B target/native-core -DCLAW_BUILD_PLUGIN=OFF
cmake --build target/native-core --config Release
```

After the coordinator confirms testing readiness, explicitly configure
`CLAW_BUILD_TESTS=ON`, compile `claw-preset-tests` and run it or CTest. No post-build
command executes tests. Offline cases cover endpoints, sparse BodySlide exports,
typed families, exclusions, duplicate catalogs, bad input, stable selection,
nested third-party files and direct linked output with neutral unmapped traits
and no independent catalog/weight access. The earlier exact-SE DLL passed its offline contract checks. The universal
candidate adds runtime-policy checks alongside the existing core and matrix suites. Runtime acceptance still
needs a separately authorized
game test: multiple male/female beasts, UI assignment, human key preservation,
transform/race events, delayed/reloaded 3D, external OBody updates, saved dynamic
references and save/load. The earlier bounded SE mechanics run described above
does not qualify this revised linked behavior.
