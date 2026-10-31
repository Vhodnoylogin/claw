Scriptname CLAWPhysicsLoadRelay extends ReferenceAlias

; Optional separate player alias on the SAME quest. Never uses an actor slot.
; Record wiring/event delivery still need engine acceptance before installation.
Event OnPlayerLoadGame()
  CLAWPhysicsHost host = GetOwningQuest() as CLAWPhysicsHost
  If host != None
    host.NotifySessionChanged()
  EndIf
EndEvent
