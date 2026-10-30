"use strict";
const assert = require("node:assert/strict");
const { test } = require("node:test");
const fs = require("node:fs");
const path = require("node:path");
const core = require("../src/core.js"), { PairState, RotationSynchronizer, equalRotation } = require("../src/pair.js");
if (!process.argv[2]) throw new Error("Pass the external build's catalog.json path.");
const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]), "utf8"));
const female = catalog.profiles.find(profile => profile.family === "3BA").id;
const cbbe = catalog.profiles.find(profile => profile.family === "CBBE").id;
const male = catalog.profiles.find(profile => profile.family === "HIMBO").id;
const tick = () => new Promise(setImmediate);
const resource = (id, sex = "female", revision = "r1") => ({ id, revision, view: "view:" + id, sex });
function fixture() {
  const state = new PairState(catalog);
  const bindings = { human: resource("human"), wolf: resource("wolf") };
  state.bind(female, bindings);
  const humanNames = [...new Set(catalog.profiles.flatMap(profile => profile.rules.map(rule => rule.source))), "HumanOther"];
  const snapshots = { human: { binding: bindings.human, names: humanNames },
    wolf: { binding: bindings.wolf, names: [...Object.keys(core.evaluate(catalog, female, {}).values), "CLAWHeadEarSize", "CLAWTailLength"] } };
  state.arm(snapshots);
  return { state, bindings, snapshots };
}
const receipt = operation => ({ committed: true, complete: true, token: operation.token, bindings: operation.bindings });

test("immutable pair plans keep one human vector and the unchanged exact float32 mapping", () => {
  const { state } = fixture(), input = { Belly: .7, BigBelly: .7, HumanOther: -.25 };
  const expected = core.evaluate(catalog, female, input).values;
  const operation = state.plan(input); input.Belly = 0;
  assert.equal(operation.values.human.Belly, Math.fround(.7));
  assert.equal(operation.values.human.HumanOther, -.25);
  assert.deepEqual(operation.values.wolf, expected);
  assert.equal(operation.values.wolf.CLAWTorsoBellyRound, 1);
  assert.equal(Object.hasOwn(operation.values.wolf, "CLAWHeadEarSize"), false);
  assert.equal(Object.hasOwn(operation.values.wolf, "CLAWTailLength"), false);
  assert.ok(Object.isFrozen(operation.values.human));
  assert.throws(() => { operation.bindings.wolf.id = "other"; }, TypeError);
});

test("pair authority requires distinct resource/view identities and matching declared sex", () => {
  const state = new PairState(catalog);
  assert.throws(() => state.bind(female, { human: resource("same"), wolf: resource("same") }), /distinct/);
  assert.throws(() => state.bind(female, { human: resource("human", "male"), wolf: resource("wolf") }), /sex/);
  assert.throws(() => state.bind(female, { human: { id: "human" }, wolf: resource("wolf") }), /identity/);
});

test("model names from another resource revision cannot arm a pair or permit a partial write", () => {
  const { state, snapshots } = fixture(); state.invalidate();
  assert.throws(() => state.plan({ Belly: 1 }), /arm/);
  snapshots.human.binding = { ...snapshots.human.binding, revision: "changed" };
  assert.throws(() => state.arm(snapshots), /exact bound/);
  const other = fixture(); other.state.invalidate();
  other.snapshots.wolf.names = other.snapshots.wolf.names.filter(name => name !== "CLAWTorsoGirth");
  assert.throws(() => other.state.arm(other.snapshots), /missing linked body targets/);
  assert.throws(() => fixture().state.plan({ UnavailableHumanMorph: 1 }), /missing input/);
  const wrongHuman = fixture(); wrongHuman.state.invalidate(); wrongHuman.snapshots.human.names = ["CLAWTorsoGirth"];
  assert.throws(() => wrongHuman.state.arm(wrongHuman.snapshots), /Human model has no configured source/);
});

test("only exact acknowledged commits acquire ownership; stale or forged receipts do not", () => {
  const { state } = fixture(), operation = state.plan({ Belly: .5 });
  assert.throws(() => state.acknowledge({ ...operation }, receipt(operation)), /Unknown/);
  assert.throws(() => state.acknowledge(operation, { bindings: {} }), /expected model revisions/);
  for (const overrides of [{ committed: false }, { complete: false }, { partial: true },
    { stale: true }, { token: "another-operation" }]) {
    assert.throws(() => state.acknowledge(operation, { ...receipt(operation), ...overrides }), /Complete commit receipt/);
  }
  assert.equal(state.ledger("wolf").size, 0);
  assert.equal(state.acknowledge(operation, receipt(operation)), true);
  assert.throws(() => state.acknowledge(operation, receipt(operation)), /already acknowledged/);
  const stale = state.plan({ Belly: 1 }); state.invalidate();
  assert.equal(state.acknowledge(stale, receipt(stale)), false);
});

