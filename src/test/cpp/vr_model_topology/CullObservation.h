#pragma once

#include <algorithm>
#include <array>
#include <cstddef>
#include <optional>

namespace claw::vr_diagnostic {

enum class ParentEnd { complete, depthLimit, cycle };

template <class Object, std::size_t Limit>
struct CullObservation {
    std::array<const Object*, Limit + 1> path{};
    std::array<bool, Limit> ancestorFlags{};
    const Object* stop{};
    std::size_t ancestorCount{};
    bool rootFlag{};
    ParentEnd end = ParentEnd::complete;

    std::optional<bool> effective() const {
        const auto last = ancestorFlags.begin() + ancestorCount;
        if (rootFlag || std::find(ancestorFlags.begin(), last, true) != last) return true;
        if (end == ParentEnd::complete) return false;
        return std::nullopt;
    }

    bool operator==(const CullObservation&) const = default;
};

template <std::size_t Limit, class Object, class Parent, class AppCulled>
CullObservation<Object, Limit> observeCull(const Object& root, Parent parent, AppCulled appCulled) {
    CullObservation<Object, Limit> result;
    result.path[0] = &root;
    result.rootFlag = appCulled(root);
    auto* current = parent(root);
    while (current) {
        const auto end = result.path.begin() + result.ancestorCount + 1;
        if (std::find(result.path.begin(), end, current) != end) {
            result.end = ParentEnd::cycle;
            result.stop = current;
            break;
        }
        if (result.ancestorCount == Limit) {
            result.end = ParentEnd::depthLimit;
            result.stop = current;
            break;
        }
        result.ancestorFlags[result.ancestorCount++] = appCulled(*current);
        result.path[result.ancestorCount] = current;
        current = parent(*current);
    }
    return result;
}

}  // namespace claw::vr_diagnostic
