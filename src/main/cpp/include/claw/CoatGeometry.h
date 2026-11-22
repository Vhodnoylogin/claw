#pragma once
#include "claw/TargetModelAvailability.h"
#include <ranges>
#include <string_view>

namespace claw::appearance {
inline bool vrEarCoatBodyTriMatches(std::string_view observed, bool female) {
    const std::string_view expected = female ?
        R"(actors\werewolfbeast\claw\firstperson\female\earworldtrial.tri)" :
        R"(actors\werewolfbeast\claw\firstperson\male\earworldtrial.tri)";
    const auto normalized = [](char c) {
        if (c == '/') return '\\';
        return c >= 'A' && c <= 'Z' ? static_cast<char>(c - 'A' + 'a') : c;
    };
    return std::ranges::equal(observed, expected, {}, normalized);
}

template<class Geometry, std::size_t Roles>
struct CoatGeometry {
    TargetModelObservation graph;
    std::array<Geometry*, targetModelMaxGeometries> geometries{};
    std::array<Geometry*, Roles> roles{};
    std::array<std::size_t, Roles> matches{};

    [[nodiscard]] bool complete() const {
        return graph.rootPresent && graph.collection == TargetModelCollection::complete;
    }
    [[nodiscard]] Geometry* unique(std::size_t role) const {
        return complete() && matches[role] == 1 ? roles[role] : nullptr;
    }
    [[nodiscard]] bool contains(const Geometry* geometry) const {
        return geometry && std::ranges::find(geometries, geometry) != geometries.end();
    }
    template<class Retained>
    [[nodiscard]] bool clearOf(const Retained& retained) const {
        return complete() && std::ranges::none_of(retained, [this](const auto& geometry) {
            return contains(geometry.get());
        });
    }
};

template<class Geometry, std::size_t Roles, class Object, class Describe, class Children>
CoatGeometry<Geometry, Roles> collectCoatGeometry(Object* root, Describe&& describe, Children&& children) {
    CoatGeometry<Geometry, Roles> result;
    std::size_t count{};
    result.graph = collectTargetModel(root, [&](auto* object) {
        auto [geometry, role] = describe(object);
        if (geometry && count < result.geometries.size()) result.geometries[count++] = geometry;
        if (role && *role < Roles) {
            ++result.matches[*role];
            result.roles[*role] = geometry;
        }
        return TargetModelObject{geometry != nullptr};
    }, children);
    return result;
}
}
