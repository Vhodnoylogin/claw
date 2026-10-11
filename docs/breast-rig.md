# Female breast shape and rig development

The owner reports that the current enlargement looks unrealistic. A new shape is
required; adding bones or physics alone does not repair the static silhouette.
Prefer the existing XP32 skeleton. Replacement is a fallback only when existing
bones cannot meet a demonstrated requirement.

## Verified starting point

Read-only PyNifly inspection on 11 October 2026 finds 345 nodes in the pinned XP32
werewolf skeleton, including bilateral PreBreast/Breast/Breast01 chains. The breast
heads are approximately `(+-8, 19.17, 90.014)` in the inspected rest frame. The
published female `_0` mesh contains 85 nodes and no breast nodes or weights.
Its current breast recipe gates deformation through Spine/Clavicle weights across
body, head, fur_chest, fur_belly, fur_shoulders and ChestBlend.

Importing existing bone matrices into a skinned mesh and assigning weights does
not itself add bones to the game's skeleton. Fit pivots and verify transforms in
the actual werewolf rest pose; human breast settings cannot be blindly copied.

## Chosen direction and alternative

First reshape the breast volume with a stable root, a smooth underside and a
controlled transition into the thorax. Separate volume, lower projection and sag
instead of one large swelling amplitude. Preserve the neutral body and UV/texture
continuity. Shape references and exact artistic proportions still need agreement.

Then use existing bilateral breast chains for local skin weights: firm attachment
near the thorax, progressively mobile tissue away from it, normalized weights and
smooth boundaries. Corresponding skin, fur cards and blend patches must share the
same deformation field at their joins. Keep Spine/Clavicle influence outside the
breast region. Dedicated colliders and physics are separate engine configurations;
their motion, contact and compatibility need runtime tests.

An independent breast mesh is a viable alternative, similar to an attached anatomy
part. It still needs skinning to existing dynamic bones for soft deformation; a
rigid attachment to one bone moves the entire part as one object. It also needs
matched thorax edges or controlled overlap, UV continuity, matching fur, normals
and removal/coverage of the old volume. Merely placing a new rounded part on top
would introduce clipping or another seam. Prototype one breast before selecting
integrated versus separate topology. No topology replacement is implemented here.

## First offline seam experiment

A local candidate changes CLAWTorsoBreastSize from separately deforming all six
shapes to a body-based field with explicit layer followers. At coefficient 0.5,
Morphbench reports p99 edge strain reductions: head 0.402->0.055, fur_belly
0.486->0.113, fur_chest 0.324->0.025. Body strain is unchanged. At full morph,
maximum head displacement drops from15.991 to5.711; this also changes the visible
volume, so the result is not a faithful shape-preserving repair. ChestBlend still
moves only0.007 units. The experiment identifies a mechanism for disagreement
between layers but does **not** establish that the reported underside gap is fixed.

Candidate recipe, NIF/TRI, command log, strain/layer tables and renders are retained
outside Git in the session's `roadmap-implementation-20261011` evidence. Production
`female.json`, build recipe and published assets remain unchanged. Future repair
must check neutral and morphed join distances/UVs, shared weight transitions, several
views and animated game poses. The known published gap remains disclosed.
