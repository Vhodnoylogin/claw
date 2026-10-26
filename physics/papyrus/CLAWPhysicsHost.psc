Scriptname CLAWPhysicsHost extends Quest

; Optional finite controller. The separate wiring recipe supplies the quest.
; Configure 1..16 distinct OPTIONAL aliases on this quest, each with our helper.
; Configuration is copied once. Keep the quest/aliases alive until all ledgers clear.
CLAWPhysicsActor[] Property ActorSlots Auto
Bool Property IntegrationOptIn = False Auto

CLAWPhysicsActor[] _slots
Int _slotCount = 0
Bool _busy = False
String _error = ""
String _lastResetEvidence = ""
Int _sessionGeneration = 0
Int _enabledGeneration = -1
String _activationEvidence = ""

Int Function GetSessionGeneration()
  Return _sessionGeneration
EndFunction

Bool Function IntegrationEnabled()
  Return IntegrationOptIn && _enabledGeneration == _sessionGeneration && _activationEvidence != ""
EndFunction

Bool Function EnableIntegration(Int expectedSessionGeneration, String evidence)
  If _busy || evidence == "" || expectedSessionGeneration != _sessionGeneration || !IsRunning() || !Initialize()
    Return False
  EndIf
  _activationEvidence = evidence
  _enabledGeneration = expectedSessionGeneration
  IntegrationOptIn = True
  Return expectedSessionGeneration == _sessionGeneration
EndFunction

String Function GetLastError()
  Return _error
EndFunction

String Function GetLastResetEvidence()
  Return _lastResetEvidence
EndFunction

Int Function Fail(Int code, String reason)
  _error = reason
  Return code
EndFunction

Bool Function Initialize()
  If _slots != None
    Return True
  EndIf
  If ActorSlots == None || ActorSlots.Length < 1 || ActorSlots.Length > 16
    Fail(-1, "Supply 1..16 optional actor aliases; no automatic allocation exists")
    Return False
  EndIf
  Int slot = 0
  While slot < ActorSlots.Length
    If ActorSlots[slot] == None || ActorSlots[slot].GetOwningQuest() != Self
      Fail(-1, "Every configured helper must belong to this quest")
      Return False
    EndIf
    Int other = 0
    While other < slot
      If ActorSlots[other] == ActorSlots[slot]
        Fail(-1, "The same alias cannot occupy two slots")
        Return False
      EndIf
      other += 1
    EndWhile
    slot += 1
  EndWhile
  CLAWPhysicsActor[] prepared = new CLAWPhysicsActor[16]
  slot = 0
  While slot < ActorSlots.Length
    prepared[slot] = ActorSlots[slot]
    slot += 1
  EndWhile
  _slotCount = ActorSlots.Length
  _slots = prepared
  Return True
EndFunction

CLAWPhysicsActor Function SlotAt(Int index)
  If !Initialize() || index < 0 || index >= _slotCount
    Return None
  EndIf
  Return _slots[index]
EndFunction

Int Function GetSlotCount()
  If !Initialize()
    Return 0
  EndIf
  Return _slotCount
EndFunction

Int Function GetSlotGeneration(Int index)
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None
    Return -1
  EndIf
  Return helper.GetModelGeneration()
EndFunction

Int Function GetSlotStatus(Int index)
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None
    Return -1
  EndIf
  Return helper.GetStatus()
EndFunction

Int Function GetSlotLedgerCount(Int index)
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None
    Return -1
  EndIf
  Return helper.GetAcceptedLedgerCount()
EndFunction

Bool Function HasRememberedCapsules()
  If !Initialize()
    ; Failure to inspect aliases is not proof that a stopped quest is empty.
    Return True
  EndIf
  Int slot = 0
  While slot < _slotCount
    If _slots[slot].GetAcceptedLedgerCount() > 0
      Return True
    EndIf
    slot += 1
  EndWhile
  Return False
EndFunction

Bool Function ActorInOtherSlot(Int index, Actor target)
  Int slot = 0
  While slot < _slotCount
    If slot != index
      If _slots[slot].GetActorReference() == target || _slots[slot].GetTrackedActor() == target
        Return True
      EndIf
    EndIf
    slot += 1
  EndWhile
  Return False
EndFunction

Function Revoke(CLAWPhysicsActor helper)
  helper.ProviderQualified = False
  helper.ExclusiveIndexRange = False
  helper.MarkModelGenerationChanged()
EndFunction

Int Function Assign(Int index, Actor target)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = AssignInternal(index, target)
  _busy = False
  Return outcome
EndFunction

