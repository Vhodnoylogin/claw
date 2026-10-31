# One native CommonLib DLL

The current candidate builds **one CLAWDistribution.dll** for SE, AE and VR.
There is no DLL choice in its build target or runtime logic. The preserved
30 October release still contains its original exact-SE binary; this new source
and build do not retroactively qualify that release or install anything.

| Engine executable version | Family used by CommonLib | Minimum SKSE |
|---|---|---|
| 1.5.97.0 | SE | 2.0.20 |
| 1.6.640.0 | AE | 2.2.3 |
| 1.6.659.0 (GOG) | AE | 2.2.3 |
| 1.6.1170.0 | AE | 2.2.6 |
| 1.6.1179.0 (GOG) | AE | 2.2.6 |
| 1.7.104.0 | AE layout family, sold as Skyrim SE | 2.3.1 |
| 1.4.15.0 | VR | 2.0.12 |

These are explicit **candidate load boundaries**, defined once in
`distribution/include/claw/RuntimeSupport.h`. Both SKSE exports and the Load
check use that list. Editor, unknown/future versions and older SKSE fail before
plugin engine work. The shared metadata minimum is zero because SKSE minima
differ between families; Query and Load enforce the appropriate minimum.
After CommonLib initialization, its detected version and SE/AE/VR family must
agree with the selected candidate. The game needs the matching Address Library
data and compatible RaceMenu/SKEE installation for its actual runtime.

The external SDK is CommonLibSSE-NG 9.1.0 at parent
`a898f469851c464d05137bb74b069dd234897643`, with the owner's isolated TypeInfo
object-array mask correction in `0c95630c29ff98f64caeea83c29ca373cf93e58b`.
SE, AE and VR are all enabled in the same SDK compilation. The official OpenVR
submodule is pinned at `60eb187801956ad277f1cae6680e3a410ee0873b`.
`distribution/dependencies.json` records the external source/archive identities.
The older CommonLib 3.7.0 build is retained history and cannot build this source.

This implements runtime routing through the SDK, rather than changing only a
version guard. Actor race and actor-base lookup use CommonLib methods. Loaded
3D uses its virtual wrappers; current actor data uses its versioned accessors.
Weak handles, reference pins, process-list enumeration, VM handle-policy access,
Papyrus native registration and SKSE task/message/serialization interfaces also
use the same current SDK. CLAW adds no hardcoded engine addresses, vtable indices
or runtime-specific object-offset arithmetic. The SDK supplies those differences.
The matrix kernel remains exactly the same source compiled native and WASM.

SKEE is a separate public ABI. Every morph call passes through `skeeReference`:
first convert Actor to the actual CommonLib TESObjectREFR base pointer, then
bridge the official header's opaque global namespace spelling. No handle,
sub-interface address or fabricated numeric adjustment is passed. The exchange
requires the v4 BodyMorph prefix, accepts v5's appended callback, and never calls
that v5-only method. This excludes an older provider rather than assuming a
matching version number guarantees its ABI. The correct runtime's SKEE binary
still needs a real application/readback test.

Build with `distribution/build.ps1` into a fresh external directory. Its default
and only selector is `UNIVERSAL`; the target is `CLAWDistribution`. Both Query
and Version metadata exports are retained for old/new SKSE discovery. CommonLib's
variable-layout compatibility flag and Address Library V5 capability are loader
mechanisms, not claims of completed SE/AE/VR game testing.

Offline checks cover all seven runtime/minimum boundaries, rejection of older
SKSE/editor/future runtimes, matrix arithmetic and source capture, v5 rule
serialization and old-record defaults. PE inspection verifies the actual one
DLL's exports and metadata without loading it. Game checks are tracked separately:
the fresh SE core105 and born27 mechanisms now pass on
this exact universal DLL, as recorded in [31 October verification](verification-20261031.md).
VR remains unrun; AE has structural review/build evidence only because its runtime
is unavailable in the current setup. The offline checks alone do not certify rendering,
transformation lifecycle, physics or third-party provider behavior in an engine.

Explicit offline verification after building:

```powershell
ctest --test-dir '<external-universal-build>' -C Release --output-on-failure
python distribution/tests/UniversalMetadata.py '<external-universal-build>/Release/CLAWDistribution.dll' --report '<external-evidence>/pe.json'
```

The PE inspector uses the caller's external `pefile` installation and never loads
the DLL. It also rejects unconditional OpenVR/SKEE DLL imports, which would make
one engine family depend on another engine's provider before plugin discovery.
