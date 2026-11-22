Scriptname CLAWVRNpcPose

; The dynamic FormID and handle are passed as signed Int representations of raw bits.
String Function BeginNpc(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon) Global Native
String Function BeginFemaleNpc(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon) Global Native
String Function BeginNpcWithMorphs(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon, String[] names) Global Native
String Function BeginNpcContact(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon, String[] names) Global Native
String Function BeginNpcTailRefit(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon, String[] names) Global Native
String Function SampleNpc(Int nonce, Int sequence) Global Native
String Function ReadNpc(Int nonce, Int sequence) Global Native
; Read an ordinary Distribution snapshot event from a loaded contact or tail-refit lease.
String Function ReadPhysicsSnapshot(Int nonce, Int previousToken) Global Native
String Function EndNpc(Int nonce) Global Native
