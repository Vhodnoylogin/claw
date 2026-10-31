Scriptname CLAWOBodySourceHost extends Quest

; Set only by an explicit install choice or Enable(). No independent wolf presets.
Bool Property IntegrationOptIn = False Auto
String lastResult = "disabled"

Event OnInit()
    Listen()
    If IntegrationOptIn
        Enable()
    EndIf
EndEvent

Function Listen()
    RegisterForModEvent("CLAWDistribution_Loaded", "OnDistributionLoaded")
    RegisterForModEvent("CLAWDistribution_OBodySourceCandidate", "OnSourceCandidate")
    RegisterForModEvent("CLAWDistribution_OBodySourceReady", "OnSourceReady")
    RegisterForModEvent("CLAWDistribution_OBodySourceAvailable", "OnSourceAvailable")
EndFunction

Bool Function Enable()
    If !IsRunning() || Game.GetModByName("OBody.esp") == 255
        lastResult = "OBody plugin or running host unavailable"
        Return False
    EndIf
    IntegrationOptIn = True
    Listen()
    Bool admitted = CLAWDistributionNative.EnableOBodySourcePopulation(True)
    If admitted
        lastResult = "enable queued; source assignment is not confirmed"
    Else
        If CLAWDistributionNative.GetOBodySourceStatus() == 2
            lastResult = "waiting for an actual stock OBody generation"
        Else
            lastResult = "native source adapter unavailable or waiting for provider readiness"
        EndIf
    EndIf
    Return admitted
EndFunction

Function Disable()
    IntegrationOptIn = False
    CLAWDistributionNative.EnableOBodySourcePopulation(False)
    lastResult = "disabled; existing OBody assignments retained"
EndFunction

String Function GetLastResult()
    Return lastResult
EndFunction

Int Function GetProviderStatus()
    Return CLAWDistributionNative.GetOBodySourceStatus()
EndFunction

Bool Function Eligible(Actor target)
    If !IntegrationOptIn || !IsRunning() || !target || !target.Is3DLoaded() || CLAWDistributionNative.GetOBodySourceStatus() != 4
        Return False
    EndIf
    Race beast = Game.GetFormFromFile(0xCDD84, "Skyrim.esm") as Race
    Return beast != None && target.GetRace() == beast
EndFunction

Int Function Token(Float value)
    Int result = value as Int
    If result <= 0 || result > 16777215 || (result as Float) != value
        Return 0
    EndIf
    Return result
EndFunction

Function OnDistributionLoaded(String eventName, String profile, Float value, Form sender)
    If IntegrationOptIn
        Enable()
    EndIf
EndFunction

Function OnSourceAvailable(String eventName, String profile, Float value, Form sender)
    If IntegrationOptIn
        Enable()
    EndIf
EndFunction

Function OnSourceCandidate(String eventName, String profile, Float value, Form sender)
    Actor target = sender as Actor
    Int request = Token(value)
    If !request || !Eligible(target)
        Return
    EndIf
    ; A legitimate neutral preset is still an assignment: never infer absence from zero.
    If OBodyNative.GetPresetAssignedToActor(target) != ""
        CLAWDistributionNative.Refresh(target)
        lastResult = "existing OBody assignment retained"
        Return
    EndIf
    If CLAWDistributionNative.RequestSourceBootstrap(target, request)
        lastResult = "fresh beast source revalidation queued"
    EndIf
EndFunction

Function OnSourceReady(String eventName, String profile, Float value, Form sender)
    Actor target = sender as Actor
    Int request = Token(value)
    If !request || !Eligible(target)
        Return
    EndIf
    If OBodyNative.GetPresetAssignedToActor(target) != ""
        CLAWDistributionNative.Refresh(target)
        lastResult = "existing OBody assignment retained"
        Return
    EndIf
    ; Native claim consumes a freshly revalidated, actor/world/root-bound token.
    ; Stock GenActor owns the final processed/blacklist decision and preset choice.
    If !CLAWDistributionNative.ClaimSourceBootstrap(target, request)
        lastResult = "stale source request rejected"
        Return
    EndIf
    OBodyNative.GenActor(target)
    CLAWDistributionNative.Refresh(target)
    lastResult = "request handed to OBody; actual source values still require observation"
EndFunction
