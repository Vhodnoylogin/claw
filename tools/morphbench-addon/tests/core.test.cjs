"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../src/core.js");
if (!process.argv[2]) throw new Error("Pass the external build's catalog.json path.");
const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"));
const male = "CLAW.HIMBO.5.8.Geometry1", female = "CLAW.3BA.2.48.Geometry1";
const belly = "CLAWTorsoBellyRound", girth = "CLAWTorsoGirth", chest = "CLAWTorsoChestSize";
const clone = value => JSON.parse(JSON.stringify(value));
const approximate = (actual, expected, tolerance = 1e-7) => assert.ok(Math.abs(actual - expected) <= tolerance,
  `${actual} differs from ${expected}`);

function host(profileId, missing) {
  const names = Object.keys(core.evaluate(catalog, profileId, {}).values).filter(name => name !== missing);
  const values = { CLAWHeadEarSize: 0.73, CLAWTailLength: 0.4, unrelated: -0.2 };
  const calls = [];
  const sdk = { async request(method, params) {
    calls.push({ method, params });
    if (method === "scene.get") return { open: true, names: { nif: "body.nif", tri: "body.tri" } };
    if (method === "morphs.get") return { names, values: { ...values } };
    if (method === "morphs.set") {
      for (const name of Object.keys(params.values)) assert.ok(names.includes(name));
      Object.assign(values, params.values);
      return { names, values: { ...values } };
    }
    throw new Error("Unexpected SDK call: " + method);
  } };
  return { sdk, names, values, calls };
}

test("recorded male heavy sources reproduce Belly ~0.7963179 and retain contribution detail", () => {
  const result = core.evaluate(catalog, male, { BellyPot: .5, BellyRounder: .2, TorsoBelly: .6, TorsoBellyChub: .35 });
  approximate(result.values[belly], .7963179);
  const row = result.rows.find(item => item.target === belly);
  assert.equal(row.contributions.filter(item => item.input !== 0).length, 4);
  approximate(row.contributions.reduce((sum, item) => sum + item.contribution, 0), row.rawSum, 1e-15);
});

test("female 3BA combined Belly and BigBelly saturate at 1", () => {
  const result = core.evaluate(catalog, female, { Belly: .7, BigBelly: .7 });
  assert.equal(result.values[belly], 1);
  assert.ok(result.rows.find(row => row.target === belly).rawSum > 1);
});

test("male PecsMass and PecsSize combine to Chest .3", () => {
  approximate(core.evaluate(catalog, male, { PecsMass: .25, PecsSize: .5 }).values[chest], .3);
});

test("cap multiplies the clamped sum, with both below-cap and saturated cases", () => {
  const small = core.evaluate(catalog, male, { BodyMass: .1 });
  const row = small.rows.find(item => item.target === girth);
  assert.ok(row.rawSum > .1 && row.rawSum < 1);
  approximate(row.value, row.rawSum * .25);
  assert.notEqual(row.value, Math.min(row.rawSum, .25));
  const saturated = core.evaluate(catalog, male, { BodyMass: 100 });
  assert.equal(saturated.values[girth], .25);
});

test("neutral, explicit zero and negative-source clipping retain zero targets", () => {
  const neutral = core.evaluate(catalog, male, {}).values;
  assert.ok(Object.keys(neutral).length > 5);
  assert.ok(Object.values(neutral).every(value => value === 0));
  assert.deepEqual(core.evaluate(catalog, male, { BellyPot: 0 }).values, neutral);
  assert.equal(core.evaluate(catalog, male, { BellyPot: -1 }).values[belly], 0);
  assert.equal(core.evaluate(catalog, male, { Lean: 1 }).values[belly], 0);
});

test("native neutral baseline clears body names absent from a profile's rules", async () => {
  const result = core.evaluate(catalog, male, {});
  const neck = result.rows.find(row => row.target === "CLAWTorsoNeckGirth");
  assert.equal(neck.value, 0);
  assert.equal(neck.contributions.length, 0);
  assert.equal(result.values.CLAWTorsoBackWide, 0);
  assert.equal(Object.hasOwn(result.values, "CLAWTorsoBreastSize"), false);
  const mock = host(male);
  mock.values.CLAWTorsoNeckGirth = .9;
  mock.values.CLAWTorsoBackWide = .7;
  await core.writeLinked(mock.sdk, catalog, male, { PecsSize: .5 }, false, []);
  assert.equal(mock.values.CLAWTorsoNeckGirth, 0);
  assert.equal(mock.values.CLAWTorsoBackWide, 0);
  assert.equal(mock.values.CLAWHeadEarSize, .73);
});

