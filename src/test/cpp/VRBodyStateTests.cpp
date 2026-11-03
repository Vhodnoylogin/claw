#include "claw/VRBodyState.h"
#undef NDEBUG
#include <cassert>
#include <iostream>

namespace {
claw::VRBodyInput beast() {
    return {true, true, true, 0, 7, 1, 100, 200, 0};
}

void missingAndDelayedFirstGraph() {
    claw::VRBodyState state;
    auto input = beast();
    const auto initial = state.observe(input);
    assert(initial.changed && initial.reapply && !initial.firstLoaded && !initial.distinctFirst);
    assert(state.roots().count == 1 && state.roots().identities[0] == input.thirdRoot);
    const auto old = *state.lease();
    assert(state.current(old, input));
    assert(!state.observe(input).reapply); // No repeated missing-body request.

    input.firstRoot = 300;
    assert(!state.current(old, input)); // Fresh engine read expires cached work.
    const auto arrived = state.observe(input);
    assert(arrived.changed && arrived.reapply && arrived.firstLoaded && arrived.distinctFirst);
    assert(state.roots().count == 2);
    assert(!state.current(old, input));
    assert(!state.observe(input).reapply);
}

void sharedAndReplacedRoots() {
    claw::VRBodyState state;
    auto input = beast();
    input.firstRoot = input.thirdRoot;
    auto transition = state.observe(input);
    assert(transition.reapply && transition.firstLoaded && !transition.distinctFirst);
    assert(state.roots().count == 1);
    const auto shared = *state.lease();
    input.firstRoot = 301;
    transition = state.observe(input);
    assert(transition.reapply && transition.distinctFirst && state.roots().count == 2);
    assert(!state.current(shared, input));
    const auto distinct = *state.lease();
    input.firstRoot = 302; // Third-person root and actor remain unchanged.
    assert(state.observe(input).reapply);
    assert(!state.current(distinct, input));
}

void unloadReloadAndStaleLease() {
    claw::VRBodyState state;
    auto input = beast();
    input.firstRoot = 300;
    state.observe(input);
    const auto original = *state.lease();
    input.firstRoot = 0;
    const auto lostFirst = state.observe(input);
    assert(lostFirst.changed && lostFirst.reapply && !lostFirst.firstLoaded);
    assert(state.roots().count == 1 && !state.current(original, input));
    input.thirdRoot = 0;
    assert(state.observe(input).changed);
    assert(state.roots().count == 0 && !state.lease());
    input.thirdRoot = 200;
    input.firstRoot = 300; // Reused identities still belong to a later generation.
    assert(state.observe(input).reapply);
    assert(!state.current(original, input));
    const auto beforeLoad = *state.lease();
    ++input.lifecycle;
    assert(state.observe(input).reapply);
    assert(!state.current(beforeLoad, input));
}

void ownershipRaceAndSexTransitions() {
    claw::VRBodyState state;
    auto input = beast();
    state.observe(input);
    const auto male = *state.lease();
    input.sex = 1;
    assert(state.observe(input).reapply && !state.current(male, input));
    const auto female = *state.lease();
    ++input.race;
    assert(state.observe(input).reapply && !state.current(female, input));
    const auto sameBeast = *state.lease();
    input.beast = false;
    assert(state.observe(input).changed && !state.lease());
    assert(state.roots().count == 0 && !state.current(sameBeast, input));
    ++input.race; // Human-to-human race changes also invalidate the observed stamp.
    assert(state.observe(input).changed);
    input.beast = true;
    assert(state.observe(input).reapply);
    const auto previousOwner = *state.lease();
    ++input.owner;
    assert(state.observe(input).reapply && !state.current(previousOwner, input));
    input.sex = -1;
    const auto invalidSex = state.observe(input);
    assert(invalidSex.changed && !invalidSex.reapply && !state.lease());
}

void inactiveAndIncompleteContexts() {
    claw::VRBodyState state;
    auto input = beast();
    input.vrPlayer = false;
    assert(!state.observe(input).changed && !state.lease());
    ++input.firstRoot;
    assert(!state.observe(input).changed); // NPC and non-VR graphs are ignored.
    input.vrPlayer = true;
    input.enabled = false;
    assert(!state.observe(input).reapply);
    input.enabled = true;
    input.owner = 0;
    assert(!state.observe(input).reapply && !state.lease());
    input.owner = 7;
    input.lifecycle = 0;
    assert(!state.observe(input).reapply && !state.lease());
    input.lifecycle = 1;
    input.race = 0;
    assert(!state.observe(input).reapply && !state.lease());
    input.race = 100;
    input.thirdRoot = 0;
    input.firstRoot = 300;
    assert(!state.observe(input).reapply && !state.lease()); // No third graph to update.
}
void replacedPartsUnderStableRoots() {
    // Every current/buffered slot in both views is relevant to SKEE traversal.
    for (std::size_t slot = 0; slot < claw::vrBipedPartCount; ++slot) {
        claw::VRBodyState state;
        auto input = beast();
        input.firstRoot = 300;
        state.observe(input);
        const auto beforeArrival = *state.lease();
        input.partClones[slot] = 1000 + slot;
        assert(!state.current(beforeArrival, input));
        const auto arrival = state.observe(input);
        assert(arrival.changed && arrival.reapply);
        assert(state.parts()[slot] == input.partClones[slot]);
        assert(state.roots().count == 2); // Skeleton roots never changed.
        assert(!state.observe(input).changed && !state.observe(input).reapply);
        const auto beforeReplacement = *state.lease();
        input.partClones[slot] += 1000;
        assert(!state.current(beforeReplacement, input));
        assert(state.observe(input).reapply);
        const auto beforeRemoval = *state.lease();
        input.partClones[slot] = 0;
        assert(!state.current(beforeRemoval, input));
        assert(state.observe(input).reapply && state.parts()[slot] == 0);
    }
}

void orderedPartsAndRelease() {
    claw::VRBodyState state;
    auto input = beast();
    input.firstRoot = 300;
    for (std::size_t slot = 0; slot < input.partClones.size(); ++slot)
        input.partClones[slot] = 1000 + slot;
    state.observe(input);
    const auto old = *state.lease();
    // Current-to-buffered movement with the same object set changes context.
    const auto first = input.partClones[0];
    input.partClones[0] = input.partClones[claw::vrBipedSlotCount];
    input.partClones[claw::vrBipedSlotCount] = first;
    assert(!state.current(old, input) && state.observe(input).reapply);
    input.beast = false;
    assert(state.observe(input).changed && !state.lease());
    for (const auto part : state.parts()) assert(part == 0);
    input.beast = true;
    state.observe(input);
    input.enabled = false;
    state.observe(input);
    for (const auto part : state.parts()) assert(part == 0);
    input = beast();
    input.vrPlayer = false;
    state.observe(input);
    input.partClones.back() = 99;
    assert(!state.observe(input).changed && !state.lease());
}

}

int main() {
    missingAndDelayedFirstGraph();
    sharedAndReplacedRoots();
    unloadReloadAndStaleLease();
    ownershipRaceAndSexTransitions();
    inactiveAndIncompleteContexts();
    replacedPartsUnderStableRoots();
    orderedPartsAndRelease();
    std::cout << "VR loaded-graph lifecycle contracts passed\n";
}
