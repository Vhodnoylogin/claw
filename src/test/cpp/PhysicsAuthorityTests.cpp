#include "claw/PhysicsAuthority.h"
#include "claw/PhysicsObserver.h"
#undef NDEBUG
#include <cassert>
#include <iostream>
#include <limits>
#include <type_traits>
#include <utility>

using namespace claw;
namespace {
constexpr PhysicsOwner owner{10, 20};
constexpr PhysicsBodyStamp beastA = [] {
    PhysicsBodyStamp stamp{30, 100, 0, true, true};
    for (std::size_t slot = 0; slot < stamp.partClones.size(); ++slot) stamp.partClones[slot] = 1000 + slot;
    return stamp;
}();
constexpr PhysicsBodyStamp beastB = [] { auto stamp = beastA; stamp.root = 200; return stamp; }();
PhysicsAuthority granted(PhysicsBodyStamp stamp = beastA) {
    PhysicsAuthority a{owner};
    auto ticket = a.admit(PhysicsAdmission::qualified, owner, 1);
    assert(ticket);
    a.observe(stamp); // First actual context is captured on the main task.
    assert(a.commit(*ticket, owner, 1));
    return a;
}
void rejectionSurvivesDroppedReceiptsAndLifecycle() {
    for (auto reason : {PhysicsRejection::domain, PhysicsRejection::weight, PhysicsRejection::model,
             PhysicsRejection::tokenLimit, PhysicsRejection::identity, PhysicsRejection::provider}) {
        auto a = granted();
        const auto old = a.revision();
        a.reject(reason); // No Host receipt/acknowledgment is needed for revocation.
        assert(!a.publishable(owner, old));
        assert(!a.admit(PhysicsAdmission::renewal, owner, 2));
        assert(!a.admit(PhysicsAdmission::initialPopulation, owner, 2));
        a.observe({31, 0, 0, false, false}); // Human + unloaded cannot overwrite a terminal reason.
        a.observe(beastB);
        assert(a.rejected() && !a.renewable(owner));
        const bool safeCleanup = reason != PhysicsRejection::identity && reason != PhysicsRejection::provider;
        assert(a.cleanupAllowed(owner) == safeCleanup);
        a.suspend(); a.forgetStamp(); // Alias release retains a cheap tombstone, not a graph.
        assert(a.rejected() && !a.stamp());
        assert(!a.admit(PhysicsAdmission::renewal, owner, 3));
        assert(!a.admit(PhysicsAdmission::initialPopulation, owner, 3));
        assert(a.cleanupAllowed(owner) == safeCleanup);
    }
}
void cleanupRevocationIsIndependentOfFirstTerminalReason() {
    for (auto unsafe : {PhysicsRejection::identity, PhysicsRejection::provider}) {
        auto a = granted(); a.reject(PhysicsRejection::domain);
        assert(a.cleanupAllowed(owner));
        a.reject(unsafe);
        a.observe({31, 0, 0, false, false}); a.observe(beastB);
        assert(!a.cleanupAllowed(owner));
        assert(a.condition() == (unsafe == PhysicsRejection::identity ? "identity" : "provider"));
        assert(!a.cleanupAllowed({11, 20}) && !a.cleanupAllowed({10, 21}));
    }
}
void pendingAndStaleAdmissionsCannotRestoreAuthority() {
    auto a = granted(); const auto published = a.revision();
    auto fresh = a.admit(PhysicsAdmission::qualified, owner, 2);
    assert(fresh && !a.publishable(owner, published) && a.cleanupAllowed(owner));
    assert(!a.admit(PhysicsAdmission::renewal, owner, 3));
    a.reject(PhysicsRejection::domain);
    assert(!a.commit(*fresh, owner, 2)); // Rejection after admission wins even with latest request/world unchanged.
    auto explicitAfterRejection = a.admit(PhysicsAdmission::qualified, owner, 4);
    assert(explicitAfterRejection && a.commit(*explicitAfterRejection, owner, 4));
    assert(a.renewable(owner)); // This is caller assertion, not a provider test.
    auto renewal = a.admit(PhysicsAdmission::renewal, owner, 5);
    assert(renewal && !a.commit(*renewal, {11, 20}, 5) && !a.commit(*renewal, owner, 6));
    a.suspend();
    assert(!a.commit(*renewal, owner, 5)); // Unregister cancels queued work.
    auto older = a.admit(PhysicsAdmission::qualified, owner, 6);
    auto newer = a.admit(PhysicsAdmission::qualified, owner, 7);
    assert(older && newer && !a.commit(*older, owner, 6));
    a.cancel(*older); // An old failure cannot cancel a later admitted task.
    assert(a.commit(*newer, owner, 7));
}
void observedContextChangesInvalidateTicketsAndOldSnapshots() {
    auto a = granted(); const auto previous = a.revision();
    auto renewal = a.admit(PhysicsAdmission::renewal, owner, 2);
    a.observe(beastB); a.observe(beastA);
    assert(renewal && !a.commit(*renewal, owner, 2));
    assert(a.condition() == "model" && !a.publishable(owner, previous));
    auto sex = granted(); sex.observe({30, 100, 1, true, true});
    assert(sex.condition() == "identity" && !sex.cleanupAllowed(owner));
    auto lifecycle = granted();
    auto old = lifecycle.admit(PhysicsAdmission::qualified, owner, 2);
    lifecycle.observe({31, 0, 0, false, false}); lifecycle.observe(beastB);
    assert(old && !lifecycle.commit(*old, owner, 2));
    assert(!lifecycle.rejected()); // Expected roots across human/unload remain renewable while the grant is retained.
    auto next = lifecycle.admit(PhysicsAdmission::renewal, owner, 3);
    assert(next && lifecycle.commit(*next, owner, 3));
}
void populationInitialIsNotAHiddenFreshQualification() {
    PhysicsAuthority a{owner};
    auto first = a.admit(PhysicsAdmission::initialPopulation, owner, 1);
    assert(first && !a.admit(PhysicsAdmission::initialPopulation, owner, 2));
    a.observe(beastA); assert(a.commit(*first, owner, 1));
    a.suspend(); a.forgetStamp(); // Empty ledger release frees the bounded root, but not history.
    assert(!a.admit(PhysicsAdmission::initialPopulation, owner, 3));
    assert(!a.admit(PhysicsAdmission::renewal, owner, 3));
    auto explicitGrant = a.admit(PhysicsAdmission::qualified, owner, 4);
    a.observe(beastB); assert(explicitGrant && a.commit(*explicitGrant, owner, 4));
}
void sameRootPartChangesRejectThePreviousResourceGrant() {
    static_assert(physicsBipedSlotCount == 42 && physicsBipedPartCount == 84);
    for (std::size_t slot = 0; slot < physicsBipedPartCount; ++slot) {
        for (unsigned mutation = 0; mutation < 5; ++mutation) {
            auto initial = beastA, changed = beastA;
            if (mutation == 0) changed.partClones[slot] += 10000; // Replacement.
            if (mutation == 1) changed.partClones[slot] = 0; // Removal.
            if (mutation == 2) initial.partClones[slot] = 0; // Delayed arrival.
            if (mutation == 3) { // Same clones moved within one ordered table.
                const auto other = (slot / physicsBipedSlotCount) * physicsBipedSlotCount +
                    (slot + 1) % physicsBipedSlotCount;
                std::swap(changed.partClones[slot], changed.partClones[other]);
            }
            if (mutation == 4) { // Same clones moved between current/buffered tables.
                const auto other = (slot + physicsBipedSlotCount) % physicsBipedPartCount;
                std::swap(changed.partClones[slot], changed.partClones[other]);
            }
            assert(initial.root == changed.root && initial != changed);
            auto a = granted(initial);
            auto unchangedActor = granted();
            const auto published = a.revision();
            const auto untouchedRevision = unchangedActor.revision();
            auto queued = a.admit(PhysicsAdmission::renewal, owner, 2);
            assert(queued);
            a.observe(changed);
            assert(a.condition() == "model" && !a.publishable(owner, published));
            assert(!a.commit(*queued, owner, 2));
            assert(!a.admit(PhysicsAdmission::renewal, owner, 3));
            assert(!a.admit(PhysicsAdmission::initialPopulation, owner, 3));
            assert(a.cleanupAllowed(owner)); // Existing own-capsule cleanup remains possible, never acknowledged here.
            a.observe(initial); // Restoring old pointers cannot silently renew rejected qualification.
            assert(a.condition() == "model" && !a.renewable(owner) && a.cleanupAllowed(owner));
            assert(unchangedActor.publishable(owner, untouchedRevision));
        }
    }
}
void partsChangingDuringFreshAdmissionInvalidateItsTicket() {
    auto a = granted();
    auto queued = a.admit(PhysicsAdmission::qualified, owner, 2);
    auto changed = beastA; changed.partClones.back() += 10000;
    a.observe(changed);
    assert(queued && !a.commit(*queued, owner, 2) && a.condition() == "model");
    const auto rejectedRevision = a.revision();
    a.observe(changed);
    assert(a.revision() == rejectedRevision && !a.renewable(owner));
    // A caller must establish fresh external resource/provider qualification.
    // This policy cannot retire any outstanding Papyrus cleanup ledger.
    auto fresh = a.admit(PhysicsAdmission::qualified, owner, 3);
    assert(fresh && a.commit(*fresh, owner, 3) && a.renewable(owner));
    assert(a.stamp()->partClones == changed.partClones);
}
void retiredAuthorityKeepsOnlyCheapRejectionHistory() {
    static_assert(!std::is_copy_constructible_v<PhysicsAuthority> && std::is_nothrow_move_constructible_v<PhysicsAuthority>);
    PhysicsAuthority virgin{owner};
    assert(!virgin.stamp());
    auto active = granted();
    const auto* stamp = active.stamp();
    assert(stamp);
    active.observe(beastA);
    assert(active.stamp() == stamp); // A stable sample does not allocate another stamp.
    auto moved = std::move(active); // State insertion/assignment transfers the existing pure stamp allocation.
    assert(!active.stamp() && moved.stamp() == stamp);
    moved.reject(PhysicsRejection::model);
    moved.suspend(); moved.forgetStamp();
    assert(!moved.stamp() && moved.condition() == "model" && moved.cleanupAllowed(owner));
    assert(!moved.admit(PhysicsAdmission::renewal, owner, 2));
    assert(!moved.admit(PhysicsAdmission::initialPopulation, owner, 2));
}
void finiteObservationPathIsUnchanged() {
    auto a = granted(); PhysicsObservation observation;
    const std::vector<float> values{-2, -0.0F, 0, 2, std::numeric_limits<float>::max()};
    assert(validPhysicsValues(values) && a.publishable(owner, a.revision()));
    assert(!observation.observe(100, values, 0.5F));
    assert(observation.observe(100, values, 0.5F));
    assert(observation.published == values && observation.publishedWeight == 0.5F);
    const auto revision = a.revision();
    a.observe(beastA); // In-place morph deformation preserves actual part identities.
    assert(a.revision() == revision && a.publishable(owner, revision));
    assert(!observation.observe(100, std::vector<float>{.2F, .3F}, .7F));
    assert(observation.observe(100, std::vector<float>{.2F, .3F}, .7F));
    a.observe(beastA);
    assert(a.revision() == revision && a.publishable(owner, revision));
}
}
int main() {
    rejectionSurvivesDroppedReceiptsAndLifecycle(); cleanupRevocationIsIndependentOfFirstTerminalReason();
    pendingAndStaleAdmissionsCannotRestoreAuthority(); observedContextChangesInvalidateTicketsAndOldSnapshots();
    populationInitialIsNotAHiddenFreshQualification(); finiteObservationPathIsUnchanged();
    sameRootPartChangesRejectThePreviousResourceGrant(); partsChangingDuringFreshAdmissionInvalidateItsTicket();
    retiredAuthorityKeepsOnlyCheapRejectionHistory();
    std::cout << "Physics authority policy passed\n";
    std::cout << "Pure authority bytes=" << sizeof(PhysicsAuthority) << "; active body stamp bytes=" << sizeof(PhysicsBodyStamp) << '\n';
}
