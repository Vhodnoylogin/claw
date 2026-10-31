"""Package CLAW 0.7.0.0 from tested 31 October bytes; never install or publish."""
from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
RELEASE = ROOT / 'src/main/resources/publication/working-installer'
CANDIDATE_SHA = "cc6e9ec89065715da422fc0ffb9ffafacb68051ef48e790cbabe615ccbeb7412"
NATIVE_SHA = "e7b238c82428f76cbefb58a322d25d05580519553ab3aa307d7ce6cc080ac3d5"
NAME = "CLAW - Configurable Lycanthrope Anatomy and Weight"
VERSION = "0.7.0.0"
ARCHIVE = NAME + " - " + VERSION + ".zip"
SOURCE = "Source/CLAW-Corresponding-Source-" + VERSION + ".zip"
RUNTIMES = ("1.5.97.0", "1.6.640.0", "1.6.659.0", "1.6.1170.0",
            "1.6.1179.0", "1.7.104.0", "1.4.15.0")
# Only these reviewed non-library subtrees are excluded from dependency source.
# CommonLib's complete LGPL source ZIP and every library/header/build/license
# input stay intact. SOURCE.md and the included build helper disable these
# optional documentation/test/example targets explicitly.
VENDOR_PRUNE = {
    "fmt": ("doc", "test"),
    "nlohmann-json": ("docs", "tests", "tools"),
    "pugixml-1.15": ("docs", "tests"),
    "rapidcsv": ("doc", "examples", "tests"),
    "simpleini": ("tests",),
    "spdlog": ("bench", "example", "tests", "logos"),
    "toml11": ("docs", "examples", "tests", "tools"),
    "xbyak": ("doc", "sample", "test"),
}
spec = importlib.util.spec_from_file_location("unified", ROOT / 'src/main/python/build-tools/build-unified-release.py')
unified = importlib.util.module_from_spec(spec)
spec.loader.exec_module(unified)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)+"\n").encode("utf-8")


