# Loaded VR player graph lifecycle

The development DLL observes the already loaded first- and third-person graphs
of the VR player on its existing main-thread actor pass. A changed first-person
graph invalidates the ordinary morph application even when the third-person
graph and effective coefficient values have stayed unchanged. It also observes
the two 42-slot current/buffered biped tables in each view, matching the inspected
SKEE traversal. Arrival, removal, replacement or slot movement of a model clone
invalidates application even when both skeleton roots stay the same. The existing
SKEE application path is reused; there is no second morph cache or extra weight
multiplier. SE, AE and NPC processing do not enter this VR policy.

`VRBodyState` is a pure policy over actual graph, race, sex, runtime owner and
world identities and ordered biped clone identities. The engine adapter retains
graph and clone references to prevent recycled addresses from impersonating the
previous observation. Only the VR player allocates these fixed-size tables;
NPC/SE state does not carry them. An unload, human return or quarantined actor
releases these retained objects on an SKSE main task. One process-lifetime
retention slot owns the actual references; serialized actor states hold only a
pure policy. Load/revert/quarantine invalidates ownership and queues collection,
so VM callbacks and static teardown never release the last scene reference.
Before a beast morph write, the adapter checks a fresh graph observation against
the captured generation. A changed observation leaves the actor pending for its
next ordinary pass.

A missing first-person graph does not create one or block the existing
third-person body. A shared first/third root is retained once. Stable missing
graphs do not trigger a repeated reapply loop. The policy tests cover delayed
arrival, first-only replacement, shared roots, unload/reload, stale generations
and race/sex/world/owner changes, plus all 168 clone slots and current/buffered
slot movement. This identity policy detects object replacement, not arbitrary
in-place edits within an unchanged clone.

This is only the lifecycle mechanism for loaded graphs. It does not choose the
engine's first-person armor/model route, make human hands into a werewolf body,
hide a head, modify VRIK/skeleton/animations, or add first-person coat leases or
hand contact. Those features still need actual model-dispatch evidence and VR
game checks. An offline test or universal compile is not VR engine acceptance.
