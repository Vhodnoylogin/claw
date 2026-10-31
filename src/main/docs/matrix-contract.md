# Human-to-wolf coefficient and function matrices

Each profile is an ordered sparse representation of two matching matrices:
`gain` is coefficient C, and `function` with its parameters is function F.
The source is a human morph column and the target is a wolf morph row. Missing
edges contribute zero. A constant edge uses the explicit empty source column
`source=""`; that column never names or reads a human morph.

For each target, accumulate `gain * F(human[source])` in XML rule order using
binary64 arithmetic. Clamp the completed sum to [0,1], multiply by the target's
cap, then round once to float32. All inputs, gains, caps and constant values are
finite float32. Each target has one consistent cap in (0,1]. Independent body
presets are absent. Actor weight contributes only through an explicit matrix
source; it never multiplies the already-effective RaceMenu inputs or the final
output. Unmapped public wolf outputs start at zero.
After float32 normalization, an edge with `abs(gain) <= float32(1e-6)` is absent,
independently of the current source value. The shared exports
`claw_matrix_gain_epsilon()` and `claw_matrix_gain_active(float)` define this
inclusive cutoff for native/WASM consumers. Rule syntax and finite parameters
are validated before omission; active duplicate/cap checks, source capture,
target binding and canonical save/export operate on the surviving ordered edges.
This is not a contribution/output threshold. A large-gain edge with a zero input
is retained. The separate runtime readback tolerance remains 1e-4.

Source and target names preserve their authored spelling. Provider-bound names
are printable ASCII of at most 160 bytes without surrounding whitespace/control
characters. SKEE's `SKEEFixedString` uses `hash_lower`/`_stricmp` identity, so active
names differing only in ASCII case cannot represent independent game controls.
The adapters use deterministic A-Z to a-z identity, reject case-only source or
target aliases, and keep repeated identical spellings for valid many-to-many
edges. No process-locale case conversion is used. Linked
targets have no body-prefix or compiled sex/name allowlist; actual model TRI
availability must be checked by the resource consumer. The generated native XML
format retains its existing printable ASCII/entity-free restrictions. Legacy
independent-preset validation is unchanged. At most 128 structural edges and 64
distinct active targets are supported. Native output metadata also retains the
legacy neutral names outside those 64 numeric target slots.

