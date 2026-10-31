# CLAW — The Beast Within

Repository: https://github.com/Vhodnoylogin/claw
Default branch: main

Read README.md or README.ru.md and CLAUDE.md if present before editing.
Production source, authored resources and documentation live under `src/main/`;
all tests and reusable inspection fixtures live under `src/test/`. Generated
output belongs in ignored `target/` or a configured external build directory.
Keep the root clean. Do not commit generated DLL/PEX/ESP/ZIP or release payloads,
including through LFS; authored binary inputs need origin/hash/licence records.
Machine paths belong in ignored `build.local.json`; see `src/main/docs/rebuild.md`.

CLAW owns the shared C++ matrix kernel in `src/main/cpp/shared/`. The independent
Morphbench plugin lives in https://github.com/Vhodnoylogin/claw-morphbench-plugin
and consumes an explicit pinned dependency. Other products have separate
repositories; do not maintain silent implementation copies here.

Released source and reusable test source reach `main`; unfinished work uses one
active development branch based on latest released main. Verify fresh remote
refs, unique commits and worktree ownership before removing merged task branches.
Preserve historical tags/assets, owner work and required upstream/service branches.
Read `src/main/docs/release-workflow.md` before packaging or publication.
End-user archives contain ready runtime/install files, required notices and brief
user instructions only. Keep developer sources, build instructions/toolchains
and test fixtures outside the working mod archive; publish matching source and
rebuild instructions on GitHub. Runtime-interpreted code remains runtime content.
Before committing or pushing, verify `git remote -v` and name this repository.
Do not commit credentials, external model weights, live sessions or local caches.
