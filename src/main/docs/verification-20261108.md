# CLAW 0.9.0 verification — 8 November 2026

## Exact artifact and source

The single working FOMOD archive is `CLAW - Customizable Lycanthrope Appearance and Weight.zip`,
366,307,929 bytes, SHA256 `a78be77099738b2284585f4c50d8d06a5f5a4c1088bbe438d6908183711ce859`.
Its 396 members contain runtime/install files and required notices, without source
archives, tests, developer tools, new physics adapters or first-person VR resources.
The matching source is released on `main` and tag `claw/0.9.0`; generated output is not tracked.

The fresh universal CommonLib DLL is SHA256
`84b6da830fd21c61974c37051a8d9ececd07470cc14223c1c13a616fd0ddde64`.
All 21 compiled own C++ inputs still match the native build receipt; subsequent
edits were packaging metadata and documentation. Fourteen native CTests passed.
The source suite passed 591 checks with 30 explicit skips; 23 focused package tests
also passed after final source-version metadata cleanup. Papyrus native declarations
and all 31 API bindings were checked against the packaged PEX.

## Archive and installer

CRC/readback, all 34 coat entries and 355 DDS resources were checked offline.
All 20 selections passed: two male families, five female families, optional OBody
host on/off. Selected installations contain 367 files without the host or 369 with it.
The FOMOD retains separate male/female pages, nonblocking body recommendations,
body links and explicit OBody on/off help. Vortex string-stream regression passed.
The owner accepted manual installer inspection before publication.

Native MO2 test installation used the preceding v2 archive, with all 367 selected
hashes, VFS winners and native Installed accounting verified. The published v3
differs only in installer descriptions; all runtime members and every selected
payload are byte-identical. Fresh disk readback confirmed this before game tests.
This is runtime-equivalence evidence, not a claim that the native v2 receipt
identifies a separate v3 installation.

## Actual game checks

Three fresh runs used Skyrim SE 1.7.104.0 / SKSE 2.3.1, official RaceMenu,
HIMBO male and classic UNP female selections. The dedicated test instance used a
20-mod/21-plugin disposable copy of the 22-mod CLAW source profile. Physics was
disabled only in that copy. Resolution remained 1920×1080 windowed.

| Run | Scenario | Outcome |
| --- | --- | --- |
| `20261108-180552-c79f26` | game-a | Passed; normal menu exit 0; restored and collected |
| `20261108-181700-8e97cc` | game-b | Passed; normal menu exit 0; restored and collected |
| `20261108-182807-42342c` | lifecycle-final | Passed; normal menu exit 0; restored and collected |

The two disjoint palette batches covered every one of the 34 IDs on both sexes:
816 actual managed-surface checks, plus 48 baseline checks. Seventy-two fresh
native chunk arrays were independently decoded. Actual texture paths AND bound
resources, private material ownership, neutral tint and finite alpha were verified
for the head, body and all managed fur surfaces. A female was created directly as
a beast; a male was transformed from human form. No human source was fabricated
for the born-beast fixture. This proves technical availability through assignment,
not artistic quality or exhaustive random automatic selection of all patterns.

The final lifecycle scenario checked automatic baseline, independent manual
assignments, two changes on one actor, model refresh, one owned ESS/SKSE save/load
with current two-reference/VM remapping, and clearing one override while preserving
the other. Fourteen fresh surface audits checked the resulting resource bindings.
All three operators and native games exited 0 through the normal menu route.
Each run restored all 122 snapshots; collected evidence, source-profile preimages,
RootBuilder/game files and temporary-profile removal were independently verified.
No launch defect occurred in these three runs. Known recent starts are 29;
the historical global start count remains unknown.

## Limits and retained evidence

The DLL targets the declared SE/AE/VR boundaries; these runs establish only the
specific SE setup above. They do not qualify AE, VR, every body family afresh,
physics, contact collisions, first-person VR anatomy or artistic refinement.
Earlier matrix/Vanilla/BHUNP and human-return checks remain in the
[0.8 record](verification-20261102.md); these new runs do not rewrite its historical
abnormal teardown result. Existing actors retain their saved/custom matrices.
Classic UNP supplies weight and available generic traits, not invented BodySlide sliders.

Raw packets and native artifacts remain outside Git. Their immutable final packet SHA256 values:

- `20261108-180552-c79f26`: `1ffe659cfc92b95f1fbcc6b9e8a89adf4fffdbaa1a3c0b51caabab3bc9daa641`
- `20261108-181700-8e97cc`: `48e173fa8621de3341bcc6915933da81cc0464a98836d4254d65f5f0bf6b56f2`
- `20261108-182807-42342c`: `b92ce3620478c945d7fb6ca3cab4dd1e45fe97102eace3b79ef4e697f898b8c6`

Combined palette review SHA256: `fd5dd6346774112f23213f9a1c7a795ec3721a385351c5aaef601b51aaa032d6`.
Lifecycle review SHA256: `edb6fc93ce96312639b321b03cf926e1e01400efb6983a7834c961bbb85c2f20`.
