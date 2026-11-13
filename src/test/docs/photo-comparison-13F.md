# Nonshipping photo comparison checks

The four helpers in `../python/photo_comparison/` retain the actual 13F pose,
capture-readback, offline registration and screenshot-custody checks. They are
test source only. No executor, runtime wrapper, machine freeze, provider, original
PNG or shipping payload is imported.

Run explicitly from repository root with Python3.11+, Pillow, NumPy and OpenCV:

```powershell
python -B -m unittest discover -s src/test/python/photo_comparison -p 'test_*.py' -v
```

`CLAW_PHOTO_HELPER_ROOT` and `CLAW_PHOTO_FIXTURE_ROOT` may select explicit source
and fixture directories. Defaults are this source folder and
`src/test/resources/photo_comparison`. Missing dependencies/fixtures fail; they
are not replaced by another machine's runtime. Synthetic files live only in
ignored `target/photo-comparison-tests` and are removed after each test.

## Scope and portability

`capture_guards` and `photo_pose` retain their source bytes.
One helper adaptation is `screenshot_custody.reserve_ini(..., set_ini=...)`:
the caller supplies the INI authoring function instead of importing an executor.
The helper still checks that only the reserved index's parsed semantics changed.
This callback does not establish ownership or authorize a live write.

The portable registration helper additionally requires all five existing manual
pixel-admission booleans explicitly true. The retained packet's expression could
accept a hashes-only review through an empty `all(...)`; the new missing-flags
regression exposed that case. This is a narrow fail-closed reuse correction, not
a change to image math or thresholds. Actual13F had all five true, remains
unchanged, and is not rescored by this import.

The same-opened-file screenshot removal remains the original Windows handle
contract. Its four native-file tests run only on Windows, against temporary
synthetic files and eight synthetic protected originals. Other platforms report
those explicit skips; no POSIX imitation claims equivalent deletion custody.
All other tests are offline numeric/file checks. No game path or process is used.

Pose admission retains exact actor/root/scale identity, six finite bone transforms,
two advancing samples, producer and wall-clock spans, and the original strict
translation/rotation tolerances. The retained actual 13E pre-park/final sample
remains a negative case. A synthetic stationary second sample tests the boundary;
it is not another observation from that game. Fixture sourcePins were omitted,
and the protocol contains only required numeric/position fields. Raw pose values
and thresholds are unchanged; stored reference IDs never authorize game actions.

Registration estimates displacement over admitted static wall/ground regions. It
does not warp, shift, resample or write image pixels. Fitted corner displacement
does not replace individual feature/photometric limits, root pixel review, pose
continuity or actual source-file hashes. The file API withholds comparison without
root pixel admission even when identical synthetic frames register numerically.

## Retained actual evidence

The actual 13F run `20261113-062001-a97fa3` produced four untouched FHD originals.
Its source/pixel comparison and ended/restored custody passed; root independently
verified all 2,084 game pins after contained archive. Maximum background-feature
displacement was **0.118855 pixels**; maximum fitted FHD-corner displacement was
**0.083902 pixels**. Those are historical measured results, not new assertions from
these synthetic tests or permission to alter an image.

`qualification-scope.json` records exact helper and retained receipt hashes plus
the unrounded measurements. It imports no images, snapshots or machine pin map.
This suite does not prove identical silhouettes between different NPCs, arbitrary
camera/projection support, later unseen time-scale generations, live ownership,
physics, or new capture/game qualification. Old failed attempts remain unchanged.