test("family change zeroes only acknowledged wolf outputs, leaves human controls and invalidates work", () => {
  const { state, snapshots } = fixture();
  const notAccepted = state.plan({ Belly: 1 });
  assert.throws(() => state.changeProfile(cbbe), /pending preview commit/);
  state.invalidate();
  const empty = state.changeProfile(cbbe);
  assert.deepEqual(empty.values, { human: {}, wolf: {} });
  assert.equal(state.acknowledge(notAccepted, receipt(notAccepted)), false);
  state.acknowledge(empty, receipt(empty));
  state.arm(snapshots);
  const accepted = state.plan({ Belly: .5 }); state.acknowledge(accepted, receipt(accepted));
  const cleanup = state.changeProfile(female);
  assert.deepEqual(Object.keys(cleanup.values.wolf).sort(), Object.keys(accepted.values.wolf).sort());
  assert.deepEqual(cleanup.values.human, {});
  assert.ok(Object.values(cleanup.values.wolf).every(value => value === 0));
  assert.equal(Object.hasOwn(cleanup.values.wolf, "CLAWHeadEarSize"), false);
  state.acknowledge(cleanup, receipt(cleanup));
  assert.equal(state.ledger("wolf").size, 0);
  const maleCleanup = state.changeProfile(male);
  state.acknowledge(maleCleanup, receipt(maleCleanup));
  assert.throws(() => state.arm(snapshots), /Rebind resources/);
});

test("rebinding to a new model revision never inherits ownership or applies a delayed old plan", () => {
  const { state } = fixture(), first = state.plan({ Belly: .5 });
  state.acknowledge(first, receipt(first));
  const pending = state.plan({ Belly: .9 });
  state.bind(female, { human: resource("human", "female", "r2"), wolf: resource("wolf", "female", "r2") });
  assert.equal(state.acknowledge(pending, receipt(pending)), false);
  assert.deepEqual(state.cleanup("wolf").values.wolf, {});
});

test("omitted prior human fields are zeroed only within the same acknowledged binding", () => {
  const { state } = fixture(), first = state.plan({ HumanOther: -.25, Belly: 1 });
  state.acknowledge(first, receipt(first));
  const second = state.plan({ Belly: .25 });
  assert.equal(second.values.human.HumanOther, 0);
  assert.equal(Object.hasOwn(second.values.human, "CLAWTailLength"), false);
});

test("unacknowledged morph plans cannot race another batch or a family transition", () => {
  const { state } = fixture(), first = state.plan({ HumanOther: .5 });
  assert.throws(() => state.plan({ Belly: 1 }), /pending preview commit/);
  assert.throws(() => state.changeProfile(cbbe), /pending preview commit/);
  assert.throws(() => state.cleanup(), /pending preview commit/);
  assert.throws(() => state.arm(fixture().snapshots), /pending preview commit/);
  state.acknowledge(first, receipt(first));
  assert.equal(state.plan({ Belly: 1 }).values.human.HumanOther, 0);
});

test("cleanup must resolve before a new morph plan or rearm can overwrite its outputs", () => {
  const { state, snapshots } = fixture(), first = state.plan({ Belly: .5 });
  state.acknowledge(first, receipt(first));
  const cleanup = state.cleanup();
  assert.throws(() => state.plan({ Belly: 1 }), /pending preview commit/);
  assert.throws(() => state.arm(snapshots), /pending preview commit/);
  state.acknowledge(cleanup, receipt(cleanup));
  assert.equal(state.plan({ Belly: 1 }).values.wolf.CLAWTorsoBellyRound > 0, true);
});

function cameraFixture(setter) {
  const { state, bindings } = fixture(), calls = [], errors = [];
  let sync;
  sync = new RotationSynchronizer({ snapshot: () => state.snapshot(), current: snapshot => state.current(snapshot),
    onError: error => errors.push(error), setRotation: async operation => {
      calls.push(operation);
      if (setter) return setter(operation, sync);
      return { binding: operation.target, yaw: operation.yaw, pitch: operation.pitch };
    } });
  const event = (role, sequence, yaw, extra = {}) => ({ binding: bindings[role], sequence, yaw, pitch: 10, origin: "user", ...extra });
  sync.enable(); return { sync, state, bindings, calls, errors, event };
}

