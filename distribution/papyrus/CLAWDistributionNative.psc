Scriptname CLAWDistributionNative Native Hidden

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
; Removes only CLAW.Distribution and suppresses auto assignment until AssignPreset.
Bool Function ClearOwn(Actor target) Global Native
Bool Function Refresh(Actor target) Global Native