Int Function AssignInternal(Int index, Actor target)
  If !IntegrationEnabled()
    Return Fail(-6, "Explicit current-session integration opt-in is required")
  EndIf
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None || target == None
    Return Fail(-1, "Invalid slot or actor")
  EndIf
  If ActorInOtherSlot(index, target)
    Return Fail(-2, "Actor already assigned or retained by another slot's cleanup ledger")
  EndIf
  If helper.GetActorReference() == target
    Return 0
  EndIf
  Int cleanup = helper.Cleanup()
  If cleanup == 8 || helper.GetAcceptedLedgerCount() > 0
    Return Fail(-3, "Previous actor cleanup pending; alias has not been cleared or retargeted")
  EndIf
  Revoke(helper)
  helper.Clear()
  If helper.GetReference() != None
    Return Fail(-4, "Alias Clear failed; configure it Optional before integration")
  EndIf
  helper.ForceRefTo(target)
  If helper.GetActorReference() != target
    Return Fail(-4, "Alias assignment was not observed; attachment has not been attempted")
  EndIf
  Return 0
EndFunction

Int Function Release(Int index)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = ReleaseInternal(index)
  _busy = False
  Return outcome
EndFunction

Int Function ReleaseInternal(Int index)
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None
    Return Fail(-1, "Invalid slot")
  EndIf
  Int cleanup = helper.Cleanup()
  If cleanup == 8 || helper.GetAcceptedLedgerCount() > 0
    Return Fail(-3, "Cleanup pending; alias and ledger retained")
  EndIf
  Revoke(helper)
  helper.Clear()
  If helper.GetReference() != None
    Return Fail(-4, "Alias Clear failed; configure it Optional before integration")
  EndIf
  Return 0
EndFunction

Int Function Qualify(Int index, Actor expectedActor, Int expectedGeneration, String evidence, Bool provider, Bool exclusiveIndices, Bool staticPose)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = QualifyInternal(index, expectedActor, expectedGeneration, evidence, provider, exclusiveIndices, staticPose)
  _busy = False
  Return outcome
EndFunction

Int Function QualifyInternal(Int index, Actor expectedActor, Int expectedGeneration, String evidence, Bool provider, Bool exclusiveIndices, Bool staticPose)
  If !IntegrationEnabled()
    Return Fail(-6, "Explicit current-session integration opt-in is required")
  EndIf
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None || expectedActor == None || ActorInOtherSlot(index, expectedActor)
    Return Fail(-1, "Invalid slot/actor or duplicate actor ownership")
  EndIf
  If !helper.QualifyForActor(expectedActor, expectedGeneration, evidence, provider, exclusiveIndices, staticPose)
    Return Fail(-5, "Qualification rejected: stale actor/generation, empty evidence or helper busy")
  EndIf
  Return 0
EndFunction

Int Function Pulse(Int index, Actor expectedActor)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = PulseInternal(index, expectedActor)
  _busy = False
  Return outcome
EndFunction

Int Function PulseInternal(Int index, Actor expectedActor)
  If !IntegrationEnabled()
    Return Fail(-6, "Explicit current-session integration opt-in is required")
  EndIf
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None || expectedActor == None || helper.GetActorReference() != expectedActor
    Return Fail(-1, "Pulse actor no longer matches the alias")
  EndIf
  If ActorInOtherSlot(index, expectedActor)
    Return Fail(-2, "Duplicate actor ownership; pulse refused")
  EndIf
  ; One explicit attempt. No retry queue, all-actor scan or binding/reset guess.
  Return helper.Synchronize()
EndFunction

Bool Function AcknowledgeReset(Int index, Actor previousActor, String resetEvidence, Bool previousContainersDiscarded)
  If _busy || resetEvidence == ""
    Return False
  EndIf
  _busy = True
  CLAWPhysicsActor helper = SlotAt(index)
  Bool accepted = False
  If helper != None
    accepted = helper.AcknowledgeProviderReset(previousActor, previousContainersDiscarded)
  EndIf
  If accepted
    _lastResetEvidence = resetEvidence
  EndIf
  _busy = False
  Return accepted
EndFunction

Function NotifySessionChanged()
  ; Call on load/new session/provider replacement BEFORE qualifying or pulsing.
  ; Deliberately allowed while busy: in-flight helper sees generation invalidation.
  ; Retains all accepted ledgers. No assumption that native containers survived.
  IntegrationOptIn = False
  _sessionGeneration += 1
  If !Initialize()
    Return
  EndIf
  Int slot = 0
  While slot < _slotCount
    Revoke(_slots[slot])
    slot += 1
  EndWhile
EndFunction