test("rotation from either panel updates only the other panel and never forwards zoom/pan", async () => {
  const { sync, calls, event, bindings } = cameraFixture();
  sync.receive(event("human", 1, 25)); await sync.flush();
  sync.receive(event("wolf", 2, 50)); await sync.flush();
  assert.equal(calls.length, 2);
  assert.deepEqual(calls.map(call => call.target), [bindings.wolf, bindings.human]);
  assert.ok(calls.every(call => !Object.hasOwn(call, "zoom") && !Object.hasOwn(call, "pan")));
});

test("programmatic echoes and copied operation tokens never create feedback requests", async () => {
  let f;
  f = cameraFixture(async (operation, sync) => {
    assert.equal(sync.receive({ binding: operation.target, sequence: operation.sourceSequence + 1,
      yaw: operation.yaw, pitch: operation.pitch, origin: "programmatic", token: operation.token }), false);
    assert.equal(sync.receive({ binding: operation.target, sequence: operation.sourceSequence + 2,
      yaw: operation.yaw, pitch: operation.pitch, origin: "user", token: operation.token }), false);
    return { binding: operation.target, yaw: operation.yaw, pitch: operation.pitch };
  });
  f.sync.receive(f.event("human", 1, 30)); await f.sync.flush();
  assert.equal(f.calls.length, 1);
});

test("latest rotation coalesces across panels; host adapter rejects an overtaken in-flight write", async () => {
  let release; const gate = new Promise(resolve => { release = resolve; });
  const committed = [];
  const f = cameraFixture(async (operation, sync) => {
    if (operation.sourceSequence === 1) await gate;
    if (operation.sourceSequence !== sync.lastSequence) return { stale: true };
    committed.push(operation.sourceSequence);
    return { binding: operation.target, yaw: operation.yaw, pitch: operation.pitch };
  });
  f.sync.receive(f.event("human", 1, 10)); await tick();
  f.sync.receive(f.event("human", 2, 20));
  f.sync.receive(f.event("wolf", 3, 30)); release(); await f.sync.flush();
  assert.deepEqual(f.calls.map(call => call.sourceSequence), [1, 3]);
  assert.deepEqual(committed, [3]);
  assert.equal(f.calls[1].target.id, "human");
});

test("yaw wrapping, equal orientation and out-of-order events do not create extra writes", async () => {
  const f = cameraFixture();
  f.sync.receive(f.event("human", 5, 359.9999999)); await f.sync.flush();
  assert.equal(f.sync.receive(f.event("human", 6, -.0000001)), false);
  assert.equal(f.sync.receive(f.event("wolf", 4, 90)), false);
  assert.equal(f.calls.length, 1);
  assert.equal(equalRotation({ yaw: 359.9999999, pitch: 0 }, { yaw: 0, pitch: 0 }), true);
});

test("observed programmatic reset updates the cache without forwarding or hiding the next user mismatch", async () => {
  const f = cameraFixture();
  f.sync.receive(f.event("human", 1, 20)); await f.sync.flush();
  assert.equal(f.sync.receive(f.event("wolf", 2, 0, { origin: "programmatic" })), false);
  assert.equal(f.calls.length, 1);
  assert.equal(f.sync.receive(f.event("human", 3, 20)), true); await f.sync.flush();
  assert.equal(f.calls.length, 2);
  assert.equal(f.calls[1].target.id, "wolf");
  assert.equal(f.calls[1].yaw, 20);
});

test("invalidation or disabling discards queued work and stale acknowledgments", async () => {
  let release; const gate = new Promise(resolve => { release = resolve; });
  const f = cameraFixture(async operation => { await gate; return { binding: operation.target, yaw: 5, pitch: 0 }; });
  f.sync.receive(f.event("human", 1, 10)); await tick();
  f.sync.receive(f.event("wolf", 2, 30));
  f.state.invalidate(); f.sync.disable(); release(); await f.sync.flush();
  assert.equal(f.calls.length, 1);
  assert.equal(f.sync.known.size, 0);
  assert.equal(f.sync.receive(f.event("human", 3, 20)), false);
});

test("wrong-revision camera event/acknowledgment and malformed values cannot gain authority", async () => {
  const f = cameraFixture(async operation => ({ binding: { ...operation.target, revision: "other" }, yaw: 0, pitch: 0 }));
  assert.equal(f.sync.receive(f.event("human", 1, 20, { binding: resource("human", "female", "other") })), false);
  assert.throws(() => f.sync.receive(f.event("human", 1, NaN)), /finite/);
  assert.throws(() => f.sync.receive(f.event("human", 1.5, 20)), /ordered/);
  f.sync.receive(f.event("human", 2, 20)); await f.sync.flush();
  assert.equal(f.errors.length, 1);
  assert.match(f.errors[0].message, /another resource revision/);
});
