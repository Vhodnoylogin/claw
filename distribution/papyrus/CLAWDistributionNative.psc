Scriptname CLAWDistributionNative Native Hidden

; Explicit body-resource family binding; does not choose a human family by sex.
String[] Function GetMorphFamilies(Bool female) Global Native
Bool Function ConfigureMorphFamily(Actor target, String profileId) Global Native
; Last actually observed same-reference NPC weight / 100 in each form.
; -1 means unknown or an unavailable actor identity; these getters never set it.
Float Function GetHumanWeight(Actor target) Global Native
Float Function GetBeastWeight(Actor target) Global Native

; Optional OBody host: explicit session opt-in, fresh automatic defaults only.
; Candidate/Ready mod events carry Actor sender, profile strArg and integer token.
; Request queues main-thread identity/root/race/source-name validation; Claim
; atomically consumes a ready cached token immediately before stock GenActor.
; This class never invokes OBody or writes its keys. Existing zero-valued source
; names, restored/manual/suppressed/known-human actors cannot bootstrap.
Bool Function EnableOBodySourcePopulation(Bool optIn) Global Native
; 0 no API, 1 world/official readiness pending, 2 genuine stock-generation
; witness pending, 3 protocol ready/disabled, 4 enabled. No timer guesses.
Int Function GetOBodySourceStatus() Global Native
Bool Function RequestSourceBootstrap(Actor target, Int token) Global Native
Bool Function ClaimSourceBootstrap(Actor target, Int token) Global Native

; Standalone typed CLAW catalogs; this class does not write OBody assignments.
String[] Function GetPresetNames(Bool female) Global Native
; True means queued; inspect GetStatus/GetLastError for the application outcome.
Bool Function AssignPreset(Actor target, String presetName) Global Native
String Function GetAssigned(Actor target) Global Native
; 0 unknown, 1 pending, 2 coefficients read back/update requested, 3 unloaded,
; 4 error, 5 human (own key cleared), 6 explicitly cleared, 7 SKEE unavailable.
Int Function GetStatus(Actor target) Global Native
String Function GetLastError(Actor target) Global Native
; Last verified own coefficient; 0 when status is not 2 (not aggregate/multiple keys).
Float Function GetOwnMorph(Actor target, String morphName) Global Native
; Removes only CLAW.Distribution; AssignPreset or ConfigureMorphLink explicitly resumes.
Bool Function ClearOwn(Actor target) Global Native
Bool Function Refresh(Actor target) Global Native

; Explicit morph-to-morph developer profile. No preset-name pairing or OBody writes.
; Applied signed source values are read from SKEE; weight must not be applied twice.
; Equal-size arrays, 1..128 rows. sum(source*gain), clamp 0..1, multiply target cap.
; Duplicate source/target rows, inconsistent target caps, CLAW sources are rejected.
; Wait for the preceding queued request to finish before sending another request.
; A valid configuration explicitly resumes a suppressed actor.
Bool Function ConfigureMorphLink(Actor target, String profile, String[] sources, String[] targets, Float[] gains, Float[] caps) Global Native
Bool Function DisableMorphLink(Actor target) Global Native
