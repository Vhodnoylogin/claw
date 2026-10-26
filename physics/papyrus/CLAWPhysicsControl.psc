Scriptname CLAWPhysicsControl Hidden

; Finite coordinator API. Lookup alone has no start/assignment/qualification effect.
CLAWPhysicsHost Function GetHost() Global
  Return Game.GetFormFromFile(0x000800, "CLAW - Physics.esp") as CLAWPhysicsHost
EndFunction

Bool Function BeginSession(Bool optIn, String evidence) Global
  If !optIn || evidence == ""
    Return False
  EndIf
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return False
  EndIf
  If !host.IsRunning()
    If host.HasRememberedCapsules()
      Return False
    EndIf
    If !host.Start()
      Return False
    EndIf
  EndIf
  ; Starting/enabling only the host never qualifies a provider or attaches an actor.
  host.NotifySessionChanged()
  Return host.EnableIntegration(host.GetSessionGeneration(), evidence)
EndFunction

Int Function RegisterActor(Int slot, Actor target) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.Assign(slot, target)
EndFunction

Int Function GetGeneration(Int slot) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.GetSlotGeneration(slot)
EndFunction

Int Function QualifyActor(Int slot, Actor target, Int generation, String evidence, Bool provider, Bool indices, Bool pose) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.Qualify(slot, target, generation, evidence, provider, indices, pose)
EndFunction

Int Function PulseActor(Int slot, Actor expectedActor) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.Pulse(slot, expectedActor)
EndFunction

Int Function ReleaseActor(Int slot) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.Release(slot)
EndFunction

Int Function GetStatus(Int slot) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.GetSlotStatus(slot)
EndFunction

Int Function GetLedgerCount(Int slot) Global
  CLAWPhysicsHost host = GetHost()
  If host == None
    Return -1
  EndIf
  Return host.GetSlotLedgerCount(slot)
EndFunction

Function SuspendSession() Global
  CLAWPhysicsHost host = GetHost()
  If host != None
    ; No Quest.Stop/Reset/Clear: every remembered actor/ledger stays available.
    host.NotifySessionChanged()
  EndIf
EndFunction
