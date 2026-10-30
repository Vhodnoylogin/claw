/* CLAW mapping evaluator. Independent of Morphbench and the browser DOM. */
;(function (global) {
  "use strict";

  const unsafeNames = new Set(["__proto__", "prototype", "constructor"]);
  const bodyTargets = new Set(["CLAWArmGirth", "CLAWLegCalfGirth", "CLAWLegThighGirth",
    "CLAWTorsoBackWide", "CLAWTorsoBellyRound", "CLAWTorsoBreastSize", "CLAWTorsoChestSize",
    "CLAWTorsoFlankWidth", "CLAWTorsoGirth", "CLAWTorsoNeckGirth",
    "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow"]);
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);

  function fail(message) { throw new Error(message); }
  function object(value) {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }
  function identifier(name) {
    return typeof name === "string" && name.length > 0 && new TextEncoder().encode(name).length <= 160 &&
      !/^[\x00-\x20]|[\x00-\x20]$|[\x00-\x1f\x7f]/.test(name) && !unsafeNames.has(name);
  }
  function finiteFloat(value, label) {
    if (typeof value !== "number" || !Number.isFinite(value) || !Number.isFinite(Math.fround(value))) {
      fail(label + " must be a finite float32 number.");
    }
    return Math.fround(value);
  }
  function linkedTarget(name) {
    return bodyTargets.has(name);
  }
  function validateHuman(values) {
    if (!object(values)) fail("Human values must be a JSON object mapping names to numbers.");
    const result = Object.create(null);
    for (const [name, value] of Object.entries(values)) {
      if (!identifier(name) || name.startsWith("CLAW")) fail("Invalid human morph name: " + name);
      result[name] = finiteFloat(value, name);
    }
    return result;
  }
  function parseHuman(text) { return validateHuman(JSON.parse(text)); }

  function getProfile(catalog, id) {
    if (!object(catalog) || catalog.schemaVersion !== 1 || !Array.isArray(catalog.profiles)) {
      fail("Invalid CLAW mapping catalog.");
    }
    if (!identifier(id)) fail("Unknown CLAW profile.");
    const matches = catalog.profiles.filter(profile => object(profile) && profile.id === id);
    if (matches.length !== 1) fail("Unknown or ambiguous CLAW profile: " + id);
    const profile = matches[0];
    if (!["CBBE", "3BA", "HIMBO"].includes(profile.family) ||
        profile.sex !== (profile.family === "HIMBO" ? "male" : "female") ||
        !Array.isArray(profile.rules) || !profile.rules.length || profile.rules.length > 128) {
      fail("Invalid CLAW profile metadata.");
    }
    const pairs = new Set(), caps = new Map();
    for (const rule of profile.rules) {
      if (!object(rule) || !identifier(rule.source) || rule.source.startsWith("CLAW") ||
          !identifier(rule.target) || !linkedTarget(rule.target) ||
          (profile.sex === "male" && rule.target === "CLAWTorsoBreastSize")) {
        fail("Invalid CLAW mapping rule.");
      }
      finiteFloat(rule.gain, "Rule gain");
      const cap = finiteFloat(rule.cap, "Rule cap");
      if (cap <= 0 || cap > 1) fail("Rule cap must be in (0, 1].");
      const pair = JSON.stringify([rule.source, rule.target]);
      if (pairs.has(pair)) fail("Duplicate CLAW source/target rule.");
      pairs.add(pair);
      if (caps.has(rule.target) && caps.get(rule.target) !== cap) fail("Inconsistent target cap.");
      caps.set(rule.target, cap);
    }
    return profile;
  }

  function evaluate(catalog, profileId, humanValues) {
    const profile = getProfile(catalog, profileId), human = validateHuman(humanValues);
    const targets = new Map(), mappedSources = new Set();
    // Native linked composition starts neutral. Own only its linked body subset;
    // leave ear/tail/head/paw/claw controls outside this addon's write scope.
    for (const target of bodyTargets) {
      if (profile.sex !== "male" || target !== "CLAWTorsoBreastSize") {
        targets.set(target, { target: target, contributions: [], rawSum: 0, cap: 1 });
      }
    }
    // Native MorphLink uses float inputs/gains/caps, double accumulation in XML
    // rule order, clamp(sum, 0, 1) * cap, then a float output. Actor weight is absent.
    for (const rule of profile.rules) {
      const input = own(human, rule.source) ? human[rule.source] : 0;
      const gain = Math.fround(rule.gain), cap = Math.fround(rule.cap);
      const contribution = input * gain;
      let row = targets.get(rule.target);
      row.cap = cap;
      row.rawSum += contribution;
      if (!Number.isFinite(row.rawSum)) fail("CLAW mapping arithmetic overflow.");
      row.contributions.push({ source: rule.source, input: input, gain: gain, contribution: contribution });
      mappedSources.add(rule.source);
    }
    const values = Object.create(null);
    const rows = Array.from(targets.values()).sort((a, b) => a.target < b.target ? -1 : a.target > b.target ? 1 : 0);
    for (const row of rows) {
      row.clamped = Math.max(0, Math.min(1, row.rawSum));
      row.value = Math.fround(row.clamped * row.cap);
      values[row.target] = row.value;
    }
    return { profile: profile, rows: rows, values: values,
      unmapped: Object.keys(human).filter(name => !mappedSources.has(name)).sort() };
  }

  function validateModel(scene, morphs, targets) {
    if (!object(scene) || scene.open !== true || !object(scene.names) ||
        typeof scene.names.nif !== "string" || !scene.names.nif) fail("Open a CLAW body model first.");
    if (!object(morphs) || !Array.isArray(morphs.names) ||
        morphs.names.some(name => typeof name !== "string")) fail("Invalid host morph list.");
    const available = new Set(morphs.names);
    const missing = targets.filter(name => !available.has(name));
    if (missing.length) fail("Model is missing linked body targets: " + missing.join(", "));
    return scene.names.nif;
  }

  async function writeLinked(sdk, catalog, profileId, human, reset, previouslyWritten) {
    const result = evaluate(catalog, profileId, human);
    const values = Object.assign(Object.create(null), result.values);
    const allowed = bodyTargets;
    for (const target of previouslyWritten || []) {
      if (!allowed.has(target) || !linkedTarget(target)) fail("Invalid previously written target.");
      if (!own(values, target)) values[target] = 0;
    }
    if (reset) {
      for (const target of Object.keys(values)) values[target] = 0;
    }
    // Separate read validation and one atomic host batch. Never use morphs.reset.
    const scene = await sdk.request("scene.get", {});
    const morphs = await sdk.request("morphs.get", {});
    const model = validateModel(scene, morphs, Object.keys(values));
    const response = await sdk.request("morphs.set", { values: values });
    return { result: result, model: model, values: values, response: response };
  }

  const api = Object.freeze({ parseHuman, validateHuman, getProfile, evaluate, validateModel, writeLinked });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.CLAWLink = api;
})(typeof window !== "undefined" ? window : globalThis);
