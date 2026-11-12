# Shared libraries owned by CLAW

CLAW is the source repository for libraries shared by CLAW, Living Physique and
their Morphbench tools. Keep reusable implementations here and let consumers
declare pinned source dependencies. Changes to the common implementation belong
in CLAW; update consumer pins after checking compatibility.

`Projection.h` is the engine-independent numerical evaluator. Its CMake interface
target is `morph-matrix-projection`. It transforms numerical inputs through a
compiled sparse edge plan, reduces contributions and publishes bounded outputs.
Input names, actor state, hunger, morphology and application to Skyrim objects
belong to each consumer's collection, binding and application adapters.

Both game DLLs compile this evaluator directly. Morphbench consumers compile the
same C++ sources into WebAssembly. Each consumer records the required source
hashes and verifies them during its build. The compiled game DLLs contain their
own copy of the common implementation; using the library creates no gameplay
dependency between Living Physique and CLAW.

`MatrixKernel.h` and `MatrixKernel.cpp` provide CLAW's single-gain C ABI adapter.
Its supported function vocabulary is narrower than the generic evaluator's.
Portable regression tests live in `src/test/cpp/projection/`.
