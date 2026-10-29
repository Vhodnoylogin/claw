# Origin-owned Polygon restoration planning

`scripts/polygon_restoration.py` prepares an **offline fallback cleanup plan** for
CLAW's never-executed Polygon preparation. It is development tooling and is not
included in a mod release. It does not create a new mod order or change the
existing queued subject, its source, recorded test results, budgets or holds.

Physical rollback is not inherently needed to retain a verified installation.
A future supported preparation-generation adoption may preserve that installation.
The rollback protocol is a separately reviewed fallback, never an automatic
response to a tool update or an expired launch window.

## Current capability and required admission

Only `plan` is implemented. There is **no execute, archive-copy, delete, database,
HTTP, native process or UI command** in this client. Its JSON output grants no
cleanup or game start. It cannot replace the dashboard's reservation and completion.

The reviewed dashboard protocol is described in its
`docs/diagnostic-preexecution-recovery.md`. The `show`/`inspect` status alone does
not verify a current restoration lease, original file acknowledgement, retained
Q1 hold or source snapshot. Before any future live helper is implemented, require
a supported current guard under the native mutex, or an explicitly reviewed full
durable-record/current-guard binding. A duplicate reserve grants no new cleanup.
The origin also needs the technical owner's explicit cleanup handoff. An expired
test authorization is only historical installation provenance, never permission
to start Skyrim. The current planner deliberately cannot cross this boundary.

## Inputs and output outside Git

Pass a machine-local configuration; never add it, tokens, native evidence or
archives to this repository. Each pin is `{ "path": "absolute path", "sha256":
"lowercase SHA256" }`. The exact configuration keys are:

```json
{
  "schemaVersion": 1,
  "kind": "claw-origin-recovery-plan-input",
  "workspaceRoot": "<absolute workspace outside the source checkout>",
  "recoveryId": "<operator's proposed recovery id>",
  "assessment": { "path": "<reviewed assessment JSON>", "sha256": "<sha256>" },
  "preparedRequest": { "path": "<original immutable preparation>", "sha256": "<sha256>" },
  "submittedOrder": { "path": "<unchanged actual queued-order export>", "sha256": "<sha256>" },
  "reserveReview": null
}
```

`reserveReview` can be a pin to the operator's proposed review. Its presence is
not a reservation. The preparation's pinned `baselineAudit` determines the exact
ten-path VFS observation order. The planner verifies all thirteen owned current
file hashes, eleven independent fresh backups, the exact single source-modlist
addition, other-profile references, directory/reparse boundaries and the seven
original game-provider candidates. It rejects extra files and modified backups.
It requires the current ten non-modlist/manager bytes to remain exact; a changed
manager INI needs a separately reviewed producer boundary, not relaxed client logic.

```text
python scripts/polygon_restoration.py plan --config <external-config.json> --output <external-plan.json>
```

The output must be under the external workspace's
`local/skyrim-polygon/diagnostic-recoveries/<recoveryId>/` directory. It is created
once; existing output is never overwritten. All backup/native paths are read
only. The embedded receipt has a deliberately invalid `DRAFT-` kind and missing
manager/readback/archive facts, so it cannot be submitted as a completed native
restoration. Planned archive paths do not claim copied files exist.

## Future operator-assisted action plan

Every step below waits for supported actual reservation and an independently
reviewed helper plus explicit technical handoff. These instructions are not a
cleanup grant.

1. Under the shared native mutex, verify the exact recovery, original preparation,
   queued subject, slot/file acknowledgement, Q1 hold, producer/executor source
   pins and current control state. Preserve the lease throughout partial work.
2. Verify the actual SE manager PID, full process birth and executable path,
   selected profile and known-idle bridge. Reject game/loader/unknown-owner state.
3. Preserve and hash all thirteen postimages outside installed directories:
   ten new payload files, the native mod's `meta.ini` and the two copied download
   records. Verify all eleven existing fresh preimage copies before any removal.
4. Reobserve MO2 through the supported Windows UI surface. Use fresh observations
   for each input. Archive raw accessibility/screenshot evidence for selecting and
   removing only the reviewed new mod. Recheck every profile's references and
   the exact directory inventory immediately before the global mod is removed.
5. Through native Downloads UI, remove only the two proven copied records. The
   retained original acquisition remains external and untouched. Record actual
   native outcomes; a hidden download is not proof that its files were removed.
6. Verify the source modlist equals its **fresh** native preimage and the other
   nine profile files remain exact. If restoring the modlist bytes is needed,
   first normally close only the verified manager and confirm that identity
   ended, restore only that fresh modlist, and reopen that exact SE instance.
   Do not restore stale earlier-plan plugin/loadorder files.
7. Never copy an INI over a live manager. Capture an immutable post-restoration
   INI under this recovery's evidence folder. The producer's strict ten-key
   GUI-only parser decides allowed persistence differences. If other values
   changed, retain the lease and stop for reviewed repair.
8. Refresh MO2. Capture actual current manager identity, profile, known idle,
   mod/download absence and ten ordered VFS responses. Seven game endpoints
   require original pinned providers/hashes. Only the three root metadata paths
   may be absent or have another current provider; none may point to the removed
   mod. Record the original API bodies without authorization headers or tokens.
9. Build the exact typed native restoration receipt from those actual observations,
   archive manifest and pinned UI/helper evidence; independently review it and
   complete through the supported dashboard API. Filesystem checks alone do not
   establish native UI provenance. Completion ends only the old technical
   preparation and its lease. The same queued subject/history and Q1 hold remain;
   no game, result notification, new order or automatic preparation follows.

All Windows UI input belongs to the approved computer-use surface. Do not add
an alternative UI automation transport or shell deletion shortcut to this planner.

## Verification

```text
python -m unittest discover -s tests -p "test_polygon_restoration.py" -v
```

The fixtures are temporary synthetic filesystem contracts, not evidence of an
actual native restoration. Machine-specific case-fit observations and prospective
plans remain outside Git and never establish mod runtime acceptance.
