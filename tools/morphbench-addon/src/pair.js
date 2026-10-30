/* Consumer-only paired preview foundation. No Morphbench methods or DOM access.
 * A future documented host adapter must enforce every expected binding revision
 * and source interaction sequence at commit time. These plans do not supply that
 * missing host capability, and making a plan never changes a preview.
 */
;(function (global) {
  "use strict";
  const core = typeof module !== "undefined" && module.exports ? require("./core.js") : global.CLAWLink;
  const roles = ["human", "wolf"];
  const plain = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const fail = message => { throw new Error(message); };
  const detached = value => JSON.parse(JSON.stringify(value));
  function freeze(value) {
    if (value && typeof value === "object") {
      Object.values(value).forEach(freeze); Object.freeze(value);
    }
    return value;
  }
  function token(value) { return typeof value === "string" && value.length > 0 && value.length <= 512; }
  function binding(value) {
    if (!plain(value) || !token(value.id) || !token(value.revision) || !token(value.view) ||
        !["male", "female"].includes(value.sex)) fail("An explicit model/view identity, revision and sex are required.");
    return freeze({ id: value.id, revision: value.revision, view: value.view, sex: value.sex });
  }
  function sameBinding(left, right) {
    return plain(left) && plain(right) && ["id", "revision", "view", "sex"].every(key => left[key] === right[key]);
  }
  function key(value) { return JSON.stringify([value.id, value.revision, value.view, value.sex]); }
  function names(snapshot, expected) {
    if (!plain(snapshot) || !sameBinding(snapshot.binding, expected) || !Array.isArray(snapshot.names) ||
        snapshot.names.some(name => typeof name !== "string" || !name) || new Set(snapshot.names).size !== snapshot.names.length) {
      fail("Model names must belong to the exact bound resource revision.");
    }
    return new Set(snapshot.names);
  }

  class PairState {
    constructor(catalog) {
      this.catalog = catalog; this.epoch = 0; this.enabled = false;
      this.profileId = null; this.bindings = null; this.available = null;
      this.owned = new Map(); this.sequence = 0; this.plans = new WeakSet(); this.pendingOperation = null;
    }
    bind(profileId, pair) {
      const profile = core.getProfile(this.catalog, profileId);
      const human = binding(pair.human), wolf = binding(pair.wolf);
      if (human.id === wolf.id || human.view === wolf.view) fail("Human and wolf need distinct model and view identities.");
      if (human.sex !== profile.sex || wolf.sex !== profile.sex) fail("Resource sex does not match the selected human family.");
      this.invalidate(); this.profileId = profileId; this.bindings = freeze({ human, wolf });
      return this.snapshot();
    }
    invalidate() { this.epoch += 1; this.enabled = false; this.available = null; this.pendingOperation = null; }
    snapshot() {
      return freeze({ epoch: this.epoch, profileId: this.profileId,
        bindings: this.bindings ? detached(this.bindings) : null, enabled: this.enabled });
    }
    current(snapshot, requireEnabled = true) {
      return plain(snapshot) && snapshot.epoch === this.epoch && snapshot.profileId === this.profileId &&
        (!requireEnabled || this.enabled) && plain(snapshot.bindings) && this.bindings !== null &&
        roles.every(role => sameBinding(snapshot.bindings[role], this.bindings[role]));
    }
    arm(snapshots) {
      if (!this.bindings) fail("Bind both resources first.");
      if (this.pendingOperation) fail("Resolve the pending preview commit before rearming the pair.");
      const profile = core.getProfile(this.catalog, this.profileId);
      if (roles.some(role => this.bindings[role].sex !== profile.sex)) fail("Rebind resources for the selected family sex.");
      const available = {};
      for (const role of roles) available[role] = names(snapshots[role], this.bindings[role]);
      if (!profile.rules.some(rule => available.human.has(rule.source))) fail("Human model has no configured source morphs for the declared family.");
      const targets = Object.keys(core.evaluate(this.catalog, this.profileId, {}).values);
      const missing = targets.filter(name => !available.wolf.has(name));
      if (missing.length) fail("Wolf model is missing linked body targets: " + missing.join(", "));
      this.epoch += 1; this.available = available; this.enabled = true;
      return this.snapshot();
    }
    ledger(role, resource = this.bindings && this.bindings[role]) {
      return new Set(resource ? this.owned.get(role + ":" + key(resource)) || [] : []);
    }
    plan(humanValues) {
      if (!this.enabled || !this.available) fail("Explicitly arm the validated pair before preparing writes.");
      if (this.pendingOperation) fail("Resolve the pending preview commit before preparing another write.");
      const human = core.validateHuman(humanValues);
      const result = core.evaluate(this.catalog, this.profileId, human);
      const inputs = Object.create(null), outputs = Object.assign(Object.create(null), result.values);
      for (const rule of result.profile.rules) {
        if (this.available.human.has(rule.source)) inputs[rule.source] = human[rule.source] || 0;
      }
      for (const [name, value] of Object.entries(human)) {
        if (!this.available.human.has(name)) fail("Human model is missing input morph: " + name);
        inputs[name] = value;
      }
      for (const [role, values] of [["human", inputs], ["wolf", outputs]]) {
        for (const name of this.ledger(role)) {
          if (!this.available[role].has(name)) fail("Bound revision lost a previously owned morph: " + name);
          if (!Object.hasOwn(values, name)) values[name] = 0;
        }
        const missing = Object.keys(values).filter(name => !this.available[role].has(name));
        if (missing.length) fail("Bound model is missing planned morphs: " + missing.join(", "));
      }
      const operation = freeze({ ...this.snapshot(), kind: "morphs", token: "pair:" + this.epoch + ":" + (++this.sequence),
        values: { human: inputs, wolf: outputs } });
      this.plans.add(operation); this.pendingOperation = operation; return operation;
    }
    acknowledge(operation, receipt) {
      if (!plain(operation) || !this.plans.has(operation)) fail("Unknown or already acknowledged pair operation.");
      if (!this.current(operation, operation.kind === "morphs")) return false;
      if (!plain(receipt) || receipt.committed !== true || receipt.complete !== true ||
          receipt.stale === true || receipt.partial === true || receipt.token !== operation.token || !plain(receipt.bindings) ||
          roles.some(role => !sameBinding(receipt.bindings[role], operation.bindings[role]))) {
        fail("Complete commit receipt must match the operation token and expected model revisions.");
      }
      if (operation.kind === "morphs") {
        for (const role of roles) this.owned.set(role + ":" + key(operation.bindings[role]), new Set(Object.keys(operation.values[role])));
      } else if (operation.kind === "cleanup") {
        for (const role of roles) {
          const remaining = new Set(this.ledger(role, operation.bindings[role]));
          Object.keys(operation.values[role]).forEach(name => remaining.delete(name));
          this.owned.set(role + ":" + key(operation.bindings[role]), remaining);
        }
      } else fail("Unknown pair operation.");
      this.pendingOperation = null; this.plans.delete(operation); return true;
    }
    changeProfile(profileId) {
      core.getProfile(this.catalog, profileId);
      if (this.pendingOperation) fail("Resolve the pending preview commit before changing family.");
      this.invalidate(); this.profileId = profileId;
      // Only acknowledged wolf outputs are neutralized. Shared human input and
      // unrelated preview controls are not silently reset by a family change.
      return this.cleanup("wolf");
    }
    cleanup(role = "wolf") {
      if (!roles.includes(role) || !this.bindings) fail("No bound cleanup role.");
      if (this.pendingOperation) fail("Resolve the pending preview commit before preparing cleanup.");
      const values = { human: {}, wolf: {} };
      for (const name of this.ledger(role)) values[role][name] = 0;
      const operation = freeze({ ...this.snapshot(), kind: "cleanup", token: "cleanup:" + this.epoch + ":" + (++this.sequence), values });
      this.plans.add(operation); this.pendingOperation = operation; return operation;
    }
  }

  function angle(value) {
    if (typeof value !== "number" || !Number.isFinite(value)) fail("Camera angles must be finite.");
    return ((value % 360) + 360) % 360;
  }
  function rotation(value) {
    if (!plain(value) || typeof value.pitch !== "number" || !Number.isFinite(value.pitch)) fail("Camera angles must be finite.");
    return { yaw: angle(value.yaw), pitch: value.pitch };
  }
  function equalRotation(left, right, epsilon = 1e-6) {
    if (!left || !right) return false;
    const delta = Math.abs(left.yaw - right.yaw);
    return Math.min(delta, 360 - delta) <= epsilon && Math.abs(left.pitch - right.pitch) <= epsilon;
  }

  class RotationSynchronizer {
    constructor({ snapshot, current, setRotation, onError = () => {} }) {
      if ([snapshot, current, setRotation, onError].some(fn => typeof fn !== "function")) fail("Explicit camera adapter callbacks are required.");
      this.snapshot = snapshot; this.current = current; this.setRotation = setRotation; this.onError = onError;
      this.enabled = false; this.generation = 0; this.lastSequence = -1; this.lastSeenSequence = -1; this.counter = 0;
      this.pending = null; this.running = null; this.known = new Map(); this.echoes = new Set();
    }
    enable() {
      const state = this.snapshot();
      if (!state || !state.bindings || !this.current(state)) fail("A current validated pair is required for rotation linking.");
      this.disable(); this.enabled = true; return this.generation;
    }
    disable() {
      this.enabled = false; this.generation += 1; this.pending = null;
      this.lastSequence = -1; this.lastSeenSequence = -1; this.known.clear(); this.echoes.clear();
    }
    receive(event) {
      if (!this.enabled) return false;
      if (!plain(event) || !Number.isSafeInteger(event.sequence) || event.sequence < 0) fail("An ordered camera event is required.");
      if (!["user", "programmatic"].includes(event.origin)) return false;
      const snapshot = this.snapshot();
      if (!this.current(snapshot)) return false;
      const sourceRole = roles.find(role => sameBinding(event.binding, snapshot.bindings[role]));
      if (!sourceRole || event.sequence <= this.lastSeenSequence) return false;
      const value = rotation(event), targetRole = sourceRole === "human" ? "wolf" : "human";
      this.lastSeenSequence = event.sequence; this.known.set(key(event.binding), value);
      // Observe programmatic changes so the cache cannot hide a later real
      // mismatch, but never forward them as a new gesture. An external camera
      // reset supersedes older queued work; our own echo does not cancel a newer
      // user gesture queued while its request was in flight.
      if (event.origin !== "user" || this.echoes.has(event.token)) {
        if (!this.echoes.has(event.token)) { this.lastSequence = event.sequence; this.pending = null; }
        return false;
      }
      this.lastSequence = event.sequence; this.known.set(key(event.binding), value);
      if (equalRotation(this.known.get(key(snapshot.bindings[targetRole])), value)) { this.pending = null; return false; }
      this.pending = { snapshot, generation: this.generation, source: snapshot.bindings[sourceRole],
        target: snapshot.bindings[targetRole], sourceSequence: event.sequence, ...value };
      this.kick();
      return true;
    }
    kick() {
      if (this.running) return;
      this.running = Promise.resolve().then(() => this.drain()).finally(() => {
        this.running = null;
        if (this.pending && this.enabled) this.kick();
      });
    }
    valid(task) {
      return this.enabled && task.generation === this.generation && this.current(task.snapshot);
    }
    async drain() {
      while (this.pending) {
        const task = this.pending; this.pending = null;
        if (!this.valid(task) || task.sourceSequence !== this.lastSequence) continue;
        const token = "rotation:" + this.generation + ":" + (++this.counter);
        this.echoes.add(token);
        if (this.echoes.size > 64) this.echoes.delete(this.echoes.values().next().value);
        const operation = freeze({ ...task, token });
        try {
          // The adapter must reject a newer user interaction at commit time,
          // not merely echo a late SDK request. A local queue cannot supply a
          // missing host camera-revision fence or retract an accepted write.
          const response = await this.setRotation(operation);
          if (!this.valid(task) || task.sourceSequence !== this.lastSequence || response && response.stale === true) continue;
          if (!plain(response) || !sameBinding(response.binding, task.target)) fail("Camera acknowledgment belongs to another resource revision.");
          this.known.set(key(task.target), rotation(response));
        } catch (error) {
          if (this.valid(task)) this.onError(error);
        }
      }
    }
    async flush() { while (this.running) await this.running; }
  }

  const api = Object.freeze({ PairState, RotationSynchronizer, sameBinding, equalRotation });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.CLAWPair = api;
})(typeof window !== "undefined" ? window : globalThis);
