# FSMP release motion and CBPC research adapter

`motion_adapter.py` builds a separate provider mod-manager archive from explicitly
selected male/female weight-0/1 NIFs and the existing pinned XP32 skeleton. The
CBPC research archive includes only original motion configuration and a short README.
Neither adapter changes the universal CLAW DLL, human-family matrices, skeleton,
other mods, or the optional collider host.
Only FSMP motion is offered by the working CLAW 0.10 installer. The standalone
CBPC generator remains offline research tooling, not a released runtime option.

## Optional integration in one CLAW installer

The source packager accepts `--fsmp-motion-build <fsmp-motion-build.json>` alone,
or no motion receipt. This is an unpacked builder output, not a ZIP input.
With no receipt, the existing core-only installer and 20 family/OBody selections
are preserved. An FSMP receipt adds a default-None, mutually exclusive
None/Faster HDT-SMP choice and 40 selection plans. `--cbpc-motion-build` is
explicitly rejected by the working packager. Packaging does not establish
runtime qualification.

Build the FSMP adapter from the exact four core body inputs and pinned skeleton,
with female P1 motion included. Each endpoint needs an explicit path even when
its bytes equal the other weight endpoint. The packager verifies source/resource
and output hashes, permits only the eight FSMP NIF routes plus two XMLs, and
discards the separate adapter README. Any
unlisted payload fails. Source/recipe pins remain external provenance; no builder,
provider DLL, skeleton, collider host, anatomy or VR component is installed.

The existing lightweight SSE reader independently checks the FSMP output against
the final material-adapted core: unchanged original non-root blocks and strings,
one appended root hook, and the exact sex-specific XML. Both armor routes must
match. BODYTRI retains the core sex-specific path; both modes reference the same
core TRI bytes and their hashes are recorded with the FSMP selection. Equal endpoint
and PlayerOnly aliases reuse archive sources. No installed destination depends
on overwrite priority: each selected plan supplies exactly one body source.

The matrix-family choices still select only human-to-werewolf coefficients.
They share the werewolf resources, so motion adds no family-specific NIF or DLL.
Current morphs retain their original skin influences; this does not make motion
constants, pivots or contacts adapt to morphs. Existing human physics can coexist
only without conflicting werewolf-node writers. Packaging neither inspects a live
profile nor verifies a provider's runtime version or lifecycle behavior.

```powershell
python src/main/python/physics/motion_adapter.py --provider fsmp `
  --provider-snapshot '<baseline-winning-SKSE/Plugins>' `
  --male0 '<selected-malebodywerewolf_0.nif>' `
  --male1 '<selected-malebodywerewolf_1.nif>' `
  --female0 '<selected-femalebodywerewolf_0.nif>' `
  --female1 '<selected-femalebodywerewolf_1.nif>' `
  --skeleton '<existing-XP32-skeleton.nif>' --pynifly '<PyNifly-add-on>' `
  --with-breast-motion --out '<new-external-build-directory>'
