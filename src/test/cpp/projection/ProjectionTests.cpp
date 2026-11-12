#include "Projection.h"

#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" int projection_endpoint_smoothstep_properties();

namespace {
using namespace morph_matrix;
void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
void same(double actual, double expected, const char* message) {
    require(std::bit_cast<std::uint64_t>(actual) == std::bit_cast<std::uint64_t>(expected), message);
}
EvaluationStatus run(const std::vector<double>& inputs, const std::vector<Edge>& edges,
    const std::vector<Target>& targets, NumericPolicy policy, std::vector<double>& outputs,
    std::vector<double>* raw = nullptr) {
    std::vector<Workspace> work(targets.size());
    return evaluate(inputs.size(), edges.size(), targets.size(),
        [&](size_t index) noexcept { return inputs[index]; },
        [&](size_t index) noexcept { return edges[index]; },
        [&](size_t index) noexcept { return targets[index]; }, work.data(), policy,
        [&](size_t index, double value) noexcept { outputs[index] = value; }, raw ? raw->data() : nullptr);
}

void transformsAndOpaqueBindings() {
    struct NamedValue { std::string name; double value; };
    const std::array<NamedValue, 3> inputs{{{"unreserved.$anything", -.5}, {"opaque / input", .4}, {"third", 9.}}};
    const std::array<std::string, 7> names{{"A", "B", "C", "D", "E", "F", "G"}};
    const std::array<Edge, 7> edges{{
        {0, 0, 0, 2, 2.}, {0, 1, 1, 2, 2.}, {0, 2, 2, 2, 2.},
        {1, 3, 3, 2, 2.}, {0, 4, 4, 3, 2.}, {2, 5, 5, 2, 2., .25},
        {0, 6, 6, 2, 3., 0., -4.}}};
    std::array<Workspace, 7> work{};
    std::array<NamedValue, 7> outputs{};
    size_t edgeReads{}, targetReads{}, published{};
    require(evaluate(inputs.size(), edges.size(), work.size(),
        [&](size_t index) noexcept { return inputs[index].value; },
        [&](size_t index) noexcept { ++edgeReads; return edges[index]; },
        [&](size_t) noexcept { ++targetReads; return Target{-10., 10., 1.}; }, work.data(), {},
        [&](size_t index, double value) noexcept {
            require(edgeReads == edges.size() && targetReads == 2 * work.size(), "published before numeric completion");
            outputs[index] = {names[index], value}; ++published;
        }) == EvaluationStatus::ok, "opaque indexed vector evaluation failed");
    require(published == 7 && edgeReads == 7 && targetReads == 14, "ordered evaluator rescanned edges per target");
    for (size_t index = 0; index < 6; ++index)
        same(outputs[index].value, contribution(inputs[edges[index].input].value, edges[index].gain,
             edges[index].function, edges[index].exponent, edges[index].constant), "existing transform changed");
    same(outputs[6].value, endpointContribution(-.5, -4., 3.), "negative endpoint changed");
    for (size_t index = 0; index < names.size(); ++index)
        require(outputs[index].name == names[index], "opaque output binding changed");
}

void sparseCutoffPrecisionAndScale() {
    NumericPolicy policy;
    policy.parameters = Precision::binary32;
    policy.result = Precision::binary32;
    policy.omitSmallGains = true;
    policy.gainCutoff = static_cast<double>(1.e-6F);
    const double epsilon = policy.gainCutoff;
    const std::vector<double> inputs{1., .3333333333333333};
    const std::vector<Edge> edges{{0, 0, 0, 2, epsilon + 1.e-15},
        {1, 1, 0, 2, .7}, {0, 2, 0, 2, -.5}, {0, 3, 0, 2, 3.}};
    const std::vector<Target> targets{{0., 1., .8}, {0., 1., .7}, {-1., 1., 2.}, {-1., 1., .3}, {1., 2., 2.}};
    std::vector<double> outputs(5, 99.), raw(5, 99.);
    require(run(inputs, edges, targets, policy, outputs, &raw) == EvaluationStatus::ok, "float parameter evaluation failed");
    same(outputs[0], 0., "coefficient cutoff ran before binary32 normalization");
    const double sum = static_cast<double>(static_cast<float>(inputs[1])) * static_cast<double>(.7F);
    same(raw[1], sum, "binary32 input/gain normalization changed");
    same(outputs[1], static_cast<double>(static_cast<float>(sum * static_cast<double>(.7F))), "final rounding or scaling changed");
    same(outputs[2], -1., "signed clamp changed");
    same(outputs[3], static_cast<double>(.3F), "scale was applied before clamp");
    same(outputs[4], 2., "omitted output did not clamp numeric zero");
    policy.parameters = Precision::binary64;
    require(run(inputs, edges, targets, policy, outputs) == EvaluationStatus::ok && outputs[0] != 0., "binary64 coefficient was unexpectedly pruned");
    outputs.assign(1, 99.);
    require(run({.5}, {{0, 0, 0, 2, 2.}}, {{-2., 3., -2.}}, {}, outputs) == EvaluationStatus::ok,
        "signed numeric scale rejected");
    same(outputs[0], -2., "numeric scale changed");
}

void legacyOrderedResults() {
    const std::vector<double> inputs{.17F, -.6F, 1.25F, .8F, -.3F, .4F, 1.F};
    const std::vector<Edge> edges{{0, 0, 0, 2, .7F}, {1, 1, 2, 2, .4F}, {2, 0, 4, 3, -.2F},
        {3, 1, 3, 2, .3F}, {4, 0, 1, 2, .6F}, {5, 1, 5, 2, .5F, .2F}, {6, 0, 0, 2, 1.e-6F}};
    const std::vector<Target> targets{{0., 1., .73F}, {0., 1., .42F}};
    std::vector<double> expected(2), outputs(2), raw(2);
    for (const auto& edge : edges)
        if (edge.gain > static_cast<double>(1.e-6F) || edge.gain < -static_cast<double>(1.e-6F))
            expected[edge.target] += contribution(inputs[edge.input], edge.gain, edge.function, edge.exponent, edge.constant);
    NumericPolicy policy;
    policy.result = Precision::binary32; policy.omitSmallGains = true; policy.gainCutoff = 1.e-6F;
    require(run(inputs, edges, targets, policy, outputs, &raw) == EvaluationStatus::ok, "ordered fixture failed");
    for (size_t index = 0; index < 2; ++index) {
        same(raw[index], expected[index], "legacy ordered raw sum changed");
        same(outputs[index], static_cast<double>(static_cast<float>(bounded(expected[index], 0., 1.) * targets[index].scale)),
            "legacy ordered float output changed");
    }
    // A cancellation whose result depends on retaining the original edge order.
    outputs.assign(1, 99.); raw.assign(1, 99.);
    require(run({1.}, {{0, 0, 0, 2, 1.e16}, {0, 0, 0, 2, 1.}, {0, 0, 0, 2, -1.e16}},
        {{-10., 10., 1.}}, {}, outputs, &raw) == EvaluationStatus::ok, "ordered cancellation failed");
    same(raw[0], 0., "ordered sum silently became compensated");
}

void sourceFreeConstants() {
    for (const auto reduction : {Reduction::ordered, Reduction::scaledCompensated}) {
        NumericPolicy policy; policy.reduction = reduction;
        std::array<Workspace, 1> work{};
        size_t inputReads{}, published{};
        require(evaluate(0, 2, 1,
            [&](size_t) noexcept { ++inputReads; return std::numeric_limits<double>::quiet_NaN(); },
            [](size_t index) noexcept { return Edge{999, 0, 5, 2, index ? -.5 : 2., .25}; },
            [](size_t) noexcept { return Target{}; }, work.data(), policy,
            [&](size_t, double value) noexcept { same(value, .375, "source-free constant sum changed"); ++published; }) == EvaluationStatus::ok,
            "source-free constant matrix rejected");
        require(inputReads == 0 && published == 1, "constant matrix read an absent numeric input");
    }
    std::array<Workspace, 1> work{};
    size_t inputReads{};
    require(evaluate(1, 2, 1,
        [&](size_t) noexcept { ++inputReads; return .5; },
        [](size_t index) noexcept { return index ? Edge{999, 0, 5, 2, 1., .25} : Edge{0, 0, 0, 2, .5}; },
        [](size_t) noexcept { return Target{}; }, work.data(), {},
        [](size_t, double value) noexcept { same(value, .5, "mixed constant/ordinary sum changed"); }) == EvaluationStatus::ok,
        "mixed constant/ordinary matrix rejected");
    require(inputReads == 2, "constant edge read an input in a mixed matrix");
}

void compensatedLegacyResults() {
    NumericPolicy policy;
    policy.reduction = Reduction::scaledCompensated;
    std::uint64_t random = 0x96ea3185d2c7b04fULL;
    const auto next = [&]() { random ^= random << 13; random ^= random >> 7; random ^= random << 17; return random; };
    for (unsigned fixture = 0; fixture < 2000; ++fixture) {
        std::vector<double> inputs(7);
        std::vector<Edge> edges;
        std::array<double, 7> terms{};
        for (size_t index = 0; index < 7; ++index) {
            inputs[index] = (static_cast<double>(next() % 2001) - 1000.) / 1000.;
            double below = (static_cast<double>(next() % 20001) - 10000.) / 173.;
            double above = (static_cast<double>(next() % 20001) - 10000.) / 211.;
            if (fixture % 11 == 0) { below *= 1.e300; above *= 1.e300; }
            if (fixture % 13 == 0) { below *= 1.e-300; above *= 1.e-300; }
            if (index == 6 && fixture % 2 == 0) { inputs[index] = 0.; below = above = 0.; }
            edges.push_back({index, 0, 6, 2, above, 0., below});
            terms[index] = endpointContribution(inputs[index], below, above);
        }
        const double minimum = -static_cast<double>(fixture % 31) / 7.;
        const double maximum = static_cast<double>(fixture % 29) / 9.;
        std::vector<double> outputs(1);
        require(run(inputs, edges, {{minimum, maximum, 1.}}, policy, outputs) == EvaluationStatus::ok, "compensated fixture failed");
        same(outputs[0], compensatedProjection(terms, minimum, maximum), "legacy compensated binary64 changed");
        policy.result = Precision::binary32;
        require(run(inputs, edges, {{minimum, maximum, 1.}}, policy, outputs) == EvaluationStatus::ok, "compensated float fixture failed");
        same(outputs[0], static_cast<double>(static_cast<float>(compensatedProjection(terms, minimum, maximum))),
            "legacy compensated final float changed");
        policy.result = Precision::binary64;
    }
    const double huge = std::numeric_limits<double>::max();
    std::vector<double> outputs(1, 99.);
    require(run({1.}, {{0, 0, 0, 2, huge}, {0, 0, 0, 2, huge}}, {{-1., 1., 1.}}, policy, outputs) == EvaluationStatus::ok,
        "scaled reduction overflowed before clamp");
    same(outputs[0], 1., "large positive sum failed to clamp");
    require(run({1.}, {{0, 0, 0, 2, huge}, {0, 0, 0, 2, -huge}, {0, 0, 0, 2, .25}},
        {{-1., 1., 1.}}, policy, outputs) == EvaluationStatus::ok, "large cancellation failed");
    same(outputs[0], compensatedProjection(std::array<double, 3>{huge, -huge, .25}, -1., 1.),
        "scaled compensation changed legacy cancellation rounding");
    require(std::abs(outputs[0] - .25) < 1.e-15, "scaled compensation lost representable cancellation");
    // The second compensated pass preserves per-target edge order without rescans.
    std::array<Workspace, 2> work{}; size_t reads{};
    require(evaluate(1, 3, 2, [](size_t) noexcept { return 1.; },
        [&](size_t i) noexcept { ++reads; return Edge{0, i % 2, 0, 2, .1}; },
        [](size_t) noexcept { return Target{}; }, work.data(), policy, [](size_t, double) noexcept {}) == EvaluationStatus::ok,
        "compensated multi-target evaluation failed");
    require(reads == 6, "compensated evaluator rescanned edges per target");
}

void endpointSmoothstepPolicies() {
    static_assert(signedEndpointSmoothstep == 7);
    require(projection_endpoint_smoothstep_properties() == 0, "portable endpoint-smoothstep properties failed");
    same(endpointSmoothstepContribution(0., -4., -3.), 0., "smooth endpoint neutral changed sign");
    same(endpointSmoothstepContribution(-0., -4., -3.), 0., "negative zero did not normalize to neutral");
    NumericPolicy policy;
    policy.parameters = Precision::binary32; policy.result = Precision::binary32;
    policy.omitSmallGains = true; policy.gainCutoff = static_cast<double>(1.e-6F);
    const double roundedInactive = policy.gainCutoff + 1.e-15;
    std::vector<double> outputs(1, 99.), raw(1, 99.);
    const Edge below{0, 0, signedEndpointSmoothstep, 2, roundedInactive, 0., -.25};
    require(run({.5}, {below}, {{-1., 1., 1.}}, policy, outputs, &raw) == EvaluationStatus::ok,
        "independent smooth endpoint cutoff rejected");
    same(outputs[0], 0., "inactive above coefficient leaked the negative endpoint");
    require(run({-.5}, {below}, {{-1., 1., 1.}}, policy, outputs, &raw) == EvaluationStatus::ok,
        "active below smooth endpoint rejected");
    same(outputs[0], -.125, "active below coefficient was omitted with inactive above");
    const Edge above{0, 0, signedEndpointSmoothstep, 2, .25, 0., roundedInactive};
    require(run({-.5}, {above}, {{-1., 1., 1.}}, policy, outputs) == EvaluationStatus::ok,
        "independent negative endpoint cutoff rejected");
    same(outputs[0], 0., "inactive below coefficient leaked the positive endpoint");
    require(run({.25}, {{0, 0, signedEndpointSmoothstep, 2, .7, 0., -.4}}, {{-1., 1., .3}}, policy, outputs) == EvaluationStatus::ok,
        "smooth endpoint precision policy rejected");
    const double expected = (.15625 * static_cast<double>(.7F)) * static_cast<double>(.3F);
    same(outputs[0], static_cast<double>(static_cast<float>(expected)), "smooth coefficient/final precision or scale changed");
    const double huge = std::numeric_limits<double>::max();
    policy = {}; policy.reduction = Reduction::scaledCompensated;
    require(run({1.}, {{0, 0, signedEndpointSmoothstep, 2, huge},
        {0, 0, signedEndpointSmoothstep, 2, -huge}, {999, 0, 5, 2, 1., .25}},
        {{-1., 1., 1.}}, policy, outputs) == EvaluationStatus::ok, "smooth endpoint extreme cancellation failed");
    same(outputs[0], compensatedProjection(std::array<double, 3>{huge, -huge, .25}, -1., 1.),
        "smooth endpoint terms changed compensated reduction");
    require(std::abs(outputs[0] - .25) < 1.e-15, "smooth cancellation lost the finite residual");
}

void validationAndPublication() {
    const double huge = std::numeric_limits<double>::max();
    const double nan = std::numeric_limits<double>::quiet_NaN();
    std::vector<double> outputs(2, 91.), raw(2, 92.);
    const auto rejected = [&](const std::vector<double>& inputs, const std::vector<Edge>& edges,
        const std::vector<Target>& targets, NumericPolicy policy, EvaluationStatus status) {
        outputs.assign(targets.size(), 91.); raw.assign(targets.size(), 92.);
        require(run(inputs, edges, targets, policy, outputs, &raw) == status, "wrong rejection status");
        for (const auto value : outputs) same(value, 91., "partial output published after failure");
        for (const auto value : raw) same(value, 92., "partial raw diagnostics published after failure");
    };
    rejected({1.}, {{0, 0, 0, 2, .2}, {1, 1, 0, 2, .3}}, {{}, {}}, {}, EvaluationStatus::invalid);
    rejected({nan}, {}, {{}}, {}, EvaluationStatus::invalid);
    NumericPolicy cutoff; cutoff.omitSmallGains = true; cutoff.gainCutoff = 1.;
    rejected({1.}, {{0, 0, 0, 2, 0., nan}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, 4, 0, 0.}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, 0, 2, .2, 0., 1.}}, {{}}, {}, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, signedEndpointSmoothstep, 3, 0., 0., 0.}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, signedEndpointSmoothstep, 2, 0., .1, 0.}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, signedEndpointSmoothstep, 2, 0., 0., nan}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, 8, 2, 0.}}, {{}}, cutoff, EvaluationStatus::invalid);
    rejected({1.}, {}, {{1., -1., 1.}}, {}, EvaluationStatus::invalid);
    NumericPolicy narrow; narrow.parameters = Precision::binary32;
    rejected({huge}, {}, {{}}, narrow, EvaluationStatus::invalid);
    rejected({1.}, {{0, 0, 0, 2, huge}, {0, 0, 0, 2, huge}}, {{}}, {}, EvaluationStatus::arithmetic);
    rejected({2.}, {{0, 0, 0, 2, huge}}, {{}}, {}, EvaluationStatus::arithmetic);
    NumericPolicy compensated; compensated.reduction = Reduction::scaledCompensated;
    rejected({1.}, {{0, 0, 0, 2, huge}, {0, 0, 0, 2, huge}}, {{}}, compensated, EvaluationStatus::arithmetic);
    NumericPolicy narrowResult; narrowResult.result = Precision::binary32;
    rejected({}, {}, {{huge, huge, 1.}}, narrowResult, EvaluationStatus::arithmetic);
    size_t published{};
    require(evaluate(0, 0, 0, [](size_t) noexcept { return 0.; }, [](size_t) noexcept { return Edge{}; },
        [](size_t) noexcept { return Target{}; }, nullptr, {}, [&](size_t, double) noexcept { ++published; }) == EvaluationStatus::ok,
        "empty zero-output matrix rejected");
    require(published == 0, "empty evaluator published a result");
    require(evaluate(0, 0, 1, [](size_t) noexcept { return 0.; }, [](size_t) noexcept { return Edge{}; },
        [](size_t) noexcept { return Target{}; }, nullptr, {}, [](size_t, double) noexcept {}) == EvaluationStatus::invalid,
        "null workspace accepted");
}
}

int main() {
    try {
        transformsAndOpaqueBindings();
        sparseCutoffPrecisionAndScale();
        legacyOrderedResults();
        sourceFreeConstants();
        compensatedLegacyResults();
        endpointSmoothstepPolicies();
        validationAndPublication();
        std::cout << "shared projection: transforms, sparse policies, exact legacy reductions, 2000 legacy endpoint fixtures, signed endpoint smoothstep properties, publication safety passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
