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
Bool[] _automatic
String[] _automaticEvidence
Bool[] _automaticProvider
Bool[] _automaticIndices
Bool[] _automaticFit
String[] _automaticLifecycle
Bool[] _populationSlots
Bool _populationEnabled = False
String _populationEvidence = ""
String _populationModel = ""

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
    EnsureAutomaticArrays()
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
  EnsureAutomaticArrays()
  Return True
EndFunction

Function EnsureAutomaticArrays()
  If _automatic != None && _automatic.Length == 16 && _automaticEvidence != None && _automaticEvidence.Length == 16 && _automaticLifecycle != None && _automaticLifecycle.Length == 16 && _automaticProvider != None && _automaticProvider.Length == 16 && _automaticIndices != None && _automaticIndices.Length == 16 && _automaticFit != None && _automaticFit.Length == 16 && _populationSlots != None && _populationSlots.Length == 16
    Return
  EndIf
  ; Older saves keep their aliases/cleanup ledgers; new automatic policy starts off.
  _automatic = new Bool[16]
  _automaticEvidence = new String[16]
  _automaticProvider = new Bool[16]
  _automaticIndices = new Bool[16]
  _automaticFit = new Bool[16]
  _automaticLifecycle = new String[16]
  _populationSlots = new Bool[16]
EndFunction

Int Function EnableAutomaticPopulation(String evidence, Bool provider, Bool exclusiveIndices, Bool fittedDomain)
  If _busy
    Return -8
  EndIf
  If !IntegrationEnabled() || !Initialize()
    Return Fail(-6, "Current-session integration opt-in is required")
  EndIf
  If evidence == "" || !provider || !exclusiveIndices || !fittedDomain
    Return Fail(-5, "Qualify the actual provider, index range and all matching population body resources")
  EndIf
  If CLAWPhysicsData.NativeFitRequired() && CLAWPhysicsNative.GetModelIdentity() != CLAWPhysicsData.ModelIdentity()
    Return Fail(-5, "Population host and native model identities differ")
  EndIf
  _populationEvidence = evidence
  _populationModel = CLAWPhysicsData.ModelIdentity()
  RegisterForModEvent("CLAWPhysics_Candidate", "OnPhysicsCandidate")
  _populationEnabled = CLAWPhysicsNative.SetPopulationEnabled(True)
  If !_populationEnabled
    Return Fail(-5, "Native population registry is unavailable")
  EndIf
  Return 0
EndFunction

Function DisableAutomaticPopulation()
  _populationEnabled = False
  CLAWPhysicsNative.SetPopulationEnabled(False)
  If !Initialize()
    Return
  EndIf
  Int index = 0
  While index < _slotCount
    If _populationSlots[index]
      ; Cleanup may retain its exact former actor. Never evict a pending ledger.
      Release(index)
    EndIf
    index += 1
  EndWhile
EndFunction

Function OnPhysicsCandidate(String eventName, String kind, Float unused, Form sender)
  If _busy || !_populationEnabled || !IntegrationEnabled() || !Initialize()
    Return
  EndIf
  If _populationModel != CLAWPhysicsData.ModelIdentity()
    _populationEnabled = False
    CLAWPhysicsNative.SetPopulationEnabled(False)
    Fail(-5, "Population capsule model changed; fresh explicit qualification required")
    Return
  EndIf
  Actor target = sender as Actor
  If target == None || ActorInOtherSlot(-1, target)
    Return
  EndIf
  Int index = 0
  While index < _slotCount
    CLAWPhysicsActor helper = _slots[index]
    If helper.GetActorReference() == None && helper.GetTrackedActor() == None && helper.GetAcceptedLedgerCount() == 0
      _busy = True
      Int assigned = AssignInternal(index, target)
      If assigned == 0
        Int activated = EnableAutomaticInternal(index, target, _populationEvidence, True, True, True)
        If activated == 0
          _populationSlots[index] = True
        Else
          ReleaseInternal(index)
        EndIf
      EndIf
      _busy = False
      Return
    EndIf
    index += 1
  EndWhile
  ; No free alias: retain every current actor/cleanup ledger and wait.
EndFunction

; The caller explicitly qualifies this actor/session and the matching fitted
; model. This is a real opt-in path; every bool and evidence is then bound to
; this alias's actor. It never chooses an actor or guesses provider ownership.
Int Function EnableAutomatic(Int index, Actor target, String evidence, Bool provider, Bool exclusiveIndices, Bool fittedDomain)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = EnableAutomaticInternal(index, target, evidence, provider, exclusiveIndices, fittedDomain)
  _busy = False
  Return outcome
EndFunction

