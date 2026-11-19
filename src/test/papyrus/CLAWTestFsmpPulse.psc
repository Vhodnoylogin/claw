Scriptname CLAWTestFsmpPulse

; Test-only. The runner owns the disposable actor, one call, and cleanup.
; 0: refused before Add. 1: Add returned, but Update was withheld.
; 2: Update returned. Native world/solver readback still determines the outcome.
Int Function Apply(Actor subject) Global
    String node = "NPC L PreBreast P1"
    String entryKey = "CLAW.Test.FSMP.Damping.Step"
    If !IsFixture(subject) || NiOverride.HasNodeTransformPosition(subject, false, true, node, entryKey)
        Return 0
    EndIf

    Float[] delta = new Float[3]
    delta[0] = 0.01
    NiOverride.AddNodeTransformPosition(subject, false, true, node, entryKey, delta)
    If !IsFixture(subject)
        Return 1
    EndIf

    Float[] stored = NiOverride.GetNodeTransformPosition(subject, false, true, node, entryKey)
    If stored == None || stored.Length != 3
        Return 1
    EndIf
    If stored[0] != delta[0] || stored[1] != 0.0 || stored[2] != 0.0 || !IsFixture(subject)
        Return 1
    EndIf

    NiOverride.UpdateNodeTransform(subject, false, true, node)
    Return 2
EndFunction

Bool Function IsFixture(Actor subject) Global
    If subject == None || subject.IsDisabled() || !subject.Is3DLoaded() || subject.IsDead() || subject.IsInCombat()
        Return false
    EndIf
    Int referenceId = subject.GetFormID()
    If referenceId >= 0 || referenceId < -16777216
        Return false
    EndIf

    ActorBase subjectBase = subject.GetActorBase()
    ActorBase expectedBase = Game.GetFormFromFile(0x000801, "test_CLAW - Beast and Mixed Families.esp") as ActorBase
    Race wolf = subject.GetRace()
    Cell room = subject.GetParentCell()
    Return subjectBase != None && subjectBase == expectedBase && subjectBase.GetSex() == 1 \
        && wolf != None && wolf.GetFormID() == 0x0CDD84 && room != None && room.GetFormID() == 0x032AE7
EndFunction
