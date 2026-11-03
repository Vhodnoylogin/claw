# Development verification, 3 November 2026

These are development-source, archive and offline checks. Released `main` and
the public 0.8.0 archive remain unchanged. No game was started for these changes.

## Loaded graphs and actual family observation

Source `77e77700b73c54a614d8baf08d7c4366e754b8ba` adds the
[VR loaded-graph lifecycle](vr-loaded-graphs.md) and the cached
`CLAWDistributionNative.GetMorphFamily(Actor)` getter. The getter distinguishes
the actor's bound matrix from an installer/request/evaluator input; it does not
prove geometry or successful application by itself. A source review checked
the existing actor-binding boundary and unchanged SE/AE/NPC path.

The new universal DLL is 3,902,976 bytes, SHA-256
`ff19ed20ccbe0c239ddbf6983b4917e7a1e439ea2946dcd49f63a17ac9c46a36`.
All consumed native source bytes matched that committed source after compilation.
PE inspection found x64, the three expected SKSE exports and no unconditional
SKEE/OpenVR imports. Multi-target CommonLib SE/AE/VR compilation passed; this
does not establish game acceptance at any engine boundary.

Both selected CTests passed: the loaded-graph lifecycle cases and the retained
current-vector physics fixture test. The latter checked 198 fixtures and 25,344
capsule-slot outputs with maximum coordinate/radius error `1.28786e-13`.
The fitted model remains the previously validated current-v4 model. No provider
motion, contacts, automatic activation or performance budget was qualified.

Caprica compiled the updated actual Papyrus API. Its PEX SHA-256 is
`1f1009b440726bcc04d7386d8058d29cb0a3177fb3d583a1f3aaec4fb1b34d1a`.
The new function is present in the compiled class; actual VM invocation remains
pending. No PEX/DLL is tracked in this source repository.

## Working archive and test-source repair

Development package-03 is 367,374,356 bytes, 396 members, SHA-256
`23aedb39c955ff79a736841f36cfb40cffeca5f4c71e0532f2b0bf76a9ff4e6b`.
It changes only the DLL, Papyrus API PEX and README source link from package-02.
The installer, all matrices, body resources, 355 DDS files and notices are
byte-identical. Full archive CRC and exact member comparison passed. It contains
the compiled physics model but no physics host or automatic provider activation.
This is a staged development archive, not a published or game-tested release.
An independent primary-archive review resolved all 20 installer selections and
confirmed the same three-member change boundary. Its review SHA-256 is
`b8eb29c398d81dca272a10745c3662a66fff44aadf3e71ac269c4d25f6f86b8a`.

Commit `bb75d8f` restores the original authored QASmoke lighting YAML excluded
during the source-layout migration: `*.esm` had also ignored its source directory.
The narrow ignore exception permits normal staging without changing the saved
manifest. The restored file matches its original exact and LF-normalized hashes.
After rebuilding the six-NPC test ESP from its existing Spriggit source, the
portable inspection validator passed all 12 snapshots, six presets, 12 paired
actors, six wild actors and four view contracts. This is source validation,
not a new game scene or manual inspection.

## Remaining runtime gates

The classic-UNP two-actor lifecycle remains unrun. Current generic testing
support cannot substitute its historical six-actor/OBody calculations for that
scenario. A focused SE adapter update was delegated to the testing-tool chat;
the exact original UNP fixture is retained. Offline selection preparation
verified 367 CLAW files and 59 original UNP files without changing MO2.

The remaining coat witnesses, current CBPC provider/container lifecycle and VR
model dispatch still need actual game evidence. Physics activation remains
disabled until provider/resource/cleanup ownership is established. The
[physics plan](physics-next-stage.md) records the inspected reference-source
rebinding limits without asserting equivalence to the installed CBPC binary.

Raw build, compile, archive and source-review evidence stays outside Git under
`Builds/claw-backlog-20261103/`; the offline UNP preparation is under
`Builds/claw-unp-20261103/`. No live installation, game root, profile or user
session was changed in this slice.
