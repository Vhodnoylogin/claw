Scriptname CLAWPhysicsNative Native Hidden

; Implemented by the optional Distribution DLL, not by CBPC. Registration
; queues a main-task observer; True means accepted for processing only.
Bool Function RegisterActor(Actor target, Int generation, String[] orderedMorphNames, String modelIdentity, String qualificationEvidence, String expectedSession = "") Global Native
; Only explicit external qualification may replace rejected/suspended authority.
Bool Function RegisterQualifiedActor(Actor target, Int generation, String[] orderedMorphNames, String modelIdentity, String qualificationEvidence, String expectedSession) Global Native
; Population callbacks can consume virgin authority once; never clear a tombstone.
Bool Function RegisterInitialActor(Actor target, Int generation, String[] orderedMorphNames, String modelIdentity, String qualificationEvidence, String expectedSession) Global Native
; Begin is an explicit external session action; getter never adopts/rotates it.
String Function BeginSessionToken() Global Native
String Function EndSession(String expectedSession) Global Native
String Function GetSessionToken() Global Native
Bool Function ConditionCurrent(Actor target, String condition, String expectedSession) Global Native
; Read-only candidate events from Distribution's known loaded beast registry.
Bool Function SetPopulationEnabled(Bool optIn, String expectedSession = "") Global Native
Function UnregisterActor(Actor target, Bool retainForCleanup = False, String expectedSession = "") Global Native
Bool Function ActorCurrent(Actor target) Global Native
Bool Function SnapshotCurrent(Actor target, Int generation, Int token) Global Native
Bool Function RefitPending(Actor target, Int generation, Int previousToken) Global Native
Function AcknowledgeSnapshot(Actor target, Int generation, Int token) Global Native
Function AcknowledgeLifecycle(Actor target, String condition) Global Native
Float[] Function GetValues(Actor target, Int generation, Int token) Global Native
; Independent base interpolation input, actual TESNPC weight / 100; -1 stale.
; Human and beast keep the same NPC property; this bridge never changes it.
Float Function GetWeight(Actor target, Int generation, Int token) Global Native
; p1 xyz, p2 xyz, radius. One capsule avoids Papyrus's 128-item array limit.
Float[] Function GetCapsule(Actor target, Int generation, Int token, Int slot) Global Native
String Function GetModelIdentity() Global Native
