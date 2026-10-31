"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const cp = require("node:child_process");
// Or preload the generated module with node --require <external>/matrix-kernel.js.
if (process.env.CLAW_MATRIX_KERNEL) require(path.resolve(process.env.CLAW_MATRIX_KERNEL));
const core = require("../src/core.js");
const base = rules => ({ id: "CLAW.Matrix.Test", family: "HIMBO", version: "5.8", sex: "male", calibration: "authored-test", rules });
const edge = (fn, extra = {}) => ({ source: fn === "constant" ? "" : "Human", target: "CLAWArmLean", gain: 1, cap: 1, function: fn, ...extra });

test("coefficient/function matrices retain ordered cancellation and constant independence", () => {
  const matrix = base([edge("constant", { value: .4, gain: .5 }), edge("negative", { gain: .5 })]);
  const result = core.evaluateMatrix(matrix, { Human: -.5, Other: 9 });
  assert.equal(result.values.CLAWArmLean, Math.fround(Math.fround(.4) * .5 + .25));
  assert.deepEqual(result.unmapped, ["Other"]);
  assert.equal(result.rows.find(row => row.target === "CLAWArmLean").contributions[0].transformed, Math.fround(.4));
  const fixed = base([edge("constant", { value: .4 })]);
  assert.deepEqual(core.evaluateMatrix(fixed, {}).values, core.evaluateMatrix(fixed, { Human: -1e30 }).values);
  assert.equal(core.validateMatrix(fixed).version, "5.8");
  assert.match(core.exportMatrix(fixed), /source="".*function="constant" value="0.4000000059604645"/);
});

test("bounded nonlinear functions are deterministic and power preserves negative sign", () => {
  const contribution = (fn, x, extra = {}) => core.evaluateMatrix(base([edge(fn, extra)]), { Human: x }).rows.find(row => row.target === "CLAWArmLean").contributions[0].transformed;
  assert.equal(contribution("power", -.5, { exponent: 2 }), -.25);
  assert.equal(contribution("power", -2, { exponent: 8 }), -1);
  assert.equal(contribution("smoothstep", .25), .15625);
  assert.equal(contribution("smoothstep", 2), 1);
  assert.equal(contribution("smoothstep", -2), 0);
  assert.equal(contribution("positive", -.5), 0);
  assert.equal(contribution("negative", -.5), .5);
});

test("unknown functions and ambiguous parameters are rejected", () => {
  for (const rule of [edge("eval"), edge("power"), edge("power", { exponent: 2.5 }), edge("power", { exponent: 9 }),
    edge("linear", { exponent: 2 }), edge("linear", { value: .4 }), edge("constant"), edge("constant", { source: "Human", value: .4 }),
    edge("constant", { value: Infinity }), edge("negative", { source: "" })]) assert.throws(() => core.validateMatrix(base([rule])));
  assert.throws(() => core.validateMatrix(base([edge("positive"), edge("negative")])));
});

if (process.argv[2] && process.argv[3] && process.argv[4]) {
  const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"));
  const native = path.resolve(process.argv[3]), external = path.resolve(process.argv[4]);
  fs.mkdirSync(external, { recursive: true });
  let cases = 0, values = 0;
  const compare = (matrix, human, label) => {
    const filename = path.join(external, "parity-matrix.xml");
    fs.writeFileSync(filename, core.exportMatrix(matrix));
    const input = Object.entries(human).map(([name, value]) => `${name}\t${Math.fround(value)}`).join("\n") + "\n";
    const result = cp.spawnSync(native, ["matrix", filename, matrix.id], { input, encoding: "utf8" });
    assert.equal(result.status, 0, `${label}: ${result.stderr}`);
    const observed = JSON.parse(result.stdout), expected = core.evaluateMatrix(matrix, human).values;
    for (const [target, value] of Object.entries(expected)) {
      assert.equal(Math.fround(observed[target]), value, `${label} ${target}`); values++;
    }
    cases++;
  };
  test("native C++ and JavaScript match float32 outputs for every function, extremes, ordered cancellation and real fixture matrices", () => {
    const functions = ["linear", "positive", "negative", "smoothstep", "power", "constant"];
    const inputs = [-3.4028234663852886e38, -2, -.75, -.25, -1e-30, 0, 1e-30, .25, .75, 2, 3.4028234663852886e38];
    for (const fn of functions) for (const x of inputs) {
      const extra = fn === "power" ? { exponent: 3 } : fn === "constant" ? { value: .37 } : {};
      compare(base([edge(fn, { ...extra, gain: .79, cap: .81 })]), { Human: x }, `${fn}:${x}`);
    }
    for (let exponent = 1; exponent <= 8; exponent++) compare(base([edge("power", { exponent, gain: -.71, cap: .65 })]), { Human: -.37 }, `power${exponent}`);
    let random = 0x5eed1234;
    const next = () => { random ^= random << 13; random ^= random >>> 17; random ^= random << 5; return (random >>> 0) / 4294967296; };
    for (let iteration = 0; iteration < 128; iteration++) {
      const rules = [], human = {};
      for (let i = 0; i < 18; i++) {
        const fn = functions[i % functions.length], source = fn === "constant" ? "" : `H${i}`;
        const target = ["CLAWArmLean", "CLAWTorsoGirth", "CLAWLegThighLean"][i % 3];
        // At most one constant bias per target.
        if (fn === "constant" && rules.some(rule => rule.source === "" && rule.target === target)) continue;
        const rule = { source, target, gain: (next() - .5) * 3, cap: .83, function: fn };
        if (fn === "power") rule.exponent = 1 + Math.floor(next() * 8);
        if (fn === "constant") rule.value = (next() - .5) * 2;
        else human[source] = (next() - .5) * 4;
        rules.push(rule);
      }
      compare(base(rules), human, `seeded${iteration}`);
    }
    const fixturePath = process.argv[5];
    const fixtureResults = [];
    if (fixturePath) for (const fixture of JSON.parse(fs.readFileSync(path.resolve(fixturePath), "utf8"))) {
      const matrix = core.getProfile(catalog, fixture.profileId);
      compare(matrix, fixture.humanValues, fixture.fixture);
      fixtureResults.push({ fixture: fixture.fixture, profile: matrix.id, values: core.evaluateMatrix(matrix, fixture.humanValues).values });
    }
    fs.writeFileSync(path.join(external, "native-js-parity.json"), JSON.stringify({ cases, float32ValuesCompared: values, bitEqual: true, fixtureResults }, null, 2) + "\n");
  });
}
