#pragma once
#include <algorithm>
#include <array>
#include <cstddef>
#include <optional>
#include <string>
#include <string_view>

namespace claw {
// Authored third-person CLAW roles, verified in both supplied sexes. These are
// model requirements, never a human body-family or arbitrary morph classifier.
inline constexpr std::array<std::string_view, 4> targetModelRoles{"body", "head", "claws", "fur_tailtip"};
inline constexpr std::size_t targetModelMaxObjects = 512, targetModelMaxGeometries = 64;
inline constexpr std::size_t targetModelMaxChildLinks = 2 * targetModelMaxObjects;
enum class TargetModelCollection { complete, objectLimit, geometryLimit, repeatedObject };
enum class TargetModelAvailability { ready, unloaded, missing, ambiguous, indeterminate, changed };
struct TargetModelObject {
    bool geometry{};
    std::optional<std::size_t> role;
};
struct TargetModelObservation {
    bool rootPresent{};
    TargetModelCollection collection{TargetModelCollection::complete};
    std::size_t objects{}, geometries{}, childLinks{};
    std::array<std::size_t, targetModelRoles.size()> roleObjects{}, roleGeometries{};
};

// Bounded traversal; callbacks are the explicit external-read boundary. The
// same walker is exercised with ordinary fake graphs without engine headers.
// Children must stop enumerating when push returns false. Repeated pointers
// fail closed, so malformed cycles/aliases cannot produce a partial success.
template<class Object, class Describe, class Children>
TargetModelObservation collectTargetModel(Object* root, Describe&& describe, Children&& children) {
    TargetModelObservation result;
    if (!root) return result;
    result.rootPresent = true;
    std::array<Object*, targetModelMaxObjects> pending{}, visited{};
    std::size_t queued{1}; pending[0] = root;
    while (queued) {
        auto* object = pending[--queued];
        if (std::find(visited.begin(), visited.begin() + result.objects, object) != visited.begin() + result.objects) {
            result.collection = TargetModelCollection::repeatedObject; return result;
        }
        if (result.objects == targetModelMaxObjects) {
            result.collection = TargetModelCollection::objectLimit; return result;
        }
        visited[result.objects++] = object;
        const auto actual = describe(object);
        if (actual.geometry && ++result.geometries > targetModelMaxGeometries) {
            result.collection = TargetModelCollection::geometryLimit; return result;
        }
        if (actual.role && *actual.role < targetModelRoles.size()) {
            ++result.roleObjects[*actual.role];
            if (actual.geometry) ++result.roleGeometries[*actual.role];
        }
        if (!children(object, [&](Object* child) {
            // Count empty child slots too: a sparse/malformed child table must
            // not bypass the work bound while contributing no queued objects.
            if (++result.childLinks > targetModelMaxChildLinks) return false;
            if (!child) return true;
            if (queued == pending.size()) return false;
            pending[queued++] = child;
            return true;
        })) {
            result.collection = TargetModelCollection::objectLimit; return result;
        }
    }
    return result;
}

// Coefficients, optional coats and first-person graphs cannot affect this
// decision. An all-zero valid vector still requires the same world model.
inline TargetModelAvailability targetModelAvailability(const TargetModelObservation& actual, bool current = true) {
    if (!current) return TargetModelAvailability::changed;
    if (!actual.rootPresent) return TargetModelAvailability::unloaded;
    if (actual.collection != TargetModelCollection::complete) return TargetModelAvailability::indeterminate;
    if (std::any_of(actual.roleGeometries.begin(), actual.roleGeometries.end(), [](auto count) { return count > 1; }))
        return TargetModelAvailability::ambiguous;
    if (std::any_of(actual.roleGeometries.begin(), actual.roleGeometries.end(), [](auto count) { return count == 0; }))
        return TargetModelAvailability::missing;
    return TargetModelAvailability::ready;
}

inline std::string targetModelDiagnostic(const TargetModelObservation& actual, bool current = true) {
    switch (targetModelAvailability(actual, current)) {
    case TargetModelAvailability::ready: return {};
    case TargetModelAvailability::unloaded: return "CLAW world target model unloaded";
    case TargetModelAvailability::changed: return "CLAW target model changed during refresh";
    case TargetModelAvailability::indeterminate:
        switch (actual.collection) {
        case TargetModelCollection::objectLimit: return "CLAW target model observation unavailable: object limit";
        case TargetModelCollection::geometryLimit: return "CLAW target model observation unavailable: geometry limit";
        case TargetModelCollection::repeatedObject: return "CLAW target model observation unavailable: repeated object";
        default: return "CLAW target model observation unavailable";
        }
    default: break;
    }
    std::string result{"required CLAW target model unavailable: "};
    for (std::size_t i = 0; i < targetModelRoles.size(); ++i) {
        if (actual.roleGeometries[i] == 1) continue;
        if (result.back() != ' ') result += "; ";
        result += targetModelRoles[i];
        result += actual.roleGeometries[i] > 1 ? "=ambiguous" : actual.roleObjects[i] ? "=not geometry" : "=missing";
    }
    return result;
}
}
