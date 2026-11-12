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
