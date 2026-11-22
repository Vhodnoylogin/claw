# Discrete coat inspection fixture

`scenario.json` is portable, nonshipping test source for CLAW's discrete coat
policy. It describes six owned actors and required observations; it is not a
Polygon order, a compiled `polygon-actions/1` scenario or a ready game session.
Builds, saves, machine paths, channel bindings and actual hashes stay external.
The testing chat owns tool selection, qualification and native execution.

The two human controls use their actual human hair and the selected HIMBO/3BA
body inputs. Two male born wolves share one NPC base, and two female born wolves
share another. The born actors must remain without invented human colour history.
OBody's optional originally-beast host is not required to distribute coat
patterns and stays off in this fixture. Body coefficients may therefore be
weight-only on those four actors; capture the real values rather than pretending
that OBody supplied an ordinary human preset.

Positions derive from the accepted wolf slots in the parent inspection scene.
Resolve plugin/local forms and current dynamic references in the actual run.
Preserve the explicit AI/collision-off preconditions and per-reference locomotion
hold. No new room, camera framework or tool implementation is introduced.

Use the installed schema-2 `CoatMapping.xml`, `CoatMatrix.xml` and
`CoatLibrary.xml`. The catalogue exposes ten canonical Randomized patterns.
Saved legacy IDs resolve through aliases. The automatic hair path selects one
of five groups using the observed hair RGB and chooses a variant using matrix
variation. The hairless path uses the normalized saved seed and the scalar
ranges. The mode uses original texture colours, with the installed base
material when a selected resource is unavailable. Same-base actors have
independent saved identities and seeds and may legitimately pick the same coat.

Use the exact matrix, mapping and `CWLS`/`CWLA`/`CCAS` records to check selection.
The saved namespace and distribution identity provide the seed. Retain `CCLR`
hair and skin flags/RGB and `CCPT` manual IDs independently. Keep the female
human control automatic across save/load, alongside two manual actors. Compare
the female's fresh `coatDecision` and both actual DDS fields on her remapped
reference with the verified saved choice. Returning to human clears applied
coat ownership, and a later transform must reapply the expected selection.

Requested/applied IDs and origin/status remain application diagnostics. The
additional `RequestCoatSurfaceAudit(actor)` / `GetCoatSurfaceAudit(actor)` pair
samples actual third-person beast material fields on a main task. Request a new
sample around each bounded action, then retrieve it within two seconds. A true
request result is admission; an empty, pending, invalidated or stale result is
unavailable. Retain actor identity, request/read times, sample/model-generation
tokens and the complete observations. Compare the texture-set diffuse path and
bound texture resource separately with the selected pattern. Compare complete
excluded-surface multisets within one retained root generation, including duplicate
names. `modelGeneration` tracks the third-person root only: child/biped geometry
can change beneath the same root, so an equal token does not certify unchanged
inventory. Do not infer equality from the first matching name. Source strings use the
documented byte-preserving `bytes-u00xx` encoding.

Each geometry row in a current public audit includes an opaque decimal
`geometryId`. On the same retained root, adjacent successful public samples
keep the ID of the same attached geometry independently of its name, material
or traversal order. A newly observed object receives a fresh ID. The previous
sample retains its geometry until the new sample is published, which prevents
address reuse from certifying a false match. Keep every sample in the sequence:
an object absent from a sample loses that continuity. The private first-yield
log does not advance the public geometry observations.

This readback neither observes pixels nor certifies opaque renderer state or an
arbitrary later writer. It does not sample the human-return renderer. Use cleanup
status for that transition, retaining this limit. Technical acceptance needs no
screenshot or artistic-quality judgment; optional Steam images are supplementary.
A setter returning true still only means admission.

For the bounded native-binding channel, retrieve
`GetCoatSurfaceAuditChunks(actor)` instead of the long-string getter. Concatenate
the array in order with no separator, then parse JSON. Each element is at most
1,024 ASCII bytes, so it fits the channel's 4,096-byte string limit; up to 64
elements carry one complete sample. Escape sequences can cross a boundary. Empty
arrays mean unavailable, not an empty successful inventory. Do not combine chunks
from separate calls, whose samples or ages can differ.

After the owned save/load and reference remap, clear one restored manual choice
and compare it with its retained automatic baseline and a fresh surface sample.
Keep the other actors unchanged. Clearing before the save does not cover this
post-load behavior.

The CLAW test reviewer `src/test/python/integration/coat_persistence_readback.py`
checks one automatic hair-group actor. Keep the original native save and load
results, and fresh actor-bound material audits on both sides of the load. Bind
each sample to the run, PID, world generation, actor reference, and handle at
collection. Independently decode the matching owned co-save and use the exact
matrix and catalog to supply the expected pattern, both variation scores, and
twelve surface paths. The reviewer checks the remap and fresh model generation
before comparing the two applied decisions and both diffuse fields. It reports
skin-term contrast independently of automatic coat persistence.

