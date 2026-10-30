;(function () {
  "use strict";
  const element = id => document.getElementById(id);
  const catalog = window.CLAWMorphCatalog, core = window.CLAWLink;
  const sdk = window.MorphbenchAddon;
  let connected = false, busy = false, written = new Set();
  function status(message, error) {
    element("status").textContent = message;
    element("status").className = error ? "error" : "";
  }
  function buttons() {
    element("apply").disabled = !connected || busy;
    element("reset").disabled = !connected || busy;
    element("evaluate").disabled = busy;
    element("profile").disabled = busy;
    element("human").disabled = busy;
    element("import").disabled = busy;
  }
  function format(value) { return Number(value.toPrecision(9)).toString(); }
  function cell(row, value, tag) {
    const node = document.createElement(tag || "td");
    node.textContent = value;
    row.appendChild(node);
  }
  function calculate() {
    const result = core.evaluate(catalog, element("profile").value, core.parseHuman(element("human").value));
    element("profile-info").textContent = result.profile.id + " · " + result.profile.sex +
      " · " + result.profile.calibration;
    element("unmapped").textContent = result.unmapped.length
      ? "Unmapped input names (ignored): " + result.unmapped.join(", ") : "";
    element("results").replaceChildren();
    for (const data of result.rows) {
      const details = document.createElement("details");
      const summary = document.createElement("summary");
      summary.textContent = data.target + " = " + format(data.value);
      details.appendChild(summary);
      const equation = document.createElement("p");
      equation.textContent = data.contributions.length
        ? "Raw sum " + format(data.rawSum) + " → clamp [0, 1] " + format(data.clamped) +
          " × cap " + format(data.cap) + " = " + format(data.value)
        : "No source rules for this body target. Native linked baseline is zero.";
      details.appendChild(equation);
      const table = document.createElement("table"), head = document.createElement("tr");
      ["Source", "Input", "Gain", "Contribution"].forEach(label => cell(head, label, "th"));
      table.appendChild(head);
      for (const contribution of data.contributions) {
        const row = document.createElement("tr");
        cell(row, contribution.source);
        [contribution.input, contribution.gain, contribution.contribution].forEach(value => cell(row, format(value)));
        table.appendChild(row);
      }
      details.appendChild(table);
      element("results").appendChild(details);
    }
    return result;
  }
  function showError(error) {
    status((error.code ? error.code + ": " : "") + error.message, true);
  }
  element("evaluate").addEventListener("click", () => {
    try { calculate(); status("Calculated. No preview values changed."); } catch (error) { showError(error); }
  });
  element("profile").addEventListener("change", () => {
    try { calculate(); status("Family changed. Calculate or apply the selected mapping."); } catch (error) { showError(error); }
  });
  element("human").addEventListener("input", () => {
    element("results").replaceChildren();
    status("Input changed. Calculate or apply to refresh the result.");
  });
  element("import").addEventListener("change", async () => {
    const file = element("import").files[0];
    if (!file) return;
    try {
      const text = await file.text();
      core.parseHuman(text);
      element("human").value = text;
      calculate();
      status("Imported aggregate human values. No preview values changed.");
    } catch (error) { showError(error); }
    element("import").value = "";
  });
  async function write(reset) {
    if (!connected || busy) return;
    busy = true; buttons();
    try {
      // Reset does not depend on the edited human JSON: neutral sources suffice.
      const human = reset ? {} : core.parseHuman(element("human").value);
      if (!reset) calculate();
      const response = await core.writeLinked(sdk, catalog, element("profile").value, human, reset, written);
      written = reset ? new Set() : new Set(Object.keys(response.values));
      status((reset ? "Zeroed " : "Applied ") + Object.keys(response.values).length +
        " linked body targets on " + response.model + ". Other controls are preserved.");
    } catch (error) { showError(error); }
    finally { busy = false; buttons(); }
  }
  element("apply").addEventListener("click", () => write(false));
  element("reset").addEventListener("click", () => write(true));
  try {
    for (const profile of catalog.profiles) {
      const option = document.createElement("option");
      option.value = profile.id;
      option.textContent = profile.family + " " + profile.version + " (" + profile.sex + ")";
      element("profile").appendChild(option);
    }
    element("provenance").textContent = "Mapping XML SHA-256: " + catalog.source.sha256;
    calculate();
    sdk.connect().then(info => {
      const required = ["scene.get", "morphs.get", "morphs.set"];
      if (info.apiVersion !== 1 || !Array.isArray(info.capabilities) ||
          required.some(method => !info.capabilities.includes(method))) {
        throw new Error("The host does not supply the required Morphbench API v1 methods.");
      }
      connected = true; buttons();
      status("Ready. Open the intended CLAW body in Morphbench, then apply after reviewing the calculation.");
    }).catch(showError);
  } catch (error) { showError(error); }
})();
