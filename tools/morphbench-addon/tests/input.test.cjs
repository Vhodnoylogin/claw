"use strict";
const assert = require("node:assert/strict"), { test } = require("node:test");
const input = require("../src/input.js");
test("preset percentages normalize once, preserve negative endpoints and interpolate weight0/.5/1", () => {
  const preset = input.fromRows("Human", "CBBE", [
    { name: "Butt", size: "small", value: "-50" }, { name: "Butt", size: "big", value: "100" },
    { name: "MuscleAbs", size: "big", value: "80" }]);
  assert.deepEqual({ ...input.effective(preset, 0) }, { Butt: -.5, MuscleAbs: 0 });
  assert.deepEqual({ ...input.effective(preset, .5) }, { Butt: .25, MuscleAbs: Math.fround(.4) });
  assert.deepEqual({ ...input.effective(preset, 1) }, { Butt: 1, MuscleAbs: Math.fround(.8) });
});
test("unequal percentage endpoints select exact normalized values without repeated normalization", () => {
  const preset = input.fromRows("Unequal", "CBBE", [
    { name: "Butt", size: "small", value: "100" }, { name: "Butt", size: "big", value: "10" }]);
  const original = JSON.stringify(preset), high = Math.fround(.1);
  for (let repeat = 0; repeat < 3; repeat++) {
    assert.equal(input.effective(preset, 0).Butt, 1);
    assert.equal(input.effective(preset, .5).Butt, Math.fround((1 + high) / 2));
    assert.equal(input.effective(preset, 1).Butt, high);
  }
  assert.equal(JSON.stringify(preset), original, "effective must not normalize or mutate source endpoints again");
  assert.equal(input.parseJSON(JSON.stringify(input.effective(preset, 1))).values.Butt, high);
  assert.equal(input.effective(preset, 1 - Number.EPSILON).Butt, high, "the declared float32 weight rounds to 1");
});
test("tiny endpoint coefficients survive endpoint selection in either direction", () => {
  const preset = input.fromRows("Tiny", "CBBE", [
    { name: "Butt", size: "small", value: "100" }, { name: "Butt", size: "big", value: ".000001" }]);
  const tiny = Math.fround(Math.fround(.000001) / 100);
  assert.ok(tiny > 0);
  assert.equal(input.effective(preset, 0).Butt, 1);
  assert.equal(input.effective(preset, .5).Butt, Math.fround((1 + tiny) / 2));
  assert.equal(input.effective(preset, 1).Butt, tiny);
  assert.equal(input.effective({ endpoints: { Butt: { small: tiny, big: 1 } } }, 0).Butt, tiny);
  assert.equal(input.effective({ endpoints: { Butt: { small: -0, big: 1 } } }, 0).Butt, -0);
});
test("opposite large float32 endpoints interpolate finitely within their interval", () => {
  const large = Math.fround(3e38), maximum = Math.fround(3.4028234663852886e38);
  for (const high of [large, maximum]) {
    const preset = { endpoints: { Butt: { small: -high, big: high } } };
    for (const weight of [0, .25, .5, .75, 1]) {
      assert.equal(input.effective(preset, weight).Butt, Math.fround(high * (2 * weight - 1)));
    }
    for (const [low, upper] of [[-high, high], [high, -high]]) {
      for (const weight of [Math.fround(2 ** -149), .000001, .1, .9, Math.fround(1 - 2 ** -24)]) {
        const value = input.effective({ endpoints: { Butt: { small: low, big: upper } } }, weight).Butt;
        assert.ok(Number.isFinite(value)); assert.equal(value, Math.fround(value));
        assert.ok(value >= -high && value <= high);
      }
    }
  }
});
test("equal extreme and subnormal endpoints retain their values at every weight", () => {
  const maximum = Math.fround(3.4028234663852886e38), tiny = Math.fround(2 ** -149);
  for (const endpoint of [maximum, -maximum, tiny, -tiny]) {
    for (const weight of [0, .1, .5, .9, 1]) {
      assert.equal(input.effective({ endpoints: { Butt: { small: endpoint, big: endpoint } } }, weight).Butt, endpoint);
    }
  }
});
test("complete human fixture keeps unmapped nonzero fields and their distinct provenance", () => {
  const result = input.parseJSON(JSON.stringify({ humanValues: { Arms: 1, BigButt: -.25, Butt: -.5, MuscleAbs: .8 },
    profileId: "CLAW.3BA.2.48.Geometry1", humanValueProvenance: { Arms: "observed configured source", Butt: "preset reconstruction, not runtime-observed" },
    sourceMode: "full-preset-reconstruction-with-observed-subset", runtimeObservationCompleteness: { completeHumanTRI: false } }));
  assert.equal(result.values.Butt, -.5); assert.equal(result.values.BigButt, -.25);
  assert.equal(result.values.MuscleAbs, Math.fround(.8));
  assert.match(result.provenance.Butt, /not runtime-observed/);
  assert.match(result.provenance.BigButt, /unspecified/);
  assert.equal(result.completeness.completeHumanTRI, false);
});
test("already-effective coefficients are never reweighted by fixture weight metadata", () => {
  const parsed = input.parseJSON(JSON.stringify({ humanValues: { BodyMass: .9 }, weight: { normalized0to1: .3 } }));
  assert.equal(parsed.values.BodyMass, Math.fround(.9));
  assert.equal(Object.hasOwn(parsed.values, "weight"), false);
});
test("preset duplicates, dialect ambiguity and unsafe/nonfinite values are rejected", () => {
  for (const rows of [[{ name: "Butt", size: "both", value: "50" }],
    [{ name: "Butt", size: "small", value: "0" }, { name: "Butt", size: "small", value: "50" }],
    [{ name: "Butt", size: "big", value: "1e999" }], [{ name: "Butt", size: "big", value: "" }],
    [{ name: "__proto__", size: "small", value: "1" }]]) assert.throws(() => input.fromRows("Human", "CBBE", rows));
  for (const weight of [-.1, 1.1, NaN, Infinity, "1"]) assert.throws(() => input.effective({ endpoints: {} }, weight));
  assert.throws(() => input.parseJSON('{"Butt":1e999}'));
});
test("XML rejects DTD/entity declarations and oversized documents before parsing", () => {
  let called = false;
  class NeverParser { parseFromString() { called = true; throw new Error("must not parse"); } }
  for (const text of ['<!DOCTYPE SliderPresets><SliderPresets/>',
    '<!DOCTYPE SliderPresets SYSTEM "https://example.invalid/preset.dtd"><SliderPresets/>',
    '<!ENTITY external SYSTEM "file:///example"><SliderPresets/>', " ".repeat(1024 * 1024 + 1)]) {
    assert.throws(() => input.parseXML(text, NeverParser), /declarations|oversized/);
  }
  assert.equal(called, false);
  assert.throws(() => input.parseXML('<SliderPresets/>'), /DOMParser/);
});
test("XML comments and predefined/numeric escapes reach the browser parser unchanged", () => {
  const text = '<?xml version="1.0"?><SliderPresets><!-- ordinary comment --><Preset name="A &amp; &quot;B&quot;" set="CBBE"><SetSlider name="Butt" size="big" value="&#49;0"/></Preset></SliderPresets>';
  const element = (tagName, attrs, children = []) => ({ tagName, children,
    attributes: Object.keys(attrs).map(name => ({ name })), getAttribute: name => attrs[name] ?? null });
  // This tests the parser boundary and post-parse validation, not native XML decoding.
  class BoundaryParser { parseFromString(actual, type) {
    assert.equal(actual, text); assert.equal(type, "application/xml");
    return { getElementsByTagName: () => [], documentElement: element("SliderPresets", {}, [
      element("Preset", { name: 'A & "B"', set: "CBBE" }, [element("SetSlider", { name: "Butt", size: "big", value: "10" })])]) };
  } }
  const [preset] = input.parseXML(text, BoundaryParser);
  assert.equal(preset.name, 'A & "B"'); assert.equal(input.effective(preset, 1).Butt, Math.fround(.1));
});
test("wolf presets round-trip the coefficient/function matrix and reject ambiguous or mismatched input", () => {
  const profile = { id: "female.CBBE", family: "CBBE", version: "2.0.3", sex: "female", calibration: "author-test",
    rules: [{ source: "Belly", target: "CLAWTorsoBellyRound", gain: .25, cap: .8, function: "power", exponent: 3 },
      { source: "", target: "CLAWTorsoBellyRound", gain: 1, cap: .8, function: "constant", value: .1 }] };
  const text = input.matrixJSON(profile), roundTrip = input.parseMatrixJSON(text, profile);
  assert.equal(roundTrip.calibration, profile.calibration); assert.equal(roundTrip.rules[0].exponent, 3);
  assert.equal(roundTrip.rules[1].value, Math.fround(.1)); assert.equal(roundTrip.rules[0].cap, Math.fround(.8));
  assert.equal(input.matrixJSON(roundTrip), text, "repeated exports preserve normalized float32 parameters and ordered functions");
  assert.throws(() => input.parseMatrixJSON(JSON.stringify(profile)), /wolf matrix preset/);
  assert.throws(() => input.parseMatrixJSON(text, { ...profile, version: "other" }), /family\/version/);
  assert.throws(() => input.parseMatrixJSON(text, { ...profile, sex: "male" }), /family\/version/);
});
test("numeric snapshots remain distinct from matrix presets and report full target differences", () => {
  const profile = { id: "female.CBBE", family: "CBBE", sex: "female",
    rules: [{ source: "Belly", target: "CLAWTorsoBellyRound", gain: 1, cap: 1 }] };
  const envelope = { schemaVersion: 1, kind: "claw-wolf-coefficient-snapshot", profileId: profile.id, wolfValues: { CLAWTorsoBellyRound: .5 } };
  const vector = input.parseWolfSnapshot(JSON.stringify(envelope), profile);
  assert.equal(vector.CLAWTorsoBellyRound, .5);
  assert.throws(() => input.parseMatrixJSON(JSON.stringify(envelope)), /matrix preset/);
  for (const bad of [{ ...envelope, profileId: "other" }, { ...envelope, wolfValues: { CLAWTailLength: 1 } },
    { ...envelope, wolfValues: { CLAWTorsoBellyRound: "1" } }]) assert.throws(() => input.parseWolfSnapshot(JSON.stringify(bad), profile));
  const result = input.compareWolf({ CLAWTorsoBellyRound: .75, CLAWArmGirth: .25 }, vector);
  assert.equal(result.maximum, .25); assert.equal(result.rms, .25);
  assert.deepEqual(result.rows.map(row => row.difference), [.25, .25]);
});