Int Function EnableAutomaticInternal(Int index, Actor target, String evidence, Bool provider, Bool exclusiveIndices, Bool fittedDomain)
  If !IntegrationEnabled()
    Return Fail(-6, "Current-session integration opt-in is required")
  EndIf
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None || target == None || helper.GetActorReference() != target || ActorInOtherSlot(index, target) || evidence == ""
    Return Fail(-1, "Automatic observer requires the exact uniquely assigned actor and evidence")
  EndIf
  If !provider || !exclusiveIndices || !fittedDomain
    Return Fail(-5, "Explicit provider, exclusive index ownership and fitted domain qualification are required")
  EndIf
  If CLAWPhysicsData.NativeFitRequired() && CLAWPhysicsNative.GetModelIdentity() != CLAWPhysicsData.ModelIdentity()
    Return Fail(-5, "Distribution DLL and Papyrus capsule model identities differ")
  EndIf
  If !helper.QualifyForActor(target, helper.GetModelGeneration(), evidence, provider, exclusiveIndices, fittedDomain)
    Return Fail(-5, "Actor qualification changed while enabling its observer")
  EndIf
  _automatic[index] = True
  _automaticEvidence[index] = evidence
  _automaticProvider[index] = provider
  _automaticIndices[index] = exclusiveIndices
  _automaticFit[index] = fittedDomain
  _automaticLifecycle[index] = ""
  RegisterForModEvent("CLAWPhysics_Observation", "OnPhysicsObservation")
  If !RegisterAutomatic(index, target)
    _automatic[index] = False
    Return Fail(-5, "Native observer registration was refused")
  EndIf
  Return 0
EndFunction

Bool Function RegisterAutomatic(Int index, Actor target)
  String[] names = new String[32]
  Int count = CLAWPhysicsData.MorphCount()
  If count < 1 || count > 32
    Return False
  EndIf
  ; Exact-length array: generated model names remain the single source of order.
  names = Utility.CreateStringArray(count)
  Int morph = 0
  While morph < count
    names[morph] = CLAWPhysicsData.MorphName(morph)
    morph += 1
  EndWhile
  Return CLAWPhysicsNative.RegisterActor(target, _slots[index].GetModelGeneration(), names, CLAWPhysicsData.ModelIdentity(), _automaticEvidence[index])
EndFunction

Bool Function DisableAutomatic(Int index)
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None
    Return False
  EndIf
  Bool nativeOwner = _automatic[index] || helper.HasNativeOwner()
  _automatic[index] = False
  Actor target = helper.GetActorReference()
  If nativeOwner && helper.GetQualifiedActor() != None
    target = helper.GetQualifiedActor()
  EndIf
  If nativeOwner && target != None
    CLAWPhysicsNative.UnregisterActor(target, helper.GetAcceptedLedgerCount() > 0)
  EndIf
  Return nativeOwner
EndFunction

; SKSE dispatches the registered callback by function name. PEX has the same
; callable representation for a void function and an event handler.
Function OnPhysicsObservation(String eventName, String kind, Float tokenValue, Form sender)
  ; Native repeats unacknowledged observations at its bounded two-second scan.
  If _busy || !IntegrationEnabled() || !Initialize()
    Return
  EndIf
  Actor target = sender as Actor
  If target == None
    Return
  EndIf
  Int index = 0
  While index < _slotCount
    If _automatic[index] && _slots[index].GetActorReference() == target
      _busy = True
      ProcessAutomatic(index, target, kind, tokenValue as Int)
      _busy = False
      Return
    EndIf
    index += 1
  EndWhile
EndFunction

