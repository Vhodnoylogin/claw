"use strict";
const assert = require("node:assert/strict"), fs = require("node:fs"), path = require("node:path"), os = require("node:os");
const {spawnSync} = require("node:child_process"), {test} = require("node:test");
const core = require("../src/core.js"), {PairState} = require("../src/pair.js");
const catalog = JSON.parse(fs.readFileSync(process.argv[2],"utf8"));
const matrix = {...catalog.profiles.find(profile => profile.family === "HIMBO"),
  rules:[{source:"",target:"CLAWArmLean",gain:1,cap:1,function:"constant",value:.5}]};
test("constant-only catalog can arm and plan with no human morph names", () => {
  const local = {...catalog,profiles:catalog.profiles.map(p => p.family === "HIMBO" ? matrix:p)};
  const state = new PairState(local), binding = id => ({id,revision:"1",view:"view:"+id,sex:"male"});
  const bindings = {human:binding("human"),wolf:binding("wolf")};state.bind(matrix.id,bindings);
  state.arm({human:{binding:bindings.human,names:[]},wolf:{binding:bindings.wolf,names:Object.keys(core.evaluateMatrix(matrix,{}).values)}});
  assert.equal(state.plan({}).values.wolf.CLAWArmLean,.5);
});
test("diagnostic transformation uses the exact marshalled float32 input", () => {
  const result = globalThis.CLAWMatrixKernel.evaluate([{target:0,function:"linear",input:.1,gain:1,cap:1}],1);
  assert.equal(result.details[0].transformed,Math.fround(.1));
  assert.equal(result.details[0].contribution,result.rawSums[0]);
});
test("full native game configuration preserves other families and selected defaults", () => {
  const native = process.argv[3]; if (!native) throw new Error("Pass the built native tool for an actual native roundtrip");
  const dir = fs.mkdtempSync(path.join(process.argv[4] || os.tmpdir(),"claw-config-"));
  for (const family of ["CBBE","3BA"]) {
    const file = path.join(dir,family+".xml");fs.writeFileSync(file,core.exportCatalog(catalog,matrix,family));
    const families = spawnSync(native,["families",file],{encoding:"utf8"});assert.equal(families.status,0,families.stderr);
    const parsed = JSON.parse(families.stdout);assert.equal(parsed.defaults.male,matrix.id);
    assert.equal(parsed.defaults.female,catalog.profiles.find(p=>p.family === family).id);
    for (const profile of catalog.profiles) {
      const result = spawnSync(native,["matrix",file,profile.id],{input:"",encoding:"utf8"});assert.equal(result.status,0,result.stderr);
      const observed=JSON.parse(result.stdout), expected=core.evaluateMatrix(profile.family === "HIMBO" ? matrix:profile,{}).values;
      for (const [name,value] of Object.entries(expected)) assert.equal(Math.fround(observed[name]),value,name);
    }
  }
});