```

Omit `--with-breast-motion` for the ear/tail adapter. All five explicit resource
paths remain required. Public PyNifly readback requires every intended existing
driver node and nonzero stored skin weights on each applicable body endpoint.
Thus a body containing P1 node names without actual P1 influences cannot pass.
The builder derives a new explicit P1 resource binding from the inspected female
endpoints. It reuses the existing motion-only recipe without editing its legacy
body pin. It neither reconstructs nor approves a new breast rig.

In the research-only CBPC generator, both ears (four links) and the tail (five links, including TailBone04) use the
existing race-gated original parameters. P1 is female-only. All collision response
multipliers are zero in this adapter: detailed capsule/contact work remains a
separate package and qualification. The private `CLAW_*` aliases deliberately
conflict with the earlier `CLAWPhysics`, `CLAWBreastPhysics` and
`CLAWBreastContact` motion configs. Choose one motion package; enabling both is
rejected by the static ownership audit rather than guessed to be harmless.

The CBPC baseline provider snapshot must contain a nonempty `cbp.dll`, a master config,
and all effective CBPC/SMP configuration bytes relevant to the selected profile,
before adding this adapter. Existing exact-node/ancestor writers and private-alias
reuse block creation. Presence and hashes do not qualify loaded DLL behavior,
the VFS, XML selection or race rebinding. Static audit limits in `README.md`
still apply. The deterministic ZIP is read back byte-for-byte. The external build
report records resources, stored-weight coverage, source/dependency pins, provider
inventory and archive/file hashes. Inputs are rechecked after packaging; an
interrupted or changed-input build retains `FAILED-unverified-do-not-install`.

For the exact reviewed CBPC1.7.3/SSE1.7.104 image, a bare stock Pelvis row is a
read anchor for four different child write targets. The audit retains that row
and checks its actual write set; unknown images and aliased rows remain potential
Pelvis writers. See the [binary role evidence](../../../test/docs/cbpc-pelvis-role-2026-11-11.md).
The full loaded graph still needs separate ancestry qualification before a run.

Ear/tail ownership includes the exact non-driver ancestor union read from the
pinned XP32 skeleton: Head/Neck/Spine, Tails/Pelvis, CME wrappers and shared roots.
This applies with or without P1 motion. Explicit system-level FSMP bones with one
finite zero-mass child element remain kinematic anchors, including their constraint
references; their references are retained separately in the audit. Omitted,
template-only, conflicting or implicitly created-before-declaration bones remain
potential writers; the audit does not guess mesh-driven or template defaults.
Ordinary animation files are not scanned as physics configuration.

Linked morphs already deform the same skinned vertices that receive node motion.
They do not require a second conversion or a morph-family-specific motion DLL.
This adapter does not observe coefficients, change stiffness, move rest-node
origins, refit colliders or claim tight contact as geometry changes. The existing
current-vector native observer/finite collider host supplies that separate path
when compiled with a matching model, qualified and explicitly enabled. The
motion-only archive cannot enable that host or its snapshot authority.

Select `--provider fsmp` for the working installer's motion resources in `fsmp_motion.py`.
It emits original XML with nine or eleven dynamic bones, kinematic anchors,
restoring linear/angular springs and no collision shapes. Tail constraints
connect existing driver nodes across unchanged CME wrappers. Ear/tail identity
`frameInB` uses actual loaded rest transforms. The two single-body P1 joints use
identity `frameInA`, attaching at the kinematic PreBreast origin instead of the
dynamic body's center. The pinned skeleton has a one-unit P1 lever; this pivot
change is mechanical. Earlier isolated cases recorded female11 and authored
male9 sampled response after observed
Disable/unloaded/Enable root recreation, with the actual pulse fenced to the
replacement graph. These cases do not establish human-origin transformation,
cell unload, player routing, contacts or synchronized solver/render phases. Complete motion
release acceptance still requires the [remaining lifecycle checks](#release-cut-acceptance-boundary).
Translation limits are +/-0.15 per axis;
Euler limits are +/-0.01 radians. These are original small-motion trials.

FSMP needs a mesh binding. Four selected sex/weight inputs produce eight standard
and PlayerOnly body destinations. It rewrites the declared base diffuse paths
to separately installed Elegant PlayerOnly textures, then adds one
`NiStringExtraData` named `HDT Skinned Mesh Physics Object` and one Scene Root
reference to each endpoint. Geometry, UVs, normals, skin weights and BODYTRI remain
unchanged; material-path adaptation and the XML hook are the intended edits.
Public native readback resolves all eight hooks and stored driver influences.
An existing binding is refused. No global
`defaultBBPs.xml`, skeleton, TRI, provider binary, contact model or host is
included. Install this separate binding patch after the exact selected core
body. Its matching TRI and a separately installed runtime-matched provider are
required. Generation can succeed while FSMP is absent; the report records that
dependency and never qualifies behavior by file presence.

An FSMP-only baseline does not require CBPC or `CBPCMasterConfig.txt`. The FSMP
builder omits only that CBPC prerequisite: all present CBPC/SMP configurations,
private aliases, driver/ancestor references, malformed XML and inventory changes
remain checked. CBPC motion and collider builds retain the master requirement.

Binding and XML names follow the inspected provider's
[mesh selection](https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/hdtDefaultBBP.cpp)
and [constraint parser](https://github.com/DaymareOn/hdtSMP64/blob/e52ad960048c14e637d14fcbd65314ca017fc3b8/src/hdtSkyrimSystem.cpp).
Source/binary equivalence remains unverified. FSMP motion provides no
actor-scoped replacement for CBPC's current-vector capsule API. Choose one
werewolf motion adapter. Existing human physics can coexist only when it does
not own the selected werewolf driver nodes/ancestors.

Build success means an inspectable offline adapter, with `gameValidated`,
`runtimeQualified` and `releaseReady` all false. Runtime acceptance still needs
node traces and visible ears/tail/P1 motion, neutral/disabled controls, both sexes,
weight and morph extremes, transformations, reload and human return. Bounds for
the chosen motion envelope are a separate geometry prerequisite.

The next motion trial uses the exact released v4 body endpoints and matching
TRIs. The fresh v4 body pipeline already applies the current-TRI P1 rig and
nominal motion bounds; another skeleton or morph-family-specific physics DLL is
not required. The working installer uses FSMP only; separate CBPC research is
not release qualification. Include born beasts and NPCs first admitted while
human, then transformed, so a successful initial beast bind cannot conceal a
race/root rebinding failure. Compare local driver motion with controlled movement
and a disabled/neutral control; inherited world motion alone is insufficient.
The existing offline FSMP tests exercise full package construction, written-hook
readback and changed-input rejection using synthetic NIF/API fixtures. They do
not run PyNifly, a solver or the game, and do not change the runtime status above.

## Current-TRI P1 rig and nominal bounds

`p1_rig.py` with `p1-rig-v3.json` is an explicit post-export stage for the actual
expressive v3 female NIF/TRI and existing read-only XP32 skeleton. Its
`build_candidate(body, tri, skeleton, profile_file, output, pynifly_directory=None)`
returns the external `report.json` path. The contract pins 85 source nodes,
91 output nodes, 53 actual fixed collar anchors and 29 public morphs. The older
rig's frozen 55-anchor/moderate-TRI contract is unchanged.

Expressive v4 uses a separate `p1-rig-v4.json` with profile name
`expressive-v4-current-tri-existing-xp32-p1-v1` and semantic version
`expressive-body-v4-separate-biceps-triceps-soft-arm-girth`. Its exact female
inventory contains 31 public morphs, including both `CLAWArmBiceps` and
`CLAWArmTriceps`. `CLAWArmGirth` remains the soft arm field. A same-sized inventory
with another arm-muscle name cannot satisfy this contract. The new resource pins
do not authorize v3 inputs or alter `p1-rig-v3.json`. Both stages retain the
85-to-91 node graph, 53 collar anchors, current BreastSize mobility method and
existing rig verification thresholds. These P1 checks do not establish posed
belly/thigh clearance or behavior of the two new arm fields; the geometry stage
owns those separate checks.

The new scalar mobility uses actual current head BreastSize displacement
magnitude normalized by its maximum, with bounded upper/lower roots, a fixed
face cutoff and collar anchors. Existing capacity guards, layer projection,
Spine2 transfer, XP32 bind writing and native readback are reused. No old
moderate TRI, retained NIF or weight blob is consumed. Current TRI stays byte
exact. The existing 151 controlled skeletal poses run at actual current
BreastSize 0/0.5/1. Ordinary-motion thresholds, four-influence guard, old bind
preservation and bilateral stored head coverage remain unchanged. Fur/skin
common motion, all combined morphs, animated seams and appearance remain pending.

After the named-morph bounds stage, `motion_bounds.py` `build(sourceDir,
outputDir)` accepts a directory containing the six body files, returns its report
and writes `Meshes/Actors/WerewolfBeast/Character Assets/` plus
`motion-bounds-report.json`. It extends sphere radii for five composed nominal
joint corrections, each with at most 0.5 per-axis translation and 0.0105 per-axis
Euler rotation, retaining the existing center. The recurrence includes increasing
lever arms, a one-unit lever allowance and packed-weight margin. Independent
binary readback proves only shape-sphere fields change; TRI and all other NIF
fields stay exact. Source/profile and output hashes are recorded.

That envelope assumes unit actor/node scale, unit adapter amplitude and no other
driver/armor pushup/contact or ordinary-animation displacement. It covers
declared constants without proving provider solver compliance: FSMP constraints
can overshoot numerically. Runtime traces must check these assumptions.
Enlarged bounds do not establish visible motion or contact quality.

## CBPC runtime admission investigation

CLAW 0.10 excludes CBPC motion from the working installer. The actual
human-to-wolf case did not create the selected wolf simulation Things, and the
inspected public API supplies no actor-scoped reset/rebind. No global reload is
introduced as a workaround. The standalone generator remains available for
offline research; its narrow amplitude evidence does not qualify automatic
human-origin binding. See [the human-origin record](../../../test/docs/cbpc-human-origin-automatic.md).

The first six-wolf observation used the installed CBPC 1.7.3 runtime-specific
SE 1.7.104 binary. All 240 requested bone observations were available. Ear/tail
rotations varied, while all six P1 local transform sequences were exactly
constant. P1 world positions nevertheless moved 5.17 to 9.12 units. Animation
and other writers can account for these observations; they do not establish
solver ownership or visible physics. The available observer has no qualified
CBPC bound-node inventory getter.

The provider's public [SimObj binding](https://github.com/Acro748/CBPCSSE/blob/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20/CBPC/SimObj.cpp)
checks node conditions and finds the node during a cached actor bind. Its
[actor scan](https://github.com/Acro748/CBPCSSE/blob/fabd56ce8f8ac10cde17325f0bd61ecc8cbcda20/CBPC/scan.cpp)
only binds actors whose cached object is unbound. Player beast-form changes,
cell changes and configuration reload clear that cache; this source does not
show an equivalent NPC root/race transition check. A subject admitted while
human could therefore lack the subsequently applicable werewolf-only rows.
That is a testable source-backed hypothesis. This cached source is from 2022;
equivalence to the installed 1.7.3 binary has
not been established.

The exact 1.7.3 FOMOD archive supplies the original `CBPCPluginScript.psc` with
`GetVersion`, `GetVersionMinor`, `GetVersionBeta`, `ReloadConfig`,
`StartPhysics`, `StopPhysics` and actor-setting refresh declarations. It supplies
no bound-node inventory getter. In the public implementation, `ReloadConfig`
requests cache clearing; Start/Stop only change suppression for a named node.
A later declared diagnostic can compare the same transformed actors before
and after one provider reload, followed by a controlled motion and disabled
comparison. No such call is implicit in an adapter build, and an unobserved
reload must not be presented as an automatic transformation fix. No additional
dependency or `extraRaces` edit is justified by the current evidence.

## Release-cut acceptance boundary

This source cut adds the motion builders and installer selection, retaining the
existing v4 geometry, skin weights, P1 rig and nominal shape bounds. It does not
include VR, anatomy extensions or a new contact model. The finite collider host
remains separate and disabled; choosing motion does not grant its authority.

Historical binding or response cases do not qualify this cut. FSMP
still requires matching installed resources and measured selective response,
then human-to-wolf admission, refresh, human return and a second transformation,
actual model recreation, save/load and cell-unload/reload checks with cleanup.
Visible motion, solver limit compliance and morph/weight/scale coverage are
separate observations. Exported constants and enlarged rest bounds do not
predict actual motion amplitude.
