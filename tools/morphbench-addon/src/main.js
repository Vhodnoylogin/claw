;(function () {
  "use strict";
  const el = id => document.getElementById(id);
  const catalog = window.CLAWMorphCatalog, core = window.CLAWLink, input = window.CLAWInput, sdk = window.MorphbenchAddon;
  let controller = null, supported = false, busy = false, inputRevision = 0, presets = [];
  let provenance = Object.create(null), inputLabel = "Manual preview coefficients";
  let matrix = null, matrixEdited = false, reference = null, geometry = null, geometrySupported = false;
  const exportPageBytes = 32 * 1024;
  let exportSnapshot = null, exportPage = 0;
  let downloadSupported = false;
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
    for (const id of ["matrix-import", "matrix-reset", "matrix-add", "matrix-constant"]) el(id).disabled = busy;
    el("geometry-read").disabled = !selectedPair || busy || !geometrySupported;
    el("geometry-export").disabled = !geometry;
    el("export-download").disabled = !downloadSupported || !exportSnapshot;
  }
  function cell(row, value, tag) { const node = document.createElement(tag || "td"); node.textContent = value; row.appendChild(node); }
  function calculate() {
    const vector = values(), result = core.evaluateMatrix(matrix, vector);
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
      ["Source", "Function", "Input", "Transformed", "Gain", "Contribution"].forEach(label => cell(head, label, "th")); table.appendChild(head);
      for (const contribution of data.contributions) { const row = document.createElement("tr"); cell(row, contribution.source || "Constant");
        cell(row, (contribution.function || "linear") + (contribution.exponent ? " ^" + contribution.exponent : ""));
        [contribution.input, contribution.transformed ?? contribution.input, contribution.gain, contribution.contribution].forEach(value => cell(row, format(value))); table.appendChild(row); }
      details.appendChild(table); el("results").appendChild(details);
    }
    const canonical = core.evaluate(catalog, el("profile").value, vector);
    const comparison = input.compareWolf(result.values, reference || canonical.values);
    el("comparison-head").replaceChildren(); const heading = document.createElement("tr");
    ["Wolf target", "Calculated", reference ? "Reference snapshot" : "Canonical matrix", "Difference"].forEach(label => cell(heading, label, "th")); el("comparison-head").appendChild(heading);
    el("comparison-rows").replaceChildren();
    for (const data of comparison.rows) { const row = document.createElement("tr"); cell(row, data.target);
      [data.value, data.reference, data.difference].forEach(value => cell(row, format(value))); el("comparison-rows").appendChild(row); }
    el("comparison-status").textContent = "Calculated minus " + (reference ? "reference coefficient snapshot (omitted targets = zero)" : "canonical matrix at the same human inputs") +
      ": maximum absolute difference " + format(comparison.maximum) + "; RMS " + format(comparison.rms) + ".";
    el("matrix-status").textContent = (matrixEdited ? "Edited/imported wolf matrix" : "Canonical wolf matrix") + " · " + matrix.rules.length + " ordered sparse edges · " + matrix.id +
      ". Matrix preset includes family/version/sex and functions; coefficient snapshots are diagnostics.";
    return result;
  }
  function refreshSliderValues() {
    let vector; try { vector = values(); } catch (_) { return; }
    for (const row of sliderRows) { const value = Object.hasOwn(vector, row.name) ? vector[row.name] : 0;
      row.range.min = String(Math.min(-1, value)); row.range.max = String(Math.max(2, value));
      row.range.value = String(value); row.number.value = format(value);
      row.origin.textContent = provenance[row.name] || (Object.hasOwn(vector, row.name) ?
        "Provided preview coefficient; runtime value unmeasured" : "Unspecified preview zero; runtime value unmeasured"); }
  }
  function filterSliders() { const term = el("filter").value.toLowerCase(); for (const row of sliderRows) row.node.hidden = !row.name.toLowerCase().includes(term); }
  async function applyPair() {
    if (!controller || !controller.pair) return;
    const revision = ++inputRevision;
    try { calculate(); const result = await controller.apply(values(), matrix);
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
      const origin = document.createElement("small");
      const change = control => { try { if (!String(control.value).trim()) throw new Error("Enter a finite human morph value.");
        const vector = values(); vector[name] = Number(control.value); core.validateHuman(vector);
        el("human").value = JSON.stringify(vector, null, 2); edited(name);
      } catch (error) { showError(error); } };
      range.addEventListener("input", () => change(range)); number.addEventListener("change", () => change(number));
      row.appendChild(range); row.appendChild(number); row.appendChild(origin); el("shared-sliders").appendChild(row);
      sliderRows.push({ name, node: row, range, number, origin });
    }
    refreshSliderValues(); filterSliders();
    el("human-names").replaceChildren();
    for (const name of pair.human.names) { const option = document.createElement("option"); option.value = name; el("human-names").appendChild(option); }
  }
  function pairChanged(event) {
    const pair = controller && controller.pair;
    el("pair-status").textContent = pair ? "Human: " + pair.human.name + " · Wolf: " + pair.wolf.name +
      ". Fixed selected NIFs: neutral geometry weight is not interpolated." : "No comparison pair is open.";
    if (event && event.error) showError(event.error);
    if (!pair) el("live").checked = false;
    if (event && geometry) { geometry = null; el("geometry-rows").replaceChildren();
      el("geometry-status").textContent = "Vertex snapshot invalidated by a preview change. Read again for current vertices.";
      el("geometry-shape").disabled = true; el("geometry-page").disabled = true; }
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
      resetMatrix(); reference = null; calculate(); status("Family changed. Owned wolf outputs were cleared; review resources before applying.");
    } catch (error) {
      if (error.code === "reopenRequired") { try { await controller.close(); resetMatrix(); reference = null; calculate(); status("Resource sex changed. Select matching human and wolf resources and reopen the pair."); }
        catch (cleanupError) { showError(cleanupError); } }
      else { if (controller && controller.pair) el("profile").value = controller.pair.profileId; showError(error); }
    } finally { busy = false; pairChanged(); }
  }
  function resetMatrix() { matrix = core.getProfile(catalog, el("profile").value); matrixEdited = false; buildMatrix(); }
  function matrixChange(change) {
    try {
      const candidate = JSON.parse(JSON.stringify(matrix)); change(candidate);
      matrix = core.validateMatrix(candidate); matrixEdited = true; ++inputRevision; el("live").checked = false;
      calculate(); buildMatrix(); status("Wolf matrix updated locally. Apply to update both previews.");
    } catch (error) { buildMatrix(); showError(error); }
  }
  function filterMatrix() {
    const term = el("matrix-filter").value.toLowerCase();
    Array.from(el("matrix-rows").children).forEach((row, index) => {
      const rule = matrix.rules[index]; row.hidden = !(rule.source + " " + rule.target + " " + rule.function).toLowerCase().includes(term);
    });
  }
  function buildMatrix() {
    el("matrix-rows").replaceChildren(); if (!matrix) return;
    const targets = Object.keys(core.evaluateMatrix(matrix, {}).values);
    const addControl = (row, node) => { const td = document.createElement("td"); td.appendChild(node); row.appendChild(td); return node; };
    matrix.rules.forEach((rule, index) => {
      const row = document.createElement("tr"); cell(row, String(index + 1));
      const source = document.createElement("input"); source.type = "text"; source.value = rule.source;
      source.setAttribute("list", "human-names"); source.setAttribute("aria-label", "Human source edge " + (index + 1)); source.disabled = rule.function === "constant";
      source.addEventListener("change", () => matrixChange(candidate => { candidate.rules[index].source = source.value; })); addControl(row, source);
      const target = document.createElement("select"); target.setAttribute("aria-label", "Wolf target edge " + (index + 1));
      for (const name of targets) { const option = document.createElement("option"); option.value = name; option.textContent = name; target.appendChild(option); }
      target.value = rule.target; target.addEventListener("change", () => matrixChange(candidate => {
        const existing = candidate.rules.find(edge => edge.target === target.value); candidate.rules[index].target = target.value;
        if (existing) candidate.rules[index].cap = existing.cap;
      })); addControl(row, target);
      const fn = document.createElement("select"); fn.setAttribute("aria-label", "Function edge " + (index + 1));
      for (const name of ["linear", "positive", "negative", "smoothstep", "power", "constant"]) {
        const option = document.createElement("option"); option.value = name; option.textContent = name; fn.appendChild(option);
      }
      fn.value = rule.function; fn.addEventListener("change", () => matrixChange(candidate => {
        const edge = candidate.rules[index]; edge.function = fn.value; delete edge.exponent; delete edge.value;
        if (fn.value === "constant") { edge.source = ""; edge.value = 1; }
        else if (!edge.source) edge.source = (controller && controller.pair && controller.pair.human.names[0]) || "BodyMass";
        if (fn.value === "power") edge.exponent = 2;
      })); addControl(row, fn);
      for (const field of ["gain", "cap"]) {
        const control = document.createElement("input"); control.type = "number"; control.step = "any"; control.value = String(rule[field]);
        control.setAttribute("aria-label", field + " edge " + (index + 1));
        if (field === "cap") { control.min = "0"; control.max = "1"; }
        control.addEventListener("change", () => matrixChange(candidate => {
          if (!control.value.trim()) throw new Error("Enter a finite " + field + ".");
          if (field === "cap") candidate.rules.filter(edge => edge.target === rule.target).forEach(edge => { edge.cap = Number(control.value); });
          else candidate.rules[index][field] = Number(control.value);
        })); addControl(row, control);
      }
      const parameter = document.createElement("input"); parameter.type = "number";
      parameter.setAttribute("aria-label", "Function parameter edge " + (index + 1));
      parameter.disabled = !["power", "constant"].includes(rule.function); parameter.step = rule.function === "power" ? "1" : "any";
      parameter.value = rule.function === "power" ? String(rule.exponent) : rule.function === "constant" ? String(rule.value) : "";
      if (rule.function === "power") { parameter.min = "1"; parameter.max = "8"; }
      parameter.addEventListener("change", () => matrixChange(candidate => {
        if (!parameter.value.trim()) throw new Error("Enter a finite function parameter.");
        candidate.rules[index][rule.function === "power" ? "exponent" : "value"] = Number(parameter.value);
      })); addControl(row, parameter);
      const actions = document.createElement("div"); actions.className = "order-controls";
      for (const [label, offset] of [["↑", -1], ["↓", 1], ["×", 0]]) {
        const button = document.createElement("button"); button.type = "button"; button.textContent = label;
        button.setAttribute("aria-label", (offset ? "Move edge " + (offset < 0 ? "up" : "down") : "Remove edge") + " " + (index + 1));
        button.disabled = offset ? index + offset < 0 || index + offset >= matrix.rules.length : matrix.rules.length === 1;
        button.addEventListener("click", () => matrixChange(candidate => {
          if (!offset) candidate.rules.splice(index, 1);
          else [candidate.rules[index], candidate.rules[index + offset]] = [candidate.rules[index + offset], candidate.rules[index]];
        })); actions.appendChild(button);
      }
      addControl(row, actions); el("matrix-rows").appendChild(row);
    }); filterMatrix();
  }
  function addEdge(constant) {
    matrixChange(candidate => {
      const pair = controller && controller.pair;
      const sources = constant ? [""] : [...new Set([...(pair ? pair.human.names : []), ...candidate.rules.map(rule => rule.source).filter(Boolean), ...Object.keys(values())])];
      for (const target of Object.keys(core.evaluateMatrix(candidate, {}).values)) {
        for (const source of sources) {
          if (candidate.rules.some(edge => edge.source === source && edge.target === target)) continue;
          const existing = candidate.rules.find(edge => edge.target === target);
          const edge = { source, target, gain: 1, cap: existing ? existing.cap : 1, function: constant ? "constant" : "linear" };
          if (constant) edge.value = 0; candidate.rules.push(edge); return;
        }
      }
      throw new Error("No unused source/target edge is available. Open a human model or remove an edge first.");
    });
  }
  function renderExportPage(page) {
    if (!exportSnapshot) return;
    const starts = exportSnapshot.pageStarts, count = starts.length;
    exportPage = Math.max(0, Math.min(count - 1, page));
    const start = starts[exportPage], end = starts[exportPage + 1] ?? exportSnapshot.text.length;
    el("export-text").value = exportSnapshot.text.slice(start, end);
    el("export-page").value = String(exportPage + 1); el("export-page").max = String(count);
    el("export-previous").disabled = exportPage === 0;
    el("export-next").disabled = exportPage === count - 1;
    el("export-page-status").textContent = "Page " + (exportPage + 1) + " of " + count +
      " · complete export: " + exportSnapshot.bytes + " UTF-8 bytes. All pages remain available; the host download includes every page.";
  }
  function showExport(name, text, type = "application/json") {
    // Retain the immutable full text outside the DOM. Page boundaries keep UTF-8
    // characters intact, so saving pages in order reproduces the complete export.
    const pageStarts = [0]; let bytes = 0, pageBytes = 0;
    for (let offset = 0; offset < text.length;) {
      const point = text.codePointAt(offset), width = point > 0xffff ? 2 : 1;
      const size = point <= 0x7f ? 1 : point <= 0x7ff ? 2 : point <= 0xffff ? 3 : 4;
      if (pageBytes + size > exportPageBytes) { pageStarts.push(offset); pageBytes = 0; }
      pageBytes += size; bytes += size; offset += width;
    }
    exportSnapshot = Object.freeze({ name, type, text, bytes, pageStarts: Object.freeze(pageStarts) });
    el("export-title").textContent = "Export: " + name;
    renderExportPage(0); el("export-panel").hidden = false; el("export-panel").open = true; buttons();
    status("Prepared complete export: " + name + ". Use Prepare host download, or save every text page in order.");
  }
  async function exportChecked(run) { try { return await run(); } catch (error) { showError(error); } }
  el("matrix-filter").addEventListener("input", filterMatrix);
  el("matrix-add").addEventListener("click", () => addEdge(false)); el("matrix-constant").addEventListener("click", () => addEdge(true));
  el("matrix-reset").addEventListener("click", () => exportChecked(() => { resetMatrix(); ++inputRevision; el("live").checked = false; calculate(); status("Restored the canonical wolf matrix locally. Apply to update the previews."); }));
  el("matrix-export").addEventListener("click", () => exportChecked(() => showExport(matrix.id + ".wolf-matrix.json", input.matrixJSON(matrix))));
  el("matrix-xml").addEventListener("click", () => exportChecked(() => showExport("MorphLinks.xml", core.exportCatalog(catalog, matrix, el("game-female-family").value), "application/xml")));
  el("matrix-import").addEventListener("change", async () => {
    const file = el("matrix-import").files[0]; if (!file) return; const revision = ++inputRevision; el("live").checked = false;
    try { const text = await file.text(); if (revision !== inputRevision) return;
      matrix = input.parseMatrixJSON(text, core.getProfile(catalog, el("profile").value)); matrixEdited = true;
      calculate(); buildMatrix(); status("Imported the complete wolf coefficient/function matrix. Apply to update both previews.");
    } catch (error) { showError(error); } finally { el("matrix-import").value = ""; }
  });
  el("matrix-paste-load").addEventListener("click", () => exportChecked(() => {
    ++inputRevision; el("live").checked = false;
    matrix = input.parseMatrixJSON(el("matrix-paste").value, core.getProfile(catalog, el("profile").value)); matrixEdited = true;
    calculate(); buildMatrix(); status("Loaded the pasted wolf coefficient/function matrix. Apply to update both previews.");
  }));
  el("snapshot-import").addEventListener("change", async () => {
    const file = el("snapshot-import").files[0]; if (!file) return; const revision = ++inputRevision;
    try { const text = await file.text(); if (revision !== inputRevision) return;
      reference = input.parseWolfSnapshot(text, matrix); calculate(); status("Loaded the diagnostic coefficient reference. No preview changed.");
    } catch (error) { showError(error); } finally { el("snapshot-import").value = ""; }
  });
  el("snapshot-clear").addEventListener("click", () => exportChecked(() => { reference = null; calculate(); }));
  el("snapshot-export").addEventListener("click", () => exportChecked(() => {
    const result = calculate(); showExport(matrix.id + ".wolf-coefficients.json", JSON.stringify({ schemaVersion: 1,
      kind: "claw-wolf-coefficient-snapshot", profileId: matrix.id, wolfValues: result.values, humanValues: values(),
      note: "Diagnostic coefficients only. Import/export the wolf matrix preset to preserve conversion functions." }, null, 2));
  }));
  el("export-select").addEventListener("click", () => { el("export-text").focus(); el("export-text").select(); });
  el("export-previous").addEventListener("click", () => renderExportPage(exportPage - 1));
  el("export-next").addEventListener("click", () => renderExportPage(exportPage + 1));
  el("export-go").addEventListener("click", () => exportChecked(() => {
    if (!exportSnapshot) return;
    const page = Number(el("export-page").value);
    if (!Number.isInteger(page) || page < 1 || page > exportSnapshot.pageStarts.length) {
      throw new Error("Choose an export page between 1 and " + exportSnapshot.pageStarts.length + ".");
    }
    renderExportPage(page - 1);
  }));
  el("export-download").addEventListener("click", () => exportChecked(async () => {
    const snapshot = exportSnapshot;
    if (!snapshot) throw new Error("Prepare an export first.");
    const result = await sdk.request("exports.prepare", {filename:snapshot.name, format:snapshot.type === "application/xml" ? "xml" : "json", text:snapshot.text});
    if (!result || result.prepared !== true) throw new Error("The host did not acknowledge the prepared export.");
    status("Prepared " + result.filename + " in the Morphbench host. Click the host's Download button to save the exact snapshot.");
  }));
  function geometryShapes() { return geometry ? ["human", "wolf"].flatMap(role => geometry.models[role].shapes.map(shape => ({ role, shape }))) : []; }
  function renderGeometry() {
    const entry = geometryShapes()[Number(el("geometry-shape").value)]; el("geometry-rows").replaceChildren(); if (!entry) return;
    const shape = entry.shape, pages = Math.max(1, Math.ceil(shape.vertexCount / 100));
    const page = Math.max(0, Math.min(pages - 1, Math.floor(Number(el("geometry-page").value) || 0)));
    el("geometry-page").value = String(page); el("geometry-page").max = String(pages - 1);
    const triple = (list, index) => list.slice(index, index + 3).map(format).join(", ");
    for (let vertex = page * 100; vertex < Math.min(shape.vertexCount, (page + 1) * 100); vertex++) {
      const row = document.createElement("tr"), index = vertex * 3; cell(row, String(vertex));
      [shape.baseVertices, shape.vertices, shape.deltas].forEach(list => cell(row, triple(list, index)));
      cell(row, format(Math.hypot(...shape.deltas.slice(index, index + 3)))); el("geometry-rows").appendChild(row);
    }
    el("geometry-status").textContent = entry.role + " / " + shape.name + ": " + shape.vertexCount + " vertices; max displacement " +
      format(shape.maximumDisplacement) + "; RMS " + format(shape.rmsDisplacement) + "; captured " + geometry.capturedAt + ". Page " + page + " of " + (pages - 1) + ".";
  }
  el("geometry-shape").addEventListener("change", () => { el("geometry-page").value = "0"; renderGeometry(); });
  el("geometry-page").addEventListener("change", renderGeometry);
  el("geometry-read").addEventListener("click", async () => {
    busy = true; buttons(); status("Reading every shape's current and initial vertex positions in both previews…");
    try { geometry = await controller.readGeometry(); el("geometry-shape").replaceChildren();
      geometryShapes().forEach((entry, index) => { const option = document.createElement("option"); option.value = String(index);
        option.textContent = entry.role + " / " + entry.shape.name + " (" + entry.shape.vertexCount + " vertices)"; el("geometry-shape").appendChild(option); });
      el("geometry-shape").disabled = false; el("geometry-page").disabled = false; el("geometry-page").value = "0"; renderGeometry();
      status("Read all current/rest vertices and calculated every vertex delta. Export retains the complete arrays.");
    } catch (error) { showError(error); } finally { busy = false; buttons(); }
  });
  el("geometry-export").addEventListener("click", () => exportChecked(() => { if (geometry) showExport(matrix.id + ".paired-vertices.json", JSON.stringify(geometry)); }));
  el("evaluate").addEventListener("click", () => { try { calculate(); status("Calculated. No preview changed."); } catch (error) { showError(error); } });
  el("profile").addEventListener("change", () => { ++inputRevision; return profileChanged(); });
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
    busy = true; buttons(); status("Closing this plugin's comparison previews…"); try { await controller.close(); status("Closed this plugin's comparison previews."); }
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
    resetMatrix(); el("provenance").textContent = "Mapping XML SHA-256: " + catalog.source.sha256; calculate(); buttons();
    sdk.connect().then(async info => {
      controller = new window.CLAWPreview.PreviewController(sdk, catalog, { onState: pairChanged }); supported = controller.supports(info);
      geometrySupported = info.capabilities.includes("previews.geometry");
      downloadSupported = info.capabilities.includes("exports.prepare");
      el("geometry-support").textContent = geometrySupported ? "Public scoped geometry is available. Reads use only this plugin's two previews." :
        "Unavailable: this host does not advertise previews.geometry {preview, shape}. Current/base vertex reads require that public host capability.";
      if (!supported) { el("paired-support").textContent = "This host lacks independent previews. Published Application 0.8.0 supports calculation only here; paired panels need the qualified previews.* extension.";
        status("Paired preview unavailable. Calculation and input import remain available."); buttons(); return; }
      el("paired-support").textContent = "Independent previews available. Select both resources explicitly; the host links orientation only.";
      await refreshModels(); status("Select the exact human and wolf resources, then open the pair. No model is opened or applied automatically."); buttons();
    }).catch(showError);
  } catch (error) { showError(error); }
})();
