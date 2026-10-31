# Separate motion adapters

`motion_adapter.py` builds a separate provider mod-manager archive from explicitly
selected male/female weight-0/1 NIFs and the existing pinned XP32 skeleton. The
CBPC archive includes only original motion configuration and a short README.
Neither adapter changes the universal CLAW DLL, human-family matrices, skeleton,
other mods, or the optional collider host.

```powershell
python src/main/python/physics/motion_adapter.py --provider cbpc `
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

With CBPC, both ears (four links) and the tail (five links, including TailBone04) use the
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

Linked morphs already deform the same skinned vertices that receive node motion.
They do not require a second conversion or a morph-family-specific motion DLL.
This adapter does not observe coefficients, change stiffness, move rest-node
origins, refit colliders or claim tight contact as geometry changes. The existing
current-vector native observer/finite collider host supplies that separate path
when compiled with a matching model, qualified and explicitly enabled. The
motion-only archive cannot enable that host or its snapshot authority.

Select `--provider fsmp` for the separate FSMP alternative in `fsmp_motion.py`.
It emits original XML with nine or eleven dynamic bones, kinematic anchors,
restoring linear/angular springs and no collision shapes. Tail constraints
connect existing driver nodes across unchanged CME wrappers. Identity `frameInB`
uses actual loaded rest transforms. Translation limits are +/-0.15 per axis;
Euler limits are +/-0.01 radians. These are original small-motion trials.

FSMP needs a mesh binding. The adapter appends one `NiStringExtraData` block named
`HDT Skinned Mesh Physics Object` and one Scene Root reference to each of four
cloned selected body NIFs. Existing block IDs, strings, roots and every non-root
block remain byte exact. Public native readback resolves all four written hooks
and stored driver influences. An existing binding is refused. No global
`defaultBBPs.xml`, skeleton, TRI, provider binary, contact model or host is
included. Install this separate binding patch after the exact selected core
body. Its matching TRI and a separately installed runtime-matched provider are
required. Generation can succeed while FSMP is absent; the report records that
dependency and never qualifies behavior by file presence.

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

## Current-TRI P1 rig and nominal bounds

`p1_rig.py` with `p1-rig-v3.json` is an explicit post-export stage for the actual
expressive v3 female NIF/TRI and existing read-only XP32 skeleton. Its
`build_candidate(body, tri, skeleton, profile_file, output, pynifly_directory=None)`
returns the external `report.json` path. The contract pins 85 source nodes,
91 output nodes, 53 actual fixed collar anchors and 29 public morphs. The older
rig's frozen 55-anchor/moderate-TRI contract is unchanged.

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
