#include <array>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <iomanip>
#include <iterator>
#include <limits>
#include <vector>

#include "claw/PhysicsFit.h"

using claw::physics::Capsule;
using claw::physics::Vec3;
using Matrix = std::array<double, 12>;

struct Influence { std::size_t bone; double weight; Vec3 bindPoint; };
struct Vertex { std::size_t first, count; };
struct Region { std::size_t owner, first, count; double padding; };
struct Pose { Matrix world[15], inverse[15]; };
using Expected = Capsule;

#include "observations.h"

Vec3 affine(const Matrix& matrix, const Vec3& point) {
    Vec3 result{};
    for (std::size_t axis = 0; axis < result.size(); ++axis) {
        const auto i = axis * 4;
        result[axis] = matrix[i] * point[0] + matrix[i+1] * point[1] + matrix[i+2] * point[2] + matrix[i+3];
    }
    return result;
}

class PosedSupport {
public:
    PosedSupport() : worldPoints(std::size(uniqueVertices)) {
        const auto widest = std::max_element(std::begin(regions), std::end(regions),
            [](const auto& left, const auto& right) { return left.count < right.count; });
        ownerPoints.reserve(widest->count);
    }

    void update(const Pose& pose) {
        for (std::size_t v = 0; v < worldPoints.size(); ++v) {
            const auto& vertex = uniqueVertices[v];
            Vec3 point{};
            for (std::size_t i = vertex.first; i < vertex.first + vertex.count; ++i) {
                const auto& link = influences[i];
                point = claw::physics::add(point, affine(pose.world[link.bone], link.bindPoint), link.weight);
            }
            worldPoints[v] = point;
        }
    }

    std::array<Capsule, std::size(regions)> fit(const Pose& pose) {
        std::array<Capsule, std::size(regions)> result{};
        for (std::size_t index = 0; index < result.size(); ++index) {
            const auto& region = regions[index];
            ownerPoints.clear();
            for (std::size_t i = region.first; i < region.first + region.count; ++i)
                ownerPoints.push_back(affine(pose.inverse[region.owner], worldPoints[slotPointIndices[i]]));
            result[index] = claw::physics::Fit(ownerPoints, region.padding);
        }
        return result;
    }

private:
    std::vector<Vec3> worldPoints;
    std::vector<Vec3> ownerPoints;
};

double maxDifference(const Capsule& actual, const Capsule& reference) {
    double largest = std::abs(actual.radius - reference.radius);
    for (std::size_t i = 0; i < 3; ++i)
        largest = std::max({largest, std::abs(actual.p1[i]-reference.p1[i]), std::abs(actual.p2[i]-reference.p2[i])});
    return largest;
}

int main() {
    PosedSupport support;
    const auto count = std::size(poses);
    double numericError{};
    for (std::size_t p = 0; p < count; ++p) {
        support.update(poses[p]);
        const auto fitted = support.fit(poses[p]);
        for (std::size_t i = 0; i < fitted.size(); ++i)
            numericError = std::max(numericError, maxDifference(fitted[i], expected[p][i]));
    }
    std::cout << std::setprecision(12)
              << "uniqueSupportVertices " << std::size(uniqueVertices) << " influences " << std::size(influences)
              << " slotPointMemberships " << std::size(slotPointIndices) << " slots " << std::size(regions)
              << " poses " << count << " maxCapsuleAbsError " << numericError << '\n';
    if (!std::isfinite(numericError) || numericError > 1e-6) return 1;

    using Clock = std::chrono::steady_clock;
    using Micros = std::chrono::duration<double, std::micro>;
    constexpr int iterations = 512;
    double keep{};
    for (int batch = 0; batch < 6; ++batch) {
        double skin{}, fit{};
        for (int i = 0; i < iterations; ++i) {
            auto& pose = poses[(batch+i) % count];
            const auto start = Clock::now();
            support.update(pose);
            const auto mid = Clock::now();
            const auto fitted = support.fit(pose);
            const auto stop = Clock::now();
            skin += Micros(mid-start).count();
            fit += Micros(stop-mid).count();
            keep += fitted[i % fitted.size()].radius;
        }
        std::cout << "batch " << batch << " skinUs " << skin/iterations << " fitUs " << fit/iterations
                  << " aggregateUs " << (skin+fit)/iterations << '\n';
    }
    std::cout << "checksum " << keep << '\n';
}
