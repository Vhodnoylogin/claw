# Development verification, 3 November 2026

These are development-source, archive and offline checks. Released `main` and
the public 0.8.0 archive remain unchanged. No game was started for these changes.

## Current minimal core candidate

Package-04 is the default working-mod candidate, 366,285,481 bytes, SHA-256
`95f34d7c73b43cafd8acb452215197468f86b512650af7db8ace7a8150ab7c8b`.
Its default universal DLL is 1,070,592 bytes, SHA-256
`2e29feb07aeebfb054cee6d5fa051a0d9e6de49222ce7c4ccf5f9af4949a33c9`.
It includes the family getter and loaded-graph lifecycle, with no optional
fitted physics-model data. Fresh matrix and VR-policy CTests passed. The
separate fitted-physics DLL/package-03 below remains an integration candidate;
it is not the default core download.

The same API PEX is retained. Primary archive review independently confirmed
exactly three changed members against package-02: DLL, PEX and README source URL.
Other 393 members, all 355 DDS files, matrices and installer maps are unchanged.
No physics host, source bundle, nested archive or PDB is included. Independent
review SHA-256:
`8291690107304b261fca70fd83b778ac1435158976625e2385cadabbd10e0bbc`.
The consumed native source matches commit
`53dae0b311f7d6524dc728f9815a63f0745bdc00`; native inputs are unchanged from
`77e7770`. This core candidate is not installed, published or game-accepted.

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

The initial draft also imposed global AI/collision-off before either actor
existed. That was our unnecessary constraint, not the owner's actor-freeze
requirement. The fixture now requires immediate per-owned-actor preparation
and actual AI/reference/controller readback before measurement, with rechecks
after transitions. The earlier blocked draft is retained as superseded evidence;
this correction grants no unqualified operation or game acceptance. The existing
native per-actor visual-freeze protocol still needs adapter integration and
actual engine/controller completion checks.

The remaining coat witnesses, current CBPC provider/container lifecycle and VR
model dispatch still need actual game evidence. Physics activation remains
disabled until provider/resource/cleanup ownership is established. The
[physics plan](physics-next-stage.md) records the inspected reference-source
rebinding limits without asserting equivalence to the installed CBPC binary.

Raw build, compile, archive and source-review evidence stays outside Git under
`Builds/claw-backlog-20261103/`; the offline UNP preparation is under
`Builds/claw-unp-20261103/`. No live installation, game root, profile or user
session was changed in this slice.

## Subsequent installation and load-completion correction

The default minimal core package-04 was subsequently installed through native
MO2 Bridge 2.3.6 in the CLAW source profile. An independent review rehashed all
367 selected payloads against the primary ZIP and confirmed the original UNP
body, hands and feet as VFS winners, with HIMBO/UNP matrix defaults and OBody
disabled. The original released CLAW mod was preserved. The owned manager was
closed normally; this establishes installation, not game acceptance.

Two pre-start composition findings are with the testing-tool owner: the
canonical qualification guard rejects the required `processRestart:false`
same-process save/load field, and the frozen executor rejects SE when disabled
Root mods or RootBuilder data are merely present. Foreign RootBuilder files
were preserved; no game was started to bypass these checks.

A separate source review found that failed `kPostLoadGame` messages previously
enabled scanning and emitted the loaded event. The next-candidate correction
admits only successful load completion, keeps failed or malformed completion
disabled, and preserves new-game activation. Local primary SKSE sources for
SE 2.3.1, AE 2.2.6 and VR 2.0.12 encode the boolean in the pointer value as 0/1
with data length 1; the payload is not dereferenced. The pure message-contract
test and universal translation-unit compilation passed. A fresh minimal universal
DLL was then linked from `d59fc4add97d90ec49816d4aaf76816072f3f964`: 1,071,104
bytes, SHA-256
`abd517d7392f6a2b7364d6c2c7c1b13cf112a6e79525b17c3e5705b3a27c5034`.
Matrix, loaded-VR-graph and world-start CTests passed. The build retained the same
runtime compatibility declaration, excluded the fitted physics model and had no
unresolved consumed-input pins. This remains a source/offline correction without
a reproduced failed-load game case. The installed immutable package-04 is unchanged.

## Subsequent tool-only game attempt

One physical SE start loaded the prepared core04/UNP composition and reached
the QASmoke anchor. The first actor-creation action then failed on the testing
tool's native-binding deadline limit. Only startup and world readiness passed;
there is no completed actor-creation witness or matrix snapshot. This does not
establish classic-UNP, freeze, transformation or 31-target parity acceptance.

The executor archived and removed its temporary profile, finished collection and
restored all 128 captured files without a reported restoration error. The owner
reported closing the game; the raw observer retained exit code 0 without an
owned quit request or forced stop. Keep that owner report separate from the raw
termination classification. Neither record establishes a CLAW crash or successful
scripted menu exit. The two tooling gaps were returned to the testing-tool owner;
the owner subsequently prohibited further game starts, so work continues offline.

## Offline physics input boundary

A separate three-file correction validates the effective provider vector before
the physics adapter triggers `ApplyBodyMorphs`. Empty, NaN and infinite values
invalidate its snapshot and request existing scoped domain cleanup. Finite signed
values and values above one are not clamped. The focused physics-observer test
and universal translation-unit compilation with the fitted model passed. No new
physics DLL was linked, installed or run for this change; actual provider removal
and motion remain unqualified. The separate cached-qualification renewal findings
are recorded in the [physics plan](physics-next-stage.md), without a claim that
this narrow guard fixes the whole lifecycle protocol.
