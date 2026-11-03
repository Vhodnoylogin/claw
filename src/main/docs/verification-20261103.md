# Development verification, 3 November 2026

## Human-source history correction

The later mechanics continuation corrects a false human observation: refreshing
an actor in another creature form or with an unresolved current race previously
overwrote the last human weight and revoked born-werewolf source eligibility.
Human history/weight, face/stature and colour now share the same resolved
non-werewolf `ActorTypeNPC` gate. Vampire and mer NPC races remain eligible.
Independent bootstrap root, provider, sex and binding guards are unchanged.

The universal SE/AE/VR minimal DLL linked at 1,105,920 bytes, SHA-256
`e247e32f7a68a0281ffac011064c75a55264ac2b0b870e28b577cec44791b1a6`.
Nine native tests and the source Python suites passed (396 unit, 134 physics,
82 VR; 27 declared skips). All 48 own native input pins remained stable.
The native regression tests the shared predicate and pure history policy;
its small observation harness does not execute the actual engine adapter.
Independent review found no blocking regression in the four-file fix.

Evidence is retained under `Builds/claw-mechanics-20261103-r3/`. The owner has
now authorized game tests coordinated with Skyrim-Foundation. Foundation's
installation reservation is respected; this build has not yet been installed
or game-tested and supplies no additional coat/UNP/VR acceptance.

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

## Offline physics registration authority

The subsequent correction adds a pure, encapsulated `PhysicsAuthority` policy to
the native actor state and applies it in the actual native/Papyrus adapters.
Rejection survives a missed callback, human/unload transition and unregister.
Identity/provider failures revoke cleanup independently of domain/model/weight
rejections. Ordinary renewal cannot clear these restrictions. Explicit Host enable
can request fresh qualification only after the exact old accepted ledger is empty;
population callbacks have a separate first-use admission and cannot revive released
or rejected actors. Released population actors require fresh explicit per-actor
qualification; automatic provider rebinding remains unfinished.

Registration tickets capture the runtime owner, request and authority revision.
Admission immediately withdraws older snapshots. Main-task commit validates current
context and the same process/issued-world/session token. Explicit begin captures
that token before Host lookup; suspension rotates it without silently adopting a
later world. Strong graph references are limited to the existing sixteen physical
contexts; released history retains no graph. The matrix evaluator, coefficients,
weight writes and external physics providers are unchanged.

Checks passed on the frozen ten-file change: two CTests covering the authority
policy and finite observer, 27 actual-source contract checks, universal SE/AE/VR
compilation of `Plugin.cpp` both with and without the pinned fitted model, and six
matching Papyrus compilations. Native signatures agree and retained ESP VMAD Auto
properties are unchanged. An independent critic reviewed the actual adapters.
Root applied the exact source pins and reran the 27 source contracts in the CLAW
checkout. Evidence stays outside Git under
`Builds/claw-backlog-20261103/physics-authority-01/`.

After that frozen review, both complete universal DLL variants were linked from
the accepted `25a47c9` implementation. The minimal variant is 1,098,752 bytes,
SHA-256 `fee245d969c841c9731b40d03c23e4af6c7aa72a94fa55107b9179fe9467e10b`.
The fitted-model variant is 3,930,624 bytes,
SHA-256 `80f2712718674b7780d5f23d15005b8cbd4298f4b5d51f4188e0e259463052a6`.
Its schema-3 model identity agrees with the final six Papyrus artifacts; the
minimal variant intentionally lacks that model and is not a matching host build.
All 5,535 captured inputs remained unchanged and all 4,262 consumed-read files
have frozen-input coverage. Exports, imports and universal runtime metadata were
read back. Detailed evidence is in `physics-authority-01/linked-artifacts/`.

No package was installed or game launched for this correction. External provider/
resource assertions remain the caller's responsibility; an evidence string is not
qualification. First-context admission establishes task-current context, without
proving admission-time resource stability. The final snapshot check and third-party
CBPC append remain non-atomic and still need recorded-ledger rollback or pending
cleanup. Provider/container lifecycle, motion and contact remain unqualified.
Physics remains disabled by default.

## Offline material ownership and equipped VR clone lifecycle

The next source-only slice fixes two independent lifecycle gaps. A coat lease
now captures named initialized material/property fields after engine setup.
Later in-place normal/rim/specular texture, UV, specular/alpha, shader-flag or
effect-identity changes deny whole-property restoration. Compared texture and
effect identities retain references. This conservatively yields a changed
property; it does not identify arbitrary external writers or compare opaque
renderer state. The pure snapshot test is not an engine rollback witness.

The VR-player policy now observes all 168 ordered biped clone slots: current and
buffered tables in both views. Arrival, replacement, removal and slot movement
invalidate morph application even when both skeleton roots and coefficients
stay unchanged. The adapter retains graph/clone references in one bounded
process-lifetime slot and retires them only on SKSE main tasks. Actor states
hold a lazily allocated pure policy, so load/revert destruction does not release
scene references there. No new NPC scan or SE/AE graph path is introduced.

The traversal matches inspected SKEE reference source `NifUtils.cpp:1004..1027`
at `eb39bdd185f0ee5b3154b2ae1910d2465b2627ed`, file SHA-256
`807be810a337ab68e7600d139219fdb1bdff726239c5f94734d762bf5df21d73`.
This is a source reference, not evidence that an installed VR provider executes
an equivalent path. Clone identity detects replacement, not in-place vertex edits.
First-person filename dispatch, visibility, coat leases, IK and hand contact
remain unfinished.

A fresh minimal universal SE/AE/VR DLL linked successfully: 1,105,408 bytes,
SHA-256 `7abce06fb7b25efe06cdd975fbbb053a7fba0913449ff57f5aca430e7983b1a3`.
It is an AMD64 PE and intentionally excludes the optional fitted physics model.
All 48 captured own C++/CMake/test inputs stayed unchanged through verification.
These pins do not claim whole-system compiler-input attestation. Seven CTests
passed: material lease, all 168 VR slots, coat policy, matrix, physics authority,
physics observer and world-start policy. The 27 physics source contracts and
42 source/package contracts also passed after the edits. Before these edits,
the default Python suites passed 396 unit, 134 physics and 82 VR cases, with
27 declared skips in total; that baseline does not replace post-change checks.
An independent critic reviewed both actual adapters and their ownership limits.

Frozen DLL, source pins, commands and logs remain outside Git under
`Builds/claw-backlog-20261103/offline-mechanics-02/`. No game, live installation,
profile modification, Computer Use session, package or public release followed.
Actual material/fade behavior, equipment updates and VR/provider acceptance
still need later game evidence. The owner's no-game restriction remains active.