Genuine source arrival/removal needs a supported real-appearance fixture action.
The existing actor-race action changes current race and preserves the base; it
does not erase retained hair history. Never add fabricated hair values to make
this check pass. The pure policy tests cover these transitions; a live source-
transition claim additionally requires actual source observations.

## Same-root coat recovery

Use one owned, transformed human with a verified automatic coat and all twelve
managed surfaces. Collect four consecutive public audits with the bound run,
process, world, reference, runtime handle and applied/manual coat diagnostics.
Retain the actual equipment and refresh results separately with the run.

1. **Baseline.** Read the complete applied coat and all geometry IDs.
2. **Foreign material.** On BODY use the existing typed
   `NetImmerse.SetNodeTextureSet` call with `firstPerson=false` and texture set
   `Skyrim.esm:0C0AE7`. Refresh and verify the stock BODY diffuse in both
   fields, complete geometry continuity and a yielded lease.
3. **Sibling replacement.** Swap the independently equipped HEAD mesh.
   Refresh. Verify the new HEAD ID, the original BODY ID and its foreign
   material. The rest of the managed geometry must keep its IDs.
4. **Conflicting replacement.** Swap the independently equipped BODY mesh.
   Refresh. Verify a new BODY ID, that the old one is absent even among
   unmanaged rows, and that the original automatic decision owns all twelve
   surfaces again. Keep the original root token across all four phases.

The Spriggit source in `turnover-plugin/` supplies one female Nord fixture
base (local form `000800`) and a dedicated skin (`000820`). The skin keeps
the human torso, hands and feet and supplies the wolf's fixed Tail40 model.
It has no stock wolf torso. The equippable variants are:

| Part | Slot | A form | B form |
| --- | --- | --- | --- |
| HEAD | 30 | `000832` | `000833` |
| BODY | 32 | `000830` | `000831` |

Compile with Spriggit YAML 0.41 and prepare the five NIFs and shared TRI using
`prepare_turnover_meshes.py --donor <female NIF> --tri <matching TRI> --pynifly
<addon directory> --output <new external directory>`. The builder pins the
retained r03 donor. It prunes unattached blocks, checks shape and slot
membership, preserves the packed skin buffers and keeps the original TRI
bytes under a fixture-local path. Variant A and B share geometry and material
content and use different armor records and NIF paths.

After transforming the owned fixture, confirm the dedicated skin and fixed
rest are attached and the stock wolf torso is absent. Equip A in both slots.
For the swaps, equip B directly over A and read back the worn forms with
slot masks `0x1` and `0x4`. The four actual audits must establish that the
engine retains the root and changes only the target geometry. The recorded
stock-TXST control from
`20261112-162527-512364` covered foreign material and then a different root
after load. It predates the geometry IDs and never covered this same-root case.

`src/test/python/integration/coat_turnover_readback.py` scores those four
audit observations against the expected pattern and actual material paths.
The caller binds the packet to the qualified run and checks process exit and
restoration separately. Synthetic verifier controls exercise discrimination
only. The offline package needs an admitted SE run to qualify attachment,
slot exclusivity, and preservation of the root.

`src/test/python/integration/coat_turnover_case.py` emits the
`polygon-actions/1` subject fragment and declared checks. It sets the first
settled coat audit as the factual boundary. To score a collected run, pass
`--result <result.json> --expected <expected.json>`; the expected file
contains the independently resolved `pattern` and `expected_paths` from the
winning coat configuration. The case verifies the run's owned fixture record,
the four observed worn-form pairs and actual audit evidence. Check the final
Polygon custody, installation and process evidence before using this result.

The proposed domain requires qualified reads of the fixture skin, fixed addon,
actual worn forms and coat audit. It also requires owned inventory supply,
direct equip and the stock BODY texture operation. An empty slot is a valid
native observation. Admit only the exact test actor, variant records and stock
texture set in the selected platform. Current guarded bindings lack distinct
armor and texture-set input roles, and the candidate SE platform has no
mapping for the coat observations. This fragment has no executor or launch
authorization. The originating chat can finish the schema-2 order once the
platform and the effective installed fixture are qualified.

The frozen owned interactive platform can exercise the existing typed coat APIs
for a bounded operator probe. Its transport/configuration stays outside this
portable source fixture. A formal schema2 coat order additionally needs the
testing tool's qualified coat-domain mapping; this fixture does not invent one.
