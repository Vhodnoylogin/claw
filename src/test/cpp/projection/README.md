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
fixtures, linear edge-visit counts, and unavailable outputs on failure.
`FreestandingSmoke.cpp` instantiates both reduction policies without the C++
standard library; it can be linked for WebAssembly with no imports or entry point.
With a WebAssembly-capable Clang and Node on the path, run from repository root:

```powershell
clang++ --target=wasm32-unknown-unknown -std=c++20 -O2 -ffreestanding -fno-exceptions -fno-rtti -fno-builtin -ffp-contract=off -nostdlib -Isrc/main/cpp/shared src/test/cpp/projection/FreestandingSmoke.cpp '-Wl,--no-entry' '-Wl,--export=projection_smoke' -o target/shared-projection/projection-smoke.wasm
node src/test/cpp/projection/FreestandingSmoke.cjs target/shared-projection/projection-smoke.wasm
```

These are numerical source checks, with no game or provider qualification.
