# Current-v4 breast attachment audit

`src/main/python/physics/attachment_audit.py` reads an explicit unsplit 91-node
female P1 carrier, its current v4 TRI, the reviewed XP32 skeleton and the exact
`p1-rig-v4.json` profile. It writes one new external JSON report. It never edits,
installs or packages resources and does not start a game.

```powershell
python src/main/python/physics/attachment_audit.py --body '<female_1.nif>' --body-sha256 '<receipt-sha256>' --tri '<female.tri>' --skeleton '<skeleton.nif>' --profile src/main/python/physics/p1-rig-v4.json --pynifly '<public-PyNifly-addon>' --vectors src/test/resources/geometry/expressive-fixture-vectors-v4.json --out '<new-external-evidence-directory>/audit.json'
python -m unittest discover -s src/test/python/physics -p test_attachment_audit.py -v
```

NumPy and public PyNifly are required; Blender and Morphbench processes are not.
The reader can also come from ignored `build.local.json`. The optional body hash
binds the supplied rigged carrier to its caller's receipt. The profile's body hash
describes the **unrigged** source and cannot qualify a rigged/bounds-derived NIF.
The audit checks exact TRI, skeleton and profile pins; current node ancestry,
transforms, public morph inventory, bilateral stored P1 influence, finite skin
data and packed influence budgets. It records the actual rigged NIF hash but
does not establish its geometry equivalence to that unrigged source.

The report pins consumed inputs, local helpers, PyNifly Python sources/DLL and
interpreter/NumPy computation identities, then checks the pins again before
exclusive report creation. This is a recorded computation environment, not a
complete operating-system dependency inventory. Existing outputs, source/input
directories, links and obvious live game/mod-manager destinations are refused.

The current 53 body/head collar anchors and enabled chest, belly, shoulder and
ChestBlend roots bind once to neutral skin triangles through the existing exact
projection and public surface binding helpers. Disabled/off-region groups stay
explicitly excluded. Original nonzero donor offsets are retained. For each finite
state the report distinguishes:

- Static morph offset change against the original neutral attachment.
- Pose drift against the **current morphed rest offset**, transported with the
  source skin's barycentric blend of normalized influence linear maps.
- Total residual against the transported **original neutral offset**.
- Actual root-to-triangle-barypoint distance and winding-relative signed stand-off.

Raw packed and normalized LBS are separate calculations. Offset transport uses
per-source-vertex normalized weights in both calculations so a rigid rotation of
a nonzero donor offset does not become a false separation defect. This transport
is a geometric diagnostic, not an assertion about the game shader. The signed
quantity uses the triangle's current winding; it is not a watertight inside/outside
classification. Degenerate triangle samples have no signed classification.
With unequal packed row sums, even common translation can produce a residual
in the raw calculation. Keep that result as a property of the declared raw LBS
model; it does not establish how the game normalizes or renders those vertices.

Seven default states cover neutral, half/full BreastSize and full breast paired
with ChestSize, Girth, Lean or ShoulderGirth. Optional vector JSON is a list of
`name` (or `fixture`) plus `values` records with known public names and finite
coefficients in [0,1]. Explicit male rows are excluded; female rows from the v4
fixture are preserved. Every state uses the existing 151 declared ordinary,
held-out, independent/bilateral P1 and combined controls. Bindings and summaries
retain root/triangle identities and the worst measured pose/root per group.
Full-weight and faded region followers have separate maxima and counts: a faded
card can intentionally underfollow skin, so its displacement is not silently
treated as a full-follower defect.

No universal pass threshold is invented. Report status means measurements were
completed for those states; it does not establish seam closure, common motion at
all vertices, card strain, alpha coverage, self-intersection clearance, FSMP
solver behavior, animation, game rendering or artistic acceptance. Historical
moderate-TRI repair profiles remain separate and are not repinned by this tool.

`attachment_fit.py` supplies a separate pure `fit_shift` helper for an explicitly
bounded weight shift whose interval contains zero. It intersects each supplied
sample's quadratic norm-nonincrease interval and minimizes the aggregate squared
residual inside the result. Callers retain state/convention samples explicitly;
optional zero objective weights keep a control active as a constraint. The helper
verifies its returned shift directly, reports the feasible interval and metrics,
and leaves exact-weight quantization, meaningful-gain policy, card budgets and
serialized resource application/readback to the caller. It edits no resources.
Shift arithmetic is normalized to the caller's finite bounds; zero objective
weights retain their constraints without setting the objective scale. Unsupported
float64 response/metric ranges are rejected explicitly.


## Isolated FSMP attachment trial

Generate the trial from the original 0.10.0 archive with Faster HDT-SMP selected
as its base. The four female model routes receive the same patched NIF. Use the
original released TRI and female FSMP XML identified in the generated receipt.

```powershell
python -B src/main/python/physics/breast_attachment_trial.py --release '<original 0.10.0 ZIP>' --out '<new external trial directory>'
```

The transfer gives the right P1 bone a share of the left P1 influence at three
vertices on one belly fur card. It updates the packed half weights and both
float representations, preserves the row sum, and keeps every other weight and
NIF block byte-for-byte. The release archive, the source carrier and all four
FOMOD destinations are checked before writing. These resources are for a
controlled comparison with the original FSMP carrier. Game qualification
requires a separate run with the exact trial archive and its original inputs.
