Scriptname CLAWVRNpcPose

; The dynamic FormID and handle are passed as signed Int representations of raw bits.
String Function BeginNpc(Int nonce, Int actor, Int base, Int handle, Int cell, Int addon) Global Native
String Function SampleNpc(Int nonce, Int sequence) Global Native
String Function ReadNpc(Int nonce, Int sequence) Global Native
String Function EndNpc(Int nonce) Global Native
