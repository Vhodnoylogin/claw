# CBPC stock Pelvis role — exact binary review

The ordinary ownership audit treats a configured node as a potential writer.
One exact binary/row has a narrower, verified write set. This is static role
classification, not game acceptance or a general Pelvis allowlist.

| Input | Pin |
| --- | --- |
| Official CBPC 1.7.3 archive | `70993a19b9e364ffe9c451ce708c353faf43d751b2fe9b8679eea8444a0d4e2a` |
| SSE 1.7.104 `cbp.dll` | `4996c85ee00e051a903c15746e8686a2357b70c9b27957f8ef3026dbc62d5387` |
| Matching `cbp.pdb` | `90c38d4868647f2b869b9cbc79410e36873229ffd394074dfe54fd9e45ecf2f2` |
| CodeView GUID / age | `1480b5dc-4631-4a03-8c34-8e4e2193691a` / `1` |

The installed DLL is byte-identical to that official archive member. Matching
symbols and disassembly establish:

- `Thing` construction at RVA `0x55c50` recognizes `NPC Pelvis [Pelv]` and sets
  the special flag. The dispatcher at `0x17530` calls `updatePelvis` and skips
  generic `Thing::update` for that flag.
- `updatePelvis` at `0x5e160` reads Pelvis as a world anchor. Its only direct
  node-position stores, at `0x5fa78..0x5faff`, target `NPC L Pussy02`,
  `NPC R Pussy02`, `VaginaB1` and `Clitoral1`. It does not write Pelvis's transform.
- Each missing required node branches to the epilogue before any node writes.
  Public PyNifly readback of the pinned XP32 wolf skeleton finds no `VaginaB1`
  or `Clitoral1`. Those four write targets are also disjoint from the measured
  eleven-driver/ancestor union, independently of missing-node early return.

The builder retains the original row and its file inventory. Only a **bare**
Pelvis declaration with that exact captured DLL hash records `readOnlyAnchor`
and the four `writeNodes`; overlap checks use the real write set. Unknown or
missing DLLs, aliased/conditioned rows, private aliases and every other writer
retain the conservative path. A protected graph containing one of the four
write targets still conflicts. Snapshot mutation invalidates the audit.

This does not qualify another CBPC build, VFS selection, binding or extra biped
parts. Before the stock-master game probe, inspect the full loaded graph and its
root/part identity: require the missing prerequisites or establish that all four
write targets are disjoint from the actual protected ancestry. Do not infer a
live graph's absence from donor files alone. Then run the ordinary motion and
lifecycle checks with unchanged stock master bytes.

Retained raw evidence is external under
`Builds/claw-cbpc-pelvis-proof-20261111/`: archive/PDB provenance, symbol and
disassembly records, caller/constructor analysis and wolf graph readback.
Full provider source/binary equivalence is not claimed.
