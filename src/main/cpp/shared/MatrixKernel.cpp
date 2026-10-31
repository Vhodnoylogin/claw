#include "MatrixKernel.h"

static_assert(sizeof(CLAWMatrixRule) == 28);
static_assert(alignof(CLAWMatrixRule) == 4);

namespace {
bool finiteFloat(float value) { return value >= -3.40282346638528859812e38F && value <= 3.40282346638528859812e38F; }
bool finiteDouble(double value) { return value >= -1.7976931348623157e308 && value <= 1.7976931348623157e308; }
}

extern "C" double claw_matrix_transform(double input, uint32_t function, uint32_t exponent, float value) {
    switch (function) {
    case 0: return input;
    case 1: return input > 0.0 ? input : 0.0;
    case 2: return input < 0.0 ? -input : 0.0;
    case 3: {
        const double t = input < 0.0 ? 0.0 : input > 1.0 ? 1.0 : input;
        return (t * t) * (3.0 - 2.0 * t);
    }
    case 4: {
        const double absolute = input < 0.0 ? -input : input;
        const double t = absolute > 1.0 ? 1.0 : absolute;
        double result = t;
        for (uint32_t index = 1; index < exponent; ++index) result *= t;
        return input < 0.0 ? -result : result;
    }
    case 5: return value;
    }
    return 0.0; // Evaluator rejects unknown function codes before calling.
}

extern "C" double claw_matrix_contribution(const CLAWMatrixRule* rule) {
    if (!claw_matrix_gain_active(rule->gain)) return 0.0;
    return claw_matrix_transform(rule->input, rule->function, rule->exponent, rule->value) * static_cast<double>(rule->gain);
}

extern "C" float claw_matrix_gain_epsilon(void) { return 1.0e-6F; }

extern "C" int claw_matrix_gain_active(float gain) {
    const float epsilon = claw_matrix_gain_epsilon();
    return finiteFloat(gain) && (gain > epsilon || gain < -epsilon);
}

extern "C" double claw_matrix_clamp(double value) {
    return value < 0.0 ? 0.0 : value > 1.0 ? 1.0 : value;
}

extern "C" int claw_matrix_evaluate(const CLAWMatrixRule* rules, uint32_t count,
    float* outputs, double* rawSums, uint32_t targetCount) {
    if ((!rules && count) || ((!outputs || !rawSums) && targetCount) || count > 128 || targetCount > 64 || (!targetCount && count)) return 1;
    for (uint32_t target = 0; target < targetCount; ++target) { outputs[target] = 0.F; rawSums[target] = 0.0; }
    for (uint32_t index = 0; index < count; ++index) {
        const auto& rule = rules[index];
        if (rule.target >= targetCount || rule.function > 5 ||
            (rule.function == 4 ? rule.exponent < 1 || rule.exponent > 8 : rule.exponent != 2) ||
            !finiteFloat(rule.input) || !finiteFloat(rule.gain) || !finiteFloat(rule.cap) || !finiteFloat(rule.value) ||
            rule.cap <= 0.F || rule.cap > 1.F || (rule.function != 5 && rule.value != 0.F)) return 2;
        if (!claw_matrix_gain_active(rule.gain)) continue;
        if (outputs[rule.target] != 0.F && outputs[rule.target] != rule.cap) return 3;
        outputs[rule.target] = rule.cap;
        rawSums[rule.target] += claw_matrix_contribution(&rule);
        if (!finiteDouble(rawSums[rule.target])) return 4;
    }
    for (uint32_t target = 0; target < targetCount; ++target) {
        const double clamped = claw_matrix_clamp(rawSums[target]);
        outputs[target] = static_cast<float>(clamped * static_cast<double>(outputs[target]));
    }
    return 0;
}
