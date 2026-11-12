#include "Projection.h"

// Link with no entry, standard library, or imports. Both reductions and parameter
// precisions are instantiated rather than merely parsing the portable header.
extern "C" int projection_smoke(double dynamicInput) {
    using namespace morph_matrix;
    const double input[]{dynamicInput, .25};
    const Edge edges[]{{0, 0, 6, 2, .4, 0., -.8}, {1, 0, 0, 2, .3}, {999, 0, 5, 2, 1., .2}};
    Workspace workspace[1]{};
    double output{};
    NumericPolicy policy;
    policy.result = Precision::binary32;
    for (unsigned pass = 0; pass < 2; ++pass) {
        policy.reduction = pass ? Reduction::scaledCompensated : Reduction::ordered;
        policy.parameters = pass ? Precision::binary32 : Precision::binary64;
        if (evaluate(2, 3, 1, [&](size_t index) noexcept { return input[index]; },
            [&](size_t index) noexcept { return edges[index]; },
            [](size_t) noexcept { return Target{-1., 1., .5}; }, workspace, policy,
            [&](size_t, double value) noexcept { output = value; }) != EvaluationStatus::ok)
            return 1;
        if (output < -.063 || output > -.062) return 2;
    }
    return 0;
}

// Identical property runner is compiled for native and WASM. The JS harness only
// calls compiled exports; it does not implement the response or reduction.
extern "C" int projection_endpoint_smoothstep_properties() {
    using namespace morph_matrix;
    double inputs[2]{};
    Edge edges[]{{0, 0, signedEndpointSmoothstep, 2, 1., 0., 1.},
                 {1, 0, signedEndpointSmoothstep, 2, 0., 0., 0.}};
    Workspace work[1]{};
    double value{};
    Target target{-10., 10., 1.};
    NumericPolicy policy;
    const auto evaluateCurrent = [&]() noexcept {
        return evaluate(2, 2, 1, [&](size_t i) noexcept { return inputs[i]; },
            [&](size_t i) noexcept { return edges[i]; },
            [&](size_t) noexcept { return target; }, work, policy,
            [&](size_t, double result) noexcept { value = result; });
    };
    for (unsigned pass = 0; pass < 8; ++pass) {
        policy.reduction = pass & 1 ? Reduction::scaledCompensated : Reduction::ordered;
        policy.parameters = pass & 2 ? Precision::binary32 : Precision::binary64;
        policy.result = pass & 4 ? Precision::binary32 : Precision::binary64;
        target = {-10., 10., 1.}; edges[1].gain = edges[1].negativeGain = 0.;
        edges[0].gain = 3.; edges[0].negativeGain = -2.;
        inputs[0] = 0.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != 0. || 1. / value < 0.) return 10;
        inputs[0] = -0.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != 0. || 1. / value < 0.) return 11;
        inputs[0] = -1.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != -2.) return 12;
        inputs[0] = 1.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != 3.) return 13;
        inputs[0] = -9.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != -2.) return 14;
        inputs[0] = 9.;
        if (evaluateCurrent() != EvaluationStatus::ok || value != 3.) return 15;
        edges[0].gain = 4.; edges[0].negativeGain = -8.; inputs[0] = .25;
        if (evaluateCurrent() != EvaluationStatus::ok || value != .625) return 16; // h(1/4)=5/32.
        inputs[0] = -.25;
        if (evaluateCurrent() != EvaluationStatus::ok || value != -1.25) return 17;
        // Endpoint coefficients may oppose each other; bounding is once per final output.
        edges[0].gain = 4.; edges[1].gain = -3.; inputs[0] = inputs[1] = .5;
        target = {0., 1., .75};
        if (evaluateCurrent() != EvaluationStatus::ok || value != .375) return 18;
    }
    policy = {}; target = {-10., 10., 1.};
    edges[1].gain = edges[1].negativeGain = 0.;
    edges[0].gain = 3.; edges[0].negativeGain = -2.;
    double previous = -2.;
    for (int i = -1024; i <= 1024; ++i) {
        inputs[0] = static_cast<double>(i) / 1024.;
        if (evaluateCurrent() != EvaluationStatus::ok || value < previous || value < -2. || value > 3.) return 19;
        previous = value;
    }
    // A linear or signed-smoothstep implementation has nonzero slope at a join
    // or fails the two independent endpoint values. Check both sides of all joins.
    edges[0].gain = edges[0].negativeGain = 1.;
    const double step = 1. / 1048576.;
    const double joins[]{step, -step, 1. - step, -1. + step};
    for (double x : joins) {
        inputs[0] = x;
        if (evaluateCurrent() != EvaluationStatus::ok) return 20;
        const double delta = (x < -.5 || x > .5) ? 1. - value : value;
        if (delta < 0. || delta / step > .00001) return 21;
    }
    const double maximum = 1.7976931348623157e308;
    inputs[0] = maximum; edges[0].gain = .25;
    if (evaluateCurrent() != EvaluationStatus::ok || value != .25) return 22;
    inputs[0] = -maximum; edges[0].negativeGain = -.75;
    if (evaluateCurrent() != EvaluationStatus::ok || value != -.75) return 23;
    return 0;
}
