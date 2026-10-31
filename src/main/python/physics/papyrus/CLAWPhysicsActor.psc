Scriptname CLAWPhysicsActor extends ReferenceAlias

; Source-only helper. CLAWPhysicsHost supplies ONE serialized alias per actor.
; Gates are acknowledgments from qualified preflight, not provider readback.
Bool Property ProviderQualified = False Auto
Bool Property ExclusiveIndexRange = False Auto
Bool Property StaticPoseAccepted = False Auto

Actor _tracked
Bool[] _accepted
Bool _female
Bool _busy = False
Bool _generationUnknown = False
Int _modelGeneration = 0
Int _qualifiedGeneration = -1
Actor _qualifiedActor
String _qualificationEvidence = ""
Int _status = 0
String _error = ""
Float[] _morphValues
Bool _morphValuesQualified = False
Bool _morphRefresh = False
String _morphEvidence = ""
String _acceptedModel = ""
Bool _nativeSnapshot = False
Bool _nativeOwner = False
Int _nativeToken = 0
Float _nativeWeight = -1.0

; 0 dormant, 1 capability blocked, 2 not beast, 3 unloaded,
; 4 requested native appends accepted (NO readback), 5 attach failed/rolled back,
; 6 cleanup pending/unknown, 7 matching removals reported,
; 8 busy (returned only), 9 provider reset acknowledged by host.
Int Function GetStatus()
  If _busy
    Return 8
  EndIf
  Return _status
EndFunction

String Function GetLastError()
  Return _error
EndFunction

Actor Function GetTrackedActor()
  Return _tracked
EndFunction

Actor Function GetQualifiedActor()
  Return _qualifiedActor
EndFunction

Bool Function HasNativeOwner()
  Return _nativeOwner
EndFunction

Int Function GetModelGeneration()
  Return _modelGeneration
EndFunction

String Function GetQualificationEvidence()
  Return _qualificationEvidence
EndFunction

Bool Function QualifyForActor(Actor expectedActor, Int expectedGeneration, String evidence, Bool provider, Bool exclusiveIndices, Bool staticPose)
  ; These are external assertions, never inferred from a CBPC bool/version.
  If _busy || expectedActor == None || evidence == "" || expectedActor != GetActorReference() || expectedGeneration != _modelGeneration
    Return False
  EndIf
  ProviderQualified = provider
  ExclusiveIndexRange = exclusiveIndices
  StaticPoseAccepted = staticPose
  _qualifiedActor = expectedActor
  _qualifiedGeneration = expectedGeneration
  _qualificationEvidence = evidence
  Return expectedGeneration == _modelGeneration
EndFunction

Bool Function AttachmentQualified(Actor target)
  Return ProviderQualified && ExclusiveIndexRange && StaticPoseAccepted && _qualifiedActor == target && _qualifiedGeneration == _modelGeneration
EndFunction

Bool Function CleanupContextCurrent(Actor target, Int generation)
  ; The optional native owner check reads cached runtime identity only.
  If _nativeOwner && !CLAWPhysicsNative.ActorCurrent(target)
    Return False
  EndIf
  Return target != None && _tracked == target && ProviderQualified && ExclusiveIndexRange && _modelGeneration == generation
EndFunction

Bool Function AttachmentContextCurrent(Actor target, Int generation, String node)
  ; The check and the following native mutation are NOT an atomic operation.
  If !IsCurrentBeast(target) || !target.Is3DLoaded() || !NetImmerse.HasNode(target, node, False) || GetActorReference() != target
    Return False
  EndIf
  If _nativeSnapshot && !CLAWPhysicsNative.SnapshotCurrent(target, generation, _nativeToken)
    Return False
  EndIf
  Return !_generationUnknown && _tracked == target && _modelGeneration == generation && AttachmentQualified(target)
EndFunction

String Function OwnershipNamespace()
  Return "CLAW.Physics"
EndFunction

Int Function GetAcceptedLedgerCount()
  ; Read-only: a status query must never replace an in-flight ledger array.
  If _accepted == None
    Return 0
  EndIf
  Int count = 0
  Int slot = 0
  ; Scan the remembered array, including an older nine-slot serialized ledger.
  While slot < _accepted.Length
    If _accepted[slot]
      count += 1
    EndIf
    slot += 1
  EndWhile
  Return count
EndFunction

String Function GetProviderVersion()
  If !ProviderQualified
    Return "provider-not-qualified"
  EndIf
  Return CBPCPluginScript.GetVersion()
EndFunction

Int Function Synchronize()
  If _busy
    Return 8
  EndIf
  _busy = True
  Int outcome = SynchronizeInternal()
  _busy = False
  Return outcome
EndFunction

