# CLAW Distribution — linked SE candidate

Applied human morphs determine werewolf proportions through a versioned
many-to-many mapping. OBody continues to own human preset assignment; CLAW reads
the effective RaceMenu/SKEE values and writes its own werewolf morph contribution.
There is no separate wolf preset pool or body-selection menu in this package.

This exact native artifact targets Skyrim SE 1.7.104.0 with SKSE 2.3.1,
matching Address Library v13 and official compatible RaceMenu/SKEE. Its checks
do not establish other SE/AE or VR DLL compatibility. Keep the matching native
corresponding-source download with this binary distribution.

Install the CLAW base and its dependencies. In the installer declare the actual
human resources: HIMBO 5.8 plus CBBE 2.0.3 or 3BA 2.48. These choices select morph
geometry mappings; they are not physics switches. Human body mods, generated
morph-capable human assets, OBody and ordinary human presets remain separate mods.
Install all author-declared dependencies for their selected versions.

Enable the optional wild-werewolf source integration only with active OBody.esp.
Its quest asks stock OBody to provide human source values for eligible actors
first encountered as wolves. Existing assignments and OBody restrictions are
respected. Without that option, the wild-source host plugin/scripts are absent.

These runtime files passed two actual SE regressions: 117 checks covering six
ordinary human presets, both-sex roundtrips and save/load, plus 33 checks covering
two actors created directly as wolves. Human and foreign morph keys were preserved;
both game sessions exited normally. This verifies mechanisms and numeric shapes;
final textured visual acceptance is pending.

Trial 6 strengthens bellies and HIMBO pecs. Slim limb reductions currently stop
at neutral. Head, ears and tail are outside the human-body conversion. The optional
source host asks OBody to process eligible wild actors; this is not a claim that
OBody alone supports creatures or overrides every external mod's restrictions.

No third-party DLL replacements, textures, skeletons, human or wolf presets,
test actors, physics configuration or VR body are supplied. The unchanged native
binary contains dormant development paths; their presence is not physics support.

Source and author: [Vhodnoylogin](https://github.com/Vhodnoylogin/claw).
