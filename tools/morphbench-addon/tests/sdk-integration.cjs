"use strict";
// Executes the actual public SDK and shipped consumer scripts. This detached
// protocol/DOM harness is not a browser renderer or installed-host acceptance.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const { test } = require("node:test"), core = require("../src/core.js");
if (!process.argv[2] || !process.argv[3]) throw new Error("Pass catalog.json, actual addon-sdk.js and optionally real-pair-inputs root.");
const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"));
const sdkSource = fs.readFileSync(path.resolve(process.argv[3]), "utf8");
const realRoot = process.argv[4] ? path.resolve(process.argv[4]) : null;
const source = name => fs.readFileSync(path.join(__dirname, "../src", name), "utf8");
class Element {
  constructor(tag = "div") { this.tagName = tag; this.value = ""; this.textContent = ""; this.disabled = false; this.checked = false; this.children = []; this.events = {}; this.files = []; }
  appendChild(child) { this.children.push(child); if (this.tagName === "select" && this.children.length === 1) this.value = child.value; return child; }
  replaceChildren() { this.children = []; if (this.tagName === "select") this.value = ""; }
  addEventListener(name, handler) { this.events[name] = handler; }
  async fire(name) { assert.equal(typeof this.events[name], "function"); return this.events[name](); }
}
function harness({ stable = false, missing = null, failWolfSet = false } = {}) {
  const nodes = new Map(), events = new Map(), calls = [], previews = new Map(); let serial = 0;
  const selectIds = new Set(["profile", "human-model", "wolf-model", "preset"]);
  const element = id => { if (!nodes.has(id)) nodes.set(id, new Element(selectIds.has(id) ? "select" : "div")); return nodes.get(id); };
  element("human").value = "{}"; element("weight").value = "1";
  const profile = catalog.profiles.find(item => item.family === "3BA");
  const humanNames = realRoot ? JSON.parse(fs.readFileSync(path.join(realRoot,"resource-name-audit.json"),"utf8"))[0].morphNames :
    [...new Set([...profile.rules.map(rule => rule.source), "Butt", "BigButt", "MuscleAbs", "HumanOther"])];
  const wolfNames = Object.keys(core.evaluate(catalog, profile.id, {}).values).filter(name => name !== missing).concat(["CLAWHeadEarSize", "CLAWTailLength"]);
  const legacyValues = { LegacyMain: .33 };
  const parent = { postMessage(message, origin) {
    assert.equal(origin, "*"); calls.push(message);
    queueMicrotask(async () => {
      let result, error;
      try {
        const { method, params } = message;
        if (method === "host.info") result = { apiVersion: 1, capabilities: stable ? ["scene.get", "morphs.get", "morphs.set"] :
          ["models.list", "previews.create", "previews.close", "previews.scene.get", "previews.morphs.get", "previews.morphs.set", "previews.link"],
          previewLimits: { maxPreviews: 4, loadTimeoutMs: 8000 }, language: "en", scope: "browser-session" };
        else if (method === "models.list") result = { root: "isolated", entries: ["human.nif", "wolf.nif"].map(name => ({ name, nif: name, tri: name + ".tri" })) };
        else if (method === "previews.create") { const preview = "opaque:" + (++serial), human = params.name === "human.nif";
          previews.set(preview, { name: params.name, names: human ? humanNames : wolfNames, values: human ? {} : { CLAWHeadEarSize: .6, CLAWTailLength: .8 } }); result = { preview, name: params.name }; }
        else if (method === "previews.link") { assert.deepEqual(JSON.parse(JSON.stringify(params)), { previews: ["opaque:1", "opaque:2"], properties: ["orientation"] }); result = params; }
        else {
          const preview = previews.get(params.preview); assert.ok(preview, "Only a live explicit scoped preview may be targeted.");
          if (method === "previews.close") { previews.delete(params.preview); result = { closed: true }; }
          else if (method === "previews.scene.get") result = { open: true, names: { nif: preview.name, tri: preview.name + ".tri" }, shapes: [] };
          else if (method === "previews.morphs.get" || method === "previews.morphs.set") {
            if (method.endsWith(".set")) {
              if (failWolfSet && preview.name === "wolf.nif") throw new Error("Wolf scoped write failed after human write");
              assert.ok(Object.keys(params.values).every(name => preview.names.includes(name))); Object.assign(preview.values, params.values);
            }
            result = { names: preview.names, values: { ...preview.values } };
          } else throw new Error("Unexpected SDK method: " + method);
        }
      } catch (failure) { error = { code: failure.code || "operationFailed", message: failure.message }; }
      events.get("message")({ source: parent, data: { type: "morphbench-addon:response", apiVersion: 1, id: message.id, ...(error ? { error } : { result }) } });
    });
  } };
  const context = vm.createContext({ parent, TextEncoder, console, setTimeout, clearTimeout,
    document: { getElementById: element, createElement: tag => new Element(tag) },
    addEventListener(name, handler) { events.set(name, handler); } }); context.window = context; context.CLAWMorphCatalog = catalog;
  vm.runInContext(sdkSource, context, { filename: "actual-host-addon-sdk.js" });
  for (const name of ["core.js", "pair.js", "input.js", "preview-controller.js", "main.js"]) vm.runInContext(source(name), context, { filename: name });
  return { element, calls, previews, legacyValues };
}
const settle = () => new Promise(setImmediate);
async function open(bench) { await settle(); bench.element("human-model").value = "human.nif"; bench.element("wolf-model").value = "wolf.nif";
  await bench.element("human-model").fire("change"); await bench.element("open-pair").fire("click"); }

