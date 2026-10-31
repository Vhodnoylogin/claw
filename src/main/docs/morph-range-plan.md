# Expressive morph range and release sequence

Owner direction, 30 October 2026: freeze the working projection as a technical
Git release, then make ordinary human presets visibly distinguish wolves.
The final artistic judgement belongs to the owner. The offline comparison tool
must measure the actual mesh response before another game inspection.

## Latest paired game evidence

The accepted twelve-actor QASmoke scene contains six pairs with equal observed
conversion inputs. Reads compared 339 configured conversion-source values per
side: 61 names for each male type and 52 for each female type. Keyed evidence and
actor weight were also compared. There were zero pair differences within
that captured scope. These are historical runtime reads, not the full human
morph set. Maximum error between native stored wolf coefficients and the declared
conversion is 5.43e-8. This measures stored morphs, not posed rendered vertices.

The external `claw-morphbench-addon-20261030/real-pair-inputs/` reconciliation
separately reconstructs all 834 assigned-preset values for the six human types,
including 22 negative values; the observed configured subset contains 339 values
and 20 negatives. Five nonzero female preset entries were outside that capture:
FThin `BigButt=-0.25`, `Butt=-0.5`; FMuscular `MuscleAbs=0.8`; FHeavy
`BigButt=0.14`, `Butt=0.21` (rounded here). They are currently unmapped and do not
change the linked wolf outputs, but matter to a full preset-based human-body comparison.
Those additions come from the assigned preset and must not be presented as
runtime-measured values or replaced with invented zeros. Observed values match
their preset counterparts at float32 precision. Full reconstructed human inputs
and captured conversion inputs remain distinct fixtures; no new game capture is
implied.

| Pair | NPC weight (0..100) | Arm girth | Thigh girth | Belly | Breast | Torso girth | Waist narrowing |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Iney | 100 | 0 | 0 | 0 | — | 0 | .767 |
| Kedr | 100 | 1 | .320 | .007 | — | 0 | 0 |
| Grom | 30 | .255 | .228 | .796 | — | .240 | 0 |
| Lada | 100 | 0 | 0 | 0 | 0 | 0 | .450 |
| Mira | 100 | 1 | .478 | 0 | .540 | 0 | .394 |
| Runa | 50 | .800 | .418 | 1 | 1 | .159 | 0 |

All six currently have zero linked head, ear, tail, paw, claw and digitigrade
coefficients. Iney's arm raw sum is -1.810; Lada's is -.589. They become zero,
leaving the neutral bulky mesh. Both sexes still have byte-identical `_0`/`_1`
files. Merely separating actor-weight endpoints would not fix Iney/Lada at the
same weight100; named lean deformations are independently necessary.

Runa already saturates belly and breast. Increasing conversion gains cannot
extend their authored endpoints. Torso girth is deliberately capped at .25
because the wider field had geometry-quality problems; lifting that cap is not
a substitute for repairing the field.

Fresh offline reconstruction applied these captured vectors to the exact frozen
NIF/TRI files and intersected their triangles at model-space Z68..96, within
X±10. At Z80 the combined coat front moves +11.414 units for Grom and +9.677
for Runa. At Z84 Runa's belly-only skin moves +8.592 but the fur front moves0;
Grom's fur moves +6.527. The upper female coat obscures the underlying belly
response in this geometric envelope. Alpha transparency, skinning, lighting and
the actual posed silhouette remain outside that measurement. Do not call these
model-space lengths live world measurements or rendered visible volume.

Raw configured-source snapshots, input hashes and section reconstruction are
retained in the external `manual-pairs-live-20261030-2/` evidence directory.
The full-preset reconciliation is retained separately in `real-pair-inputs/`.

## First shape iteration

1. Keep the frozen release intact. Author a versioned geometry candidate with
   explicit lean and bulky endpoints at a common actor weight. Start with
   torso, upper arms, thighs and calves, then chest/breast. Preserve seams,
   joints, floor contact, UV/material assignments and existing XP32 bindings.
2. Prefer opposed nonnegative named fields over silently extrapolating TRI
   values or changing the native output range. A positive growth sum activates
   growth; its negative activates the corresponding lean field. Zero remains
   the documented neutral. New target names require updates to the native
   allowlist, authoring resources and conversion together; XML alone is not an
   implementation. Calibrate each side against its measured deformation.
