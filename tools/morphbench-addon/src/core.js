/* CLAW mapping evaluator. Independent of Morphbench and the browser DOM. */
;(function (global) {
  "use strict";

  const unsafeNames = new Set(["__proto__", "prototype", "constructor"]);
  const bodyTargets = new Set(["CLAWArmGirth", "CLAWLegCalfGirth", "CLAWLegThighGirth",
    "CLAWTorsoBackWide", "CLAWTorsoBellyRound", "CLAWTorsoBreastSize", "CLAWTorsoChestSize",
    "CLAWTorsoFlankWidth", "CLAWTorsoGirth", "CLAWTorsoNeckGirth",
    "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow", "CLAWArmLean",
    "CLAWLegThighLean", "CLAWLegCalfLean", "CLAWTorsoLean"]);
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

  const functions = new Set(["linear", "positive", "negative", "smoothstep", "power", "constant"]);
  function validateMatrix(profile) {
    if (!object(profile) || !identifier(profile.id) || !["CBBE", "3BA", "HIMBO"].includes(profile.family) ||
        profile.sex !== (profile.family === "HIMBO" ? "male" : "female") ||
        !Array.isArray(profile.rules) || !profile.rules.length || profile.rules.length > 128) {
      fail("Invalid CLAW profile metadata.");
    }
    for (const key of ["version", "calibration"]) {
      if (own(profile, key) && !identifier(profile[key])) fail("Invalid CLAW profile " + key);
    }
    const pairs = new Set(), caps = new Map();
    const normalized = { ...profile, rules: [] };
    for (const rule of profile.rules) {
      if (!object(rule)) fail("Invalid CLAW mapping rule.");
      const fn = own(rule, "function") ? rule.function : "linear";
      const allowed = new Set(["source", "target", "gain", "cap", "function"]);
      if (fn === "power") allowed.add("exponent");
      if (fn === "constant") allowed.add("value");
      if (!functions.has(fn) || Object.keys(rule).some(key => !allowed.has(key)) ||
          (fn === "constant" ? rule.source !== "" : (!identifier(rule.source) || rule.source.startsWith("CLAW"))) ||
          !identifier(rule.target) || !linkedTarget(rule.target) ||
          (profile.sex === "male" && rule.target === "CLAWTorsoBreastSize")) {
        fail("Invalid CLAW mapping rule or function parameters.");
      }
      const gain = finiteFloat(rule.gain, "Rule gain");
      const cap = finiteFloat(rule.cap, "Rule cap");
      if (cap <= 0 || cap > 1) fail("Rule cap must be in (0, 1].");
      const edge = { source: rule.source, target: rule.target, gain, cap, function: fn };
      if (fn === "power") {
        if (!Number.isInteger(rule.exponent) || rule.exponent < 1 || rule.exponent > 8) fail("Power exponent must be an integer in 1..8.");
        edge.exponent = rule.exponent;
      }
      if (fn === "constant") edge.value = finiteFloat(rule.value, "Constant value");
      const pair = JSON.stringify([rule.source, rule.target]);
      if (pairs.has(pair)) fail("Duplicate CLAW source/target rule.");
      pairs.add(pair);
      if (caps.has(rule.target) && caps.get(rule.target) !== cap) fail("Inconsistent target cap.");
      caps.set(rule.target, cap);
      normalized.rules.push(edge);
    }
    return normalized;
  }

  function getProfile(catalog, id) {
    if (!object(catalog) || catalog.schemaVersion !== 1 || !Array.isArray(catalog.profiles)) fail("Invalid CLAW mapping catalog.");
    if (!identifier(id)) fail("Unknown CLAW profile.");
    const matches = catalog.profiles.filter(profile => object(profile) && profile.id === id);
    if (matches.length !== 1) fail("Unknown or ambiguous CLAW profile: " + id);
    return validateMatrix(matches[0]);
  }

  function exportMatrix(matrix) {
    const profile = validateMatrix(matrix);
    // Native generated family interchange intentionally excludes XML entities.
    const ascii = value => {
      if (typeof value !== "string" || /[^\x20-\x7e]|[&<>"']/.test(value)) fail("XML matrix fields must use plain ASCII without XML delimiters.");
      return value;
    };
    const version = profile.version || "1", calibration = profile.calibration || "authored-matrix";
    const lines = ['<MorphLinkProfiles schemaVersion="1">',
      '  <Profile id="' + ascii(profile.id) + '" family="' + profile.family + '" version="' + ascii(version) +
      '" sex="' + profile.sex + '" calibration="' + ascii(calibration) + '">'];
    for (const rule of profile.rules) {
      let line = '    <Rule source="' + ascii(rule.source) + '" target="' + rule.target + '" gain="' + rule.gain + '" cap="' + rule.cap + '" function="' + rule.function + '"';
      if (rule.function === "power") line += ' exponent="' + rule.exponent + '"';
      if (rule.function === "constant") line += ' value="' + rule.value + '"';
      lines.push(line + ' />');
    }
    lines.push('  </Profile>', '</MorphLinkProfiles>');
    return lines.join("\n") + "\n";
  }

  function evaluate(catalog, profileId, humanValues) {
    return evaluateMatrix(getProfile(catalog, profileId), humanValues);
  }

  function exportCatalog(catalog, matrix, femaleFamily) {
    const edited = validateMatrix(matrix);
    if (!["CBBE", "3BA"].includes(femaleFamily)) fail("Declare the installed female body family before exporting game configuration.");
    const profiles = catalog.profiles.map(profile => profile.family === edited.family ? edited : validateMatrix(profile));
    const male = profiles.filter(profile => profile.family === "HIMBO");
    const female = profiles.filter(profile => profile.family === femaleFamily);
    if (male.length !== 1 || female.length !== 1 || new Set(profiles.map(profile => profile.id)).size !== profiles.length) fail("Ambiguous game configuration families or identifiers.");
    const body = profiles.map(profile => exportMatrix(profile).split("\n").slice(1,-2).join("\n")).join("\n");
    // exportMatrix validates every identifier for the deliberately strict native XML format.
    return '<MorphLinkProfiles schemaVersion="1">\n  <Defaults male="' + male[0].id + '" female="' + female[0].id + '" />\n' + body + '\n</MorphLinkProfiles>\n';
  }

  function evaluateMatrix(matrix, humanValues) {
    const profile = validateMatrix(matrix), human = validateHuman(humanValues);
    const targets = new Map(), mappedSources = new Set();
    // Native linked composition starts neutral. Own only its linked body subset;
    // leave ear/tail/head/paw/claw controls outside this addon's write scope.
    for (const target of bodyTargets) {
      if (profile.sex !== "male" || target !== "CLAWTorsoBreastSize") {
        targets.set(target, { target: target, contributions: [], rawSum: 0, cap: 1 });
      }
    }
    const kernel = global.CLAWMatrixKernel || (typeof globalThis !== "undefined" && globalThis.CLAWMatrixKernel);
    if (!kernel) fail("Shared CLAW WebAssembly kernel is unavailable. Load matrix-kernel.js before core.js.");
    const ordered = Array.from(targets.keys());
    const numericRules = profile.rules.map(rule => ({ ...rule,
      target: ordered.indexOf(rule.target),
      input: rule.function === "constant" ? 0 : (own(human, rule.source) ? human[rule.source] : 0) }));
    const numeric = kernel.evaluate(numericRules, ordered.length);
    profile.rules.forEach((rule, index) => {
      const row = targets.get(rule.target);
      row.cap = rule.cap;
      row.contributions.push({ ...rule, input: numericRules[index].input, ...numeric.details[index] });
      if (rule.function !== "constant") mappedSources.add(rule.source);
    });
    const values = Object.create(null);
    ordered.forEach((target, index) => {
      const row = targets.get(target);
      row.rawSum = numeric.rawSums[index]; row.clamped = numeric.clamped[index];
      row.value = numeric.values[index]; values[target] = row.value;
    });
    const rows = Array.from(targets.values()).sort((a, b) => a.target < b.target ? -1 : a.target > b.target ? 1 : 0);
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

  const api = Object.freeze({ parseHuman, validateHuman, getProfile, validateMatrix, evaluateMatrix, exportMatrix, exportCatalog, evaluate, validateModel, writeLinked });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.CLAWLink = api;
})(typeof window !== "undefined" ? window : globalThis);
