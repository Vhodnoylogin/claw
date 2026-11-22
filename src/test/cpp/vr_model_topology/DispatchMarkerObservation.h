#pragma once

#include <array>
#include <cstddef>
#include <string_view>

namespace claw::vr_diagnostic {
inline constexpr std::array<std::string_view, 9> dispatchMarkerNames{
    "CLAW_VR_DISPATCH_PROBE_M0", "CLAW_VR_DISPATCH_PROBE_M1",
    "CLAW_VR_DISPATCH_PROBE_F0", "CLAW_VR_DISPATCH_PROBE_F1",
    "CLAW_VR_DISPATCH_PROBE_H_M0",
    "CLAW_VR_DISPATCH_PROBE_H_M_STATIC", "CLAW_VR_DISPATCH_PROBE_H_F_STATIC",
    "CLAW_VR_DISPATCH_PROBE_H_M_FSMP", "CLAW_VR_DISPATCH_PROBE_H_F_FSMP"
};

template<class Object>
struct DispatchMarkers {
    std::array<unsigned, dispatchMarkerNames.size()> counts{};
    std::array<Object*, dispatchMarkerNames.size()> objects{};
    std::array<Object*, dispatchMarkerNames.size()> parents{};
    bool invalid{};
    bool operator==(const DispatchMarkers&) const = default;

    void record(std::size_t index, Object* object, Object* parent, bool valid) {
        if (!counts[index]) {
            objects[index] = object;
            parents[index] = parent;
        }
        if (counts[index] < 2) ++counts[index];
        invalid = invalid || !valid;
    }

    [[nodiscard]] std::string_view classify(bool complete) const {
        if (!complete || invalid) return "indeterminate";
        unsigned total{};
        for (const auto count : counts) total += count;
        if (!total) return "unmarked";
        return total == 1 ? "marked" : "ambiguous";
    }
};

template<class Object, class Linked>
bool belongsToGraph(const Object* object, const Object* root, std::size_t limit, Linked&& linked) {
    if (!root) return false;
    for (std::size_t depth = 0; object && depth < limit; ++depth) {
        if (object == root) return true;
        const auto* parent = object->parent;
        if (!parent || !linked(*parent, object)) return false;
        object = parent;
    }
    return false;
}
}
