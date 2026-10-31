# CLAW — The Beast Within

Human body morphs shape male and female werewolves through editable coefficient
and function matrices for HIMBO, CBBE and CBBE+3BA. Optional OBody integration
supplies human preset inputs to actors first encountered as werewolves.

[Download CLAW 0.7.0.0](https://github.com/Vhodnoylogin/claw/releases/tag/claw/0.7.0.0)
· [Nexus](https://www.nexusmods.com/skyrimspecialedition/mods/194798)
· [Русский](README.ru.md)

## Source layout

```text
src/
  main/
    cpp/               # Game DLL, shared evaluator and native build
    papyrus/           # Game scripts and optional OBody source host
    python/            # Body authoring, physics/VR tools and packaging
    resources/         # Original donors, authored recipes, YAML, matrices, media
    docs/              # Contracts, build instructions and roadmap
  test/
    cpp/               # Native regression tests
    python/            # Python regression tests
    papyrus/           # Test script source
    resources/         # Test actors, paired scene, presets and inspection data
target/                # Ignored generated files, dependencies, reports and archives
```

Only source and authored input resources are tracked. Original binary donor
meshes are source inputs with recorded provenance; generated NIF/TRI, ESP, PEX,
DLL and ZIP files belong in `target/` and GitHub Release assets. Older release
commits and tags retain their historical layout; history has not been rewritten.

The independent [CLAW Morphbench plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
has its own repository. It consumes a pinned revision of this repository's shared
evaluator instead of maintaining another conversion implementation.

## Build and checks

```text
python build.py test
python build.py test-integration
python build.py bodies --help
python build.py native -?
python build.py plugins --help
python build.py package --help
```

The root CMake project also supports ordinary `cmake -S . -B target/native`
configuration. Native builds use an external pinned CommonLibSSE-NG SDK and the
official SKEE/OBody headers. Local tool paths go in ignored `build.local.json`.
Read the [build instructions](src/main/docs/rebuild.md) for exact prerequisites,
body authoring stages, packaging and the distinction between source checks and
game acceptance. Building never implicitly installs a mod or starts Skyrim.

`test` runs source-level tests. `test-integration` additionally requires built
body/test-plugin resources and explicitly prepared historical package references;
see [test prerequisites](src/test/README.md). Missing integration inputs are not
reported as successful coverage.

## Installation and scope

The working mod is one FOMOD archive. HIMBO and CBBE are required; 3BA is optional.
Install Elegant Werewolf Replacer for its textures, a compatible XP32 skeleton,
runtime-matched SKSE, RaceMenu/SKEE, Address Library and Microsoft Visual C++ x64
runtime. OBody and its own requirements apply when automatic preset distribution
or the optional originally-beast source host is used. Dependencies remain separate
mods; no human bodies, textures or skeleton are bundled.

One CommonLib DLL targets SE, AE and VR. Actual 0.7 game acceptance covers Skyrim
SE 1.7.104 / SKSE 2.3.1 with HIMBO/3BA and official RaceMenu: both sexes,
transformation/return, human-value preservation, save/load and born werewolves.
Other runtime boundaries and CBBE have offline coverage. A fresh build or source
layout change does not establish new game acceptance.

Physics, fitted colliders, distinct neutral weight endpoints and a first-person
VR body remain development work. See the [roadmap](src/main/docs/roadmap.md),
[release record](src/main/resources/publication/CLAW-0.7.0.0.md),
[matrix contract](src/main/docs/matrix-contract.md) and
[reusable inspection configuration](src/test/resources/inspection/README.md).

## Repository and releases

Released source belongs on `main`. One development branch starts from the latest
released main; unfinished work stays there. All tests share `src/test/` and are
excluded from the working installer. Follow the
[release workflow](src/main/docs/release-workflow.md).

The original bodies derive from Elegant Werewolf Replacer. Credit
[Wolflady500](https://www.nexusmods.com/profile/Wolflady500) and
[KaienHash](https://www.nexusmods.com/profile/KaienHash); see the
[donor record](src/main/resources/donors/README.md) for permissions and limits.
Developed with assistance from [Codex](https://github.com/codex).
