/* Scoped independent previews only. No global model/morph/view writes. */
;(function (global) {
  "use strict";
  const node = typeof module !== "undefined" && module.exports;
  const core = node ? require("./core.js") : global.CLAWLink;
  const { PairState } = node ? require("./pair.js") : global.CLAWPair;
  const requiredCapabilities = Object.freeze(["models.list", "previews.create", "previews.close",
    "previews.scene.get", "previews.morphs.get", "previews.morphs.set", "previews.link"]);
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const copy = value => JSON.parse(JSON.stringify(value));
  function frozen(value) {
    if (value && typeof value === "object") { Object.values(value).forEach(frozen); Object.freeze(value); }
    return value;
  }
  function failure(code, message) { return Object.assign(new Error(message), { code }); }
  const descriptor = error => ({ code: error.code || "previewFailure", message: error.message || String(error) });
  function binding(preview, sex) { return { id: preview, revision: preview, view: preview, sex }; }
  function morphSnapshot(value) {
    if (!object(value) || !Array.isArray(value.names) || !object(value.values) ||
        value.names.some(name => typeof name !== "string" || !name) || new Set(value.names).size !== value.names.length ||
        Object.entries(value.values).some(([name, number]) => !value.names.includes(name) || typeof number !== "number" || !Number.isFinite(number))) {
      throw failure("invalidResponse", "The host returned an invalid scoped morph snapshot.");
    }
    return value;
  }
  function readback(value, expectedNames, values) {
    morphSnapshot(value);
    if (value.names.length !== expectedNames.length || expectedNames.some(name => !value.names.includes(name)) ||
        Object.entries(values).some(([name, wanted]) => (value.values[name] || 0) !== wanted)) {
      throw failure("invalidResponse", "The scoped morph response does not confirm the complete requested batch.");
    }
  }

  class PreviewController {
    static get requiredCapabilities() { return requiredCapabilities; }
    static supports(info) {
      return object(info) && info.apiVersion === 1 && Array.isArray(info.capabilities) &&
        requiredCapabilities.every(name => info.capabilities.includes(name)) &&
        (!info.previewLimits || Number.isSafeInteger(info.previewLimits.maxPreviews) && info.previewLimits.maxPreviews >= 2);
    }
    constructor(sdk, catalog, { onState = () => {} } = {}) {
      if (!sdk || typeof sdk.request !== "function" || typeof sdk.connect !== "function" || typeof onState !== "function") {
        throw failure("invalidAdapter", "An SDK and state callback are required.");
      }
      this.sdk = sdk; this.catalog = catalog; this.onState = onState;
      this._state = new PairState(catalog); this._pair = null; this._epoch = 0;
      this._owned = new Map(); this._jobs = []; this._running = false;
      if (typeof sdk.on === "function") this._unsubscribe = sdk.on("previews.changed", event => {
        if (!event || !this._owned.has(event.preview)) return;
        if (event.method === "previews.close") {
          this._owned.delete(event.preview);
          if (this._pair && [this._pair.human.preview, this._pair.wolf.preview].includes(event.preview)) {
            // close() revokes pair authority immediately and serializes disposal
            // of its surviving owned handle behind any in-flight operation.
            // Internal closes already cleared _pair, so their events cannot
            // recursively enqueue another close or claim another preview.
            const closing = this.close();
            this._notify("previews.changed", failure("previewClosed", "A bound preview was closed. Reopen the pair."));
            closing.catch(() => {}); // close.failed already retains/reports handles.
            return;
          }
        }
        this._notify("previews.changed");
      });
    }
    supports(info) { return PreviewController.supports(info); }
    get pair() { return this._pair ? frozen(copy(this._pair)) : null; }
    get failedCleanup() {
      return frozen([...this._owned.values()].filter(item => item.error).map(item => copy(item)));
    }
    _notify(method, error = null) {
      // Observer code cannot turn an accepted host operation into a failed commit.
      try { this.onState({ method, pair: this.pair, error: error ? descriptor(error) : null, failedCleanup: this.failedCleanup }); }
      catch (_) { /* UI observers do not own lifecycle authority. */ }
    }
    _assert(epoch, pair = null) {
      if (epoch !== this._epoch || pair && pair !== this._pair) throw failure("stalePair", "The preview pair changed while the operation was pending.");
    }
    async _request(method, params, epoch, pair = null) {
      const result = await this.sdk.request(method, params); this._assert(epoch, pair); return result;
    }
    async _supported(epoch) {
      const info = await this.sdk.connect(); this._assert(epoch);
      if (!this.supports(info)) throw failure("unsupportedPreviews", "This host does not support the required independent preview methods.");
      return info;
    }
    _enqueue(kind, epoch, run, data = null) {
      return new Promise((resolve, reject) => {
        const last = this._jobs[this._jobs.length - 1];
        if (kind === "apply" && last && last.kind === kind && last.epoch === epoch) {
          last.reject(failure("superseded", "A newer human vector replaced this unsent preview request."));
          this._jobs.pop();
        }
        this._jobs.push({ kind, epoch, run, data, resolve, reject }); this._pump();
      });
    }
    async _pump() {
      if (this._running) return;
      this._running = true;
      try {
        while (this._jobs.length) {
          const job = this._jobs.shift();
          try { this._assert(job.epoch); job.resolve(await job.run(job.data, job.epoch)); }
          catch (error) { job.reject(error); }
        }
      } finally { this._running = false; }
    }
    async _cleanup(items) {
      const errors = [];
      for (const item of items) {
        if (!this._owned.has(item.preview)) continue;
        try {
          const result = await this.sdk.request("previews.close", { preview: item.preview });
          if (!result || result.closed !== true) throw failure("invalidResponse", "The host did not confirm preview closure.");
          this._owned.delete(item.preview);
        } catch (error) {
          if (error.code === "unknownPreview") this._owned.delete(item.preview);
          else { item.error = descriptor(error); this._owned.set(item.preview, item); errors.push({ preview: item.preview, ...descriptor(error) }); }
        }
      }
      return errors;
    }
    async _discard(pair, error) {
      if (pair === this._pair) { this._pair = null; this._state.invalidate(); this._epoch += 1; }
      const handles = new Set([pair.human.preview, pair.wolf.preview]);
      const errors = await this._cleanup([...this._owned.values()].filter(item => handles.has(item.preview)));
      if (errors.length) error.cleanupErrors = errors;
      this._notify("failed", error);
    }
    async listModels() {
      const epoch = this._epoch; await this._supported(epoch);
      const result = await this._request("models.list", {}, epoch);
      if (!object(result) || !Array.isArray(result.entries) || result.entries.some(item => !object(item) || typeof item.name !== "string")) {
        throw failure("invalidResponse", "The host returned an invalid model catalogue.");
      }
      return copy(result);
    }
    open(profileId, humanName, wolfName) {
      let profile;
      try {
        profile = core.getProfile(this.catalog, profileId);
        if ([humanName, wolfName].some(name => typeof name !== "string" || !name)) throw failure("invalidModel", "Select both catalogue names explicitly.");
      } catch (error) { return Promise.reject(error); }
      const epoch = ++this._epoch; this._pair = null; this._state.invalidate();
      return this._enqueue("open", epoch, async () => {
        const created = [];
        try {
          const cleanupErrors = await this._cleanup([...this._owned.values()]); this._assert(epoch);
          if (cleanupErrors.length) throw failure("cleanupFailed", "Previous preview cleanup remains unresolved.");
          await this._supported(epoch);
          const models = await this._request("models.list", {}, epoch);
          if (!models || !Array.isArray(models.entries) || [humanName, wolfName].some(name => !models.entries.some(item => item.name === name))) {
            throw failure("invalidModel", "Choose exact names from the host model catalogue.");
          }
          const result = { profileId };
          for (const [role, name] of [["human", humanName], ["wolf", wolfName]]) {
            // Record a late successful create before the epoch check so close()
            // can never strand a handle published while it was waiting.
            const response = await this.sdk.request("previews.create", { name });
            if (!response || typeof response.preview !== "string" || !response.preview || this._owned.has(response.preview)) {
              throw failure("invalidResponse", "The host did not return a new opaque preview handle.");
            }
            const item = { preview: response.preview, name }; this._owned.set(item.preview, item); created.push(item);
            this._assert(epoch);
            if (response.name !== name) throw failure("invalidResponse", "Created preview does not match the selected catalogue name.");
            const scene = await this._request("previews.scene.get", { preview: item.preview }, epoch);
            if (!scene || scene.open !== true) throw failure("invalidResponse", "Created preview has no open scene.");
            const morphs = morphSnapshot(await this._request("previews.morphs.get", { preview: item.preview }, epoch));
            result[role] = { preview: item.preview, name, names: [...morphs.names], scene: copy(scene) };
          }
          const bindings = { human: binding(result.human.preview, profile.sex), wolf: binding(result.wolf.preview, profile.sex) };
          this._state.bind(profileId, bindings);
          this._state.arm({ human: { binding: bindings.human, names: result.human.names }, wolf: { binding: bindings.wolf, names: result.wolf.names } });
          const linked = await this._request("previews.link", {
            previews: [result.human.preview, result.wolf.preview], properties: ["orientation"]
          }, epoch);
          if (!linked || JSON.stringify(linked.previews) !== JSON.stringify([result.human.preview, result.wolf.preview]) ||
              JSON.stringify(linked.properties) !== '["orientation"]') throw failure("invalidResponse", "The host did not confirm the requested orientation link.");
          this._pair = frozen(result); this._notify("open"); return this.pair;
        } catch (error) {
          this._state.invalidate();
          const errors = await this._cleanup(created); if (errors.length) error.cleanupErrors = errors;
          this._notify("open.failed", error); throw error;
        }
      });
    }
    apply(fullHumanVector) {
      let human;
      try { human = core.validateHuman(fullHumanVector); }
      catch (error) { return Promise.reject(error); }
      return this._enqueue("apply", this._epoch, async (_, epoch) => {
        const pair = this._pair;
        if (!pair) throw failure("noPair", "Open both previews before applying human morphs.");
        this._assert(epoch, pair);
        // PairState validates every supplied human name and every wolf target
        // before either scoped write. Unmapped human TRI names remain present.
        const operation = this._state.plan(human);
        const evaluated = core.evaluate(this.catalog, pair.profileId, human);
        try {
          for (const role of ["human", "wolf"]) {
            const response = await this._request("previews.morphs.set", { preview: pair[role].preview, values: operation.values[role] }, epoch, pair);
            readback(response, pair[role].names, operation.values[role]);
          }
          if (!this._state.acknowledge(operation, { token: operation.token, committed: true, complete: true, bindings: operation.bindings })) {
            throw failure("stalePair", "The paired morph receipt is stale.");
          }
          const result = frozen({ humanValues: copy(operation.values.human), wolfValues: copy(operation.values.wolf),
            unmapped: [...evaluated.unmapped], profile: copy(evaluated.profile) });
          this._notify("apply"); return result;
        } catch (error) { await this._discard(pair, error); throw error; }
      });
    }
    async _zero(operation, pair, epoch) {
      try {
        if (Object.keys(operation.values.wolf).length) {
          const response = await this._request("previews.morphs.set", { preview: pair.wolf.preview, values: operation.values.wolf }, epoch, pair);
          readback(response, pair.wolf.names, operation.values.wolf);
        }
        this._assert(epoch, pair);
        if (!this._state.acknowledge(operation, { token: operation.token, committed: true, complete: true, bindings: operation.bindings })) {
          throw failure("stalePair", "The wolf cleanup receipt is stale.");
        }
      } catch (error) { await this._discard(pair, error); throw error; }
    }
    changeProfile(profileId) {
      let profile;
      try { profile = core.getProfile(this.catalog, profileId); }
      catch (error) { return Promise.reject(error); }
      return this._enqueue("profile", this._epoch, async (_, epoch) => {
        const pair = this._pair;
        if (!pair) throw failure("noPair", "Open both previews before changing family.");
        const oldProfile = core.getProfile(this.catalog, pair.profileId);
        if (profile.sex !== oldProfile.sex) throw failure("reopenRequired", "Changing resource sex requires reopening the two models.");
        if (profileId === pair.profileId) return this.pair;
        const operation = this._state.changeProfile(profileId); await this._zero(operation, pair, epoch);
        this._state.arm({ human: { binding: operation.bindings.human, names: pair.human.names }, wolf: { binding: operation.bindings.wolf, names: pair.wolf.names } });
        this._pair = frozen({ ...pair, profileId }); this._notify("profile"); return this.pair;
      });
    }
    zeroWolf() {
      return this._enqueue("zero", this._epoch, async (_, epoch) => {
        const pair = this._pair;
        if (!pair) throw failure("noPair", "Open both previews before clearing wolf outputs.");
        await this._zero(this._state.cleanup("wolf"), pair, epoch);
        this._notify("zeroWolf"); return this.pair;
      });
    }
    close() {
      const epoch = ++this._epoch; this._pair = null; this._state.invalidate();
      return this._enqueue("close", epoch, async () => {
        const errors = await this._cleanup([...this._owned.values()]);
        if (errors.length) {
          const error = failure("cleanupFailed", "Some owned preview handles could not be closed; retry Close.");
          error.cleanupErrors = errors; this._notify("close.failed", error); throw error;
        }
        this._notify("close"); return { closed: true };
      });
    }
  }
  const api = Object.freeze({ PreviewController, requiredCapabilities });
  if (node) module.exports = api;
  else { global.CLAWPreview = api; global.CLawPreview = api; }
})(typeof window !== "undefined" ? window : globalThis);
