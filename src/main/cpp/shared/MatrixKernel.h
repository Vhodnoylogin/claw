#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

// Stable native/WASM ABI: seven 4-byte fields, 28 bytes, alignment 4.
typedef struct CLAWMatrixRule {
    uint32_t target;
    uint32_t function; // linear=0, positive=1, negative=2, smoothstep=3, power=4, constant=5
    uint32_t exponent; // 1..8 for power, canonical default 2 otherwise
    float input;
    float gain;
    float cap;
    float value;       // constant only; zero otherwise
} CLAWMatrixRule;

// Caller validates the rule before requesting contribution diagnostics.
double claw_matrix_transform(double input, uint32_t function, uint32_t exponent, float value);
double claw_matrix_contribution(const CLAWMatrixRule* rule);
double claw_matrix_clamp(double value);

// No allocation, libraries, locale, engine or browser dependencies. Buffers must
// be nonoverlapping. Ordered sum, final clamp then cap, one float32 output round.
// Returns 0 on success; 1 bounds/pointers; 2 invalid rule; 3 inconsistent cap;
// 4 nonfinite arithmetic. Outputs are unavailable after any error.
int claw_matrix_evaluate(const CLAWMatrixRule* rules, uint32_t count,
    float* outputs, double* rawSums, uint32_t targetCount);

#ifdef __cplusplus
}
#endif
