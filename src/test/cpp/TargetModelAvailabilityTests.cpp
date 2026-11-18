#include "claw/TargetModelAvailability.h"
#include "claw/Preset.h"
#include "claw/VRBodyState.h"
#include "claw/PhysicsAuthority.h"
#include "claw/PhysicsObserver.h"
#undef NDEBUG
#include <cassert>
#include <iostream>
#include <vector>

namespace {
struct Node {
    std::string name;
    bool geometry{};
    std::vector<Node*> children;
};

claw::TargetModelObservation sample(Node* root) {
    return claw::collectTargetModel(root, [](Node* node) {
        claw::TargetModelObject result{node->geometry};
        for (std::size_t i = 0; i < claw::targetModelRoles.size(); ++i) {
            // Fake the provider's case-insensitive identity without engine calls.
            const claw::MorphNameLess less;
            if (!less(node->name, claw::targetModelRoles[i]) && !less(claw::targetModelRoles[i], node->name)) {
                result.role = i; break;
            }
        }
        return result;
    }, [](Node* node, auto&& push) {
        for (auto* child : node->children) if (!push(child)) return false;
        return true;
    });
}

struct Model {
    Node root{"world"}, body{"BODY", true}, head{"HEAD", true}, claws{"claws", true}, tail{"fur_tailtip", true};
    Model() { root.children = {&body, &head, &claws, &tail}; }
    auto sample() { return ::sample(&root); }
};

void presenceAndTypes() {
    using A = claw::TargetModelAvailability;
    Model model;
    assert(claw::targetModelAvailability(model.sample()) == A::ready);
    assert(claw::targetModelDiagnostic(model.sample()).empty());
    // No nonzero coefficient, tint, material, bounds or visibility field is
    // required by the policy. The same healthy model admits a neutral vector.
    const claw::Morphs neutral{{"CLAWArmGirth", 0.F}, {"CLAWHeadSize", 0.F}};
    assert(neutral.begin()->second == 0 && claw::targetModelAvailability(model.sample()) == A::ready);
    model.head.geometry = false;
    assert(claw::targetModelAvailability(model.sample()) == A::missing);
    assert(claw::targetModelDiagnostic(model.sample()).find("head=not geometry") != std::string::npos);
    model.head.geometry = true;
    Node duplicate{"body", true}; model.root.children.push_back(&duplicate);
    assert(claw::targetModelAvailability(model.sample()) == A::ambiguous);
    assert(claw::targetModelDiagnostic(model.sample()).find("body=ambiguous") != std::string::npos);
    model.root.children.pop_back();
    model.root.children.pop_back();
    assert(claw::targetModelAvailability(model.sample()) == A::missing);
    assert(claw::targetModelDiagnostic(model.sample()).find("fur_tailtip=missing") != std::string::npos);
    Node empty{"world"};
    assert(claw::targetModelAvailability(sample(&empty)) == A::missing);
    assert(claw::targetModelAvailability(sample(nullptr)) == A::unloaded);
}

void boundedTraversal() {
    using C = claw::TargetModelCollection;
    using A = claw::TargetModelAvailability;
    std::vector<Node> chain(claw::targetModelMaxObjects + 1);
    for (std::size_t i = 0; i + 1 < chain.size(); ++i) chain[i].children = {&chain[i + 1]};
    chain[claw::targetModelMaxObjects - 1].children.clear();
    assert(sample(chain.data()).collection == C::complete); // Inclusive object bound.
    chain[claw::targetModelMaxObjects - 1].children = {&chain.back()};
    auto result = sample(chain.data());
    assert(result.objects == claw::targetModelMaxObjects && result.collection == C::objectLimit);
    assert(claw::targetModelAvailability(result) == A::indeterminate);
    assert(claw::targetModelDiagnostic(result).find("object limit") != std::string::npos);
    Node wide{"world"};
    for (auto& node : chain) wide.children.push_back(&node);
    assert(sample(&wide).collection == C::objectLimit); // Pending work is bounded too.
    Node sparse{"world", false, std::vector<Node*>(claw::targetModelMaxChildLinks + 1, nullptr)};
    assert(sample(&sparse).collection == C::objectLimit); // Null slots cannot evade the work bound.
    std::vector<Node> shapes(claw::targetModelMaxGeometries + 1);
    Node root{"world"};
    for (auto& node : shapes) { node.geometry = true; root.children.push_back(&node); }
    root.children.pop_back();
    assert(sample(&root).collection == C::complete);
    root.children.push_back(&shapes.back());
    assert(sample(&root).collection == C::geometryLimit);
    Node cycle{"world"}; cycle.children = {&cycle};
    assert(sample(&cycle).collection == C::repeatedObject);
    Node shared{"unrelated"}; Node aliases{"world", false, {&shared, nullptr, &shared}};
    assert(sample(&aliases).collection == C::repeatedObject);
}

void freshLifecycleAndViews() {
    using A = claw::TargetModelAvailability;
    Model model;
    auto* stableRoot = &model.root;
    model.root.children.clear();
    const auto missing = sample(stableRoot);
    assert(claw::targetModelAvailability(missing) == A::missing);
    model.root.children = {&model.body, &model.head, &model.claws, &model.tail};
    assert(claw::targetModelAvailability(sample(stableRoot)) == A::ready); // Same-root late arrival.
    assert(claw::targetModelAvailability(missing) == A::missing); // Old plain observation cannot change.
    const auto beforeRemoval = model.sample();
    model.root.children.pop_back();
    assert(claw::targetModelAvailability(beforeRemoval) == A::ready);
    assert(claw::targetModelAvailability(model.sample()) == A::missing); // Fresh post-side-effect sample.
    assert(claw::targetModelAvailability(beforeRemoval, false) == A::changed); // Owner/root/VR lease expired.

    model.root.children.push_back(&model.tail);
    claw::VRBodyState vr;
    claw::VRBodyInput input{true, true, true, 0, 7, 1, 100, 200, 0};
    vr.observe(input);
    assert(vr.lease() && claw::targetModelAvailability(model.sample()) == A::ready); // No first graph.
    Node first{"first", false, {&model.claws}}; // Deliberately partial first-person model.
    input.firstRoot = 300; vr.observe(input);
    assert(claw::targetModelAvailability(sample(&first)) == A::missing);
    assert(claw::targetModelAvailability(model.sample()) == A::ready); // No view union or first-person gate.
    model.root.children = {&model.body, &model.claws};
    first.children = {&model.head, &model.tail};
    assert(claw::targetModelAvailability(model.sample()) == A::missing);
    assert(claw::targetModelAvailability(sample(&first)) == A::missing); // Opposite halves cannot make one model.
    input.firstRoot = input.thirdRoot; vr.observe(input);
    assert(vr.roots().count == 1); // Shared view root must not be traversed twice as one inventory.
}

void missingGeometryRevokesAnInFlightPhysicsFit() {
    constexpr claw::PhysicsOwner owner{7, 8};
    const claw::PhysicsBodyStamp stamp{100, 200, 1, true, true};
    claw::PhysicsAuthority authority{owner};
    auto grant = authority.admit(claw::PhysicsAdmission::qualified, owner, 1);
    authority.observe(stamp);
    assert(grant && authority.commit(*grant, owner, 1));
    Model model;
    assert(authority.requireModel(claw::targetModelAvailability(model.sample()) == claw::TargetModelAvailability::ready));
    claw::PhysicsObservation observation;
    const std::vector<float> values{.25F, .75F};
    assert(!observation.observe(stamp.root, values, .5F));
    assert(observation.observe(stamp.root, values, .5F));
    const auto queuedRevision = authority.revision();
    observation.invalidate();
    // This is the queued-worker counterexample: old published inputs and every
    // root/part identity still match after invalidation clears only candidates.
    assert(observation.published == values && observation.publishedWeight == .5F && observation.root == stamp.root);
    assert(authority.publishable(owner, queuedRevision));
    model.root.children.pop_back();
    assert(!authority.requireModel(claw::targetModelAvailability(model.sample()) == claw::TargetModelAvailability::ready));
    authority.observe(stamp); // No skeleton/part pointer change is necessary.
    assert(!authority.publishable(owner, queuedRevision) && authority.condition() == "model");
    assert(!authority.admit(claw::PhysicsAdmission::renewal, owner, 2));
    assert(authority.cleanupAllowed(owner));
    const auto rejectedRevision = authority.revision();
    assert(!authority.requireModel(false) && authority.revision() == rejectedRevision); // Idempotent repeated missing reads.
    model.root.children.push_back(&model.tail);
    assert(authority.requireModel(claw::targetModelAvailability(model.sample()) == claw::TargetModelAvailability::ready));
    assert(!authority.publishable(owner, queuedRevision) && !authority.renewable(owner)); // No silent physical requalification.
    auto fresh = authority.admit(claw::PhysicsAdmission::qualified, owner, 3);
    assert(fresh && authority.commit(*fresh, owner, 3));
    // An incomplete collection defers observation; it does not prove absence.
    const auto beforeUnknown = authority.revision();
    const auto queuedRoot = observation.root;
    observation.deferModel();
    assert(queuedRoot && observation.root != queuedRoot && observation.published == values);
    assert(!authority.rejected() && authority.renewable(owner));
    assert(authority.requireModel(claw::targetModelAvailability(model.sample()) == claw::TargetModelAvailability::ready));
    auto renewal = authority.admit(claw::PhysicsAdmission::renewal, owner, 4);
    assert(renewal && !authority.publishable(owner, beforeUnknown) && authority.commit(*renewal, owner, 4));
    assert(!observation.observe(stamp.root, values, .5F));
    assert(observation.observe(stamp.root, values, .5F));
    auto pending = authority.admit(claw::PhysicsAdmission::renewal, owner, 5);
    assert(pending);
    assert(!authority.requireModel(false));
    assert(!authority.commit(*pending, owner, 5)); // Missing after admission fences the queued registration too.
    claw::PhysicsAuthority virgin{owner};
    assert(!virgin.requireModel(false) && !virgin.engaged() && !virgin.stamp());
}
}

int main() {
    presenceAndTypes();
    boundedTraversal();
    freshLifecycleAndViews();
    missingGeometryRevokesAnInFlightPhysicsFit();
    std::cout << "Target model presence, bounded collection and fresh lifecycle contracts passed\n";
}
