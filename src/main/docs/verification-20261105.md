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

Actual shader/material lifecycle acceptance is still pending. The subsequent
coat attempts did not reach the coat assertions: an experimental actor entered
the dying state, two fixture-conductor checks rejected valid runtime metadata,
and two starts stopped during the first read-only menu query. The latter requests
were abandoned before task start; New Game had not been selected. These failures
are not evidence that CLAW's coat mechanism passed or failed.

The conductor now distinguishes the pinned original MO2 INI from the exact
recorded active image and coalesces repeated paths only when their hashes agree.
Independent checks include the actual registered plan and conflicting-hash
counterexamples. These are tooling checks, not coat acceptance.

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
