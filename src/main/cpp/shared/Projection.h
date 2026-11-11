#pragma once

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

// Living Physique accepts signed binary64 coefficients, including near DBL_MAX.
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
}