def zipped(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
        for name, data in sorted(files.items()):
            unified.safe_path(name)
            info = zipfile.ZipInfo(name, (2026, 10, 31, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            writer.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def unpack(data):
    with zipfile.ZipFile(io.BytesIO(data)) as reader:
        names = reader.namelist()
        if reader.testzip() or len(names) != len(set(n.casefold() for n in names)):
            raise ValueError("Damaged ZIP or case-colliding members")
        for name in names:
            unified.safe_path(name)
        return {name: reader.read(name) for name in names}


def python_closure(inputs):
    pending = ["expressive_body", "expressive_verify", "expressive_preview",
               "build-working-release", "build-unified-release"]
    files = {}
    while pending:
        module = pending.pop()
        path = ROOT / 'src/main/python/build-tools' / (module + '.py')
        key = "claw/"+path.relative_to(ROOT).as_posix()
        if key in files:
            continue
        data = inputs.read(path)
        files[key] = data
        for node in ast.walk(ast.parse(data)):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) and node.module else
                       [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            for imported in modules:
                local = imported.split(".")[0]
                if (ROOT / 'src/main/python/build-tools' / (local + '.py')).is_file():
                    pending.append(local)
    return files


def matching_source(candidate, inputs):
    old_name = next(n for n in candidate if n.startswith("Source/") and n.endswith(".zip"))
    original = unpack(candidate[old_name])
    source = {n: data for n, data in original.items()
              if n.startswith(("upstream/", "NOTICES/", "api/", "claw/distribution/"))
              or n == "provenance/vcpkg-status.txt"}
    omitted = {}
    for name in list(source):
        parts = name.split("/")
        if len(parts) < 4 or parts[0] != "upstream":
            continue
        if parts[2] not in VENDOR_PRUNE.get(parts[1], ()):
            continue
        if parts[-1].lower().startswith(("license", "licence", "copying", "copyright", "notice")):
            continue
        data = source.pop(name)
        omitted[name] = {"sha256": sha(data), "bytes": len(data),
                         "reason": "Optional vendor documentation, tests, examples or developer tools; no library build input"}
    source["provenance/source-pruning.json"] = json_bytes({
        "schemaVersion": 1, "candidateArchiveSha256": CANDIDATE_SHA,
        "policy": {name: list(paths) for name, paths in VENDOR_PRUNE.items()},
        "completeCommonLibSourceArchiveRetained": True,
        "allLicensesAndNativeSourcesRetained": True,
        "requiredBuildOptionsDocumentedIn": "claw/release/working-installer/build-source-dependencies.ps1",
        "omittedFiles": omitted})
    native_files = {}
    for name, data in source.items():
        if name.startswith("claw/distribution/"):
            current = inputs.read(ROOT/name.removeprefix("claw/"))
            if data.replace(b"\r", b"") != current.replace(b"\r", b""):
                raise ValueError("Native source drift from tested candidate: "+name)
            native_files[name] = sha(data)
    if not native_files:
        raise ValueError("Missing tested native corresponding source")
    additions = python_closure(inputs)
    additions.update({"claw/"+path: inputs.read(ROOT/path) for path in (
        'src/main/resources/recipes/expressive-body-v1.json', 'src/main/resources/recipes/expressive-fixture-vectors-v1.json',
        'src/main/docs/rebuild.md', 'src/main/docs/expressive-body.md', 'src/main/docs/matrix-contract.md',
        'src/main/docs/universal-runtime.md', 'src/main/docs/verification-20261031.md',
        'src/main/resources/donors/README.md', 'src/main/resources/plugins/CLAW/RecordData.yaml',
        'src/main/resources/plugins/CLAW/spriggit-meta.json', 'src/main/resources/plugins/CLAW/ArmorAddons/GroupRecordData.yaml',
        'src/main/resources/plugins/CLAW/ArmorAddons/NakedTorsoWerewolfBeast - 0CDD87_Skyrim.esm.yaml')})
    for path in sorted(RELEASE.iterdir()):
        if path.is_file():
            additions["claw/"+path.relative_to(ROOT).as_posix()] = inputs.read(path)
    # Runtime snapshots remain the exact candidate bytes; new authoring additions
    # are separately pinned and cannot overwrite compiled native sources.
    if set(additions) & set(native_files):
        raise ValueError("Authoring additions overlap tested native source")
    source.update(additions)
    source["README.md"] = inputs.read(RELEASE/"SOURCE.md")
    source["source-manifest.json"] = json_bytes({
        "schemaVersion": 1, "repository": "https://github.com/Vhodnoylogin/claw",
        "releaseVersion": VERSION,
        "candidateArchiveSha256": CANDIDATE_SHA, "nativeSha256": NATIVE_SHA,
        "buildSelector": "UNIVERSAL", "nativeRebuiltByPackager": False,
        "compiledNativeSources": native_files,
        "authoringAndPackagingAdditions": {n: sha(d) for n, d in sorted(additions.items())},
        "files": {n: sha(d) for n, d in sorted(source.items())},
        "manifestSelfExcluded": True})
    return source


def resolve_selection(config, entries, *, native=True, family=None, host=False,
                      game_version="1.7.104.0", racemenu=True, obody=True,
                      himbo=True, cbbe=True, threeba=True):
    """Read the mandatory-body revision's real FOMOD with the reviewed resolver."""
    if not native or family not in ("CBBE", "3BA"):
        raise ValueError("Human linkage and exactly one HIMBO/CBBE body combination are required")
    markers = ({"HIMBO.esp"} if himbo else set()) | ({"CBBE.esp"} if cbbe else set()) | ({"3BBB.esp"} if threeba else set())
    installed = unified.resolve_selection(config, entries, native=True, family=family, host=host,
                                         game_version=game_version, racemenu=racemenu, obody=obody,
                                         additional_active=markers)
    # The legacy resolver owns optional folder selection. Required base files
    # use the FOMOD's explicit source/destination mapping so identical _0/_1
    # runtime NIFs need only one stored archive source per sex.
    required = config.find("requiredInstallFiles")
    if required is None or any(row.tag != "file" for row in required):
        raise ValueError("The minimal working installer requires explicit base file mappings")
    for row in required:
        source = unified.safe_path(row.attrib["source"])
        destination = unified.safe_path(row.attrib["destination"])
        if source not in entries or destination.casefold() in {n.casefold() for n in installed}:
            raise ValueError("Missing source or colliding explicit file mapping")
        installed[destination] = source
    return installed


def verify_required_contract(config):
    required = next(p for p in config.findall(".//plugin")
                    if p.find("files/folder").get("source") == "10 Native")
    native_type = required.find("typeDescriptor/type")
    if native_type is None or native_type.get("name") != "Required":
        raise ValueError("Native linkage must be forced by FOMOD Required semantics")
    declaration = config.find("installSteps/installStep[@name='Required human body combination']")
    if declaration is None or declaration.find("visible") is not None:
        raise ValueError("Required body declaration cannot be hidden")
    group = declaration.find("optionalFileGroups/group")
    if group.get("type") != "SelectExactlyOne" or len(group.findall('plugins/plugin')) != 2:
        raise ValueError("Exactly one of two human body combinations must be declared")
    module = config.find("moduleDependencies")
    markers = {(d.get("file"), d.get("state")) for d in module} if module is not None else set()
    if module is None or module.get("operator") != "And" or markers != {
            ("RaceMenu.esp", "Active"), ("HIMBO.esp", "Active"), ("CBBE.esp", "Active")}:
        raise ValueError("HIMBO, CBBE and RaceMenu active plugin markers must gate the module")
    for threeba, expected in ((True, {"CBBE": "Optional", "3BA": "Recommended"}),
                             (False, {"CBBE": "Recommended", "3BA": "NotUsable"})):
        active = {"RaceMenu.esp", "HIMBO.esp", "CBBE.esp"} | ({"3BBB.esp"} if threeba else set())
        actual = {}
        for plugin in group.findall('plugins/plugin'):
            family = plugin.find("files/folder").get("source").removeprefix("20 Human Family/HIMBO-and-")
            actual[family] = unified.plugin_type(plugin, "1.7.104.0", active, {})
        if actual != expected:
            raise ValueError("Human body recommendation or 3BA marker gate is inaccurate")


def selections(entries, original):
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    required = config.find("requiredInstallFiles")
    if required is None or len(required) != len(unified.BASE_RUNTIME) or any(row.tag != "file" for row in required):
        raise ValueError("Serialized FOMOD must contain every explicit base file mapping")
    if {row.get("destination") for row in required} != unified.BASE_RUNTIME:
        raise ValueError("Serialized FOMOD base destinations are incomplete")
    config_before = ET.tostring(config)
    entry_hashes_before = {name: sha(data) for name, data in entries.items()}
    verify_required_contract(config)
    previous = ET.fromstring(original["fomod/ModuleConfig.xml"])
    rows = []
    for family, host in (("CBBE", False), ("CBBE", True), ("3BA", False), ("3BA", True)):
        kwargs = {"native": True, "family": family, "host": host}
        installed = resolve_selection(config, entries, **kwargs)
        old = unified.resolve_selection(previous, original, **kwargs)
        expected = unified.BASE_RUNTIME | unified.NATIVE_RUNTIME | {unified.FAMILY_DEST} | (unified.HOST_RUNTIME if host else set())
        if set(installed) != expected:
            raise ValueError("Nonminimal or incomplete runtime selection")
        for name, origin in installed.items():
            if entries[origin] != original[old[name]]:
                raise ValueError("Tested runtime bytes changed: "+name)
        rows.append({"selection": family+("-OBody" if host else ""),
                     "runtimeFileCount": len(installed),
                     "installedFiles": [{"path": n, "archivePath": origin,
                                         "sha256": sha(entries[origin]), "bytes": len(entries[origin])}
                                        for n, origin in sorted(installed.items())]})
    for runtime in RUNTIMES:
        for family in ("CBBE", "3BA"):
            installed = resolve_selection(config, entries, game_version=runtime,
                                                   native=True, family=family)
            if installed["SKSE/Plugins/CLAWDistribution.dll"] != "10 Native/SKSE/Plugins/CLAWDistribution.dll":
                raise ValueError("More than one native runtime variant")
    for kwargs in ({"native": False}, {"native": True}, {"family": "Vanilla"},
                   {"himbo": False, "family": "3BA"}, {"cbbe": False, "family": "3BA"},
                   {"threeba": False, "family": "3BA"},
                   {"racemenu": False, "native": True, "family": "3BA"},
                   {"obody": False, "native": True, "family": "3BA", "host": True}):
        try:
            resolve_selection(config, entries, **kwargs)
        except ValueError:
            pass
        else:
            raise ValueError("Mandatory-body or dependency gate accepted an invalid selection")
    # The FOMOD itself, without the wrapper's input guard, must also refuse a
    # skipped body declaration; SelectExactlyOne is the manager-facing control.
    try:
        unified.resolve_selection(config, entries, additional_active={"HIMBO.esp", "CBBE.esp"})
    except ValueError:
        pass
    else:
        raise ValueError("FOMOD itself allowed omission of the required body declaration")
    resolve_selection(config, entries, family="CBBE", threeba=False)
    if ET.tostring(config) != config_before or {name: sha(data) for name, data in entries.items()} != entry_hashes_before:
        raise ValueError("Selection verification modified its XML or archive inputs")
    return rows


def build(candidate_path, out):
    out = unified.output_directory(out)
    inputs = unified.Inputs()
    raw = inputs.read(candidate_path)
    if sha(raw) != CANDIDATE_SHA:
        raise ValueError("Expected exact tested candidate03 working archive")
    original = unpack(raw)
    entries = {n: d for n, d in original.items() if n.startswith(
        ("00 Base/", "10 Native/", "20 Human Family/", "30 OBody Source/", "fomod/"))}
    entries.pop("00 Base/README.md")
    for name in list(entries):
        if name.startswith("10 Native/NOTICES/"):
            entries["NOTICES/"+name.removeprefix("10 Native/NOTICES/")] = entries.pop(name)
    if sha(entries["10 Native/SKSE/Plugins/CLAWDistribution.dll"]) != NATIVE_SHA:
        raise ValueError("Wrong native binary")
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    required = config.find("requiredInstallFiles")
    required.clear()
    for destination in sorted(unified.BASE_RUNTIME):
        stored = destination.replace("bodywerewolf_1.nif", "bodywerewolf_0.nif")
        ET.SubElement(required, "file", source="00 Base/"+stored, destination=destination)
    for sex in ("male", "female"):
        stem = "00 Base/"+unified.MESH+"/"+sex+"bodywerewolf"
        if entries[stem+"_0.nif"] != entries[stem+"_1.nif"]:
            raise ValueError("Weight endpoints differ; source deduplication is not valid")
        del entries[stem+"_1.nif"]
    dependencies = ET.Element("moduleDependencies", operator="And")
    for marker in ("RaceMenu.esp", "HIMBO.esp", "CBBE.esp"):
        ET.SubElement(dependencies, "fileDependency", file=marker, state="Active")
    config.insert(1, dependencies)
    steps = config.find("installSteps")
    steps[0].set("name", "Required bodies and human morph linkage")
    option = config.find("installSteps/installStep/optionalFileGroups/group/plugins/plugin")
    option.set("name", "Required: HIMBO male + CBBE female bodies and human morph linkage")
    option.find("description").text = (
        "HIMBO male and CBBE female bodies are mandatory separate dependencies. If you use 3BA, "
        "install CBBE as its required female base too. Declare CBBE or CBBE+3BA on the next page. "
        "This installer supplies conversion profiles, not human bodies. Vanilla human bodies are "
        "not supported by this release. Human morph linkage is required and cannot be unchecked. "
        "One CommonLib DLL serves the declared "
        "SE, AE and VR candidate versions. Game mechanism tests passed on SE 1.7.104.0 / SKSE 2.3.1 "
        "with official RaceMenu and HIMBO/3BA; other runtimes and CBBE have offline coverage only. "
        "Install matching SKSE, RaceMenu/SKEE and Address Library separately. The module requires "
        "active RaceMenu.esp, HIMBO.esp and CBBE.esp markers; no ESP name or shared mesh path proves a complete human-body "
        "installation. Read the included runtime contract for exact load boundaries.")
    descriptor = option.find("typeDescriptor")
    descriptor.clear()
    ET.SubElement(descriptor, "type", name="Required")
    family_step = steps[1]
    family_step.set("name", "Required human body combination")
    family_step.remove(family_step.find("visible"))
    family_options = family_step.findall("optionalFileGroups/group/plugins/plugin")
    family_options[0].set("name", "HIMBO 5.8 male + CBBE 2.0.3 female (required)")
    family_options[1].set("name", "HIMBO 5.8 male + CBBE 2.0.3 + 3BA 2.48 female (required)")
    for index, family_option in enumerate(family_options):
        family_option.find("description").text = (
            "Declare the human bodies actually installed. HIMBO and the CBBE female base are "
            "required in both choices; 3BA is an extension that also requires CBBE. Install all "
            "author-declared dependencies separately. This choice adds only CLAW conversion "
            "profiles and does not install bodies, presets or physics. Active 3BBB.esp recommends "
            "3BA; otherwise CBBE is recommended. You may choose CBBE even when the 3BA marker is "
            "active if your winning body meshes require it. These markers do not prove the "
            "effective meshes or DLL compatibility. Reinstall CLAW when changing body families. "
            "Vanilla is not supported.")
        descriptor = family_option.find("typeDescriptor")
        descriptor.clear()
        dependent = ET.SubElement(descriptor, "dependencyType")
        ET.SubElement(dependent, "defaultType", name="Recommended" if index == 0 else "NotUsable")
        pattern = ET.SubElement(ET.SubElement(dependent, "patterns"), "pattern")
        condition = ET.SubElement(pattern, "dependencies", operator="And")
        ET.SubElement(condition, "fileDependency", file="3BBB.esp", state="Active")
        ET.SubElement(pattern, "type", name="Optional" if index == 0 else "Recommended")
    ET.indent(config)
    entries["fomod/ModuleConfig.xml"] = ET.tostring(config, encoding="utf-8", xml_declaration=True)
    info = ET.fromstring(entries["fomod/info.xml"])
    info.find("Version").text = VERSION
    info.find("Description").text = (
        "CLAW requires HIMBO male and CBBE female bodies; choose CBBE or CBBE+3BA. "
        "Human linkage is mandatory; Vanilla support is deferred. One CommonLib DLL; "
        "SE 1.7.104.0 mechanisms tested. Other declared runtimes retain offline coverage. "
        "All six comparison presets have owner-confirmed visible differences.")
    entries["fomod/info.xml"] = ET.tostring(info, encoding="utf-8", xml_declaration=True)
    for language in ("", ".ru"):
        entries["README"+language+".md"] = inputs.read(RELEASE/("README"+language+".md"))
    for doc in ("universal-runtime", "matrix-contract", "expressive-body", "verification-20261031", "rebuild"):
        entries["Docs/"+doc+".md"] = inputs.read(ROOT/('src/main/docs/'+doc+".md"))
    # Preserve relative recipe links from the detailed body recipe.
    entries['src/main/resources/recipes/expressive-body-v1.json'] = inputs.read(ROOT / 'src/main/resources/recipes/expressive-body-v1.json')
    source = matching_source(original, inputs)
    entries[SOURCE] = zipped(source)
    entries["NOTICES/CORRESPONDING-SOURCE.json"] = json_bytes({
        "archive": SOURCE, "sha256": sha(entries[SOURCE]), "nativeSha256": NATIVE_SHA,
        "repository": "https://github.com/Vhodnoylogin/claw", "installedByFomod": False})
    rows = selections(unpack(zipped(entries)), original)
    entries["claw-unified-release.json"] = json_bytes({
        "schemaVersion": 2, "name": NAME, "version": VERSION,
        "releaseId": "claw-" + VERSION, "candidateArchiveSha256": CANDIDATE_SHA,
        "versionScope": "Installer/product release; retained runtime files are not relabelled or rebuilt",
        "installerPolicy": {"humanLinkageRequired": True, "baseOnlyAvailable": False,
                            "maleBodyRequired": "HIMBO", "femaleBaseRequired": "CBBE",
                            "femaleChoices": ["CBBE", "CBBE+3BA"], "vanillaSupported": False,
                            "requiredActiveMarkers": ["HIMBO.esp", "CBBE.esp", "RaceMenu.esp"],
                            "recommendedFemale": "3BA when 3BBB.esp is Active; CBBE otherwise",
                            "threebaRequiresActiveMarker": "3BBB.esp",
                            "markersProveEffectiveBodyMeshes": False,
                            "reinstallOnBodyFamilyChange": True,
                            "calculationProfilesUnchanged": ["HIMBO", "CBBE", "3BA"]},
        "nativeSha256": NATIVE_SHA, "runtimePayloadsModified": False,
        "transportDeduplication": {"nifSources": 2, "installedNifDestinations": 4,
                                   "requiredBaseUsesExplicitFileMappings": True},
        "packagerSha256": sha(inputs.read(Path(__file__))), "selections": rows,
        "acceptance": {"gameMechanisms": ["SE 1.7.104.0 / SKSE 2.3.1 / HIMBO+3BA"],
                       "ownerVisualObservation": "All six comparison presets visibly differ",
                       "otherDeclaredRuntimes": "Offline coverage only; no new game acceptance",
                       "completeArtisticAcceptance": False},
        "payloads": {n: sha(d) for n, d in sorted(entries.items())}, "manifestSelfExcluded": True})
    inputs.verify()
    packed = zipped(entries)
    if unpack(packed) != entries:
        raise ValueError("Written archive readback differs")
    if selections(unpack(packed), original) != rows:
        raise ValueError("ZIP-extracted XML installation differs from the recorded selection")
    # Source licenses and DLL discovery must remain outside selected game files.
    if len([n for n in entries if n.lower().endswith(".dll")]) != 1:
        raise ValueError("Expected exactly one DLL in installer")
    out.mkdir(parents=True, exist_ok=False)
    archive_path = out/ARCHIVE
    archive_path.write_bytes(packed)
    receipt = {"archive": str(archive_path), "version": VERSION,
               "sha256": sha(packed), "bytes": len(packed),
               "archiveFiles": len(entries), "sourceFiles": len(source), "selections": rows,
               "runtimePayloadsModified": False, "sourceArchiveInstalled": False,
               "gameOrManagerExecuted": False, "nativeRebuilt": False}
    (out/"build-receipt.json").write_bytes(json_bytes(receipt))
    inputs.verify()
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.candidate, args.out), indent=2))