test("input permits finite extrapolation/negative values and reports unmapped aggregate names", () => {
  const result = core.evaluate(catalog, male, { BellyPot: 2, Lean: -.25, HumanOther: .5 });
  assert.equal(result.values[belly], 1);
  assert.deepEqual(result.unmapped, ["HumanOther"]);
});

test("input rejects NaN, infinity, float overflow, nonnumeric, unsafe and malformed maps", () => {
  for (const input of [null, [], 1, "{}", { BellyPot: NaN }, { BellyPot: Infinity },
    { BellyPot: -Infinity }, { BellyPot: 1e39 }, { BellyPot: "1" }, { BellyPot: true },
    { "bad\nname": .2 }, { " BellyPot": .2 }, { ["é".repeat(81)]: 0 }, { CLAWTorsoGirth: .1 },
    JSON.parse('{"__proto__":0}'), { constructor: 0 }, { prototype: 0 }]) {
    assert.throws(() => core.validateHuman(input));
  }
  for (const text of ["{", '{"BellyPot":NaN}', '{"BellyPot":1e999}']) assert.throws(() => core.parseHuman(text));
});

test("unknown or unsafe profile and malformed mappings reject instead of falling back", () => {
  for (const id of ["HIMBO", "__proto__", "constructor", male + " ", ""]) {
    assert.throws(() => core.evaluate(catalog, id, {}));
  }
  const invalid = clone(catalog);
  invalid.profiles.find(profile => profile.id === male).rules[0].target = "CLAWHeadEarSize";
  assert.throws(() => core.evaluate(invalid, male, {}));
  const duplicate = clone(catalog);
  duplicate.profiles[0].rules.push(duplicate.profiles[0].rules[0]);
  assert.throws(() => core.evaluate(duplicate, female, {}));
});

test("apply validates the loaded model/morphs then makes one merge batch, preserving unrelated controls", async () => {
  const mock = host(male);
  const response = await core.writeLinked(mock.sdk, catalog, male, { PecsMass: .25, PecsSize: .5 }, false, []);
  assert.deepEqual(mock.calls.map(call => call.method), ["scene.get", "morphs.get", "morphs.set"]);
  approximate(mock.values[chest], .3);
  assert.equal(mock.values.CLAWHeadEarSize, .73);
  assert.equal(mock.values.CLAWTailLength, .4);
  assert.equal(mock.values.unrelated, -.2);
  assert.equal(mock.values[belly], 0);
  assert.equal(Object.keys(response.values).length, mock.names.length);
});

test("one missing model target rejects the complete apply and reset without writes", async () => {
  for (const reset of [false, true]) {
    const mock = host(male, belly);
    await assert.rejects(core.writeLinked(mock.sdk, catalog, male, { BodyMass: 1 }, reset, []), /missing linked body targets/);
    assert.deepEqual(mock.calls.map(call => call.method), ["scene.get", "morphs.get"]);
    assert.equal(mock.values[chest], undefined);
  }
});

test("closed model and malformed host morph list reject without a write", async () => {
  const mock = host(male);
  mock.sdk.request = async method => method === "scene.get" ? { open: false } : { names: [] };
  await assert.rejects(core.writeLinked(mock.sdk, catalog, male, {}, false, []), /Open a CLAW body/);
  assert.throws(() => core.validateModel({ open: true, names: { nif: "body.nif" } }, { names: [42] }, []));
});

test("reset writes only linked body zeros, including a previously written female target", async () => {
  const mock = host(female);
  mock.values.CLAWTorsoBreastSize = .8;
  await core.writeLinked(mock.sdk, catalog, male, {}, true, ["CLAWTorsoBreastSize"]);
  const writes = mock.calls.filter(call => call.method === "morphs.set");
  assert.equal(writes.length, 1);
  assert.ok(Object.values(writes[0].params.values).every(value => value === 0));
  assert.equal(mock.values.CLAWTorsoBreastSize, 0);
  assert.equal(mock.values.CLAWHeadEarSize, .73);
  assert.equal(mock.values.CLAWTailLength, .4);
  await assert.rejects(core.writeLinked(mock.sdk, catalog, male, {}, true, ["CLAWHeadEarSize"]), /Invalid previously/);
});

test("changing family clears formerly written targets and host failures propagate", async () => {
  const mock = host(female);
  mock.values.CLAWTorsoBreastSize = .8;
  await core.writeLinked(mock.sdk, catalog, male, { PecsSize: .5 }, false, ["CLAWTorsoBreastSize"]);
  assert.equal(mock.values.CLAWTorsoBreastSize, 0);
  const error = Object.assign(new Error("disabled"), { code: "disabledAddon" });
  await assert.rejects(core.writeLinked({ request: async () => { throw error; } }, catalog, male, {}, false, []),
    failure => failure === error);
});
