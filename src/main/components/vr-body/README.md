# CLAW VR body component

Develop the optional VR body in this directory of the CLAW repository. Keep its
component-specific C++, authoring tools and resources here; put corresponding
tests and fixtures under `src/test/components/vr-body/`. Build outputs stay in
ignored `target/` or the external workspace build directory.

The 12 November owner plan includes this candidate after offline qualification
of shared mathematics and motion-physics/tool changes. Female breast aesthetics
remain deferred. Existing
prototypes still live in the earlier C++/Python/resource locations; migrate them
with their imports, build/package paths and tests when this phase begins. This
directory does not establish a working or released VR body.

Start from the retained [VR body design](../../docs/vr-body.md),
[head policy](../../docs/vr-head-policy.md) and
[loaded-graph notes](../../docs/vr-loaded-graphs.md). Shared matrix mathematics
and the core game adapter remain shared source. Do not create a separate product
repository or a second copy of that code for this component.
