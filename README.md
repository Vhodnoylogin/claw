# CLAW — Customizable Lycanthrope Appearance and Weight

Human body morphs shape male and female werewolves through editable coefficient
and function matrices. CLAW 0.9 supports HIMBO, CBBE, CBBE+3BA, BHUNP, classic UNP Renewal and
separate male/female Vanilla matrices. Available human face and stature inputs
also influence the head, ears, tail and claws. A complete Elegant coat library
provides persistent individual patterns selected from human hair colour and a
stable character seed. Optional OBody integration supplies human preset inputs to
eligible actors first encountered as werewolves.

Every matrix explicitly reads `$actor.weight`, independently of the already
effective RaceMenu morph values. The installer selects one male and one female
family. Native and the matching development Morphbench plugin use the same
compiled evaluator. Installed-game evidence is recorded separately from source
features in the [verification record](src/main/docs/verification-20261108.md).

[Download CLAW 0.9.0](https://github.com/Vhodnoylogin/claw/releases/tag/claw/0.9.0)
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

The optional [CLAW Morphbench comparison plugin](https://github.com/Vhodnoylogin/claw-morphbench-plugin)
is maintained in its independent source repository and is not a gameplay
requirement. The earlier 0.3 release targets CLAW 0.7 matrices; an updated tool
release for the expanded 0.8 matrices is not yet available. The game mod and
matching development plugin compile the same evaluator.

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

The working mod is one FOMOD archive. The installer has separate male and
female pages: HIMBO or Vanilla for males; CBBE, CBBE+3BA, BHUNP 3.34 Advanced Ver4,
classic UNP Renewal 4.6 or Vanilla for females. Choices stay available; active plugin markers only suggest
a default. When multiple body mods are installed, choose the actual winning body
resources and build morphs for that body. The BHUNP choice requires BHUNP 3.34
Advanced Ver4, Build Morphs output and a compatible UNP skin, with that body's own
dependencies installed separately. Replacement bodies are required only for their
selected matrices; Vanilla and classic UNP body deformation use weight; no nonexistent UNP BodySlide sliders are invented.
Keep Elegant Werewolf Replacer as the credited base dependency. Install a compatible XP32 skeleton,
runtime-matched SKSE, RaceMenu/SKEE, Address Library and Microsoft Visual C++ x64
runtime. OBody and its own requirements apply when automatic preset distribution
or the optional originally-beast source host is used. Dependencies remain separate
mods; no human bodies, human textures or skeleton are bundled. The complete
Elegant 2K 2.1 werewolf texture library is included for per-actor coats
under its original asset conditions; the Elegant Nexus requirement is retained. Existing saved actors
keep their stored conversion matrices after an update; a new game adopts the new
defaults. Reinstalling a family choice alone does not reset existing actors.

One CommonLib DLL targets SE, AE and VR. The 0.8 technical game checks on Skyrim
SE 1.7.104 / SKSE 2.3.1 cover both Vanilla sexes through transformation, model
refresh, save/load and human return. The separate BHUNP/HIMBO run also passed
all mechanical phases and its real 47-key BHUNP source proof, then ended
abnormally during teardown; its overall result remains failed. The verification
record preserves this limit and earlier HIMBO/3BA and born-werewolf evidence.
CBBE and other runtime boundaries have offline coverage; SE checks do not
establish AE or VR game acceptance.

The 0.9 runtime adds classic UNP, all 34 Elegant coat patterns, saved automatic
and explicit coat assignments, live-opacity-safe material ownership and corrected
human reference-scale capture. Automatic selection uses 32 natural coats; two
stylised variants require an explicit integration assignment. Unknown human hair
colour uses a stable natural-pool selection. The default preserves authored
texture colours. This is texture selection, not arbitrary recolouring.

The [5 November record](src/main/docs/verification-20261105.md) establishes a
complete original-UNP lifecycle. The [6 November record](src/main/docs/verification-20261106.md)
records mixed-origin coat persistence, material restoration and stature checks.
The [0.9 release verification](src/main/docs/verification-20261108.md) identifies
the final archive and its exact validation scope. Different runtime builds,
complete-palette rendering and artistic quality are distinct checks.

Physics is planned for 0.10.0. VR body and morph-responsive flat/VR colliders
follow it; the adult anatomy supplement follows those. Comparison-plugin UI and
artistic mesh refinement remain deferred. See the [roadmap](src/main/docs/roadmap.md),
[release record](src/main/resources/publication/CLAW-0.9.0.md),
[matrix contract](src/main/docs/matrix-contract.md),
[coat contract](src/main/docs/coat-library.md) and
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
