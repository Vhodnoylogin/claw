#include <array>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <iomanip>
#include <iostream>
#include <iterator>
#include <limits>
#include <vector>

#include "claw/PosedContactSupport.h"

using claw::physics::Capsule;
using claw::physics::PoseMorphDelta;
using claw::physics::PoseVertexFields;
using claw::physics::PosedContactModel;
using claw::physics::PosedContactSupport;
using claw::physics::Vec3;
using Matrix = claw::physics::PoseAffine;
using Influence = claw::physics::PoseInfluence;
using Vertex = claw::physics::PoseVertex;
using Region = claw::physics::PoseRegion;
struct Pose { Matrix world[15], inverse[15]; };
using Expected = Capsule;

#include "observations.h"

double maxDifference(const Capsule& actual, const Capsule& reference) {
    double largest = std::abs(actual.radius - reference.radius);
    for (std::size_t i = 0; i < 3; ++i)
        largest = std::max({largest, std::abs(actual.p1[i]-reference.p1[i]), std::abs(actual.p2[i]-reference.p2[i])});
    return largest;
}

bool checkDeformationAndRejections() {
    constexpr Influence links[]{{0, .25, {1., 0., 0.}, 0}, {1, .75, {0., 1., 0.}, 1}, {0, 1., {0., 0., 1.}, 0}};
    constexpr Vertex vertices[]{{0, 2}, {2, 1}};
    constexpr std::size_t points[]{0, 1};
    constexpr Region slots[]{{0, 0, 2, .0001}};
    constexpr PoseMorphDelta deltas[]{{0, {0., 4., 0.}}};
    const PoseVertexFields fields[]{{{2., 0., 0.}, deltas}, {{}, {}}};
    constexpr claw::physics::PoseLinear bind[]{{{{1., 0., 0.}, {0., 1., 0.}, {0., 0., 1.}}},
                                               {{{0., -1., 0.}, {1., 0., 0.}, {0., 0., 1.}}}};
    static constexpr Matrix world[]{{2., 0., 0., 10., 0., 2., 0., 20., 0., 0., 2., 30.},
                                    {1., 0., 0., 2., 0., 1., 0., 4., 0., 0., 1., 6.}};
    constexpr Matrix inverse[]{{.5, 0., 0., -5., 0., .5, 0., -10., 0., 0., .5, -15.},
                               {1., 0., 0., -2., 0., 1., 0., -4., 0., 0., 1., -6.}};
    const PosedContactModel model{links, vertices, points, slots, 2, 1, fields, bind};
    const PosedContactSupport support(model);
    static constexpr double neutral[]{0.}, active[]{.25};
    std::array<Vec3, 2> positions{};
    std::array<Capsule, 1> fitted{};
    std::vector<Vec3> ownerPoints;
    support.skin(world, .5, active, positions);
    support.fit(inverse, positions, ownerPoints, fitted);
    const auto expectedFit = claw::physics::Fit({{-2.875, -5., -9.}, {0., 0., 1.}});
    if (positions[0] != Vec3{4.25, 10., 12.} || positions[1] != Vec3{10., 20., 32.} ||
        maxDifference(fitted[0], expectedFit) != 0.) return false;

    support.skin(world, .5, neutral, positions);
    if (positions[0] != Vec3{5., 9.5, 12.}) return false;
    support.skin(world, 0., active, positions);
    if (positions[0] != Vec3{3.75, 9.25, 12.}) return false;
    support.skin(world, 0., neutral, positions);
    if (positions[0] != Vec3{4.5, 8.75, 12.}) return false;

    const auto rejects = [](const auto& operation) {
        try { operation(); }
        catch (const std::invalid_argument&) { return true; }
        return false;
    };
    constexpr std::size_t badPoints[]{0, 2};
    constexpr Vertex badVertices[]{{0, 2}, {std::numeric_limits<std::size_t>::max(), 1}};
    const Influence badLinks[]{{2, .25, {1., 0., 0.}, 0}, links[1], links[2]};
    const PoseMorphDelta badDeltas[]{{1, {0., 4., 0.}}};
    const PoseVertexFields badFields[]{{{}, badDeltas}, fields[1]};
    const double invalidMorph[]{std::numeric_limits<double>::quiet_NaN()};
    Matrix invalidPose[]{world[0], world[1]};
    invalidPose[1][6] = std::numeric_limits<double>::infinity();
    auto badModel = model;
    badModel.slotPoints = badPoints;
    if (!rejects([&] { const PosedContactSupport invalid(badModel); })) return false;
    badModel = model;
    badModel.vertices = badVertices;
    if (!rejects([&] { const PosedContactSupport invalid(badModel); })) return false;
    badModel = model;
    badModel.influences = badLinks;
    if (!rejects([&] { const PosedContactSupport invalid(badModel); })) return false;
    badModel = model;
    badModel.vertexFields = badFields;
    if (!rejects([&] { const PosedContactSupport invalid(badModel); })) return false;
    return rejects([&] { support.skin(world, .5, invalidMorph, positions); }) &&
           rejects([&] { support.skin(invalidPose, .5, active, positions); });
}

int main() {
    if (!checkDeformationAndRejections()) {
        std::cerr << "Posed contact support controls failed\n";
        return 1;
    }
    const PosedContactSupport support({influences, uniqueVertices, slotPointIndices, regions, std::size(poses[0].world)});
    std::vector<Vec3> worldPoints(std::size(uniqueVertices));
    std::vector<Vec3> ownerPoints;
    const auto widest = std::max_element(std::begin(regions), std::end(regions),
        [](const auto& left, const auto& right) { return left.count < right.count; });
    ownerPoints.reserve(widest->count);
    std::array<Capsule, std::size(regions)> fitted{};
    const auto count = std::size(poses);
    double numericError{};
    for (std::size_t p = 0; p < count; ++p) {
        support.skin(poses[p].world, 0., {}, worldPoints);
        support.fit(poses[p].inverse, worldPoints, ownerPoints, fitted);
        for (std::size_t i = 0; i < fitted.size(); ++i)
            numericError = std::max(numericError, maxDifference(fitted[i], expected[p][i]));
    }
    std::cout << std::setprecision(12)
              << "Posed contact deformation and malformed input controls passed\n"
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
            const auto& pose = poses[(batch+i) % count];
            const auto start = Clock::now();
            support.skin(pose.world, 0., {}, worldPoints);
            const auto mid = Clock::now();
            support.fit(pose.inverse, worldPoints, ownerPoints, fitted);
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