An active source must not share provider identity with an active output target,
including across
different edges. This rejects refresh feedback rather than treating the DLL's
own wolf output as a new human input. Runtime capture also refuses an input name
that currently exists under CLAW's exact output key; clear that prior assignment
before explicitly rebinding. Other valid human source prefixes are accepted.
An empty/all-omitted profile remains an enabled, neutral linked profile and reads
no human sources; it never falls back to an independent beast preset.
The one implementation is `src/main/cpp/shared/MatrixKernel.cpp`, compiled into
the native DLL and into the plugin's WebAssembly module. JavaScript validates and
marshals profiles; it does not provide an alternative numeric implementation.
The independently maintained [Morphbench plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
uses an explicit pinned dependency on CLAW's kernel source rather than keeping a
second implementation or a permanent plugin subtree in this repository.
Function evaluation and each product/sum use binary64 after float32 parameter
normalization. Compiler contraction is disabled; operation order is preserved.

| F name | Parameters | Binary64 evaluation |
|---|---|---|
| `linear` (default) | none | x |
| `positive` | none | max(x,0) |
| `negative` | none | max(-x,0) |
| `smoothstep` | none | t*t*(3-2*t), t=clamp(x,0,1) |
| `power` | integer `exponent` in 1..8 | t=clamp(abs(x),0,1); multiply t by itself exponent times in order; restore x's sign |
| `constant` | finite float32 `value` | value; source must be empty |

There is no arbitrary expression or executable-code evaluation. Unknown functions,
irrelevant parameters, malformed numbers, duplicate source/target edges and
inconsistent caps fail validation. Functions other than constant require a valid
human source. Power deliberately uses integer repeated multiplication rather
than platform transcendental math. All-constant profiles capture an empty source
snapshot and require no human input. Constant-only columns never appear in source
capture or the mapped-human set, including in a mixed profile.

Existing schemaVersion=1 XML remains readable; retained linear edges keep their
original arithmetic, subject to the explicit coefficient cutoff above. Function
attributes are additive, for example:

```xml
<Rule source="Muscle" target="CLAWTorsoGirth" gain="0.7" cap="1" />
<Rule source="Muscle" target="CLAWArmLean" gain="0.5" cap="1" function="negative" />
<Rule source="Belly" target="CLAWTorsoBellyRound" gain="1" cap="1" function="power" exponent="2" />
<Rule source="" target="CLAWTorsoChestSize" gain="1" cap="1" function="constant" value="0.4" />
```

## Explicit actor weight and the five default matrices

`$actor.weight` is the sole built-in actor input. It is represented as an ordinary
source column in the matrix. The game adapter reads the current NPC base weight
in 0..100 and divides it once by 100; the evaluator and offline plugin receive
the resulting finite float32 in 0..1. It is not a SKEE/TRI morph. Missing or invalid
weight is an error, not an implicit zero. All other source and target names remain
data-driven; adding a real morph does not require rebuilding the DLL.

The ASCII-casefolded `$actor.` namespace is reserved. Only the exact spelling
`$actor.weight` is supported, and reserved names cannot be output targets. The
shared C++ source-kind and source-value validators are compiled into both native
and WebAssembly consumers. Ordinary human inputs remain signed, already-effective
SKEE values. The scalar is recaptured on refresh, including for originally-beast
actors, and stored in the same source snapshot as the other declared inputs.
Scalar-only matrices neither request OBody generation nor depend on human TRI
availability. Mixed matrices still let OBody supply their ordinary morph inputs.

The canonical file contains HIMBO male, CBBE female, 3BA female, Vanilla male and
Vanilla female matrices. Every matrix explicitly includes weight. Installation
selects exactly one male and one female matrix independently; no random matrix
distribution or runtime mesh-name guess is involved. Existing saved assignments
remain authoritative until explicitly rebound to a selected default.

For the modded families, the new centered weight terms affect torso lean/girth;
their combined contribution is zero at weight 50. The original calibrated morph
edges are retained. At the weight endpoints the added torso contributions are
bounded to 0.125. Vanilla uses only weight and constant bias cells: weight 50 is
neutral, lower weights add lean fields and higher weights add growth fields for
limbs, torso and belly. These are conservative authored defaults, not a new
artistic calibration or a claim of installed-game acceptance.

The Morphbench plugin keeps the scalar in a separate `actorWeight` field. It
never writes `$actor.weight` into a human model's morph controls. Both previews
use explicitly selected fixed NIFs; changing the scalar does not interpolate
the human neutral `_0`/`_1` geometry. The preview states that limitation.

JavaScript uses the same fields in a profile's `rules` array; gain/cap/value are
numbers and exponent is an integer. `CLAWLink.validateMatrix(profile)` returns a
validated profile, `evaluateMatrix(profile,humanValues)` returns the usual values,
rows and per-edge contributions, and `exportMatrix(profile)` emits standalone
MorphLinkProfiles XML. `evaluate(catalog,id,humanValues)` retains its existing API.
Explicit linear and omitted linear produce identical outputs. The matrix keeps
ordered sparse edges rather than reordering a sum through a dense table.

Actor co-save record v6 persists each rule's function code, exponent and constant
value. Readers retain versions 1..5: v1 is independent, v2..4 rules migrate to
linear. Version 6 retains the v5 byte layout, but identifies the explicit actor
source semantics. A pre-v6 assignment containing a now-reserved `$actor.` name
is retained as suppressed and requires an explicit rebind; it is never silently
reinterpreted as an actor scalar or replaced by a new default. On load,
now-inactive saved rules and their declared source-snapshot entries are removed;
unrelated entries, missing active values and nonfinite values still reject the
record. A saved neutral/all-omitted link remains linked. This deliberately applies
the new coefficient cutoff to old tiny edges, without substituting a current XML
profile. Saved rules remain authoritative after load; replacing a family XML does
not silently change a saved actor. Explicit ConfigureMorphFamily binds a fresh
validated profile. Existing ConfigureMorphLink Papyrus arrays continue to create
linear rules; new function profiles use ConfigureMorphFamily. No runtime or
rendered-body qualification follows from offline arithmetic parity.

Runtime cleanup snapshots every name under the exact `CLAW.Distribution` key,
then clears those names after enumeration. Removed/custom names cannot survive
because a new catalog no longer lists them, and other providers' keys are not
cleared. Actual writes omit zero coefficients; zeros remain part of legacy
coefficient metadata/readback without affecting SKEE's aggregate source policy.
Linked cache metadata is bounded by 64 active targets plus 29 legacy neutral
names. Original independent-preset cache validation remains sex/allowlist based.

The current default profiles retain their explicit family IDs and existing
linear growth edges, and append positive/negative edges for four new authored
fields: CLAWArmLean, CLAWLegThighLean, CLAWLegCalfLean and CLAWTorsoLean. Their
calibration marker is `authored-opposed-matrix1`. Male lean gains are deliberately
stronger than the old growth projection so the retained slim fixture uses the
new geometry. This is an offline authoring choice, pending visual acceptance.
The original linear XML is retained at
`src/main/resources/profiles/legacy/MorphLinks-linear-20261030.xml`; the frozen release
is unchanged. A source-independent example lives at
`src/main/resources/profiles/examples/ConstantWolf.xml`. Neither nested file is scanned
automatically: runtime loads its one explicit SKSE/Plugins/CLAW/MorphLinks.xml.

Existing saves continue their saved matrices after upgrade. To adopt these
defaults for an existing actor, explicitly call ConfigureMorphFamily after the
new resources and family XML have been installed. Fresh-game/default adoption
and an existing-save matrix refresh are separate game checks.
