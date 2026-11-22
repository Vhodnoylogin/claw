# FSMP contact witness for the CLAW test pair

This is an internal diagnostic for published FSMP 4.1.1. The adapter records
accepted contact points after the provider inserts them in
`SkinnedMeshAlgorithm::MergeBuffer::apply`. It preserves the source mesh pair
that is lost once only the two rigid bodies are visible. The record contains
the signed depth and normal of the accepted point. These are pre-solve
contact data, with no claim of impulse, game collision, or rendered motion.

The diagnostic is off by default and absent from the CLAW runtime and test
archive. The optional derivative adds no physics parameters, substitutions
or forces. Neither the matching files nor the staged derivative establishes
behavior in a running game.

## Build and check outside the game

```powershell
cmake -S src/test/cpp/fsmp_pair_contact -B <external-tests>
cmake --build <external-tests> --config Release
ctest --test-dir <external-tests> -C Release --output-on-failure
python -B src/test/cpp/fsmp_pair_contact/stage_provider.py --provider <retained-published-source> --out <fresh-external-stage>
```

The staging tool verifies untouched inputs against five exact hashes,
applies bounded substitutions in the new copy and records the resulting
file identities. It never changes a source or provider already in use.
Use the retained release build recipe and dependencies with the staged
`source` directory and a fresh CMake binary directory. Pass
`-DCLAW_FSMP_PAIR_CONTACT_TEST=ON -DCOPY_OUTPUT=OFF -DFETCHCONTENT_FULLY_DISCONNECTED=ON`.
Compile the accompanying PSC with the local Bethesda compiler and flags.
The import list is this source directory, the SKSE source directory and the
Bethesda source directory, in that order. Keep generated PEX and DLL external.

## Measure a selected pair

Use two independently placed test actors, the actual armor-addons, a unique
positive trial nonce and the verified load epoch. All probes must use their
respective retained contact configurations. Compare only confirmed frames
from the same live scene and capture protocol.

- `Arm(surfaceActor, surfaceAddon, probeActor, probeAddon, nonce, callerEpoch, frames)`
  requires distinct dynamically placed references, separately active provider
  roots, supported effective XML paths, exact tags and the expected bones.
  It observes 1–120 subsequent simulation frames. Bind failure returns false.
- `Describe(nonce)` reports state, actor and armor-addon form IDs, tag
  mode, QPC bounds, observed frame count and contact count. A completed
  trial is revalidated against the original owned pair during this call.
- `Read(nonce, offset)` paginates the completed trial in groups of up to
  twelve points. Each point contains a stable driver name, QPC and frame
  index, negative depth, normal toward the surface, and two rigid-body
  local points in provider units. No addresses are returned.
- `Cancel(nonce)` refuses an unfinished trial before cleaning up.
  A higher nonce starts a different trial after completion or refusal.

Confirm both registrations and continuous same-pair ownership. Capture a
separated baseline, equal-motion tag-mismatch overlap, reciprocal overlap and
separation after withdrawing the probe. Treat zero as evidence only from a
completed window with verified pose and identity. Missing bodies, invalid
records and overflow refuse the trial. Save the stock read-only pose
capture separately to compare response under the corresponding stimulus.
