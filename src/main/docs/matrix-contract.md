# Human-to-wolf coefficient and function matrices

Each profile is an ordered sparse representation of two matching matrices:
`gain` is coefficient C, and `function` with its parameters is function F.
The source is a human morph column and the target is a wolf morph row. Missing
edges contribute zero. A constant edge uses the explicit empty source column
`source=""`; that column never names or reads a human morph.

For each target, accumulate `gain * F(human[source])` in XML rule order using
binary64 arithmetic. Clamp the completed sum to [0,1], multiply by the target's
cap, then round once to float32. All inputs, gains, caps and constant values are
finite float32. Each target has one consistent cap in (0,1]. NPC weight and
independent body presets are absent. Unmapped public wolf outputs start at zero.
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

Existing schemaVersion=1 XML remains readable with precisely its original linear
math. New attributes are additive, for example:

```xml
<Rule source="Muscle" target="CLAWTorsoGirth" gain="0.7" cap="1" />
<Rule source="Muscle" target="CLAWArmLean" gain="0.5" cap="1" function="negative" />
<Rule source="Belly" target="CLAWTorsoBellyRound" gain="1" cap="1" function="power" exponent="2" />
<Rule source="" target="CLAWTorsoChestSize" gain="1" cap="1" function="constant" value="0.4" />
```

JavaScript uses the same fields in a profile's `rules` array; gain/cap/value are
numbers and exponent is an integer. `CLAWLink.validateMatrix(profile)` returns a
validated profile, `evaluateMatrix(profile,humanValues)` returns the usual values,
rows and per-edge contributions, and `exportMatrix(profile)` emits standalone
MorphLinkProfiles XML. `evaluate(catalog,id,humanValues)` retains its existing API.
Explicit linear and omitted linear produce identical outputs. The matrix keeps
ordered sparse edges rather than reordering a sum through a dense table.

Actor co-save record v5 persists each rule's function code, exponent and constant
value. Readers retain versions 1..4: v1 is independent, v2..4 rules migrate to
linear. Saved rules remain authoritative after load; replacing a family XML does
not silently change a saved actor. Explicit ConfigureMorphFamily binds a fresh
validated profile. Existing ConfigureMorphLink Papyrus arrays continue to create
linear rules; new function profiles use ConfigureMorphFamily. No runtime or
rendered-body qualification follows from offline arithmetic parity.

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
