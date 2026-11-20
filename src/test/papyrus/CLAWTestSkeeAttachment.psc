Scriptname CLAWTestSkeeAttachment Hidden

; Test-only. Return -1 for a rejected fixture, 0 for a completed native refusal,
; or 1 for a completed attach or detach. The runner separately verifies geometry.
Int Function Attach(Actor subject) Global
    If !IsFixture(subject)
        Return -1
    EndIf

    String[] filter = new String[1]
    filter[0] = "CLAW_AttachProbe_20261120_AbsentFilter"
    Bool attached = NiOverride.AttachMesh(subject, false, "Meshes\\Actors\\WerewolfBeast\\CLAW\\Tests\\Attach\\probe.nif", "CLAW_AttachProbe_20261120_Wrapper", false, filter)
    Return Completed(attached)
EndFunction

Int Function Detach(Actor subject) Global
    If !IsFixture(subject)
        Return -1
    EndIf

    Bool detached = NiOverride.DetachMesh(subject, false, "CLAW_AttachProbe_20261120_Wrapper")
    Return Completed(detached)
EndFunction

Int Function Completed(Bool success) Global
    If success
        Return 1
    EndIf
    Return 0
EndFunction

Bool Function IsFixture(Actor subject) Global
    Actor player = Game.GetPlayer()
    If subject == None || player == None || subject == player || subject.IsDisabled() || !subject.Is3DLoaded() || subject.IsDead()
        Return false
    EndIf
    Int referenceId = subject.GetFormID()
    If referenceId >= 0 || referenceId < -16777216
        Return false
    EndIf

    ActorBase expected = Game.GetFormFromFile(0x000800, "test_CLAW - Physics Probe.esp") as ActorBase
    Race wolf = subject.GetRace()
    Cell room = player.GetParentCell()
    Return expected != None && subject.GetActorBase() == expected && expected.GetSex() == 1 && expected.GetWeight() == 100.0 \
        && wolf != None && wolf.GetFormID() == 0x0CDD84 && room != None && subject.GetParentCell() == room
EndFunction