test("stable v1 capability gap is explicit and sends no preview or legacy mutation", async () => {
  const bench = harness({ stable: true }); await settle();
  assert.equal(bench.element("open-pair").disabled, true); assert.equal(bench.element("apply").disabled, true);
  assert.match(bench.element("paired-support").textContent, /lacks independent previews/);
  bench.element("human").value = '{"Belly":0.7}'; await bench.element("evaluate").fire("click");
  assert.deepEqual(bench.calls.map(call => call.method), ["host.info"]);
});
test("actual SDK connects paired UI, preserves human-only values and derives wolf outputs without global writes", async () => {
  const bench = harness(); await open(bench); assert.equal(bench.element("apply").disabled, false);
  bench.element("human").value = '{"Belly":0.7,"BigBelly":0.7,"Butt":-0.5,"BigButt":-0.25}';
  await bench.element("evaluate").fire("click"); assert.equal(bench.calls.filter(call => call.method.endsWith(".set")).length, 0);
  await bench.element("apply").fire("click");
  assert.equal(bench.previews.get("opaque:1").values.Butt, -.5); assert.equal(bench.previews.get("opaque:1").values.BigButt, -.25);
  assert.equal(bench.previews.get("opaque:2").values.CLAWTorsoBellyRound, 1);
  assert.equal(bench.previews.get("opaque:2").values.CLAWHeadEarSize, .6);
  assert.match(bench.element("unmapped").textContent, /Butt=-0.5/);
  assert.deepEqual(bench.legacyValues, { LegacyMain: .33 });
  assert.ok(!bench.calls.some(call => ["models.open", "morphs.set", "morphs.reset", "view.set", "previews.view.set"].includes(call.method)));
  bench.element("human").value = "invalid JSON is irrelevant to zeroing acknowledged wolf outputs";
  await bench.element("reset").fire("click");
  assert.equal(bench.previews.get("opaque:2").values.CLAWTorsoBellyRound, 0);
  assert.equal(bench.previews.get("opaque:1").values.Butt, -.5);
  await bench.element("close-pair").fire("click"); assert.equal(bench.previews.size, 0);
});
test("missing wolf target refuses opening and disposes both created previews without morph writes", async () => {
  const bench = harness({ missing: "CLAWTorsoBellyRound" }); await open(bench);
  assert.match(bench.element("status").textContent, /missing linked body targets/);
  assert.equal(bench.previews.size, 0); assert.equal(bench.calls.filter(call => call.method.endsWith(".set")).length, 0);
});
test("partial pair write failure closes both previews and displays readable failure", async () => {
  const bench = harness({ failWolfSet: true }); await open(bench);
  bench.element("human").value = '{"Belly":0.7}'; await bench.element("apply").fire("click");
  assert.equal(bench.previews.size, 0); assert.equal(bench.element("apply").disabled, true);
  assert.match(bench.element("status").textContent, /Wolf scoped write failed/);
});
test("changing declared resource sex closes the old pair before any new-family apply", async () => {
  const bench = harness(); await open(bench);
  bench.element("human").value = '{"Belly":0.7}';
  bench.element("profile").value = catalog.profiles.find(item => item.family === "HIMBO").id;
  await bench.element("profile").fire("change");
  assert.equal(bench.previews.size, 0); assert.equal(bench.element("apply").disabled, true);
  assert.match(bench.element("status").textContent, /sex changed/);
  assert.match(bench.element("profile-info").textContent, /HIMBO/);
  assert.equal(bench.calls.filter(call => call.method.endsWith(".set")).length, 0);
});
test("real full-preset fixture import retains provenance and all nonzero human-only fields", { skip: !realRoot }, async () => {
  const bench = harness(); await open(bench);
  const fixture = fs.readFileSync(path.join(realRoot,"full-preset-fixtures/FThin.json"),"utf8");
  bench.element("import").files = [{ name: "FThin.json", text: async () => fixture }]; await bench.element("import").fire("change");
  assert.match(bench.element("input-provenance").textContent, /full-preset-reconstruction-with-observed-subset/);
  await bench.element("apply").fire("click");
  const actual = bench.previews.get("opaque:1").values;
  assert.equal(actual.BigButt, -.25); assert.equal(actual.Butt, -.5);
  assert.equal(Object.keys(JSON.parse(bench.element("human").value)).length, 154);
  assert.match(bench.element("unmapped").textContent, /BigButt=-0.25/);
  assert.ok(bench.element("shared-sliders").children.length >= 154);
});
