"""Build one working CLAW FOMOD from the frozen release and explicit new inputs.

No installation or publication. Preserve third-party notices/corresponding sources,
replace only CLAW-owned native source, body resources and matrix configuration.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "4d58714f83e4dea70b52d0d2d2ea2fd0aff9f54b2cd1c321c02f7a97ae038a49"
MESH = "Meshes/Actors/WerewolfBeast/Character Assets"
FULL_NAME = "CLAW - Configurable Lycanthrope Anatomy and Weight"

def sha(data): return hashlib.sha256(data).hexdigest()

def zip_bytes(files):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name,data in sorted(files.items()):
            info = zipfile.ZipInfo(name, date_time=(2026,10,31,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.create_system = 3; info.external_attr = 0o100644 << 16
            archive.writestr(info,data)
    return out.getvalue()

def profiles(female):
    tree = ET.fromstring((ROOT / "distribution/profiles/MorphLinks.xml").read_bytes())
    male = next(p.attrib["id"] for p in tree.findall("Profile") if p.attrib["family"] == "HIMBO")
    woman = next(p.attrib["id"] for p in tree.findall("Profile") if p.attrib["family"] == female)
    tree.insert(0, ET.Element("Defaults", male=male, female=woman))
    ET.indent(tree)
    return ET.tostring(tree, encoding="utf-8") + b"\n"

def build(baseline, bodies, dll, output):
    output = output.resolve()
    if output == ROOT or ROOT in output.parents: raise ValueError("Use external output directory")
    baseline_data = baseline.read_bytes()
    if sha(baseline_data) != BASE_SHA: raise ValueError("Unexpected frozen release archive")
    with zipfile.ZipFile(io.BytesIO(baseline_data)) as archive:
        if archive.testzip(): raise ValueError("Damaged baseline archive")
        payload = {name:archive.read(name) for name in archive.namelist()}
    native = dll.read_bytes()
    if native[:2] != b"MZ": raise ValueError("Expected built Windows DLL")
    payload["10 Native/SKSE/Plugins/CLAWDistribution.dll"] = native
    installer = ET.fromstring(payload["fomod/ModuleConfig.xml"])
    option = installer.find("installSteps/installStep/optionalFileGroups/group/plugins/plugin")
    option.set("name", "Human morph linkage (one CommonLib DLL for SE, AE and VR)")
    option.find("description").text = "Install the human-to-werewolf matrix link with the matching SKSE, RaceMenu/SKEE and Address Library for your game. One CommonLib DLL selects its runtime path at load; see the included compatibility guide for exact candidate versions and actual testing status. Leave unchecked for body resources alone."
    patterns = option.find("typeDescriptor/dependencyType/patterns")
    patterns.clear()
    pattern = ET.SubElement(patterns,"pattern")
    dependencies = ET.SubElement(pattern,"dependencies",operator="And")
    ET.SubElement(dependencies,"fileDependency",file="RaceMenu.esp",state="Active")
    ET.SubElement(pattern,"type",name="Optional")
    ET.indent(installer)
    payload["fomod/ModuleConfig.xml"] = ET.tostring(installer,encoding="utf-8",xml_declaration=True)
    info = ET.fromstring(payload["fomod/info.xml"])
    info.find("Version").text = "2026.10.31"
    info.find("Description").text = "CLAW expressive body and coefficient/function matrix candidate, with one CommonLib DLL for the declared SE/AE/VR runtimes. Included compatibility guide distinguishes builds from game acceptance."
    payload["fomod/info.xml"] = ET.tostring(info,encoding="utf-8",xml_declaration=True)
    inputs = {str(baseline.resolve()): BASE_SHA, str(dll.resolve()):sha(native)}
    for sex in ("male", "female"):
        for suffix in ("_0.nif", "_1.nif", ".tri"):
            name = sex+"bodywerewolf"+suffix; path = bodies / name; data = path.read_bytes()
            if len(data) < 100: raise ValueError("Missing body resource: "+name)
            payload["00 Base/"+MESH+"/"+name] = data; inputs[str(path.resolve())] = sha(data)
    for family in ("CBBE", "3BA"):
        payload["20 Human Family/HIMBO-and-"+family+"/SKSE/Plugins/CLAW/MorphLinks.xml"] = profiles(family)
    old_source = next(name for name in payload if name.startswith("Source/") and name.endswith(".zip"))
    with zipfile.ZipFile(io.BytesIO(payload.pop(old_source))) as archive:
        source = {name:archive.read(name) for name in archive.namelist() if not name.startswith("claw/distribution/")}
    for path in sorted((ROOT/"distribution").rglob("*")):
        if path.is_file() and path.suffix.lower() in {".h", ".cpp", ".xml", ".json", ".md", ".ps1", ".psc", ".py", ".txt"}:
            source["claw/"+path.relative_to(ROOT).as_posix()] = path.read_bytes()
    source["claw/docs/matrix-contract.md"] = (ROOT/"docs/matrix-contract.md").read_bytes()
    own_sources = {name:sha(data) for name,data in source.items() if name.startswith("claw/distribution/")}
    source["CLAW-matrix-source-manifest.json"] = (json.dumps({"files":own_sources,"nativeSha256":sha(native)},sort_keys=True,indent=2)+"\n").encode()
    source_name = "Source/CLAW-Matrix-Corresponding-Source-20261031.zip"
    payload[source_name] = zip_bytes(source)
    payload["10 Native/NOTICES/CORRESPONDING-SOURCE.json"] = (json.dumps({
        "archive": source_name.removeprefix("Source/"),"sha256":sha(payload[source_name]),
        "repository":"https://github.com/Vhodnoylogin/claw", "nativeSha256":sha(native),
        "note":"This package includes current CLAW source snapshot and retained pinned external corresponding sources; source-manifest identifies exact owned bytes."},indent=2)+"\n").encode()
    payload["Docs/Matrix-contract.md"] = (ROOT/"docs/matrix-contract.md").read_bytes()
    payload["Docs/Expressive-body.md"] = (ROOT/"docs/expressive-body.md").read_bytes()
    payload["Docs/Universal-runtime.md"] = (ROOT/"docs/universal-runtime.md").read_bytes()
    payload["Docs/Distribution/README.md"] = (ROOT/"distribution/README.md").read_bytes()
    base_readme = ("# CLAW body resources — 31 October candidate\n\nMale and female bodies include four opposed lean fields and repaired growth fields for arms, legs, torso, belly, shoulders and chest. Each sex still uses equal neutral _0/_1 weight endpoints. The immutable30October inputs are the donor baseline, not this candidate's TRI output.\n\nInstall Elegant textures separately. New matrix linkage uses the optional single CommonLib DLL; see Docs/Universal-runtime.md for declared runtime boundaries and actual test status. Physics, first-person VR body and test actors are not included in the working mod.\n").encode()
    payload["00 Base/README.md"] = base_readme
    payload["Docs/Base/README.md"] = base_readme
    payload["Docs/Base/README.ru.md"] = ("# Ресурсы тел CLAW — кандидат 31 октября\n\nДобавлены худые формы рук, бёдер, голеней и торса; переработаны поля увеличения тела и живота с учётом шерсти. Нейтральные _0/_1 по-прежнему одинаковы внутри каждого пола. Текстуры Elegant устанавливаются отдельно.\n\nСвязь с человеческими морфами использует одну DLL CommonLib для заявленных SE/AE/VR. Точные версии и состояние игровых проверок: Docs/Universal-runtime.md. Физики, тела VR от первого лица и тестовых актёров в рабочем моде нет.\n").encode()
    payload["Docs/Distribution/README.ru.md"] = ("# Преобразование морфов CLAW — кандидат 31 октября\n\nПресет волка — матрица коэффициентов и функций преобразования человеческих морфов. Полностью постоянная матрица задаёт независимого волка. DLL и плагин Morphbench используют один исходный вычислительный модуль; браузер исполняет его сборку WebAssembly.\n\nОдна игровая DLL собирается через CommonLib с поддержкой SE, AE и VR. Заявленные версии, зависимости и фактическое подтверждение в игре перечислены в Docs/Universal-runtime.md; сборка не заменяет игровую проверку.\n\nВыберите фактически установленные HIMBO и CBBE/3BA. OBody, RaceMenu, SKSE и Address Library с подходящими зависимостями устанавливаются отдельными модами. Существующие сохранённые матрицы не заменяются автоматически: требуется явное ConfigureMorphFamily. Формат: Docs/Matrix-contract.md; полный справочник API: Docs/Distribution/README.md.\n").encode()
    payload["README.md"] = ("# " + FULL_NAME + "\n\n31 October development candidate: expressive body fields and authorable coefficient/function matrices.\n\nOne CommonLib DLL covers the declared candidate SE/AE/VR runtimes. Read Docs/Universal-runtime.md for exact boundaries, game-specific dependencies and actual acceptance status.\n\nSelect your installed human body family. OBody and its matching dependencies remain separate mods. Elegant textures are required and are not included. Test actors/presets are in the separate test_CLAW archive. No physics or first-person VR body is included.\n\nWolf presets are conversion matrices; an all-constant matrix defines an independent wolf. Existing saved mappings remain authoritative until explicitly rebound. See Docs/Matrix-contract.md and Docs/Expressive-body.md.\n").encode()
    payload.pop("claw-unified-release.json")
    manifest = {"name":FULL_NAME,"build":"matrix-expressive-20261031-candidate", "acceptedInGame":False,
                "baselineArchiveSha256":BASE_SHA,"inputs":inputs,"ownSourceFiles":own_sources,
                "payloads":{name:sha(data) for name,data in sorted(payload.items())}}
    payload["claw-unified-release.json"] = (json.dumps(manifest,sort_keys=True,indent=2)+"\n").encode()
    spec = importlib.util.spec_from_file_location("unified", ROOT/"scripts/build-unified-release.py")
    unified = importlib.util.module_from_spec(spec); spec.loader.exec_module(unified)
    config = ET.fromstring(payload["fomod/ModuleConfig.xml"])
    selections = {}
    for family, host in [(None,False),("CBBE",False),("CBBE",True),("3BA",False),("3BA",True)]:
        rows = unified.resolve_selection(config,set(payload), native=family is not None, family=family, host=host)
        selections[str((family,host))] = rows
        for destination, source_name in rows.items():
            if source_name not in payload: raise ValueError("Unresolved selected source")
            if destination.lower().endswith(".dds") or "test_" in destination: raise ValueError("Foreign texture/test runtime payload")
    for game_version in ("1.5.97.0","1.6.640.0","1.6.659.0","1.6.1170.0","1.6.1179.0","1.7.104.0","1.4.15.0"):
        for family in ("CBBE","3BA"):
            rows=unified.resolve_selection(config,set(payload),game_version=game_version,native=True,family=family,host=False)
            if rows["SKSE/Plugins/CLAWDistribution.dll"] != "10 Native/SKSE/Plugins/CLAWDistribution.dll": raise ValueError("Runtime-specific DLL substitution")
    for path, digest in inputs.items():
        if sha(Path(path).read_bytes()) != digest: raise ValueError("Input changed during packaging")
    output.mkdir(parents=True,exist_ok=True)
    archive_path = output/(FULL_NAME+" - matrix-expressive-20261031.zip")
    if archive_path.exists(): raise ValueError("Immutable candidate already exists; use a new output directory")
    archive_path.write_bytes(zip_bytes(payload))
    report = {"archive":str(archive_path),"sha256":sha(archive_path.read_bytes()),"bytes":archive_path.stat().st_size,
              "files":len(payload),"selections":selections,"inputs":inputs,"acceptedInGame":False}
    (output/"package-report.json").write_bytes((json.dumps(report,indent=2)+"\n").encode())
    return report

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("baseline","bodies","dll","output"): parser.add_argument("--"+name,required=True,type=Path)
    args=parser.parse_args();print(json.dumps(build(args.baseline,args.bodies,args.dll,args.output),indent=2))
