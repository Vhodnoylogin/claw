#pragma once

#include "claw/PhysicsFit.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <span>
#include <stdexcept>
#include <vector>

namespace claw::physics {

using PoseAffine = std::array<double, 12>; // Row-major 3x4 matrix.
using PoseLinear = std::array<Vec3, 3>;

inline PoseAffine InvertPoseAffine(const PoseAffine& matrix) {
    const Vec3 x{matrix[0], matrix[1], matrix[2]}, y{matrix[4], matrix[5], matrix[6]},
        z{matrix[8], matrix[9], matrix[10]};
    const Vec3 origin{matrix[3], matrix[7], matrix[11]};
    const std::array columns{cross(y, z), cross(z, x), cross(x, y)};
    const double determinant = dot(x, columns[0]);
    if (!std::isfinite(determinant) || determinant <= 0 || !finite(origin))
        throw std::invalid_argument("Invalid world-to-capsule pose transform");
    PoseAffine result{};
    for (std::size_t axis = 0; axis < 3; ++axis) {
        const Vec3 row{columns[0][axis] / determinant, columns[1][axis] / determinant,
            columns[2][axis] / determinant};
        const double translation = -dot(row, origin);
        if (!finite(row) || !std::isfinite(translation))
            throw std::invalid_argument("Nonfinite world-to-capsule pose transform");
        std::copy(row.begin(), row.end(), result.begin() + 4 * axis);
        result[4 * axis + 3] = translation;
    }
    return result;
}

inline constexpr double poseCapsuleTolerance = 0.05; // Owner-local game units, pending runtime calibration.

// A capsule is a segment swept by a sphere. Direct and reversed endpoint
// matchings both bound the surface shift by the end movement plus radius change.
inline bool PoseCapsuleChanged(const Capsule& previous, const Capsule& next, double tolerance) {
    const double remaining = tolerance - std::abs(previous.radius - next.radius);
    if (remaining < 0) return true;
    const auto differs = [squared = remaining * remaining](const Vec3& a, const Vec3& b) {
        const auto delta = add(a, b, -1.);
        return dot(delta, delta) > squared;
    };
    return (differs(previous.p1, next.p1) || differs(previous.p2, next.p2)) &&
           (differs(previous.p1, next.p2) || differs(previous.p2, next.p1));
}

struct PoseInfluence {
    std::size_t bone;
    double weight;
    Vec3 bindPoint; // Neutral shape point already projected into this bone's bind space.
    std::size_t bind{}; // The linear part of the same bind mapping, used for shape-space deltas.
};

struct PoseVertex { std::size_t first, count; };
struct PoseRegion { std::size_t owner, first, count; double padding; };
struct PoseMorphDelta { std::size_t morph; Vec3 delta; };

struct PoseVertexFields {
    // Independent endpoint and sparse TRI deltas, in the original shape's coordinates.
    Vec3 weightDelta{};
    std::span<const PoseMorphDelta> morphs;
};

struct PosedContactModel {
    std::span<const PoseInfluence> influences;
    std::span<const PoseVertex> vertices;
    std::span<const std::size_t> slotPoints;
    std::span<const PoseRegion> regions;
    std::size_t boneCount;
    std::size_t morphCount{};
    std::span<const PoseVertexFields> vertexFields{};
    std::span<const PoseLinear> bindLinear{};
};

// Numeric support only. Keep the backing arrays immutable and alive for this view.
class PosedContactSupport {
public:
    explicit PosedContactSupport(PosedContactModel model) : model_(model) {
        if (!model_.boneCount || model_.morphCount > 32 || model_.vertices.empty() || model_.regions.empty() ||
            (!model_.vertexFields.empty() && model_.vertexFields.size() != model_.vertices.size()))
            throw std::invalid_argument("Invalid posed contact model dimensions");

        for (const auto& influence : model_.influences) {
            if (influence.bone >= model_.boneCount || !std::isfinite(influence.weight) ||
                influence.weight <= 0. || influence.weight > 1. || !finite(influence.bindPoint) ||
                (!model_.vertexFields.empty() && influence.bind >= model_.bindLinear.size()))
                throw std::invalid_argument("Invalid posed contact skin influence");
        }
        for (const auto& vertex : model_.vertices) {
            const auto links = subrange(model_.influences, vertex.first, vertex.count);
            double weight = 0.;
            for (const auto& influence : links) weight += influence.weight;
            if (links.empty() || std::abs(weight - 1.) > 1.e-8)
                throw std::invalid_argument("Posed contact skin weights must be normalized");
        }
        for (const auto& transform : model_.bindLinear) {
            if (!std::all_of(transform.begin(), transform.end(), finite))
                throw std::invalid_argument("Nonfinite posed contact bind transform");
        }
        for (const auto& fields : model_.vertexFields) {
            if (!finite(fields.weightDelta)) throw std::invalid_argument("Nonfinite pose weight delta");
            std::array<bool, 32> seen{};
            for (const auto& field : fields.morphs) {
                if (field.morph >= model_.morphCount || seen[field.morph] || !finite(field.delta))
                    throw std::invalid_argument("Invalid posed contact morph field");
                seen[field.morph] = true;
            }
        }
        for (const auto& region : model_.regions) {
            if (region.owner >= model_.boneCount || region.count < 2 ||
                !std::isfinite(region.padding) || region.padding <= 0. || region.padding > 0.01)
                throw std::invalid_argument("Invalid posed contact region");
            for (const auto point : subrange(model_.slotPoints, region.first, region.count)) {
                if (point >= model_.vertices.size()) throw std::invalid_argument("Invalid posed contact point index");
            }
        }
    }

