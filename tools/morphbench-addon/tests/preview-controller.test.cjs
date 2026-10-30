"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const core = require("../src/core.js");
const { PreviewController } = require("../src/preview-controller.js");
const catalog = { schemaVersion: 1, profiles: [
  { id: "female.3BA", family: "3BA", sex: "female", rules: [{ source: "Belly", target: "CLAWTorsoBellyRound", gain: .75, cap: .8 }] },
  { id: "female.CBBE", family: "CBBE", sex: "female", rules: [{ source: "Belly", target: "CLAWTorsoBellyRound", gain: .5, cap: 1 }] },
  { id: "male.HIMBO", family: "HIMBO", sex: "male", rules: [{ source: "Belly", target: "CLAWTorsoBellyRound", gain: 1, cap: 1 }] }
] };
const wolfNames = Object.keys(core.evaluate(catalog, "female.3BA", {}).values).concat(["CLAWHeadEarSize", "CLAWTailLength"]);
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
const tick = () => new Promise(setImmediate);

function host(options = {}) {
  const calls = [], events = new Map(), previews = new Map(); let serial = 0;
  previews.set("third-party", { preview: "third-party", name: "unrelated", names: ["Other"], values: { Other: .6 } });
  const sdk = {
    async connect() { return { apiVersion: 1, capabilities: options.capabilities || [...PreviewController.requiredCapabilities], previewLimits: { maxPreviews: 4, loadTimeoutMs: 8000 } }; },
    on(name, handler) { events.set(name, handler); return () => events.delete(name); },
    async request(method, params) {
      calls.push({ method, params: JSON.parse(JSON.stringify(params)) });
      if (options.before) await options.before(method, params, { previews, calls });
      if (method === "models.list") { assert.deepEqual(params, {}); return { root: "catalogue", entries: ["human.nif", "wolf.nif", "another.nif"].map(name => ({ name, nif: name, tri: name + ".tri" })) }; }
      if (method === "previews.create") {
        assert.deepEqual(Object.keys(params), ["name"]);
        const preview = "opaque:" + (++serial), isHuman = params.name === "human.nif";
        const names = isHuman ? ["Belly", "HumanOther", "UnmappedHuman"] : [...(options.wolfNames || wolfNames)];
        previews.set(preview, { preview, name: params.name, names, values: isHuman ? {} : { CLAWHeadEarSize: .6, CLAWTailLength: .8 } });
        return { preview, name: params.name };
      }
      if (method === "previews.link") {
        assert.deepEqual(Object.keys(params).sort(), ["previews", "properties"]);
        assert.deepEqual(params.properties, ["orientation"]);
        assert.equal(params.previews.length, 2); assert.ok(params.previews.every(id => previews.has(id)));
        return JSON.parse(JSON.stringify(params));
      }
      assert.equal(typeof params.preview, "string");
      const item = previews.get(params.preview);
      if (!item) throw Object.assign(new Error("Expired handle"), { code: "unknownPreview" });
      if (method === "previews.close") { assert.deepEqual(Object.keys(params), ["preview"]); previews.delete(params.preview); return { closed: true }; }
      if (method === "previews.scene.get") { assert.deepEqual(Object.keys(params), ["preview"]); return { open: true, names: { nif: item.name, tri: item.name + ".tri" }, shapes: [{ name: "Body", vertices: 3, triangles: 1 }] }; }
      if (method === "previews.morphs.set") {
        assert.deepEqual(Object.keys(params).sort(), ["preview", "values"]);
        assert.ok(Object.keys(params.values).every(name => item.names.includes(name)));
        Object.assign(item.values, params.values);
      } else assert.equal(method, "previews.morphs.get", "No legacy/global or camera-echo method is allowed");
      return { names: [...item.names], values: { ...item.values } };
    }
  };
  return { sdk, calls, previews, events };
}
async function opened(options = {}) {
  const fake = host(options), observations = [];
  const controller = new PreviewController(fake.sdk, catalog, { onState: event => observations.push(event) });
  await controller.open("female.3BA", "human.nif", "wolf.nif");
  return { ...fake, controller, observations };
}

test("capability discovery keeps stable v1 hosts unavailable without creating anything", async () => {
  const f = host({ capabilities: ["models.list", "morphs.get", "morphs.set"] });
  const c = new PreviewController(f.sdk, catalog);
  assert.equal(c.supports(await f.sdk.connect()), false);
  await assert.rejects(c.open("female.3BA", "human.nif", "wolf.nif"), { code: "unsupportedPreviews" });
  assert.equal(f.calls.length, 0); assert.equal(c.pair, null);
  assert.equal(PreviewController.supports({ apiVersion: 1, capabilities: [...PreviewController.requiredCapabilities], previewLimits: { maxPreviews: 1 } }), false);
});

