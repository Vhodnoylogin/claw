# V3 FSMP onset observations,19 November2026

Run`20261119-015300-201ec0` qualified the read-only v3 witness's co-temporal
velocity/inverse-inertia fields and900 completed-host-pair dt statistics.
The original damping peak gate **failed** with
`Unchanged right certified peak control exceeded`; damping acceptance remains
false. Root independently verified normal exit0,128 snapshot preimages,268 cold
pins,266 VFS winners and unchanged all31 morph values.

The actual pair74 associates left parent token13 and driver14, with exactly
matching pre/post QPCs. Driver inverse mass20 and inverse local inertia(10,10,10)
were observed. Its WORLD-Y COM velocity changes from−.0000707411 to−4.022846699
inside that provider step; parent velocity is−5.946395397. Their translations
change−.06701660156 and−.09912109375 respectively. A large dynamic kick was not
already present in the captured PreStep velocity.

The pinned rest-frame attachment point uses `rB=−RB*R0ᵀ*t0` and velocity
`vB+omegaB×rB`. Angular motion adds−.1235718775 WORLD-Y, making point velocity
−4.1464185763. Projecting its velocity relative to the parent onto the actual
joint-X axis gives **−1.79997682247**. COM-only or raw WORLD-X reasoning misses
the lever arm/rotated axis.

The source-law comparison is **conditional**. Spring2 emits a predictive lower
limit row even inside an enabled lower<upper interval. FSMP's PDB-matched source
defaults stopERP=.2 and explicitly sets it. Supplied lower−.15, fps60 and measured
pre qx−.00000171536 predict−1.79997941572; observed minus target is
**+.00000259325**. This is a concrete source-based explanation consistent with
the onset observations. The isolated spring screening already included the ideal
damping impulse but omitted the predictive limit-row response. This comparison
does not establish an exclusive cause or directly observe actual
constraint coefficients, ERP, solver fps or the applied row impulse. No new
acceptance tolerance is inferred from this residual.

The witness reports host minimum.01649999805 and host sum15.09016625769 seconds
over900 completed callback pairs. FSMP may split/discard time internally; those
fields do not establish Bullet-substep counts or integrated simulation time.
Right driver first changes at75 while its parent starts at98; these onset pairs
cannot be spliced into one co-temporal calculation.

The pure helper `python/integration/fsmp_attachment_point_readback.py` reuses
canonical joint/rest transforms and the sole v3 pose/window validator. It separates
COM, angular lever and rotating-parent-axis terms and makes optional supplied
lower-row assumptions explicit. Portable tests use authored numeric fixtures;
they do not qualify runtime physics. No callback, transport, v4 observer or
constraint-reference implementation is included.

An optional exact archived bundle remains outside Git. Select it explicitly:

```powershell
$env:CLAW_FSMP_ATTACHMENT_POINT_EVIDENCE = '<reviewed-actual-attachment-bundle.json>'
$env:CLAW_FSMP_ATTACHMENT_POINT_REQUIRED = '1'
python -B -m unittest discover -s src/test/python/integration -p 'test_fsmp_attachment_point_readback.py' -v
```

Its SHA256 is`d742a7709ebee5aef07f53b449c704a50da0e601d765f10f9f397bf4679c8059`.
The source root acceptance receipt SHA256 is
`511ee8b52e1e81989f035bb35d28170311329ae99531b169f69bf9aba5d05dce`.
Unset evidence visibly skips actual replay; required, explicitly missing or
hash-changed selection fails. Replay checks numeric consistency/corruption only;
it neither admits a live game nor independently rechecks restoration. The
unchanged failed damping result is part of the reviewed bundle's scope.