; Values must be the effective aggregate of ALL SKEE keys for each generated
; MorphName, after its model update completes. Never pass only CLAW's own key.
; The coordinator calls this after a morph change; no world scan or timer runs.
Int Function SynchronizeMorphs(Actor expectedActor, Float[] values, String evidence, Bool nativeSnapshot = False, Int snapshotToken = 0)
  If _busy
    Return 8
  EndIf
  _busy = True
  Int snapshotGeneration = _modelGeneration
  Float snapshotWeight = -1.0
  If nativeSnapshot && !CLAWPhysicsNative.SnapshotCurrent(expectedActor, snapshotGeneration, snapshotToken)
    _busy = False
    Return SetStatus(1, "Native aggregate snapshot is stale; no append attempted")
  EndIf
  If nativeSnapshot
    snapshotWeight = CLAWPhysicsNative.GetWeight(expectedActor, snapshotGeneration, snapshotToken)
    If !(snapshotWeight >= 0.0 && snapshotWeight <= 1.0)
      _busy = False
      Return SetStatus(1, "Native independent weight input is stale or invalid")
    EndIf
  EndIf
  If CLAWPhysicsData.NativeFitRequired() && !nativeSnapshot
    _busy = False
    Return SetStatus(1, "Current-vector model requires the matching native fitted capsule snapshot")
  EndIf
  If expectedActor == None || expectedActor != GetActorReference() || evidence == ""
    _busy = False
    Return SetStatus(1, "Effective morph snapshot actor/evidence missing; no append attempted")
  EndIf
  If !CLAWPhysicsData.MorphValuesValid(values)
    ; Once a known requested shape leaves the fitted domain, do not knowingly
    ; keep its previous mismatching capsules. Scoped cleanup may remain pending.
    CleanupInternal()
    _morphValuesQualified = False
    _morphRefresh = True
    _busy = False
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Morph vector outside fitted domain; previous capsule cleanup remains unresolved")
    EndIf
    Return SetStatus(1, "Morph vector outside fitted domain; old own capsules removed and no append attempted")
  EndIf
  Int count = CLAWPhysicsData.MorphCount()
  ; A private copy prevents later caller array edits from changing an append.
  Float[] prepared = new Float[32]
  Int index = 0
  While index < count
    prepared[index] = values[index]
    index += 1
  EndWhile
  If !CLAWPhysicsData.MorphValuesValidCopy(prepared) || expectedActor != GetActorReference() || snapshotGeneration != _modelGeneration
    _morphValuesQualified = False
    _morphRefresh = True
    _busy = False
    Return SetStatus(1, "Morph snapshot changed or became invalid while copying; no append attempted")
  EndIf
  Bool changed = !_morphValuesQualified || (nativeSnapshot && snapshotWeight != _nativeWeight)
  index = 0
  While index < count
    If _morphValues == None || _morphValues[index] != prepared[index]
      changed = True
    EndIf
    index += 1
  EndWhile
  _morphValues = prepared
  _morphValuesQualified = True
  _morphRefresh = _morphRefresh || changed
  _morphEvidence = evidence
  _nativeSnapshot = nativeSnapshot
  _nativeOwner = _nativeOwner || nativeSnapshot
  _nativeToken = snapshotToken
  _nativeWeight = snapshotWeight
  Int outcome = SynchronizeInternal()
  _busy = False
  Return outcome
EndFunction

String Function GetMorphEvidence()
  Return _morphEvidence
EndFunction

Int Function Cleanup()
  If _busy
    Return 8
  EndIf
  _busy = True
  Int outcome = CleanupInternal()
  _busy = False
  Return outcome
EndFunction

Function MarkModelGenerationChanged()
  _modelGeneration += 1
  StaticPoseAccepted = False
  _morphValuesQualified = False
  _nativeSnapshot = False
  _nativeToken = 0
  _generationUnknown = True
  If GetAcceptedLedgerCount() > 0
    SetStatus(6, "Model/provider generation changed; previous container presence is unknown")
  EndIf
EndFunction

Bool Function AcknowledgeProviderReset(Actor previousActor, Bool previousContainersDiscarded)
  ; No public CBPC readback proves a reset. Only a qualified host may assert it.
  If _busy || !ProviderQualified || !ExclusiveIndexRange || !previousContainersDiscarded || previousActor == None || previousActor != _tracked
    Return False
  EndIf
  EnsureLedger()
  Int slot = 0
  While slot < _accepted.Length
    _accepted[slot] = False
    slot += 1
  EndWhile
  _tracked = None
  _acceptedModel = ""
  _nativeOwner = False
  _generationUnknown = False
  SetStatus(9, "Host acknowledged old CBPC containers discarded; not independently read back")
  Return True
EndFunction

Function EnsureLedger()
  If _accepted == None
    _accepted = new Bool[128]
  EndIf
EndFunction