test("real scoped contract opens two immutable IDs, links orientation natively and preserves a third preview", async () => {
  const f = await opened(), pair = f.controller.pair;
  assert.equal(pair.profileId, "female.3BA"); assert.equal(pair.human.name, "human.nif");
  assert.ok(Object.isFrozen(pair.human.scene));
  assert.equal(f.calls.filter(call => call.method === "previews.link").length, 1);
  const models = await f.controller.listModels(); assert.equal(models.entries.length, 3);
  await f.controller.close(); assert.equal(f.controller.pair, null);
  assert.deepEqual([...f.previews.keys()], ["third-party"]);
  assert.ok(f.calls.filter(call => call.method === "previews.close").every(call => call.params.preview !== "third-party"));
});

test("failure creating the second preview closes only the successfully created first", async () => {
  const f = host({ before(method, params) { if (method === "previews.create" && params.name === "wolf.nif") throw new Error("load failed"); } });
  const c = new PreviewController(f.sdk, catalog);
  await assert.rejects(c.open("female.3BA", "human.nif", "wolf.nif"), /load failed/);
  assert.deepEqual([...f.previews.keys()], ["third-party"]); assert.equal(c.pair, null);
});

test("close while create is pending invalidates the open and disposes its late handle", async () => {
  const gate = deferred(); let started = false;
  const f = host({ async before(method) { if (method === "previews.create" && !started) { started = true; await gate.promise; } } });
  const c = new PreviewController(f.sdk, catalog);
  const opening = c.open("female.3BA", "human.nif", "wolf.nif");
  const refused = assert.rejects(opening, { code: "stalePair" }); await tick();
  const closing = c.close(); gate.resolve(); await refused; await closing;
  assert.equal(c.pair, null); assert.deepEqual([...f.previews.keys()], ["third-party"]);
  assert.equal(f.calls.filter(call => call.method === "previews.create").length, 1);
});

test("all names are validated before either write and full unmapped human fields survive", async () => {
  const f = await opened(), pair = f.controller.pair;
  await assert.rejects(f.controller.apply({ MissingHuman: 1 }), /missing input/);
  assert.equal(f.calls.filter(call => call.method === "previews.morphs.set").length, 0);
  const input = { Belly: .7, UnmappedHuman: -.25, HumanOther: .4 }, result = await f.controller.apply(input);
  const expected = core.evaluate(catalog, "female.3BA", input);
  assert.deepEqual(result.wolfValues, JSON.parse(JSON.stringify(expected.values)));
  assert.equal(result.humanValues.UnmappedHuman, -.25); assert.equal(result.humanValues.HumanOther, Math.fround(.4));
  assert.deepEqual(result.unmapped, ["HumanOther", "UnmappedHuman"]);
  assert.equal(f.previews.get(pair.human.preview).values.UnmappedHuman, -.25);
  assert.equal(f.previews.get(pair.wolf.preview).values.CLAWHeadEarSize, .6);
  assert.equal(f.previews.get(pair.wolf.preview).values.CLAWTailLength, .8);
  assert.equal(f.calls.filter(call => /^(previews\.view\.|view\.|rotation|previews\.unlink)/.test(call.method)).length, 0);
});

test("a missing wolf target refuses opening before any morph write", async () => {
  const f = host({ wolfNames: wolfNames.filter(name => name !== "CLAWTorsoGirth") }), c = new PreviewController(f.sdk, catalog);
  await assert.rejects(c.open("female.3BA", "human.nif", "wolf.nif"), /missing linked body targets/);
  assert.deepEqual([...f.previews.keys()], ["third-party"]);
  assert.equal(f.calls.filter(call => call.method === "previews.morphs.set").length, 0);
});

test("partial second-model failure closes the pair and never reports paired success", async () => {
  let writes = 0;
  const f = await opened({ before(method) { if (method === "previews.morphs.set" && ++writes === 2) throw Object.assign(new Error("unknown commit"), { code: "timeout" }); } });
  await assert.rejects(f.controller.apply({ Belly: 1 }), { code: "timeout" });
  assert.equal(f.controller.pair, null); assert.deepEqual([...f.previews.keys()], ["third-party"]);
  assert.equal(f.observations.filter(item => item.method === "apply").length, 0);
});

test("an unknown first-model failure also closes both handles instead of assuming no write", async () => {
  const f = await opened({ before(method) { if (method === "previews.morphs.set") throw Object.assign(new Error("reply lost"), { code: "timeout" }); } });
  await assert.rejects(f.controller.apply({ Belly: .5 }), { code: "timeout" });
  assert.equal(f.controller.pair, null); assert.deepEqual([...f.previews.keys()], ["third-party"]);
});

