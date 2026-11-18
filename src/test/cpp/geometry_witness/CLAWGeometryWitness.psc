Scriptname CLAWGeometryWitness

; Form IDs use signed Papyrus Int bit patterns. No world pointer is read on this call.
; Fixed dynamic female fixture base only. Positive increasing nonce; at most32 captures.
; A pending request or consumed nonce is never requeued/replayed.
String Function Capture(Int actorFormId, Int expectedBaseId, Int nonce) Global Native
String Function ReadState(Int serial) Global Native
; Immutable JSON chunks, not a fresh capture. Maximum chunk size4096 characters.
String Function ReadChunk(Int serial, Int index) Global Native
