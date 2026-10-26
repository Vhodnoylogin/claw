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

; 0 dormant, 1 capability blocked, 2 not beast, 3 unloaded,
; 4 eight native appends accepted (NO readback), 5 attach failed/rolled back,
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
  ; No native queries here: recheck the captured ledger/authority after data reads.
  Return target != None && _tracked == target && ProviderQualified && ExclusiveIndexRange && _modelGeneration == generation
EndFunction

Bool Function AttachmentContextCurrent(Actor target, Int generation, String node)
  ; The check and the following native mutation are NOT an atomic operation.
  If !IsCurrentBeast(target) || !target.Is3DLoaded() || !NetImmerse.HasNode(target, node, False) || GetActorReference() != target
    Return False
  EndIf
  Return !_generationUnknown && _tracked == target && _modelGeneration == generation && AttachmentQualified(target)
EndFunction

String Function OwnershipNamespace()
  Return "CLAW.Physics"
EndFunction

Int Function GetAcceptedLedgerCount()
  EnsureLedger()
  Int count = 0
  Int slot = 0
  While slot < 9
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
  EnsureLedger()
  _modelGeneration += 1
  StaticPoseAccepted = False
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
  While slot < 9
    _accepted[slot] = False
    slot += 1
  EndWhile
  _tracked = None
  _generationUnknown = False
  SetStatus(9, "Host acknowledged old CBPC containers discarded; not independently read back")
  Return True
EndFunction

Function EnsureLedger()
  If _accepted == None
    _accepted = new Bool[9]
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
    Return SetStatus(0)
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
  While slot < 9
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
  Return SetStatus(7, "Native reported matching-index removals; no collider enumeration exists")
EndFunction

Int Function SynchronizeInternal()
  EnsureLedger()
  Int synchronizationGeneration = _modelGeneration
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
  If GetAcceptedLedgerCount() == 8
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
  _tracked = target
  _female = female
  _generationUnknown = False
  Int slot = 0
  Bool failed = False
  While slot < 9 && !failed
    If CLAWPhysicsData.HasCapsule(slot)
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
        ; Data access/preclean may yield. Recheck AFTER them, immediately before append.
        If !AttachmentContextCurrent(target, synchronizationGeneration, node)
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
  Return SetStatus(4, "Eight native appends accepted; TailBone04 motion only; simulation/contact readback unavailable")
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
