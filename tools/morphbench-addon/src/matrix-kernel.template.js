/* Generated browser adapter for the same MatrixKernel.cpp compiled into CLAW. */
;(function (global) {
  "use strict";
  const encoded = "__CLAW_WASM_BASE64__";
  const bytes = typeof Buffer !== "undefined" ? Uint8Array.from(Buffer.from(encoded, "base64")) :
    Uint8Array.from(atob(encoded), char => char.charCodeAt(0));
  let instance;
  try { instance = new WebAssembly.Instance(new WebAssembly.Module(bytes), {}); }
  catch (error) {
    throw new Error("CLAW shared computation kernel could not start. This Morphbench host must permit packaged WebAssembly. " + error.message);
  }
  const exports = instance.exports;
  const functions = Object.freeze({ linear: 0, positive: 1, negative: 2, smoothstep: 3, power: 4, constant: 5 });
  const base = (Number(exports.__heap_base.value) + 7) & ~7;
  const ruleBytes = 28, maxRules = 128, maxTargets = 64;
  const outputs = base + ruleBytes * maxRules;
  const sums = outputs + 4 * maxTargets;
  const required = sums + 8 * maxTargets;
  if (exports.memory.buffer.byteLength < required) exports.memory.grow(Math.ceil((required - exports.memory.buffer.byteLength) / 65536));
  function evaluate(rules, targetCount) {
    if (!Array.isArray(rules) || rules.length < 1 || rules.length > maxRules ||
        !Number.isInteger(targetCount) || targetCount < 1 || targetCount > maxTargets) throw new Error("Invalid shared-kernel dimensions.");
    const view = new DataView(exports.memory.buffer);
    rules.forEach((rule, index) => {
      const pointer = base + index * ruleBytes;
      if (!Object.prototype.hasOwnProperty.call(functions, rule.function) ||
          !Number.isInteger(rule.target) || rule.target < 0 || rule.target >= targetCount) throw new Error("Invalid shared-kernel rule.");
      view.setUint32(pointer, rule.target, true);
      view.setUint32(pointer + 4, functions[rule.function], true);
      view.setUint32(pointer + 8, rule.exponent === undefined ? 2 : rule.exponent, true);
      view.setFloat32(pointer + 12, rule.input, true);
      view.setFloat32(pointer + 16, rule.gain, true);
      view.setFloat32(pointer + 20, rule.cap, true);
      view.setFloat32(pointer + 24, rule.value === undefined ? 0 : rule.value, true);
    });
    const status = exports.claw_matrix_evaluate(base, rules.length, outputs, sums, targetCount);
    if (status !== 0) throw new Error("Shared CLAW matrix kernel rejected the calculation (" + status + ").");
    return {
      values: Array.from({length: targetCount}, (_, index) => view.getFloat32(outputs + index * 4, true)),
      rawSums: Array.from({length: targetCount}, (_, index) => view.getFloat64(sums + index * 8, true)),
      clamped: Array.from({length: targetCount}, (_, index) => exports.claw_matrix_clamp(view.getFloat64(sums + index * 8, true))),
      details: rules.map((rule, index) => ({
        transformed: exports.claw_matrix_transform(view.getFloat32(base + index * ruleBytes + 12,true), functions[rule.function], rule.exponent === undefined ? 2 : rule.exponent, view.getFloat32(base + index * ruleBytes + 24,true)),
        contribution: exports.claw_matrix_contribution(base + index * ruleBytes)
      }))
    };
  }
  global.CLAWMatrixKernel = Object.freeze({ evaluate, sourceSha256: "__CLAW_SOURCE_SHA256__", wasmSha256: "__CLAW_WASM_SHA256__", abi: 1 });
  if (typeof module !== "undefined" && module.exports) module.exports = global.CLAWMatrixKernel;
})(typeof window !== "undefined" ? window : globalThis);
