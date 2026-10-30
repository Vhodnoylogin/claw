;(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const catalog = window.CLAWMorphCatalog, core = window.CLAWLink, input = window.CLAWInput, sdk = window.MorphbenchAddon;
  let controller = null, supported = false, busy = false, inputRevision = 0, presets = [];
  let provenance = Object.create(null), inputLabel = "Manual preview coefficients";
  const sliderRows = []; let sliderPairKey = null;
  function status(message, error = false) { el("status").textContent = message; el("status").className = error ? "error" : ""; }
  function showError(error) { if (error.code !== "superseded") status((error.code ? error.code + ": " : "") + error.message, true); }
  function format(value) { return Number(value.toPrecision(9)).toString(); }
  function values() { return core.parseHuman(el("human").value); }
  function buttons() {
    const pair = controller && controller.pair;
    const selectedPair = pair && pair.profileId === el("profile").value &&
      pair.human.name === el("human-model").value && pair.wolf.name === el("wolf-model").value;
    for (const id of ["apply", "reset", "live"]) el(id).disabled = !selectedPair || busy;
    el("open-pair").disabled = !supported || busy || !el("human-model").value || !el("wolf-model").value;
    el("close-pair").disabled = !supported || busy || (!pair && !controller.failedCleanup.length);
    el("refresh-models").disabled = !supported || busy;
    for (const id of ["profile", "human-model", "wolf-model", "import"]) el(id).disabled = busy;
  }
  function cell(row, value, tag) { const node = document.createElement(tag || "td"); node.textContent = value; row.appendChild(node); }
  function calculate() {
    const vector = values(), result = core.evaluate(catalog, el("profile").value, vector);
    el("profile-info").textContent = result.profile.id + " · " + result.profile.sex + " · " + result.profile.calibration;
    const nonzero = result.unmapped.filter(name => vector[name] !== 0);
    el("unmapped").textContent = nonzero.length ? "Human-only nonzero inputs, preserved in the human preview: " +
      nonzero.map(name => name + "=" + format(vector[name])).join(", ") : "No nonzero human-only inputs in this vector.";
    el("unmapped-names").textContent = result.unmapped.length ? "All input names outside the wolf mapping (" +
      result.unmapped.length + "): " + result.unmapped.join(", ") : "";
    el("input-provenance").textContent = inputLabel + ". " + Object.keys(provenance).length +
      " per-name provenance entries retained. Unspecified names are preview zeros, not measured game observations.";
    el("results").replaceChildren();
    for (const data of result.rows) {
      const details = document.createElement("details"), summary = document.createElement("summary");
      summary.textContent = data.target + " = " + format(data.value); details.appendChild(summary);
      const equation = document.createElement("p"); equation.textContent = data.contributions.length ?
        "Raw sum " + format(data.rawSum) + " → clamp [0, 1] " + format(data.clamped) + " × cap " + format(data.cap) + " = " + format(data.value) :
        "No source rules for this body target. Linked baseline is zero."; details.appendChild(equation);
      const table = document.createElement("table"), head = document.createElement("tr");
      ["Source", "Input", "Gain", "Contribution"].forEach(label => cell(head, label, "th")); table.appendChild(head);
      for (const contribution of data.contributions) { const row = document.createElement("tr"); cell(row, contribution.source);
        [contribution.input, contribution.gain, contribution.contribution].forEach(value => cell(row, format(value))); table.appendChild(row); }
      details.appendChild(table); el("results").appendChild(details);
    }
    return result;
  }
  function refreshSliderValues() {
    let vector; try { vector = values(); } catch (_) { return; }
    for (const row of sliderRows) { const value = Object.hasOwn(vector, row.name) ? vector[row.name] : 0;
      row.range.min = String(Math.min(-1, value)); row.range.max = String(Math.max(2, value));
      row.range.value = String(value); row.number.value = format(value); }
  }
  function filterSliders() { const term = el("filter").value.toLowerCase(); for (const row of sliderRows) row.node.hidden = !row.name.toLowerCase().includes(term); }
  async function applyPair() {
    if (!controller || !controller.pair) return;
    const revision = ++inputRevision;
    try { calculate(); const result = await controller.apply(values());
      if (revision === inputRevision) status("Applied " + Object.keys(result.humanValues).length + " human inputs and " +
        Object.keys(result.wolfValues).length + " derived wolf body targets. The host links rotation from either panel.");
    } catch (error) { showError(error); } buttons();
  }
  function edited(name) {
    if (name) provenance[name] = "Manually edited preview coefficient; not a game observation";
    inputLabel = "Edited human preview vector"; ++inputRevision;
    try { calculate(); refreshSliderValues(); if (el("live").checked) applyPair(); } catch (error) { showError(error); }
  }
  function buildSliders() {
    el("shared-sliders").replaceChildren(); sliderRows.length = 0;
    const pair = controller && controller.pair; if (!pair) return;
    for (const name of pair.human.names) {
      const row = document.createElement("label"); row.className = "morph-row";
      const title = document.createElement("span"); title.textContent = name; row.appendChild(title);
      const range = document.createElement("input"); range.type = "range"; range.step = ".01";
      const number = document.createElement("input"); number.type = "number"; number.step = "any";
      const origin = document.createElement("small"); origin.textContent = provenance[name] || "Unspecified preview zero; runtime value unmeasured";
      const change = control => { try { if (!String(control.value).trim()) throw new Error("Enter a finite human morph value.");
        const vector = values(); vector[name] = Number(control.value); core.validateHuman(vector);
        el("human").value = JSON.stringify(vector, null, 2); origin.textContent = "Manually edited preview coefficient; not a game observation"; edited(name);
      } catch (error) { showError(error); } };
      range.addEventListener("input", () => change(range)); number.addEventListener("change", () => change(number));
      row.appendChild(range); row.appendChild(number); row.appendChild(origin); el("shared-sliders").appendChild(row);
      sliderRows.push({ name, node: row, range, number });
    }
    refreshSliderValues(); filterSliders();
  }
  function pairChanged(event) {
    const pair = controller && controller.pair;
    el("pair-status").textContent = pair ? "Human: " + pair.human.name + " · Wolf: " + pair.wolf.name +
      ". Fixed selected NIFs: neutral geometry weight is not interpolated." : "No comparison pair is open.";
    if (event && event.error) showError(event.error);
    if (!pair) el("live").checked = false;
    const bindingKey = pair ? pair.human.preview + ":" + pair.wolf.preview : null;
    if (bindingKey !== sliderPairKey) { sliderPairKey = bindingKey; buildSliders(); }
    buttons();
  }
  async function refreshModels() {
    const response = await controller.listModels();
    for (const id of ["human-model", "wolf-model"]) {
      const select = el(id), previous = select.value; select.replaceChildren();
      const empty = document.createElement("option"); empty.value = ""; empty.textContent = "Select the exact catalog resource…"; select.appendChild(empty);
      for (const row of response.entries) { const option = document.createElement("option"); option.value = row.name; option.textContent = row.name; select.appendChild(option); }
      select.value = response.entries.some(row => row.name === previous) ? previous : "";
    }
    buttons();
  }
  async function profileChanged() {
    el("live").checked = false; busy = true; buttons();
    try { if (controller && controller.pair) await controller.changeProfile(el("profile").value);
      calculate(); status("Family changed. Owned wolf outputs were cleared; review resources before applying.");
    } catch (error) {
      if (error.code === "reopenRequired") { try { await controller.close(); calculate(); status("Resource sex changed. Select matching human and wolf resources and reopen the pair."); }
        catch (cleanupError) { showError(cleanupError); } }
      else { if (controller && controller.pair) el("profile").value = controller.pair.profileId; showError(error); }
    } finally { busy = false; pairChanged(); }
  }
  el("evaluate").addEventListener("click", () => { try { calculate(); status("Calculated. No preview changed."); } catch (error) { showError(error); } });
  el("profile").addEventListener("change", profileChanged);
  el("human").addEventListener("input", () => { provenance = Object.create(null); edited(); });
  el("filter").addEventListener("input", filterSliders);
  for (const id of ["human-model", "wolf-model"]) el(id).addEventListener("change", () => {
    ++inputRevision; el("live").checked = false; buttons(); status("Resource selection changed. Open the selected comparison pair before applying.");
  });
  el("refresh-models").addEventListener("click", () => refreshModels().catch(showError));
  el("open-pair").addEventListener("click", async () => {
    busy = true; buttons(); el("live").checked = false;
    status("Opening the selected human and wolf resources…");
    try { await controller.open(el("profile").value, el("human-model").value, el("wolf-model").value);
      status("Opened independent human and wolf panels. Rotate either one; apply the shared human vector when ready.");
    } catch (error) { showError(error); } finally { busy = false; pairChanged(); }
  });
  el("close-pair").addEventListener("click", async () => {
    busy = true; buttons(); status("Closing this addon's comparison previews…"); try { await controller.close(); status("Closed this addon's comparison previews."); }
    catch (error) { showError(error); } finally { busy = false; pairChanged(); }
  });
  el("apply").addEventListener("click", applyPair);
  el("reset").addEventListener("click", async () => { el("live").checked = false;
    try { await controller.zeroWolf(); status("Zeroed only acknowledged wolf outputs. Human controls are retained."); }
    catch (error) { showError(error); } buttons(); });
  el("live").addEventListener("change", () => { if (el("live").checked) applyPair(); });
  function loadPreset() {
    const preset = presets[Number(el("preset").value)]; if (!preset) return;
    ++inputRevision;
    const vector = input.effective(preset, Number(el("weight").value));
    provenance = Object.fromEntries(Object.keys(vector).map(name => [name, "Preset endpoint interpolation; not runtime-observed"]));
    inputLabel = "Preset " + preset.name + " at coefficient weight " + el("weight").value + "; selected NIF geometry stays fixed";
    el("human").value = JSON.stringify(vector, null, 2); calculate(); buildSliders();
    status("Loaded human preset coefficients once. Apply to update both previews.");
  }
  for (const id of ["preset", "weight"]) el(id).addEventListener("change", () => { el("live").checked = false;
    try { loadPreset(); } catch (error) { showError(error); } });
  el("import").addEventListener("change", async () => {
    const file = el("import").files[0]; if (!file) return; const importRevision = ++inputRevision; el("live").checked = false;
    try { const text = await file.text();
      if (importRevision !== inputRevision) return;
      if (file.name && file.name.toLowerCase().endsWith(".xml")) {
        presets = input.parseXML(text); el("preset").replaceChildren();
        presets.forEach((preset, index) => { const option = document.createElement("option"); option.value = String(index);
          option.textContent = preset.name + " · " + preset.set; el("preset").appendChild(option); });
        el("preset-controls").hidden = false; loadPreset();
      } else {
        const parsed = input.parseJSON(text);
        if (parsed.profileId) { core.getProfile(catalog, parsed.profileId); if (parsed.profileId !== el("profile").value) {
          el("profile").value = parsed.profileId; await profileChanged(); } }
        if (importRevision !== inputRevision) return;
        provenance = parsed.provenance; inputLabel = parsed.label; el("human").value = JSON.stringify(parsed.values, null, 2);
        presets = []; el("preset-controls").hidden = true; calculate(); buildSliders();
        status("Imported the complete provided human vector and per-name provenance. Apply when the resources and family are ready.");
      }
    } catch (error) { showError(error); } el("import").value = "";
  });
  try {
    for (const profile of catalog.profiles) { const option = document.createElement("option"); option.value = profile.id;
      option.textContent = profile.family + " " + profile.version + " (" + profile.sex + ")"; el("profile").appendChild(option); }
    el("provenance").textContent = "Mapping XML SHA-256: " + catalog.source.sha256; calculate(); buttons();
    sdk.connect().then(async info => {
      controller = new window.CLAWPreview.PreviewController(sdk, catalog, { onState: pairChanged }); supported = controller.supports(info);
      if (!supported) { el("paired-support").textContent = "This host lacks independent previews. Published Application 0.8.0 supports calculation only here; paired panels need the qualified previews.* extension.";
        status("Paired preview unavailable. Calculation and input import remain available."); buttons(); return; }
      el("paired-support").textContent = "Independent previews available. Select both resources explicitly; the host links orientation only.";
      await refreshModels(); status("Select the exact human and wolf resources, then open the pair. No model is opened or applied automatically."); buttons();
    }).catch(showError);
  } catch (error) { showError(error); }
})();
