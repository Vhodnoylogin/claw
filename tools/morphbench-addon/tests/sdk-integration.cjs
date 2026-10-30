"use strict";
// Offline DOM/protocol harness. Executes the host's actual public SDK unchanged;
// this is not an actual browser/installed-host or rendered-layout test.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { test } = require("node:test");
const core = require("../src/core.js");
if (!process.argv[2] || !process.argv[3]) throw new Error("Pass catalog.json and host web/addon-sdk.js paths.");
const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"));
const sdkSource = fs.readFileSync(path.resolve(process.argv[3]), "utf8");
const source = name => fs.readFileSync(path.join(__dirname, "../src", name), "utf8");

class Element {
  constructor() { this.value = ""; this.textContent = ""; this.disabled = false; this.children = []; this.events = {}; this.files = []; }
  appendChild(child) { this.children.push(child); if (!this.value && child.value) this.value = child.value; return child; }
  replaceChildren() { this.children = []; }
  addEventListener(name, handler) { this.events[name] = handler; }
  async fire(name) { return this.events[name](); }
}
function harness(missing) {
  const nodes = new Map();
  const element = id => { if (!nodes.has(id)) nodes.set(id, new Element()); return nodes.get(id); };
  element("human").value = "{}";
  const events = new Map(), calls = [], values = { CLAWHeadEarSize: .6, CLAWTailLength: .8 };
  const profile = catalog.profiles.find(item => item.family === "3BA");
  const names = Object.keys(core.evaluate(catalog, profile.id, {}).values).filter(name => name !== missing);
  let context;
  const parent = { postMessage(message, origin) {
    assert.equal(origin, "*");
    calls.push(message);
    let result;
    if (message.method === "host.info") result = { apiVersion: 1, capabilities: ["scene.get", "morphs.get", "morphs.set"],
      addon: { id: "claw-human-link-dev-001", name: "CLAW human morph link", version: "0.1.0-dev.1" }, language: "en", scope: "browser-session" };
    else if (message.method === "scene.get") result = { open: true, names: { nif: "female.nif", tri: "female.tri" } };
    else if (message.method === "morphs.get") result = { names, values: { ...values } };
    else if (message.method === "morphs.set") { Object.assign(values, message.params.values); result = { names, values: { ...values } }; }
    else throw new Error("Unexpected request: " + message.method);
    queueMicrotask(() => events.get("message")({ source: parent, data: {
      type: "morphbench-addon:response", apiVersion: 1, id: message.id, result } }));
  } };
  context = vm.createContext({ parent, TextEncoder, console, setTimeout, clearTimeout,
    document: { getElementById: element, createElement: () => new Element() },
    addEventListener(name, handler) { events.set(name, handler); } });
  context.window = context;
  context.CLAWMorphCatalog = catalog;
  vm.runInContext(sdkSource, context, { filename: "actual-host-addon-sdk.js" });
  vm.runInContext(source("core.js"), context, { filename: "core.js" });
  vm.runInContext(source("main.js"), context, { filename: "main.js" });
  return { element, calls, values };
}

test("classic UI scripts connect with the actual v1 SDK, calculate, apply and reset via protocol", async () => {
  const bench = harness();
  await new Promise(setImmediate);
  assert.equal(bench.element("apply").disabled, false);
  bench.element("human").value = '{"Belly":0.7,"BigBelly":0.7}';
  await bench.element("evaluate").fire("click");
  assert.equal(bench.calls.filter(item => item.method === "morphs.set").length, 0);
  await bench.element("apply").fire("click");
  assert.equal(bench.values.CLAWTorsoBellyRound, 1);
  assert.equal(bench.values.CLAWHeadEarSize, .6);
  assert.equal(bench.values.CLAWTailLength, .8);
  bench.element("human").value = "broken JSON is irrelevant to reset";
  await bench.element("reset").fire("click");
  assert.equal(bench.values.CLAWTorsoBellyRound, 0);
  assert.equal(bench.values.CLAWHeadEarSize, .6);
  assert.equal(bench.values.CLAWTailLength, .8);
  assert.equal(bench.calls.filter(item => item.method === "morphs.set").length, 2);
  assert.ok(bench.calls.every(item => item.apiVersion === 1));
});

test("classic UI surfaces missing-target rejection and sends no partial SDK write", async () => {
  const bench = harness("CLAWTorsoBellyRound");
  await new Promise(setImmediate);
  bench.element("human").value = '{"Belly":0.7}';
  await bench.element("apply").fire("click");
  assert.match(bench.element("status").textContent, /missing linked body targets/);
  assert.equal(bench.calls.filter(item => item.method === "morphs.set").length, 0);
});
