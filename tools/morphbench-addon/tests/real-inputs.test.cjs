"use strict";
// Contract checks using audited real-resource names and retained fixture data.
// No NIF renderer, game, actual SDK host or runtime capture is executed here.
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path");
const { test } = require("node:test"), core = require("../src/core.js"), input = require("../src/input.js");
const { PreviewController } = require("../src/preview-controller.js");
if (!process.argv[2] || !process.argv[3]) throw new Error("Pass catalog.json and real-pair-inputs root.");
const catalog = JSON.parse(fs.readFileSync(path.resolve(process.argv[2]),"utf8"));
const root = path.resolve(process.argv[3]);
const audits = JSON.parse(fs.readFileSync(path.join(root,"resource-name-audit.json"),"utf8"));
const fixtures = ["MThin","MMuscular","MHeavy","FThin","FMuscular","FHeavy"];
for (const fixtureName of fixtures) test("real full human input and exact mapped wolf coefficients: " + fixtureName, async () => {
  const fixtureText = fs.readFileSync(path.join(root,"full-preset-fixtures",fixtureName+".json"),"utf8");
  const fixture = JSON.parse(fixtureText), imported = input.parseJSON(fixtureText);
  const humanAudit = audits.find(row => row.entry.name === fixture.resources.human.high);
  const wolfAudit = audits.find(row => row.entry.name === fixture.resources.wolf.high);
  assert.ok(humanAudit && wolfAudit);
  const models = new Map(), calls = []; let serial = 0;
  const sdk = { async connect() { return { apiVersion:1,capabilities:[...PreviewController.requiredCapabilities],previewLimits:{maxPreviews:4,loadTimeoutMs:8000} }; },
    async request(method, params) {
      calls.push({method,params});
      if (method === "models.list") return {root:"audited resources",entries:audits.map(row=>row.entry)};
      if (method === "previews.create") { const preview="fixture:"+(++serial),audit=audits.find(row=>row.entry.name===params.name);
        models.set(preview,{audit,values:{}});return {preview,name:params.name}; }
      if (method === "previews.link") return params;
      const model = models.get(params.preview);assert.ok(model);
      if (method === "previews.scene.get") return {open:true,names:{nif:model.audit.entry.file,tri:model.audit.entry.tri},summary:model.audit.summary};
      if (method === "previews.close") {models.delete(params.preview);return {closed:true};}
      if (method === "previews.morphs.set") Object.assign(model.values,params.values);
      else assert.equal(method,"previews.morphs.get");
      return {names:model.audit.morphNames,values:{...model.values}};
    } };
  const controller = new PreviewController(sdk,catalog);
  await controller.open(fixture.profileId,fixture.resources.human.high,fixture.resources.wolf.high);
  const result = await controller.apply(imported.values);
  const expected = fixture.fullPresetLinkedWolfValues;
  assert.deepEqual({...result.wolfValues},expected);
  assert.deepEqual({...core.evaluate(catalog,fixture.profileId,fixture.runtimeObservedHumanValues).values},fixture.expectedLinkedWolfValues);
  for (const [name,value] of Object.entries(imported.values)) assert.equal(result.humanValues[name],value,name);
  assert.equal(Object.keys(imported.values).length,fixture.sex === "male" ? 124 : 154);
  if (fixtureName === "FThin") {assert.equal(result.humanValues.BigButt,-.25);assert.equal(result.humanValues.Butt,-.5);}
  if (fixtureName === "FMuscular") assert.equal(result.humanValues.MuscleAbs,Math.fround(.8));
  if (fixtureName === "FHeavy") {assert.equal(result.humanValues.BigButt,Math.fround(.14));assert.equal(result.humanValues.Butt,Math.fround(.21));}
  assert.equal(calls.filter(call=>call.method === "previews.link").length,1);
  assert.ok(!calls.some(call=>["morphs.set","morphs.reset","models.open","previews.view.set"].includes(call.method)));
  await controller.close();assert.equal(models.size,0);
});
test("retained observed source coverage is never promoted to the full human preset catalogue",()=>{
  const expectedCounts = {male:61,female:52};
  for (const name of fixtures) {
    const fixture=JSON.parse(fs.readFileSync(path.join(root,"full-preset-fixtures",name+".json"),"utf8"));
    assert.equal(Object.keys(fixture.runtimeObservedHumanValues).length,expectedCounts[fixture.sex]);
    assert.ok(Object.keys(fixture.humanValues).length>Object.keys(fixture.runtimeObservedHumanValues).length);
    if(name === "FThin") assert.match(fixture.humanValueProvenance.Butt,/not-runtime-observed/);
  }
});