Function ProcessAutomatic(Int index, Actor target, String kind, Int token)
  CLAWPhysicsActor helper = _slots[index]
  If ActorInOtherSlot(index, target)
    DisableAutomatic(index)
    Fail(-2, "Duplicate alias ownership disabled automatic observer")
    Return
  EndIf
  Int generation = helper.GetModelGeneration()
  If kind == "snapshot"
    If !CLAWPhysicsNative.SnapshotCurrent(target, generation, token)
      ; A Papyrus lifecycle event may precede the native receipt. Renew only
      ; after actual scoped cleanup; no provider-reset inference is made.
      If helper.Cleanup() != 8 && helper.GetAcceptedLedgerCount() == 0
        If helper.QualifyForActor(target, generation, _automaticEvidence[index], _automaticProvider[index], _automaticIndices[index], _automaticFit[index])
          RegisterAutomatic(index, target)
        EndIf
      EndIf
      Return
    EndIf
    Float[] values = CLAWPhysicsNative.GetValues(target, generation, token)
    Int outcome = helper.SynchronizeMorphs(target, values, _automaticEvidence[index], True, token)
    If outcome == 4
      CLAWPhysicsNative.AcknowledgeSnapshot(target, generation, token)
    ElseIf outcome == 6
      ; Keep the native observation unacknowledged while old capsules need
      ; reported removal. The next bounded pass can retry after cleanup.
      helper.Cleanup()
    EndIf
  ElseIf kind == "refit"
    ; A delayed old refit receipt cannot remove newly accepted current capsules.
    If CLAWPhysicsNative.RefitPending(target, generation, token)
      helper.Cleanup()
    EndIf
  ElseIf kind == "ready"
    If helper.Cleanup() == 8 || helper.GetAcceptedLedgerCount() > 0
      Return
    EndIf
    If helper.QualifyForActor(target, generation, _automaticEvidence[index], _automaticProvider[index], _automaticIndices[index], _automaticFit[index])
      _automaticLifecycle[index] = ""
      RegisterAutomatic(index, target)
    EndIf
  ElseIf kind == "human" || kind == "unloaded" || kind == "model"
    ; Preserve provider/index cleanup authority; model/fit acceptance expires.
    If _automaticLifecycle[index] != kind
      helper.MarkModelGenerationChanged()
      _automaticLifecycle[index] = kind
    EndIf
    Int cleanup = helper.Cleanup()
    If cleanup != 8 && helper.GetAcceptedLedgerCount() == 0
      CLAWPhysicsNative.AcknowledgeLifecycle(target, kind)
      If kind == "model"
        ; A changed model is never automatically qualified by the old policy.
        DisableAutomatic(index)
      EndIf
      If _populationSlots[index]
        ReleaseInternal(index)
      EndIf
    EndIf
  Else
    If kind == "identity" || kind == "provider"
      helper.ProviderQualified = False
      helper.ExclusiveIndexRange = False
    EndIf
    helper.MarkModelGenerationChanged()
    helper.Cleanup()
    DisableAutomatic(index)
    If _populationSlots[index] && helper.GetAcceptedLedgerCount() == 0
      ReleaseInternal(index)
    EndIf
    Fail(-5, "Native observer refused the current identity/provider/fitted domain")
  EndIf
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
  Bool wasNative = DisableAutomatic(index)
  Int cleanup = helper.Cleanup()
  If cleanup == 8 || helper.GetAcceptedLedgerCount() > 0
    Return Fail(-3, "Previous actor cleanup pending; alias has not been cleared or retargeted")
  EndIf
  If wasNative
    CLAWPhysicsNative.UnregisterActor(helper.GetQualifiedActor())
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
  Bool wasNative = DisableAutomatic(index)
  Int cleanup = helper.Cleanup()
  If cleanup == 8 || helper.GetAcceptedLedgerCount() > 0
    Return Fail(-3, "Cleanup pending; alias and ledger retained")
  EndIf
  If wasNative
    CLAWPhysicsNative.UnregisterActor(helper.GetQualifiedActor())
  EndIf
  Revoke(helper)
  helper.Clear()
  If helper.GetReference() != None
    Return Fail(-4, "Alias Clear failed; configure it Optional before integration")
  EndIf
  _populationSlots[index] = False
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

Int Function PulseMorphs(Int index, Actor expectedActor, Float[] effectiveMorphs, String evidence)
  If _busy
    Return -8
  EndIf
  _busy = True
  Int outcome = PulseMorphsInternal(index, expectedActor, effectiveMorphs, evidence)
  _busy = False
  Return outcome
EndFunction

Int Function PulseMorphsInternal(Int index, Actor expectedActor, Float[] effectiveMorphs, String evidence)
  If !IntegrationEnabled()
    Return Fail(-6, "Explicit current-session integration opt-in is required")
  EndIf
  CLAWPhysicsActor helper = SlotAt(index)
  If helper == None || expectedActor == None || helper.GetActorReference() != expectedActor
    Return Fail(-1, "Morph pulse actor no longer matches the alias")
  EndIf
  If ActorInOtherSlot(index, expectedActor)
    Return Fail(-2, "Duplicate actor ownership; morph pulse refused")
  EndIf
  Return helper.SynchronizeMorphs(expectedActor, effectiveMorphs, evidence)
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
  If _populationEnabled
    CLAWPhysicsNative.SetPopulationEnabled(False)
  EndIf
  _populationEnabled = False
  _sessionGeneration += 1
  If !Initialize()
    Return
  EndIf
  Int slot = 0
  While slot < _slotCount
    DisableAutomatic(slot)
    Revoke(_slots[slot])
    slot += 1
  EndWhile
EndFunction