Int Function SetStatus(Int value, String reason = "")
  _status = value
  _error = reason
  Return value
EndFunction

Bool Function IsCurrentBeast(Actor target)
  If target == None
    Return False
  EndIf
  Race beast = Game.GetFormFromFile(0x000CDD84, "Skyrim.esm") as Race
  Return beast != None && target.GetRace() == beast
EndFunction

Int Function CleanupInternal()
  EnsureLedger()
  If GetAcceptedLedgerCount() == 0
    _tracked = None
    _nativeOwner = False
    Return SetStatus(0)
  EndIf
  If _accepted.Length > 128
    Return SetStatus(6, "Unsupported saved ledger length; entries retained and no native cleanup attempted")
  EndIf
  If _acceptedModel != CLAWPhysicsData.ModelIdentity()
    Return SetStatus(6, "Capsule data changed while old slots remain; old node/index layout must not be guessed")
  EndIf
  If !ProviderQualified || !ExclusiveIndexRange
    Return SetStatus(6, "Cannot safely call scoped detach without provider/index ownership qualification")
  EndIf
  Actor cleanupActor = _tracked
  Int cleanupGeneration = _modelGeneration
  If cleanupActor == None || !cleanupActor.Is3DLoaded()
    Return SetStatus(6, "Tracked actor is unavailable/unloaded; cleanup has not been proven")
  EndIf
  Int slot = 0
  While slot < CLAWPhysicsData.SlotCount()
    If _accepted[slot]
      String node = CLAWPhysicsData.Node(slot)
      Int colliderIndex = CLAWPhysicsData.ColliderIndex(slot)
      If NetImmerse.HasNode(cleanupActor, node, False)
        If !CleanupContextCurrent(cleanupActor, cleanupGeneration)
          Return SetStatus(6, "Cleanup actor/authority/generation changed; remaining ledger retained")
        EndIf
        ; type=1 is capsule; True selects the affected-node bucket only.
        Bool removed = CBPCPluginScript.DetachCollider(cleanupActor, node, 1, colliderIndex, True)
        If !CleanupContextCurrent(cleanupActor, cleanupGeneration)
          Return SetStatus(6, "Cleanup context changed during native detach; result not used to erase ledger")
        EndIf
        If removed
          _accepted[slot] = False
        EndIf
      EndIf
    EndIf
    slot += 1
  EndWhile
  If GetAcceptedLedgerCount() > 0
    Return SetStatus(6, "Detach false/missing node conflates absent and unavailable; ledger retained")
  EndIf
  If !CleanupContextCurrent(cleanupActor, cleanupGeneration)
    Return SetStatus(6, "Cleanup context changed before completion; tracked actor retained")
  EndIf
  _tracked = None
  _generationUnknown = False
  _nativeOwner = False
  Return SetStatus(7, "Native reported matching-index removals; no collider enumeration exists")
EndFunction