3. Deform skin and all related fur layers together. Make belly growth rounder
   and distributed over its true abdomen support. Broaden female breasts along
   the torso and settle the mass downward, with less forward projection.
   Recheck axilla/under-breast joins and mixed head/torso geometry.
4. Compare isolated targets at0/.25/.5/.75/1 and finite combinations, for both
   sexes and weights0/.5/1. The same effective human vector must produce exactly
   the same wolf vector in native code and the Morphbench plugin. Build the human
   comparison mesh from the complete qualified human input vector, preserving
   which values were observed and which were reconstructed from the preset.
   Never multiply already weighted human values by NPC weight a second time.
5. Only after offline range/quality checks pass, install a complete candidate
   and repeat the accepted twelve-actor scene, followed by roundtrip/save-load
   checks. Keep layout110/300/320, AI/collision Off before fixture creation.

## Measurements owned by CLAW

Use fixed anatomical cross-sections and projection masks derived from the
neutral model, including separate skin and fur support. Record width, depth,
cross-section area and front/side silhouette change, not only maximum vertex
displacement. Use robust central ranges alongside full envelope extremes so a
single claw or fur-card tip cannot determine torso size. Report alpha-ignorant
envelopes separately from textured image comparisons.

For an established human/wolf region pair, compare dimensionless responses
`H=log(humanDimension/humanNeutralDimension)` and
`W=log(wolfDimension/wolfNeutralDimension)`. Require matching sign and monotonic
ordering; evaluate `W/H` only when H exceeds the region's measured noise floor.
Set the desired response interval after measuring neutral/min/max human and
wolf meshes. Arbitrary larger coefficients do not establish a good proportion.
Also retain seam-gap maxima/P95, attachment drift, flipped/degenerate triangles,
UV stretch and finite serialized skin weights. No single score overrides a
failed topology/attachment check or the owner's visual judgement.

## Optional control terminology

- **Morph Link Profile:** a transformation profile changing the gains, caps or
  curves of the deterministic human-to-wolf mapping. The human vector remains
  the source; this is not a second human body preset.
- **Standalone Werewolf Preset:** an independent fixed wolf vector that
  explicitly bypasses human morphs. Equal low/high morph vectors are necessary
  when using the legacy interpolated format; actor-weight geometry remains a
  separate input. This optional mode must never silently replace linked mode.

Human head/face links and traits without a counterpart are specified separately
in [human-head-traits.md](human-head-traits.md). Ear measurements may drive ears;
unsupported tail/claw controls remain explicit profile choices, with no arbitrary
belly-to-tail or eyebrow-to-claw rule.
Head capture and human-driven ear/tail/claw source selection remain separate open
implementation tasks; the paired body-preview plugin does not complete them.

## Proposed small releases

These are planning ranges in focused engineering hours, not measured delivery
dates. Artistic feedback and a newly found engine/provider issue can change them.
Each release includes its own offline checks and a short qualified game trial.

| Next slice | Scope | Initial planning range |
| --- | --- | ---: |
| 1. Visible contrast | Lean/bulky body fields, abdomen/muscle mapping, first static breast improvement; practical paired comparison | 12–24h |
| 2. Authorable profiles | Clearly separate Morph Link Profiles and Standalone Werewolf Presets; examples, deterministic priority/persistence | 6–12h |
| 3. Coat colour | Per-actor material isolation, all coat layers, readable human hair colour and restoration | 6–16h |
| 4. Head and traits | Qualified human head capture, muzzle/head/ear links; explicit unsupported tail/claw choices | 12–24h |
| 5. Ear/tail physics | Motion/contact, body-fit and morph-responsive colliders, distinct weight endpoints after shape stability | 16–32h |
| 6. Breast physics | Final static shape/weights, existing-bone motion, contact, fur attachment and lifecycle checks | 12–24h |

The current physics fit mismatches all six frozen NIF/TRI resources; it needs a
new geometric fit or a proven support-preserving rebase before installation.
See [physics-next-stage.md](physics-next-stage.md). VR first-person body and the
separate adult anatomy/physics module remain later releases with estimates to
be refined after their integration probes. A runtime port is also distinct from
VR first-person body work: the frozen native DLL explicitly supports only
SE1.7.104, regardless of CommonLib's three enabled edition flags.
