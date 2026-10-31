# Optional OBody public API input

The optional source bootstrap is compiled against the unmodified public
`include/API/API.h` from OBody NG source revision
`13513609145313f721970c2ebe113290f6add6e8` (version 5.2.0).
SHA-256: `42a899e88ba53bcc673d2d8e9513e839f0d661ee1e002514fe3551827a98681d`.

The external header contains its GNU General Public License version 3 text and
the author's public interoperability instructions. It is not vendored in CLAW.
An external build copies that exact file into its build directory. Preserve the
header's notice and license with any distributed corresponding source.

Only `RequestPluginInterface`, `IOBodyReadinessEventListener` and the read-only
`IActorChangeEventListener::OnActorGenerated` notification are used here.
There is no copied OBody implementation or private object-layout access.
The standalone morph link does not require this optional SDK or OBody.
