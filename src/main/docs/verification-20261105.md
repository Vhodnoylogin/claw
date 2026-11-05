# Development verification, 5 November 2026

This record separates installed-game evidence from source checks. It does not
promote the development branch or its optional physics components to a release.
The measured game runtime was Skyrim SE 1.7.104 / SKSE 2.3.1.

## Classic UNP conversion

Native runtime source `f3e1e741b98576901155640e02f2343ca7cdf024` completed a
fresh original-UNP trial, `20261105-161532-7664d6`:

- Two human baselines, transformation, model refresh, owned save/load, native
  remapping of both references, human return and another transformation.
- Twelve snapshots with 31 targets each: all 372 comparisons matched the
  production evaluator after conversion to the game's float32 representation.
  The largest decimal serialization difference was approximately `4.90e-10`.
- Human source values and foreign morph keys were preserved. The roster remained
  frozen in 48 before/after observations of AI and controller collision state.
- The owned game exited normally with code zero. The copied profile and saves
  were archived, the temporary profile removed and the environment restored.

The actual raw actor weights were 100 and 50, normalized to 1 and 0.5. Eleven
targets differed between these actors. This is not a controlled dynamic-weight
change test. The two recorded counterfactuals changed the unused `ArmsSide`
input; all outputs correctly stayed unchanged. They are negative controls, not
weight counterfactuals.

The formal tool report retains 32 passed assertions and six observational race
actions. Later snapshots confirm their resulting races. Observations have not
been relabelled as assertions. The result does not establish every body family,
other game-runtime boundary or visual quality.

## Individual coats

The installed candidate provides automatic hair-group/seed selection, manual
pattern assignment, persistence and actual-material audit APIs. Packaging checks
cover the complete Elegant coat library and every installer selection. Saved
automatic selections were also decoded from an owned co-save.

The fresh trial `20261105-231700-e041a9` completed all eight finite coat phases
using the same native runtime: automatic selection, an independent actor control,
two manual selections, refresh, owned save/load, reset to automatic and normal
finish. All 109 commands have distinct submission receipts; none was replayed.

Fourteen fresh material audits checked 12 managed surfaces each. The head and
body diffuse paths and the actually bound texture resources matched the selected
catalogue entries. Material, shader and texture-set ownership checks passed;
Original mode retained neutral tint and finite donor alpha. The 98 excluded
surface observations were compared only within the same world and model root.
The first observation and the replacement roots after loading establish new
baselines rather than claiming cross-root preservation.

The two female Nord actors selected Ashen and Umber automatically. Manual Black
and Timber assignments remained independent. The owned save/load retained both
manual assignments, advanced the world/load generation and produced fresh model
roots. Resetting the first actor returned its initial automatic Ashen selection
without changing the second actor's Black override. Refresh retained the choices
but did not replace the observed model roots.

The game exited through the owned normal-menu request with code zero. All 121
environment snapshots were restored, the copied profile and owned saves were
archived, and the reservation was released. The immutable packet contains all
eight raw phase bundles. A later derived summary is supplemental and is not
represented as part of that packet.

This accepts the measured two-female Original-mode lifecycle, including four
actual coat patterns. Male actors, originally-beast actors without human colour,
the complete live palette and AE/VR remain separate coverage. The formal
bootstrap report still contains 15 assertions and two declared race observations;
the 14 material audits are independently reviewed operator evidence. No pixel or
artistic-quality conclusion follows from these checks.

Earlier attempts remain recorded as unsuccessful: an experimental actor entered
the dying state, two conductor checks rejected valid runtime metadata, and two
starts stopped during an abandoned first read-only menu query. Their results
were not overwritten by this successful trial. The corrected startup read path
was used, but its abandoned-read retry branch was not exercised in this run.

## Physics observation retirement

Source commit `b31c13e8e5012c6acecb0c2f6d28b1e4819b4806` corrects the optional
physics Host/Actor lifecycle. It does not change the native runtime used above.
Final unregister requests now carry the captured session. Pending retirement
survives cleanup and retries, while completed empty withdrawal clears superseded
local observation ownership so repeated suspension/release cannot recreate it.

The four-file change passed an independent source review, 35 focused checks and
compilation of both Host and Actor PEX. Seven regressions reject the original
source. The matching PEX pair is prepared together; it has not been installed.

A void unregister request is not provider or root-retirement readback. CBPC
binding/container generations, retained collider indices and cleanup remain
unqualified. No automatic provider or population activation is enabled by this
change. A motion-only test can compare measured node transforms with actor/node
Stop/Start controls; it cannot establish those stronger ownership claims.

Artistic refinement and the VR first-person body remain separate work.
