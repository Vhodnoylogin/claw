#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <optional>

namespace claw {
// Opaque identities collected on the main task. The adapter retains any engine
// roots separately; this policy never dereferences, creates or owns a graph.
struct VRBodyInput {
    bool enabled{}, vrPlayer{}, beast{};
    int sex{-1};
    std::uint64_t owner{}, lifecycle{};
    std::uintptr_t race{}, thirdRoot{}, firstRoot{};
    bool operator==(const VRBodyInput&) const = default;
};

struct VRBodyRoots {
    std::array<std::uintptr_t, 2> identities{};
    std::size_t count{};
};

struct VRBodyLease {
    std::uint64_t generation{};
    VRBodyInput input;
};

struct VRBodyTransition {
    bool changed{}, reapply{}, firstLoaded{}, distinctFirst{};
    std::uint64_t generation{};
};

// One runtime player instance, without persisted state or a second morph cache.
// A missing first graph is permitted: the existing third-person path can still
// reapply once. It is never evidence that a first-person body was created.
class VRBodyState {
public:
    VRBodyTransition observe(VRBodyInput actual) {
        actual = relevant(actual);
        const bool changed = actual != input_;
        if (changed) {
            input_ = actual;
            if (generation_ == std::numeric_limits<std::uint64_t>::max()) exhausted_ = true;
            else ++generation_;
        }
        return {changed, changed && applicable(), active() && input_.firstRoot != 0,
            active() && input_.firstRoot != 0 && input_.thirdRoot != 0 && input_.firstRoot != input_.thirdRoot,
            generation_};
    }

    // Current loaded roots only, with a shared first/third identity visited once.
    VRBodyRoots roots() const {
        VRBodyRoots result;
        if (!active()) return result;
        if (input_.thirdRoot) result.identities[result.count++] = input_.thirdRoot;
        if (input_.firstRoot && input_.firstRoot != input_.thirdRoot)
            result.identities[result.count++] = input_.firstRoot;
        return result;
    }

    std::optional<VRBodyLease> lease() const {
        if (!applicable()) return std::nullopt;
        return VRBodyLease{generation_, input_};
    }

    // Require a fresh adapter observation too: queued work cannot rely only on
    // our cached stamp when an engine graph changed before the next scan.
    bool current(const VRBodyLease& lease, VRBodyInput actual) const {
        return applicable() && lease.generation == generation_ && lease.input == input_ && relevant(actual) == input_;
    }

    const VRBodyInput& input() const { return input_; }

private:
    static VRBodyInput relevant(VRBodyInput input) {
        // Inactive SE/AE/NPC observations cannot cause graph-driven reapplication.
        return input.enabled && input.vrPlayer ? input : VRBodyInput{};
    }

    bool active() const {
        return !exhausted_ && input_.enabled && input_.vrPlayer && input_.beast &&
            (input_.sex == 0 || input_.sex == 1) && input_.owner && input_.lifecycle && input_.race;
    }

    bool applicable() const { return active() && input_.thirdRoot != 0; }

    VRBodyInput input_;
    std::uint64_t generation_{};
    bool exhausted_{};
};
}
