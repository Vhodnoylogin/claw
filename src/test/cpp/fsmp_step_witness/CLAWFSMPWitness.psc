Scriptname CLAWFSMPWitness

; 0 queues one read-only main-thread snapshot. Poll its returned positive serial.
; Repeating a positive serial never queues again. v2 also returns read-only Bullet summaries.
String Function ReadState(Int serial = 0) Global Native

; Queues one consumer-only arm request. Same nonce polls, never resets.
; Positive nonce required; different nonce/process or changed load epoch refuses.
; Exactly 128 object capacity and 900 paired steps; no Bullet/engine writes.
String Function BeginWindow(Int nonce) Global Native
