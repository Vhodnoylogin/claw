#include "claw/PhysicsObserver.h"
#undef NDEBUG
#include <cassert>
#include <limits>
#include <iostream>

namespace {
void invalidProviderValuesExpireCandidate() {
    const float nan = std::numeric_limits<float>::quiet_NaN();
    const float infinity = std::numeric_limits<float>::infinity();
    for (const auto& invalid : std::vector<std::vector<float>>{{}, {nan}, {0.25F, infinity}, {-infinity, 0.5F}}) {
        assert(!claw::validPhysicsValues(invalid));
        claw::PhysicsObservation observer;
        const std::vector<float> valid{0.25F, 0.75F};
        assert(!observer.observe(100, valid));
        assert(observer.observe(100, valid));
        const auto oldSequence = observer.sequence;
        assert(!observer.observe(100, invalid));
        assert(observer.dirty && observer.candidate.empty() && observer.stablePasses == 0);
        assert(observer.sequence == oldSequence && observer.published == valid);
        // Rejected input cannot reuse the previous stable-candidate passes.
        assert(!observer.observe(100, valid));
        assert(observer.observe(100, valid));
        assert(observer.sequence != oldSequence);
    }
}

void finiteProviderRangeRemainsUnclamped() {
    const std::vector<float> values{std::numeric_limits<float>::lowest(), -2.F, -0.F, 0.F,
        2.F, std::numeric_limits<float>::max()};
    assert(claw::validPhysicsValues(values));
    claw::PhysicsObservation observer;
    assert(!observer.observe(100, values));
    assert(observer.observe(100, values));
    assert(observer.published == values && std::signbit(observer.published[2]));
    assert(!observer.observe(100, values));
}
}

int main() {
    invalidProviderValuesExpireCandidate();
    finiteProviderRangeRemainsUnclamped();
    claw::PhysicsObservation observer;
    assert(!observer.observe(100, {0.25F, 0.75F}));
    assert(observer.observe(100, {0.25F, 0.75F}));
    assert(observer.published == std::vector<float>({0.25F, 0.75F}));
    assert(!observer.observe(100, {0.25F, 0.75F}));
    // A foreign-key-only change is observed even when no event sets dirty.
    assert(!observer.observe(100, {0.5F, 0.75F}));
    assert(!observer.observe(100, {0.5F, 0.25F}));
    assert(observer.observe(100, {0.5F, 0.25F}));
    assert(!observer.observe(200, {0.5F, 0.25F}));
    assert(observer.observe(200, {0.5F, 0.25F}));
    observer.invalidate();
    assert(!observer.observe(200, {0.5F, 0.25F}));
    assert(observer.observe(200, {0.5F, 0.25F}));
    assert(!observer.observe(200, {std::numeric_limits<float>::quiet_NaN()}));
    assert(!observer.observe(0, {0}));
    assert(!observer.observe(100, {0.5F}, 0.25F));
    assert(observer.observe(100, {0.5F}, 0.25F));
    assert(!observer.observe(100, {0.5F}, 0.75F));
    assert(observer.observe(100, {0.5F}, 0.75F));
    assert(observer.published == std::vector<float>{0.5F});
    assert(observer.publishedWeight == 0.75F); // Independent base; coefficients unchanged.
    assert(!observer.observe(100, {0.5F}, 1.01F));
    assert(claw::validPhysicsNames({"CLAWHeadEarSize", "CLAWTailLength"}));
    assert(!claw::validPhysicsNames({"CLAWHeadEarSize", "CLAWHeadEarSize"}));
    assert(!claw::validPhysicsNames({"HumanForeignMorph"}));
    assert(!claw::validPhysicsNames({"CLAW\nMorph"}));
    assert(!claw::validPhysicsNames({}));
    std::cout << "Physics observer contracts passed\n";
}
