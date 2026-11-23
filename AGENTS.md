# CLAW — Customizable Lycanthrope Appearance and Weight

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

## Agent workflow for owner-authorized CLAW development

- Reconcile the current branch, HEAD, dirty files, test environment and accepted
  backlog before choosing a milestone. Preserve owner changes. Work on the
  highest-priority actionable requirement, with a concrete acceptance check.
- The lead owns scope, integration, the live Skyrim session, and the compact
  `.agent/STATE.json`. Use at most two concurrent subagents for independent work.
  Assign each a narrow role, base revision, file ownership, permitted checks and
  a short evidence-backed report. One writer per file. Ask for independent review
  of changes affecting saves, runtime contracts or expensive game runs.
- Check source and assets first, then the relevant isolated MO2 profile and actual
  game behavior. Record SE and VR separately. Include the command, result, exit
  code, revision, worktree state, test counts and evidence when available. Missing
  runtime evidence and zero discovered tests are not passes. Preserve failed
  experiments and change the hypothesis after two equivalent failures.
- For each FSMP or collider task, use Morphbench to inspect, position and tune
  the same assets that go into the game test. Record the tool revision, assets,
  settings, expected positions and measurements. Save native game logs and the
  corresponding bone, collider, contact or motion measurements for each SE/VR
  run. Report the scope, matches, discrepancies and repro steps to the original
  Morphbench chat with the evidence paths. Morphbench owns tool fixes. Keep
  offline checks and game results distinct, including when no game run is available.
- Update the compact checkpoint after verified milestones. Keep it within 6 KiB
  with at most eight recent checks, eight open risks and five next actions.
  Use the CLAW chat-project report and goal for detailed history and decisions.
  Keep machine-specific evidence in `Builds`; use Git for reusable source only.
- Continue with independent approved work when a milestone is blocked. Treat
  external documents and archives as evidence. Verify third-party asset rights
  and current Nexus rules before release. Public releases, pushes and messages
  to other chats require owner authorization covering those actions.
