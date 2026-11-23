Scriptname CLAWVRPlayerCBPCEvents

String Function GetCaptureState() Global Native
Bool Function Arm(Int nonce, Int generation, Int actorFormBits, Int cellFormBits) Global Native

; A true result means the main-thread identity check was queued.
Bool Function Seal(Int nonce, Int generation) Global Native
String Function Read(Int nonce, Int generation) Global Native
