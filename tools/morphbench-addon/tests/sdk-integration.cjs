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
  setAttribute(name, value) { this[name] = value; }
  focus() { this.focused = true; }
  select() { this.selected = true; }
  remove() {}
  addEventListener(name, handler) { this.events[name] = handler; }
  async fire(name) { assert.equal(typeof this.events[name], "function"); return this.events[name](); }
}
function harness({ stable = false, missing = null, failWolfSet = false, geometry = false,
  geometryVertexCount = 3, geometryShapeName = "Body", hostExports = false } = {}) {
  const nodes = new Map(), events = new Map(), calls = [], previews = new Map(); let serial = 0;
  const selectIds = new Set(["profile", "human-model", "wolf-model", "preset", "geometry-shape", "game-female-family"]);
  const element = id => { if (!nodes.has(id)) nodes.set(id, new Element(selectIds.has(id) ? "select" : "div")); return nodes.get(id); };
  let exportText = "", maximumExportPageBytes = 0;
  Object.defineProperty(element("export-text"), "value", {
    get() { return exportText; },
    set(value) { exportText = value; maximumExportPageBytes = Math.max(maximumExportPageBytes, Buffer.byteLength(value, "utf8")); }
  });
  element("human").value = "{}"; element("weight").value = "1";
  const profile = catalog.profiles.find(item => item.family === "3BA");
  const humanNames = realRoot ? JSON.parse(fs.readFileSync(path.join(realRoot,"resource-name-audit.json"),"utf8"))[0].morphNames :
    [...new Set([...profile.rules.map(rule => rule.source), "Butt", "BigButt", "MuscleAbs", "HumanOther"])];
  const wolfNames = Object.keys(core.evaluate(catalog, profile.id, {}).values).filter(name => name !== missing).concat(["CLAWHeadEarSize", "CLAWTailLength"]);
  const legacyValues = { LegacyMain: .33 };
  const geometryVertices = geometryVertexCount === 3 ? [1, 2, 3, -1, -2, -3, .5, .5, .5] :
    Array.from({ length: geometryVertexCount * 3 }, (_, index) => (index % 997) / 997 - .5);
  const geometryBase = geometryVertexCount === 3 ? [0, 0, 0, -1, -1, -1, .5, .5, .5] :
    Array.from({ length: geometryVertexCount * 3 }, (_, index) => (index % 911) / 911 - .5);
  const parent = { postMessage(message, origin) {
    assert.equal(origin, "*"); calls.push(message);
    queueMicrotask(async () => {
      let result, error;
      try {
        const { method, params } = message;
        if (method === "host.info") result = { apiVersion: 1, capabilities: stable ? ["scene.get", "morphs.get", "morphs.set"] :
          ["models.list", "previews.create", "previews.close", "previews.scene.get", "previews.morphs.get", "previews.morphs.set", "previews.link", ...(geometry ? ["previews.geometry"] : []), ...(hostExports ? ["exports.prepare"] : [])],
          previewLimits: { maxPreviews: 4, loadTimeoutMs: 8000 }, language: "en", scope: "browser-session" };
        else if (method === "exports.prepare") { assert.equal(hostExports, true); result = { prepared: true, filename: params.filename }; }
        else if (method === "models.list") result = { root: "isolated", entries: ["human.nif", "wolf.nif"].map(name => ({ name, nif: name, tri: name + ".tri" })) };
        else if (method === "previews.create") { const preview = "opaque:" + (++serial), human = params.name === "human.nif";
          previews.set(preview, { name: params.name, names: human ? humanNames : wolfNames, values: human ? {} : { CLAWHeadEarSize: .6, CLAWTailLength: .8 } }); result = { preview, name: params.name }; }
        else if (method === "previews.link") { assert.deepEqual(JSON.parse(JSON.stringify(params)), { previews: ["opaque:1", "opaque:2"], properties: ["orientation"] }); result = params; }
        else {
          const preview = previews.get(params.preview); assert.ok(preview, "Only a live explicit scoped preview may be targeted.");
          if (method === "previews.close") { previews.delete(params.preview); result = { closed: true }; }
          else if (method === "previews.scene.get") result = { open: true, names: { nif: preview.name, tri: preview.name + ".tri" }, shapes: geometry ? [{ name: geometryShapeName, vertices: geometryVertexCount, triangles: 1 }] : [] };
          else if (method === "previews.geometry") { assert.equal(geometry, true); assert.equal(params.shape, geometryShapeName);
            result = { name: geometryShapeName, space: "model", vertices: geometryVertices, baseVertices: geometryBase, triangles: [0, 1, 2] }; }
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
  element("game-female-family").value = "3BA"; // Native HTML select's first option.
  const context = vm.createContext({ parent, TextEncoder, console, setTimeout, clearTimeout, WebAssembly, Buffer,
    document: { getElementById: element, createElement: tag => new Element(tag), body: new Element("body") },
    addEventListener(name, handler) { events.set(name, handler); } }); context.window = context; context.CLAWMorphCatalog = catalog;
  vm.runInContext(sdkSource, context, { filename: "actual-host-addon-sdk.js" });
  vm.runInContext(fs.readFileSync(path.join(path.dirname(path.resolve(process.argv[2])), "matrix-kernel.js"), "utf8"), context, {filename: "actual-shared-kernel.js"});
  for (const name of ["core.js", "pair.js", "input.js", "preview-controller.js", "main.js"]) vm.runInContext(source(name), context, { filename: name });
  return { element, calls, previews, legacyValues, maximumExportPageBytes: () => maximumExportPageBytes };
}
const settle = () => new Promise(setImmediate);
async function open(bench) { await settle(); bench.element("human-model").value = "human.nif"; bench.element("wolf-model").value = "wolf.nif";
  await bench.element("human-model").fire("change"); await bench.element("open-pair").fire("click"); }

test("pasted standalone matrix loads without a file picker and stays independent of human values", async () => {
  const bench=harness(); await open(bench);
  const profile={...catalog.profiles[0],rules:[{source:"",target:"CLAWTorsoBellyRound",gain:1,cap:1,function:"constant",value:.35}]};
  bench.element("matrix-paste").value=JSON.stringify({schemaVersion:1,kind:"claw-wolf-matrix",profile});
  await bench.element("matrix-paste-load").fire("click");
  assert.match(bench.element("status").textContent,/Loaded the pasted wolf/);
  for(const value of [-.5,.9]) {
    bench.element("human").value=JSON.stringify({Belly:value});
    await bench.element("apply").fire("click");
    const wolf=[...bench.previews.values()].find(p=>p.name==="wolf.nif");
    assert.equal(wolf.values.CLAWTorsoBellyRound,Math.fround(.35));
  }
});

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
test("slider provenance refreshes explicit signed and zero JSON values without reopening the pair", async () => {
  const bench = harness(); await open(bench);
  const row = name => bench.element("shared-sliders").children.find(node => node.children[0].textContent === name);
  const origin = name => row(name).children[3].textContent;
  const provided = "Provided preview coefficient; runtime value unmeasured";
  const omitted = "Unspecified preview zero; runtime value unmeasured";
  const originalBellyRow = row("Belly");
  assert.equal(origin("Belly"), omitted);
  bench.element("human").value = '{"Belly":0.5,"Butt":-0.25,"BigButt":0}';
  await bench.element("human").fire("input");
  for (const name of ["Belly", "Butt", "BigButt"]) assert.equal(origin(name), provided);
  assert.equal(row("Belly").children[2].value, "0.5"); assert.equal(row("Butt").children[2].value, "-0.25");
  assert.equal(row("BigButt").children[2].value, "0"); assert.equal(origin("MuscleAbs"), omitted);
  bench.element("human").value = '{"Butt":0,"MuscleAbs":-0.5}'; await bench.element("human").fire("input");
  assert.equal(row("Belly"), originalBellyRow);
  assert.equal(origin("Belly"), omitted); assert.equal(row("Belly").children[2].value, "0");
  assert.equal(origin("Butt"), provided); assert.equal(origin("MuscleAbs"), provided); assert.equal(origin("BigButt"), omitted);
  bench.element("import").files = [{ name: "fixture.json", text: async () => JSON.stringify({
    humanValues: { Belly: .5, BigButt: 0 }, humanValueProvenance: { Belly: "Retained fixture observation", BigButt: "Retained explicit fixture zero" }
  }) }];
  await bench.element("import").fire("change");
  row("Butt").children[2].value = "-0.75"; await row("Butt").children[2].fire("change");
  assert.equal(origin("Butt"), "Manually edited preview coefficient; not a game observation");
  assert.equal(origin("Belly"), "Retained fixture observation"); assert.equal(origin("BigButt"), "Retained explicit fixture zero");
  assert.equal(bench.calls.filter(call => call.method === "previews.create").length, 2);
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
test("wolf preset import/export preserves matrix metadata/functions and Apply uses edited matrix", async () => {
  const bench = harness(); await open(bench);
  const original = core.getProfile(catalog, bench.element("profile").value);
  const matrix = { ...original, rules: [
    { source: "Belly", target: "CLAWTorsoBellyRound", gain: .5, cap: .8, function: "power", exponent: 2 },
    { source: "", target: "CLAWTorsoBellyRound", gain: 1, cap: .8, function: "constant", value: .1 }
  ] };
  bench.element("matrix-import").files = [{ text: async () => JSON.stringify({ schemaVersion: 1, kind: "claw-wolf-matrix", profile: matrix }) }];
  await bench.element("matrix-import").fire("change");
  assert.equal(bench.element("matrix-rows").children.length, 2);
  bench.element("human").value = '{"Belly":0.5}'; await bench.element("apply").fire("click");
  assert.equal(bench.previews.get("opaque:2").values.CLAWTorsoBellyRound, core.evaluateMatrix(matrix, { Belly: .5 }).values.CLAWTorsoBellyRound);
  await bench.element("matrix-export").fire("click");
  const exported = JSON.parse(bench.element("export-text").value);
  assert.equal(exported.kind, "claw-wolf-matrix"); assert.deepEqual(exported.profile, core.validateMatrix(matrix));
  assert.equal(exported.profile.version, original.version); assert.equal(exported.profile.calibration, original.calibration);
  await bench.element("matrix-xml").fire("click"); assert.match(bench.element("export-text").value, /function="power" exponent="2"/);
  assert.match(bench.element("export-text").value, /function="constant" value=/);
  assert.match(bench.element("comparison-status").textContent, /canonical matrix/);
  await bench.element("export-select").fire("click"); assert.equal(bench.element("export-text").selected, true);
});
test("structured edge editor changes gain/function/parameter, target caps and order with validation", async () => {
  const bench = harness(); await settle();
  const control = (edge, column) => bench.element("matrix-rows").children[edge].children[column].children[0];
  control(0, 3).value = "power"; await control(0, 3).fire("change");
  control(0, 6).value = "3"; await control(0, 6).fire("change");
  control(0, 4).value = "0.123"; await control(0, 4).fire("change");
  control(0, 5).value = "0.4"; await control(0, 5).fire("change");
  await bench.element("matrix-export").fire("click");
  let matrix = JSON.parse(bench.element("export-text").value).profile, first = matrix.rules[0];
  assert.equal(first.function, "power"); assert.equal(first.exponent, 3); assert.equal(first.gain, Math.fround(.123));
  assert.ok(matrix.rules.filter(rule => rule.target === first.target).every(rule => rule.cap === Math.fround(.4)));
  control(0, 6).value = "9"; await control(0, 6).fire("change"); assert.match(bench.element("status").textContent, /exponent/);
  assert.equal(control(0, 6).value, "3");
  await control(0, 7).children[1].fire("click");
  await bench.element("matrix-export").fire("click"); matrix = JSON.parse(bench.element("export-text").value).profile;
  assert.deepEqual(matrix.rules[1], first);
  await bench.element("matrix-constant").fire("click");
  await bench.element("matrix-export").fire("click"); matrix = JSON.parse(bench.element("export-text").value).profile;
  assert.equal(matrix.rules.at(-1).function, "constant"); assert.equal(matrix.rules.at(-1).source, "");
  await bench.element("matrix-reset").fire("click"); await bench.element("matrix-export").fire("click");
  assert.deepEqual(JSON.parse(bench.element("export-text").value).profile, core.getProfile(catalog, bench.element("profile").value));
});
test("diagnostic coefficient reference compares numerically without applying or replacing matrix preset", async () => {
  const bench = harness(); await settle(); bench.element("human").value = '{"Belly":0.5}';
  await bench.element("snapshot-export").fire("click"); const text = bench.element("export-text").value;
  assert.equal(JSON.parse(text).kind, "claw-wolf-coefficient-snapshot");
  bench.element("snapshot-import").files = [{ text: async () => text }]; await bench.element("snapshot-import").fire("change");
  assert.match(bench.element("comparison-status").textContent, /maximum absolute difference 0; RMS 0/);
  assert.equal(bench.calls.filter(call => call.method.endsWith(".set")).length, 0);
});
test("scoped geometry reads all vertices from both owned models and exports every initial/current/delta value", async () => {
  const bench = harness({ geometry: true }); await open(bench);
  assert.equal(bench.element("geometry-read").disabled, false); await bench.element("geometry-read").fire("click");
  assert.equal(bench.calls.filter(call => call.method === "previews.geometry").length, 2);
  assert.equal(bench.element("geometry-rows").children.length, 3); assert.equal(bench.element("geometry-export").disabled, false);
  await bench.element("geometry-export").fire("click"); const snapshot = JSON.parse(bench.element("export-text").value);
  for (const role of ["human", "wolf"]) {
    assert.deepEqual(snapshot.models[role].shapes[0].deltas, [1, 2, 3, 0, -1, -2, 0, 0, 0]);
    assert.equal(snapshot.models[role].shapes[0].vertexCount, 3);
  }
  assert.match(snapshot.precision, /not atomically/);
  bench.element("human").value = '{"Belly":1}'; await bench.element("apply").fire("click");
  assert.equal(bench.element("geometry-export").disabled, true); assert.match(bench.element("geometry-status").textContent, /invalidated/);
});

test("small matrix exports remain complete on one page and host downloads retain their exact format", async () => {
  const bench = harness({ hostExports: true }); await settle();
  await bench.element("matrix-export").fire("click");
  const json = bench.element("export-text").value;
  assert.deepEqual(JSON.parse(json).profile, core.getProfile(catalog, bench.element("profile").value));
  assert.equal(bench.element("export-page").value, "1"); assert.equal(bench.element("export-page").max, "1");
  assert.equal(bench.element("export-previous").disabled, true); assert.equal(bench.element("export-next").disabled, true);
  assert.match(bench.element("export-page-status").textContent, /Page 1 of 1/);
  await bench.element("export-download").fire("click");
  let prepared = bench.calls.filter(call => call.method === "exports.prepare").at(-1).params;
  assert.equal(prepared.text, json); assert.equal(prepared.format, "json");
  assert.equal(prepared.filename, bench.element("profile").value + ".wolf-matrix.json");
  await bench.element("matrix-xml").fire("click");
  const xml = bench.element("export-text").value;
  assert.equal(xml, core.exportCatalog(catalog, core.getProfile(catalog, bench.element("profile").value), "3BA"));
  await bench.element("export-download").fire("click");
  prepared = bench.calls.filter(call => call.method === "exports.prepare").at(-1).params;
  assert.equal(prepared.text, xml); assert.equal(prepared.format, "xml"); assert.equal(prepared.filename, "MorphLinks.xml");
});

for (const hostExports of [true, false]) test("large geometry export pages retain every byte " +
  (hostExports ? "and host downloads use the complete immutable snapshot" : "without host download support"), async () => {
  const count = 12000, shapeName = "Body Ж🌕";
  const bench = harness({ geometry: true, geometryVertexCount: count, geometryShapeName: shapeName, hostExports });
  await open(bench); await bench.element("geometry-read").fire("click"); await bench.element("geometry-export").fire("click");
  const pageCount = Number(bench.element("export-page").max), pages = [];
  assert.ok(pageCount > 32);
  for (let page = 1; page <= pageCount; page++) {
    const text = bench.element("export-text").value;
    assert.equal(bench.element("export-page").value, String(page));
    assert.equal(bench.element("export-previous").disabled, page === 1);
    assert.equal(bench.element("export-next").disabled, page === pageCount);
    assert.ok(Buffer.byteLength(text, "utf8") <= 32 * 1024);
    assert.equal(Buffer.from(text, "utf8").toString("utf8"), text, "Pages must not split a Unicode character.");
    pages.push(text);
    if (page < pageCount) await bench.element("export-next").fire("click");
  }
  const complete = pages.join(""), snapshot = JSON.parse(complete);
  assert.ok(Buffer.byteLength(complete, "utf8") > 1024 * 1024);
  assert.equal(snapshot.kind, "claw-paired-geometry-snapshot");
  for (const role of ["human", "wolf"]) {
    const shape = snapshot.models[role].shapes[0];
    assert.equal(shape.name, shapeName); assert.equal(shape.vertexCount, count);
    assert.equal(shape.vertices.length, count * 3); assert.equal(shape.baseVertices.length, count * 3); assert.equal(shape.deltas.length, count * 3);
    assert.equal(shape.vertices.at(-1), ((count * 3 - 1) % 997) / 997 - .5);
  }
  assert.ok(bench.maximumExportPageBytes() <= 32 * 1024, "The full export must never enter the textarea, even temporarily.");
  await bench.element("export-previous").fire("click"); assert.equal(bench.element("export-page").value, String(pageCount - 1));
  bench.element("export-page").value = "2"; await bench.element("export-go").fire("click");
  assert.equal(bench.element("export-text").value, pages[1]);
  await bench.element("export-select").fire("click"); assert.equal(bench.element("export-text").selected, true);
  assert.equal(bench.element("export-download").disabled, !hostExports);
  if (hostExports) {
    await bench.element("export-download").fire("click");
    const prepared = bench.calls.filter(call => call.method === "exports.prepare").at(-1).params;
    assert.deepEqual(Buffer.from(prepared.text, "utf8"), Buffer.from(complete, "utf8"));
    assert.equal(prepared.format, "json"); assert.match(prepared.filename, /\.paired-vertices\.json$/);
    // The readonly viewer is not the download's source of truth.
    bench.element("export-text").value = "altered visible page"; await bench.element("export-download").fire("click");
    assert.equal(bench.calls.filter(call => call.method === "exports.prepare").at(-1).params.text, complete);
  } else assert.equal(bench.calls.filter(call => call.method === "exports.prepare").length, 0);
  bench.element("export-page").value = "1"; await bench.element("export-go").fire("click");
  assert.equal(bench.element("export-text").value, pages[0]);
});
