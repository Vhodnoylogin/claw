/* Human input import and preset interpolation. Independent of host previews. */
;(function (global) {
  "use strict";
  const core = typeof module !== "undefined" && module.exports ? require("./core.js") : global.CLAWLink;
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const fail = message => { throw new Error(message); };
  function finite(value) {
    if (typeof value !== "number" || !Number.isFinite(value) || !Number.isFinite(Math.fround(value))) fail("Preset numbers must be finite float32 values.");
    return Math.fround(value);
  }
  function fromRows(name, set, rows) {
    if (typeof name !== "string" || !name.trim() || typeof set !== "string" || !set.trim() || !Array.isArray(rows)) fail("Invalid human preset metadata.");
    const endpoints = Object.create(null), seen = new Set();
    for (const row of rows) {
      if (!object(row) || typeof row.name !== "string" || !["small", "big"].includes(row.size)) fail("Only named explicit small/big preset endpoints are supported.");
      if (typeof row.value !== "string" && typeof row.value !== "number") fail("Invalid preset percentage.");
      if (typeof row.value === "string" && !/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(row.value)) fail("Invalid preset percentage.");
      const value = finite(finite(Number(row.value)) / 100);
      core.validateHuman({ [row.name]: value });
      const pair = JSON.stringify([row.name, row.size]);
      if (seen.has(pair)) fail("Duplicate human preset endpoint: " + row.name + "/" + row.size);
      seen.add(pair);
      if (!Object.hasOwn(endpoints, row.name)) endpoints[row.name] = { small: 0, big: 0 };
      endpoints[row.name][row.size] = value;
    }
    return { name, set, endpoints };
  }
  function effective(preset, weight) {
    if (!object(preset) || !object(preset.endpoints) || typeof weight !== "number" || !Number.isFinite(weight) || weight < 0 || weight > 1) fail("Preset weight must be finite in [0,1].");
    const w = Math.fround(weight), values = Object.create(null);
    for (const [name, row] of Object.entries(preset.endpoints)) {
      if (!object(row) || !Object.hasOwn(row, "small") || !Object.hasOwn(row, "big")) fail("Preset needs explicit normalized endpoints.");
      const low = finite(row.small), high = finite(row.big);
      // Preview policy: normalized float32 endpoints/weight, exact endpoints,
      // then one float32 rounding of a bounded binary64 convex combination.
      // Avoid a float32 delta: it can overflow or cancel a small high endpoint.
      if (w === 0) values[name] = low;
      else if (w === 1) values[name] = high;
      else values[name] = finite(Math.max(Math.min(low, high), Math.min(Math.max(low, high), low * (1 - w) + high * w)));
    }
    return core.validateHuman(values);
  }
  function parseJSON(text) {
    const parsed = JSON.parse(text);
    const envelope = object(parsed) && object(parsed.humanValues);
    const values = core.validateHuman(envelope ? parsed.humanValues : parsed);
    const provenance = Object.create(null);
    for (const name of Object.keys(values)) {
      const declared = envelope && object(parsed.humanValueProvenance) ? parsed.humanValueProvenance[name] : null;
      provenance[name] = typeof declared === "string" ? declared : "Imported preview coefficient; runtime provenance unspecified";
    }
    return { values, provenance, profileId: envelope && typeof parsed.profileId === "string" ? parsed.profileId : null,
      label: envelope && typeof parsed.sourceMode === "string" ? parsed.sourceMode : "Imported coefficient vector",
      completeness: envelope && object(parsed.runtimeObservationCompleteness) ? parsed.runtimeObservationCompleteness : null };
  }
  function parseXML(text, Parser = global.DOMParser) {
    if (typeof text !== "string" || new TextEncoder().encode(text).length > 1024 * 1024 || /<!(?:DOCTYPE|ENTITY)\b/i.test(text)) fail("Preset XML DTD/entity declarations or oversized input are unsupported.");
    if (typeof Parser !== "function") fail("XML preset parsing requires the browser DOMParser.");
    const doc = new Parser().parseFromString(text, "application/xml");
    if (doc.getElementsByTagName("parsererror").length || !doc.documentElement || doc.documentElement.tagName !== "SliderPresets") fail("Expected a valid BodySlide SliderPresets document.");
    const presets = [], seen = new Set();
    for (const element of Array.from(doc.documentElement.children)) {
      if (element.tagName !== "Preset") fail("Unexpected element in SliderPresets.");
      const name = element.getAttribute("name"), set = element.getAttribute("set");
      const rows = [];
      for (const child of Array.from(element.children)) {
        if (child.tagName === "Group") continue;
        if (child.tagName !== "SetSlider" || child.children.length) fail("Unsupported human preset element.");
        const attrs = Array.from(child.attributes, attribute => attribute.name);
        if (attrs.length !== 3 || attrs.some(attr => !["name", "size", "value"].includes(attr))) fail("Unsupported human preset slider attribute.");
        rows.push({ name: child.getAttribute("name"), size: child.getAttribute("size"), value: child.getAttribute("value") });
      }
      if (seen.has(name)) fail("Duplicate preset name; select an unambiguous source file.");
      seen.add(name); presets.push(fromRows(name, set, rows));
    }
    if (!presets.length) fail("Preset XML contains no presets.");
    return presets;
  }
  const api = Object.freeze({ fromRows, effective, parseJSON, parseXML });
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else global.CLAWInput = api;
})(typeof window !== "undefined" ? window : globalThis);
