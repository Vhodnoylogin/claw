# Shared numeric evaluator tests

These standalone tests require only a C++20 compiler and CMake. They are also
registered when the main CLAW build enables `CLAW_BUILD_TESTS`.

```powershell
cmake -S src/test/cpp/projection -B target/shared-projection
cmake --build target/shared-projection --config Release
ctest --test-dir target/shared-projection -C Release --output-on-failure
```

The tests cover opaque named bindings, all transforms, source-free constants,
sparse/cutoff and precision policies, clamp-before-scale behavior, exact legacy
ordered and compensated reductions, 2,000 deterministic signed-endpoint
fixtures, linear edge-visit counts, and unavailable outputs on failure. Function 7 adds independent signed endpoints
with a smoothstep response, checked by the same compiled property runner in
native and WebAssembly (neutral/endpoints, branch monotonicity, saturation,
endpoint derivatives, one final bound after mixed contributions, precision and
cutoff policy, and extreme compensated cancellation).
`FreestandingSmoke.cpp` instantiates both reduction policies without the C++
standard library; it can be linked for WebAssembly with no imports or entry point.
With a WebAssembly-capable Clang and Node on the path, run from repository root:

```powershell
clang++ --target=wasm32-unknown-unknown -std=c++20 -O2 -ffreestanding -fno-exceptions -fno-rtti -fno-builtin -ffp-contract=off -nostdlib -Isrc/main/cpp/shared src/test/cpp/projection/FreestandingSmoke.cpp '-Wl,--no-entry' '-Wl,--export=projection_smoke' '-Wl,--export=projection_endpoint_smoothstep_properties' -o target/shared-projection/projection-smoke.wasm
node src/test/cpp/projection/FreestandingSmoke.cjs target/shared-projection/projection-smoke.wasm
```

These are numerical source checks, with no game or provider qualification.

Function `morph_matrix::signedEndpointSmoothstep` is numeric mode 7 in the generic
`Edge`. It uses existing `gain` at positive inputs and `negativeGain` at negative
inputs, with canonical exponent 2 and constant 0. At ±0 its term is positive zero.
For any otherwise-valid finite source, its magnitude is clamped to 0..1 before
the existing smoothstep polynomial; each selected endpoint coefficient can be
positive or negative. Precision/source validation precedes this transform and
both endpoint gains follow the existing independent cutoff policy. No layer is
bounded separately: all contributions enter the chosen reduction and the output
receives its one target bound, scale and result precision after reduction.

Modes 0..6 and their helpers keep their existing arithmetic. Modes 6 and 7 need
two independent gains and are generic evaluator operations; the existing 28-byte
single-gain CLAW C ABI and product `MorphFunction` remain limited to modes 0..5.
The WASM JS harness invokes compiled property exports and contains no response
or reduction implementation. These checks do not change any product defaults,
input meaning, configuration schema or provider/application behavior.
