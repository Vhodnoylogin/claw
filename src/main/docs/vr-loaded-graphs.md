# Loaded VR player graph lifecycle

The development DLL observes the already loaded first- and third-person graphs
of the VR player on its existing main-thread actor pass. A changed first-person
graph invalidates the ordinary morph application even when the third-person
graph and effective coefficient values have stayed unchanged. The existing
SKEE application path is reused; there is no second morph cache or extra weight
multiplier. SE, AE and NPC processing do not enter this VR policy.

`VRBodyState` is a pure policy over actual graph, race, sex, runtime owner and
world identities. The engine adapter retains distinct graph references to
prevent recycled addresses from impersonating the previous observation. An
unload, human return or quarantined actor releases these retained graphs.
Before a beast morph write, the adapter checks a fresh graph observation against
the captured generation. A changed observation leaves the actor pending for its
next ordinary pass.

A missing first-person graph does not create one or block the existing
third-person body. A shared first/third root is retained once. Stable missing
graphs do not trigger a repeated reapply loop. The policy tests cover delayed
arrival, first-only replacement, shared roots, unload/reload, stale generations
and race/sex/world/owner changes.

This is only the lifecycle mechanism for loaded graphs. It does not choose the
engine's first-person armor/model route, make human hands into a werewolf body,
hide a head, modify VRIK/skeleton/animations, or add first-person coat leases or
hand contact. Those features still need actual model-dispatch evidence and VR
game checks. An offline test or universal compile is not VR engine acceptance.