    void skin(std::span<const PoseAffine> world, double weight, std::span<const double> morphs,
              std::span<Vec3> output) const {
        validateTransforms(world);
        if (output.size() != model_.vertices.size() || !inDomain(weight) || morphs.size() != model_.morphCount ||
            !std::all_of(morphs.begin(), morphs.end(), inDomain))
            throw std::invalid_argument("Invalid effective posed contact vector");

        const bool deformed = !model_.vertexFields.empty();
        for (std::size_t index = 0; index < model_.vertices.size(); ++index) {
            Vec3 delta{};
            if (deformed) {
                const auto& fields = model_.vertexFields[index];
                delta = add(delta, fields.weightDelta, weight);
                for (const auto& field : fields.morphs) delta = add(delta, field.delta, morphs[field.morph]);
            }
            const auto& vertex = model_.vertices[index];
            Vec3 point{};
            for (const auto& link : model_.influences.subspan(vertex.first, vertex.count)) {
                auto bindPoint = link.bindPoint;
                if (deformed) {
                    // Only the linear part maps a shape-space displacement to the bone's bind space.
                    const auto& bind = model_.bindLinear[link.bind];
                    bindPoint = add(bindPoint, {dot(bind[0], delta), dot(bind[1], delta), dot(bind[2], delta)});
                }
                point = add(point, transformPoint(world[link.bone], bindPoint), link.weight);
            }
            if (!finite(point)) throw std::invalid_argument("Nonfinite posed contact world point");
            output[index] = point;
        }
    }

    // Use inverse transforms from the same pose and a scratch vector distinct from worldPoints.
    void fit(std::span<const PoseAffine> worldToOwner, std::span<const Vec3> worldPoints,
             std::vector<Vec3>& ownerPoints, std::span<Capsule> output) const {
        validateTransforms(worldToOwner);
        if (worldPoints.size() != model_.vertices.size() || output.size() != model_.regions.size())
            throw std::invalid_argument("Invalid posed contact fit dimensions");
        for (std::size_t index = 0; index < model_.regions.size(); ++index) {
            const auto& region = model_.regions[index];
            ownerPoints.clear();
            for (const auto point : model_.slotPoints.subspan(region.first, region.count))
                ownerPoints.push_back(transformPoint(worldToOwner[region.owner], worldPoints[point]));
            const auto capsule = Fit(ownerPoints, region.padding);
            if (!finite(capsule.p1) || !finite(capsule.p2) || !std::isfinite(capsule.radius))
                throw std::invalid_argument("Nonfinite posed contact capsule");
            output[index] = capsule;
        }
    }

private:
    static bool inDomain(double value) { return std::isfinite(value) && value >= 0. && value <= 1.; }

    template <class T>
    static std::span<const T> subrange(std::span<const T> rows, std::size_t first, std::size_t count) {
        if (first > rows.size() || count > rows.size() - first)
            throw std::invalid_argument("Invalid posed contact array bounds");
        return rows.subspan(first, count);
    }

    void validateTransforms(std::span<const PoseAffine> transforms) const {
        if (transforms.size() != model_.boneCount)
            throw std::invalid_argument("Incomplete posed contact bone transforms");
        for (const auto& transform : transforms) {
            if (!std::all_of(transform.begin(), transform.end(), [](double value) { return std::isfinite(value); }))
                throw std::invalid_argument("Nonfinite posed contact bone transform");
        }
    }

    static Vec3 transformPoint(const PoseAffine& matrix, const Vec3& point) {
        Vec3 result{};
        for (std::size_t axis = 0; axis < result.size(); ++axis) {
            const auto i = axis * 4;
            result[axis] = matrix[i] * point[0] + matrix[i+1] * point[1] + matrix[i+2] * point[2] + matrix[i+3];
        }
        return result;
    }

    PosedContactModel model_;
};

} // namespace claw::physics