test("failed cleanup retains exact owned handles and exposes a retryable report", async () => {
  let fail = true;
  const f = await opened({ before(method) { if (method === "previews.close" && fail) throw new Error("close blocked"); } });
  await assert.rejects(f.controller.close(), { code: "cleanupFailed" });
  assert.equal(f.controller.failedCleanup.length, 2); assert.equal(f.controller.pair, null);
  assert.ok(f.controller.failedCleanup.every(item => item.error.message === "close blocked"));
  fail = false; await f.controller.close(); assert.equal(f.controller.failedCleanup.length, 0);
  assert.deepEqual([...f.previews.keys()], ["third-party"]);
});

test("family changes clear acknowledged wolf outputs only; sex changes demand reopening", async () => {
  const f = await opened(), pair = f.controller.pair;
  await f.controller.apply({ Belly: .6, HumanOther: .7 });
  const human = { ...f.previews.get(pair.human.preview).values }, before = f.calls.length;
  await f.controller.changeProfile("female.CBBE");
  const writes = f.calls.slice(before).filter(call => call.method === "previews.morphs.set");
  assert.equal(writes.length, 1); assert.equal(writes[0].params.preview, pair.wolf.preview);
  assert.ok(Object.values(writes[0].params.values).every(value => value === 0));
  assert.equal(Object.hasOwn(writes[0].params.values, "CLAWTailLength"), false);
  assert.deepEqual(f.previews.get(pair.human.preview).values, human);
  assert.equal(f.controller.pair.profileId, "female.CBBE");
  await assert.rejects(f.controller.changeProfile("male.HIMBO"), { code: "reopenRequired" });
  const zeroStart = f.calls.length; await f.controller.zeroWolf();
  assert.equal(f.calls.slice(zeroStart).filter(call => call.method === "previews.morphs.set").length, 0);
  assert.deepEqual(f.previews.get(pair.human.preview).values, human);
});

test("writes serialize and unsent vectors coalesce with explicit superseded results", async () => {
  const gate = deferred(); let first = true;
  const f = await opened({ async before(method) { if (method === "previews.morphs.set" && first) { first = false; await gate.promise; } } });
  const firstApply = f.controller.apply({ Belly: .1 }); await tick();
  const second = f.controller.apply({ Belly: .2 }); const superseded = assert.rejects(second, { code: "superseded" });
  const third = f.controller.apply({ Belly: .3 }); gate.resolve();
  assert.equal((await firstApply).humanValues.Belly, Math.fround(.1)); await superseded;
  assert.equal((await third).humanValues.Belly, Math.fround(.3));
  const humanWrites = f.calls.filter(call => call.method === "previews.morphs.set" && call.params.preview === f.controller.pair.human.preview);
  assert.deepEqual(humanWrites.map(call => call.params.values.Belly), [Math.fround(.1), Math.fround(.3)]);
});

test("close during a pending write invalidates its result and prevents the other model write", async () => {
  const gate = deferred(); let first = true;
  const f = await opened({ async before(method) { if (method === "previews.morphs.set" && first) { first = false; await gate.promise; } } });
  const applying = f.controller.apply({ Belly: 1 }); const refused = assert.rejects(applying, { code: "stalePair" }); await tick();
  const closing = f.controller.close(); gate.resolve(); await refused; await closing;
  assert.equal(f.calls.filter(call => call.method === "previews.morphs.set").length, 1);
  assert.deepEqual([...f.previews.keys()], ["third-party"]);
});

test("scoped change notifications never reapply coefficients or echo rotations", async () => {
  const f = await opened(), count = f.calls.length;
  f.events.get("previews.changed")({ preview: f.controller.pair.human.preview, method: "previews.morphs.set" });
  f.events.get("previews.changed")({ preview: "third-party", method: "previews.close" });
  await tick(); assert.equal(f.calls.length, count); assert.ok(f.controller.pair);
});

test("external closure disposes the surviving owned preview and publishes final closed state", async () => {
  const f = await opened(), pair = f.controller.pair, count = f.calls.length;
  f.previews.delete(pair.human.preview);
  f.events.get("previews.changed")({ preview: pair.human.preview, method: "previews.close" });
  assert.equal(f.controller.pair, null);
  await tick();
  assert.deepEqual(f.calls.slice(count), [{ method: "previews.close", params: { preview: pair.wolf.preview } }]);
  assert.deepEqual([...f.previews.keys()], ["third-party"]);
  assert.deepEqual(f.controller.failedCleanup, []);
  assert.equal(f.observations.at(-1).method, "close");
  assert.equal(f.observations.at(-1).pair, null);
});
