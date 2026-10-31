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

// Normalize a parameter to float32 before calling. Inactive coefficients are
// absent edges, independently of their current input or contribution. Shared
// exports keep native, WASM diagnostics and interchange normalization identical.
float claw_matrix_gain_epsilon(void);
int claw_matrix_gain_active(float gain);

// Source binding is shared with the offline editor. Printable ASCII names are
// ordinary morphs (0), except the exact explicit scalar "$actor.weight" (1).
// The entire ASCII-casefolded "$actor." namespace is reserved: unsupported or
// noncanonical spellings and malformed names return -1. Targets require kind0.
int32_t claw_matrix_source_kind(const char* name, uint32_t length);
// Normalized actor weight must be finite0..1; ordinary applied morphs may be
// signed or above1. This validates inputs, without multiplying any other value.
uint32_t claw_matrix_source_value_valid(int32_t kind, float value);

// No allocation, libraries, locale, engine or browser dependencies. Buffers must
// be nonoverlapping. Ordered sum, final clamp then cap, one float32 output round.
// A zero-rule matrix is valid and neutral; rules may be null only when count=0.
// Invalid finite/function parameters are rejected even on inactive rules, while
// inactive rules do not own a target cap or enter the ordered sum.
// Returns 0 on success; 1 bounds/pointers; 2 invalid rule; 3 inconsistent cap;
// 4 nonfinite arithmetic. Outputs are unavailable after any error.
int claw_matrix_evaluate(const CLAWMatrixRule* rules, uint32_t count,
    float* outputs, double* rawSums, uint32_t targetCount);

#ifdef __cplusplus
}
#endif