Int Function SynchronizeInternal()
  EnsureLedger()
  Int synchronizationGeneration = _modelGeneration
  If GetAcceptedLedgerCount() > 0 && _acceptedModel != CLAWPhysicsData.ModelIdentity()
    Return SetStatus(6, "Capsule model identity changed with remembered slots; cleanup/reset must be resolved under its original layout")
  EndIf
  If GetAcceptedLedgerCount() > 0 && _tracked == None
    Return SetStatus(6, "Remembered capsules have an unresolved former actor; retargeted attachment refused")
  EndIf
  Actor target = GetActorReference()
  If _tracked != None && _tracked != target && GetAcceptedLedgerCount() > 0
    CleanupInternal()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Old alias actor cleanup pending; retargeted attachment refused")
    EndIf
  EndIf
  If !IsCurrentBeast(target)
    CleanupInternal()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Human return/alias release has unresolved previous own capsules")
    EndIf
    Return SetStatus(2)
  EndIf
  If !target.Is3DLoaded()
    Return SetStatus(3, "No loaded 3D; no attachment attempted")
  EndIf
  If !AttachmentQualified(target)
    Return SetStatus(1, "Provider, exclusive index range and static measurement pose need explicit qualification")
  EndIf
  If CLAWPhysicsData.MorphCount() > 0 && !_morphValuesQualified
    Return SetStatus(1, "This fitted model requires a current effective morph snapshot through SynchronizeMorphs")
  EndIf
  If _generationUnknown && GetAcceptedLedgerCount() > 0
    Return SetStatus(6, "Rebuilt/reloaded provider generation needs cleanup or qualified reset acknowledgment")
  EndIf
  ActorBase base = target.GetLeveledActorBase()
  If base == None
    Return SetStatus(1, "No readable NPC sex")
  EndIf
  Int sex = base.GetSex()
  If sex != 0 && sex != 1
    Return SetStatus(1, "Unsupported NPC sex")
  EndIf
  Bool female = sex == 1
  If GetAcceptedLedgerCount() > 0 && female != _female
    CleanupInternal()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Previous sex capsule cleanup pending")
    EndIf
  EndIf
  If GetAcceptedLedgerCount() == CLAWPhysicsData.ExpectedCapsuleCountForSex(female) && !_morphRefresh
    If GetActorReference() != target || _modelGeneration != synchronizationGeneration || !AttachmentQualified(target) || _generationUnknown
      Return SetStatus(6, "Accepted ledger context changed during synchronization; no append attempted")
    EndIf
    Return SetStatus(4)
  EndIf
  If GetAcceptedLedgerCount() > 0
    CleanupInternal()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Partial previous capsule ledger cannot be replaced safely")
    EndIf
  EndIf
  ; An older serialized nine-slot array stays untouched until every old bit is
  ; resolved. Only an empty ledger may be replaced with the larger capacity.
  If _accepted.Length < CLAWPhysicsData.SlotCount()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Old short ledger still has unresolved slots; capacity migration refused")
    EndIf
    _accepted = new Bool[128]
  EndIf
  _tracked = target
  _nativeOwner = _nativeSnapshot
  _acceptedModel = CLAWPhysicsData.ModelIdentity()
  _female = female
  _generationUnknown = False
  Int slot = 0
  Bool failed = False
  While slot < CLAWPhysicsData.SlotCount() && !failed
    If CLAWPhysicsData.HasCapsule(slot) && CLAWPhysicsData.SlotEnabled(slot, female)
      String node = CLAWPhysicsData.Node(slot)
      Int colliderIndex = CLAWPhysicsData.ColliderIndex(slot)
      If !AttachmentContextCurrent(target, synchronizationGeneration, node)
        failed = True
      Else
        ; Append is not replacement. Exclusivity lets us remove stale own duplicates.
        ; A false detach is NOT treated as proof that an old generation is clean.
        CBPCPluginScript.DetachCollider(target, node, 1, colliderIndex, True)
        Float[] point1 = CLAWPhysicsData.Point(slot, female, False)
        Float[] point2 = CLAWPhysicsData.Point(slot, female, True)
        Float radius = CLAWPhysicsData.Radius(slot, female)
        If CLAWPhysicsData.MorphCount() > 0 && !CLAWPhysicsData.NativeFitRequired()
          point1 = CLAWPhysicsData.PointForMorphs(slot, female, False, _morphValues)
          point2 = CLAWPhysicsData.PointForMorphs(slot, female, True, _morphValues)
          radius = CLAWPhysicsData.RadiusForMorphs(slot, female, _morphValues)
        EndIf
        If CLAWPhysicsData.NativeFitRequired()
          Float[] capsule = CLAWPhysicsNative.GetCapsule(target, synchronizationGeneration, _nativeToken, slot)
          If capsule == None || capsule.Length != 7
            failed = True
          Else
            point1[0] = capsule[0]
            point1[1] = capsule[1]
            point1[2] = capsule[2]
            point2[0] = capsule[3]
            point2[1] = capsule[4]
            point2[2] = capsule[5]
            radius = capsule[6]
          EndIf
        EndIf
        ; Data access/preclean may yield. Recheck AFTER them, immediately before append.
        If failed || !AttachmentContextCurrent(target, synchronizationGeneration, node)
          failed = True
        Else
          Bool accepted = CBPCPluginScript.AttachColliderCapsule(target, node, point1, radius, point2, radius, 0.0, colliderIndex, True)
          ; Record an accepted append even if a concurrent event invalidated it.
          ; The failure path must roll it back or retain it as unresolved cleanup.
          _accepted[slot] = accepted
          If !accepted
            failed = True
          EndIf
        EndIf
      EndIf
    EndIf
    slot += 1
  EndWhile
  If !IsCurrentBeast(target) || !target.Is3DLoaded() || GetActorReference() != target || _generationUnknown || _modelGeneration != synchronizationGeneration || !AttachmentQualified(target)
    failed = True
  EndIf
  If failed
    CleanupInternal()
    If GetAcceptedLedgerCount() > 0
      Return SetStatus(6, "Attach failed and rollback remains unproven; do not retry until resolved")
    EndIf
    Return SetStatus(5, "Attach rejected or lifecycle changed; accepted subset was removed")
  EndIf
  _morphRefresh = False
  Return SetStatus(4, "All requested native appends accepted; TailBone04 motion only; simulation/contact readback unavailable")
EndFunction

Event OnUnload()
  MarkModelGenerationChanged()
EndEvent

Event OnLoad()
  MarkModelGenerationChanged()
EndEvent

Event OnRaceSwitchComplete()
  MarkModelGenerationChanged()
EndEvent
