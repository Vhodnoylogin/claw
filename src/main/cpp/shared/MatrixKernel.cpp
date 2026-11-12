#include "MatrixKernel.h"
#include "Projection.h"

static_assert(sizeof(CLAWMatrixRule) == 28);
static_assert(alignof(CLAWMatrixRule) == 4);

namespace {
bool finiteFloat(float value) { return value >= -3.40282346638528859812e38F && value <= 3.40282346638528859812e38F; }
}

extern "C" double claw_matrix_transform(double input, uint32_t function, uint32_t exponent, float value) {
    return morph_matrix::transform(input, function, exponent, value);
}

extern "C" double claw_matrix_contribution(const CLAWMatrixRule* rule) {
    if (!claw_matrix_gain_active(rule->gain)) return 0.0;
    return morph_matrix::contribution(rule->input, rule->gain, rule->function, rule->exponent, rule->value);
}

extern "C" float claw_matrix_gain_epsilon(void) { return 1.0e-6F; }
extern "C" uint32_t claw_matrix_max_rules(void) { return CLAW_MATRIX_MAX_RULES; }
extern "C" uint32_t claw_matrix_max_targets(void) { return CLAW_MATRIX_MAX_TARGETS; }

extern "C" int claw_matrix_gain_active(float gain) {
    const float epsilon = claw_matrix_gain_epsilon();
    return finiteFloat(gain) && (gain > epsilon || gain < -epsilon);
}

extern "C" int32_t claw_matrix_source_kind(const char* name, uint32_t length) {
    if (!name || !length || length > 160 || name[0] <= 32 || name[length - 1] <= 32) return -1;
    for (uint32_t index = 0; index < length; ++index)
        if (static_cast<unsigned char>(name[index]) < 32 || static_cast<unsigned char>(name[index]) >= 127) return -1;
    const auto matches = [&](const char* value, bool prefix, bool fold) {
        uint32_t index{};
        for (; value[index]; ++index) {
            if (index >= length) return false;
            const char ch = fold && name[index] >= 'A' && name[index] <= 'Z' ? static_cast<char>(name[index] + ('a' - 'A')) : name[index];
            if (ch != value[index]) return false;
        }
        return prefix || index == length;
    };
    if (matches("$actor.", true, true)) return matches("$actor.weight", false, false) ? 1 : -1;
    if (!matches("$human.", true, true)) return 0;
    if (matches("$human.height", false, false)) return 3;
    constexpr const char* channels[]{"$human.face.noseLength", "$human.face.jawWidth", "$human.face.jawForward",
        "$human.face.chinWidth", "$human.face.chinForward"};
    for (const auto* value : channels)
        if (matches(value, false, false)) return 2;
    return -1;
}

extern "C" uint32_t claw_matrix_source_value_valid(int32_t kind, float value) {
    return finiteFloat(value) && (kind == 0 || (kind == 1 && value >= 0.F && value <= 1.F) ||
        (kind == 2 && value != 3.40282346638528859812e38F) || (kind == 3 && value > 0.F));
}
extern "C" float claw_matrix_source_neutral(int32_t kind) { return kind == 3 ? 1.F : 0.F; }

extern "C" double claw_matrix_clamp(double value) {
    return morph_matrix::bounded(value, 0.0, 1.0);
}

extern "C" int claw_matrix_evaluate(const CLAWMatrixRule* rules, uint32_t count,
    float* outputs, double* rawSums, uint32_t targetCount) {
    if ((!rules && count) || ((!outputs || !rawSums) && targetCount) || count > CLAW_MATRIX_MAX_RULES || targetCount > CLAW_MATRIX_MAX_TARGETS || (!targetCount && count)) return 1;
    for (uint32_t target = 0; target < targetCount; ++target) { outputs[target] = 0.F; rawSums[target] = 0.0; }
    float caps[CLAW_MATRIX_MAX_TARGETS]{};
    for (uint32_t index = 0; index < count; ++index) {
        const auto& rule = rules[index];
        if (rule.target >= targetCount || rule.function > 5 ||
            (rule.function == 4 ? rule.exponent < 1 || rule.exponent > 8 : rule.exponent != 2) ||
            !finiteFloat(rule.input) || !finiteFloat(rule.gain) || !finiteFloat(rule.cap) || !finiteFloat(rule.value) ||
            rule.cap <= 0.F || rule.cap > 1.F || (rule.function != 5 && rule.value != 0.F)) return 2;
        if (!claw_matrix_gain_active(rule.gain)) continue;
        if (caps[rule.target] != 0.F && caps[rule.target] != rule.cap) return 3;
        caps[rule.target] = rule.cap;
    }
    morph_matrix::Workspace work[CLAW_MATRIX_MAX_TARGETS];
    const morph_matrix::NumericPolicy policy{morph_matrix::Reduction::ordered,
        morph_matrix::Precision::binary32, morph_matrix::Precision::binary32,
        true, claw_matrix_gain_epsilon()};
    const auto status = morph_matrix::evaluate(count, count, targetCount,
        [&](size_t index) noexcept { return static_cast<double>(rules[index].input); },
        [&](size_t index) noexcept {
            const auto& rule = rules[index];
            return morph_matrix::Edge{index, rule.target, rule.function, rule.exponent,
                rule.gain, rule.value, 0.0};
        },
        [&](size_t target) noexcept { return morph_matrix::Target{0.0, 1.0, caps[target]}; },
        work, policy,
        [&](size_t target, double value) noexcept { outputs[target] = static_cast<float>(value); }, rawSums);
    return status == morph_matrix::EvaluationStatus::ok ? 0 :
        status == morph_matrix::EvaluationStatus::invalid ? 2 : 4;
}
