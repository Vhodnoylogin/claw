#pragma once
#include <stddef.h>

// Engine-independent projection primitives. No allocation, runtime or standard
// library calls: used by both native mods and freestanding WASM consumers.
namespace morph_matrix {
constexpr double bounded(double value, double low, double high) noexcept {
    return value < low ? low : value > high ? high : value;
}

constexpr double transform(double input, unsigned function, unsigned exponent, double constant) noexcept {
    switch (function) {
    case 0: return input;
    case 1: return input > 0.0 ? input : 0.0;
    case 2: return input < 0.0 ? -input : 0.0;
    case 3: {
        const double t = bounded(input, 0.0, 1.0);
        return (t * t) * (3.0 - 2.0 * t);
    }
    case 4: {
        const double t = bounded(input < 0.0 ? -input : input, 0.0, 1.0);
        double result = t;
        for (unsigned i = 1; i < exponent; ++i) result *= t;
        return input < 0.0 ? -result : result;
    }
    case 5: return constant;
    }
    return 0.0; // Function and exponent validated by the product's input schema.
}

constexpr double contribution(double input, double gain, unsigned function = 0,
                              unsigned exponent = 2, double constant = 0.0) noexcept {
    return transform(input, function, exponent, constant) * gain;
}

// Separate negative and positive gains describe independent endpoints at -1/+1.
constexpr double endpointContribution(double input, double below, double above) noexcept {
    return input < 0.0 ? contribution(input, below, 2) : contribution(input, above);
}

// Signed binary64 terms may include values near DBL_MAX.
// Scaling before addition keeps opposing terms representable until clamping.
template<class Terms>
double compensatedProjection(const Terms& terms, double minimum, double maximum) noexcept {
    const auto magnitude = [](double x) { return x < 0.0 ? -x : x; };
    double scale = 0.0;
    for (double term : terms)
        if (magnitude(term) > scale) scale = magnitude(term);
    if (scale == 0.0) return bounded(0.0, minimum, maximum);
    double sum = 0.0, compensation = 0.0;
    for (double term : terms) {
        const double x = term / scale, next = sum + x;
        compensation += magnitude(sum) >= magnitude(x) ? (sum - next) + x : (x - next) + sum;
        sum = next;
    }
    sum += compensation;
    if (sum <= minimum / scale) return minimum;
    if (sum >= maximum / scale) return maximum;
    return bounded(sum * scale, minimum, maximum);
}

// Names are opaque to the numerical layer. Callers bind their named input and
// output vectors to these indices; accessors avoid copying existing rule arrays.
enum class Reduction { ordered, scaledCompensated };
enum class Precision { binary64, binary32 };
enum class EvaluationStatus { ok, invalid, arithmetic };

struct NumericPolicy {
    Reduction reduction{Reduction::ordered};
    Precision parameters{Precision::binary64}, result{Precision::binary64};
    bool omitSmallGains{false};
    double gainCutoff{};
};
struct Edge {
    size_t input{}, target{};
    unsigned function{}, exponent{2};
    double gain{}, constant{}, negativeGain{};
    // Functions 0..5 have the transform() meanings above. Function 6 describes
    // signed endpoints: negativeGain below zero, gain at and above zero.
};
struct Target {
    double minimum{}, maximum{1.0}, scale{1.0};
};
struct Workspace {
    double sum{}, compensation{}, scale{}, value{}, rawSum{};
};

namespace detail {
constexpr double magnitude(double value) noexcept { return value < 0.0 ? -value : value; }
constexpr bool finite(double value) noexcept {
    return value >= -1.7976931348623157e308 && value <= 1.7976931348623157e308;
}
inline bool parameter(double& value, Precision precision) noexcept {
    if (!finite(value)) return false;
    if (precision == Precision::binary32) {
        // Check before conversion: an out-of-range floating conversion is not
        // a portable way to obtain an infinity.
        if (value < -3.40282346638528859812e38 || value > 3.40282346638528859812e38) return false;
        value = static_cast<double>(static_cast<float>(value));
    }
    return true;
}
inline bool edgeParameters(Edge& edge, Precision precision) noexcept {
    return edge.function <= 6 &&
        (edge.function == 4 ? edge.exponent >= 1 && edge.exponent <= 8 : edge.exponent == 2) &&
        parameter(edge.gain, precision) && parameter(edge.constant, precision) &&
        parameter(edge.negativeGain, precision) &&
        (edge.function == 5 || edge.constant == 0.0) &&
        (edge.function == 6 || edge.negativeGain == 0.0);
}
inline bool targetParameters(Target& target, Precision precision) noexcept {
    return parameter(target.minimum, precision) && parameter(target.maximum, precision) &&
        parameter(target.scale, precision) && target.minimum <= target.maximum;
}
inline bool active(Edge& edge, const NumericPolicy& policy) noexcept {
    if (!policy.omitSmallGains) return true;
    const bool positive = magnitude(edge.gain) > policy.gainCutoff;
    if (edge.function != 6) return positive;
    const bool negative = magnitude(edge.negativeGain) > policy.gainCutoff;
    if (!positive) edge.gain = 0.0;
    if (!negative) edge.negativeGain = 0.0;
    return positive || negative;
}
inline double edgeContribution(double input, const Edge& edge) noexcept {
    return edge.function == 6 ? endpointContribution(input, edge.negativeGain, edge.gain) :
        contribution(input, edge.gain, edge.function, edge.exponent, edge.constant);
}
}

// One evaluator for a sparse numeric input vector and output vector. Accessors
// must be stable, nonthrowing, and free of external effects. work has targetCount
// elements; it and optional rawSums must not overlap inputs/rules/outputs. Output
// callbacks only publish local numeric results and must not call an engine.
//
// O(inputCount + edgeCount + targetCount), no allocation or library/runtime calls.
// All validation and arithmetic finish before any output callback/rawSums write.
// Workspace/results are unavailable after an error. Ordered reduction rejects
// intermediate overflow. Scaled compensated reduction clamps before expanding
// a possibly unrepresentable sum; requesting rawSums additionally requires that
// sum to be representable. An empty matrix is valid, including zero outputs.
template<class InputAt, class EdgeAt, class TargetAt, class WriteOutput>
EvaluationStatus evaluate(size_t inputCount, size_t edgeCount, size_t targetCount,
    InputAt inputAt, EdgeAt edgeAt, TargetAt targetAt, Workspace* work,
    NumericPolicy policy, WriteOutput writeOutput, double* rawSums = nullptr) noexcept {
    if ((!work && targetCount) || (edgeCount && !targetCount) ||
        (policy.reduction != Reduction::ordered && policy.reduction != Reduction::scaledCompensated) ||
        (policy.parameters != Precision::binary64 && policy.parameters != Precision::binary32) ||
        (policy.result != Precision::binary64 && policy.result != Precision::binary32) ||
        !detail::parameter(policy.gainCutoff, policy.parameters) || policy.gainCutoff < 0.0)
        return EvaluationStatus::invalid;
    for (size_t index = 0; index < inputCount; ++index) {
        double value = inputAt(index);
        if (!detail::parameter(value, policy.parameters)) return EvaluationStatus::invalid;
    }
    for (size_t index = 0; index < targetCount; ++index) {
        Target target = targetAt(index);
        if (!detail::targetParameters(target, policy.parameters)) return EvaluationStatus::invalid;
        work[index] = {};
    }
    for (size_t index = 0; index < edgeCount; ++index) {
        Edge edge = edgeAt(index);
        if ((edge.function != 5 && edge.input >= inputCount) || edge.target >= targetCount ||
            !detail::edgeParameters(edge, policy.parameters)) return EvaluationStatus::invalid;
        if (!detail::active(edge, policy)) continue;
        double input = 0.0;
        if (edge.function != 5) {
            input = inputAt(edge.input);
            if (!detail::parameter(input, policy.parameters)) return EvaluationStatus::invalid;
        }
        const double term = detail::edgeContribution(input, edge);
        if (!detail::finite(term)) return EvaluationStatus::arithmetic;
        auto& current = work[edge.target];
        if (policy.reduction == Reduction::ordered) {
            current.sum += term;
            if (!detail::finite(current.sum)) return EvaluationStatus::arithmetic;
        } else if (detail::magnitude(term) > current.scale) {
            current.scale = detail::magnitude(term);
        }
    }
    if (policy.reduction == Reduction::scaledCompensated) {
        for (size_t index = 0; index < edgeCount; ++index) {
            Edge edge = edgeAt(index);
            // Accessors are stable; these are the parameters validated above.
            detail::edgeParameters(edge, policy.parameters);
            if (!detail::active(edge, policy) || work[edge.target].scale == 0.0) continue;
            double input = 0.0;
            if (edge.function != 5) {
                input = inputAt(edge.input);
                detail::parameter(input, policy.parameters);
            }
            auto& current = work[edge.target];
            const double x = detail::edgeContribution(input, edge) / current.scale;
            const double next = current.sum + x;
            current.compensation += detail::magnitude(current.sum) >= detail::magnitude(x) ?
                (current.sum - next) + x : (x - next) + current.sum;
            current.sum = next;
            if (!detail::finite(current.sum) || !detail::finite(current.compensation))
                return EvaluationStatus::arithmetic;
        }
    }
    for (size_t index = 0; index < targetCount; ++index) {
        Target target = targetAt(index);
        detail::targetParameters(target, policy.parameters);
        auto& current = work[index];
        if (policy.reduction == Reduction::ordered || current.scale == 0.0) {
            current.rawSum = current.sum;
            current.value = bounded(current.sum, target.minimum, target.maximum);
        } else {
            current.sum += current.compensation;
            if (!detail::finite(current.sum)) return EvaluationStatus::arithmetic;
            if (rawSums) {
                current.rawSum = current.sum * current.scale;
                if (!detail::finite(current.rawSum)) return EvaluationStatus::arithmetic;
            }
            if (current.sum <= target.minimum / current.scale) current.value = target.minimum;
            else if (current.sum >= target.maximum / current.scale) current.value = target.maximum;
            else current.value = bounded(current.sum * current.scale, target.minimum, target.maximum);
        }
        current.value *= target.scale;
        if (!detail::parameter(current.value, policy.result)) return EvaluationStatus::arithmetic;
    }
    for (size_t index = 0; index < targetCount; ++index) {
        if (rawSums) rawSums[index] = work[index].rawSum;
        writeOutput(index, work[index].value);
    }
    return EvaluationStatus::ok;
}
}
