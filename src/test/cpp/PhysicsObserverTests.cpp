#include "claw/PhysicsObserver.h"
#undef NDEBUG
#include <cassert>
#include <limits>
#include <iostream>

int main() {
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
