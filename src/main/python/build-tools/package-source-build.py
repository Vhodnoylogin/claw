"""Compose a runtime-only FOMOD from explicit build outputs.

No historical candidate/source ZIP is an input. This command packages files; it
does not compile, install, publish or confer game acceptance on those files.

The external source directory must contain companion-manifest.json, schema1,
kind claw-native-source-companion. review records status source-closure-reviewed,
reviewId, nativeDllSha256 and the complete nativeSources relative-path/SHA map.
commonlib records repository, commit, sourceRoot and its license relative path.
files enumerates every other file as path, bytes, sha256 and role source/license.
The caller's review must establish closure completeness and actual build lineage;
this packager checks its bindings and exact inventory, without inferring them.
Source/SDK review is external provenance and is never included in the game ZIP.
Only runtime results, FOMOD, license notices and a short user README are shipped.
An optional source commit is checked against the actual local source inventory;
availability of that commit on the public service is a separate publication gate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[4]
NAME = "CLAW - Customizable Lycanthrope Appearance and Weight"
ARCHIVE_NAME = "CLAW - Customizable Lycanthrope Appearance and Weight.zip"
VERSION = "0.7.0.0"
MESH = "Meshes/Actors/WerewolfBeast/Character Assets"
ARCHIVES = {".zip", ".7z", ".rar", ".tar", ".gz", ".gzip", ".tgz", ".bz2", ".bzip2",
            ".tbz", ".tbz2", ".xz", ".txz", ".lz", ".lzma", ".zst", ".zstd", ".tzst",
            ".cab", ".iso", ".arj", ".ace", ".bsa", ".ba2", ".jar", ".war", ".whl",
            ".nupkg", ".msix", ".appx", ".deb", ".rpm"}
COMPILED = {".dll", ".exe", ".pex", ".esp", ".esm", ".esl", ".pdb", ".lib",
            ".obj", ".o", ".a", ".so", ".dylib", ".pyc", ".wasm", ".exp", ".ilk",
            ".pch", ".idb", ".ipdb", ".iobj", ".res"} | ARCHIVES
SOURCE_PREFIXES = ("src/main/cpp/", "src/test/cpp/", "src/main/papyrus/claw/")
SOURCE_FILES = {"CMakeLists.txt", "src/main/resources/profiles/MorphLinks.xml",
                "src/main/papyrus/claw/CLAWDistributionNative.psc",
                "src/main/python/build-tools/package-source-build.py",
                "src/main/python/build-tools/build-unified-release.py",
                "src/main/resources/publication/unified-installer/ModuleConfig.xml",
                "src/main/resources/publication/unified-installer/info.xml"}
HOST_SOURCES = {"src/main/papyrus/obody/CLAWOBodySourceHost.psc",
                "src/main/papyrus/obody/build.py", "src/main/papyrus/obody/README.md",
                "src/main/python/physics/wiring.py"}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def safe_name(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or str(path) != name:
        raise ValueError("Unsafe relative path: " + str(name))
    return name


def source_name(name):
    safe_name(name)
    parts = PurePosixPath(name).parts
    if any(part.lower() in {".git", "target", "local", "__pycache__"} for part in parts) or Path(name).suffix.lower() in COMPILED:
        raise ValueError("Compiled/archive/local material is not corresponding source: " + name)
    if Path(name).name in {"build.local.json", ".env"}:
        raise ValueError("Machine-local source input refused: " + name)
    return name


def validate_no_nested_archives(files):
    """Enforce a flat release container, including renamed archive payloads."""
    signatures = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08", b"7z\xbc\xaf\x27\x1c",
                  b"Rar!\x1a\x07", b"\x1f\x8b", b"BZh", b"\xfd7zXZ\x00", b"\x28\xb5\x2f\xfd",
                  b"MSCF", b"!<arch>\n", b"\xed\xab\xee\xdb")
    for name, data in files.items():
        safe_name(name)
        if (Path(name).suffix.lower() in ARCHIVES or data.startswith(signatures) or
                data[257:262] == b"ustar"):
            raise ValueError("Nested archive payload refused; provide unpacked source files: " + name)


def zip_bytes(files):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as writer:
        for name, data in sorted(files.items()):
            safe_name(name)
            item = zipfile.ZipInfo(name, (2026, 10, 31, 0, 0, 0))
            item.create_system = 3
            item.external_attr = 0o100644 << 16
            writer.writestr(item, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return stream.getvalue()


def read_zip(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if archive.testzip() or len(names) != len({name.casefold() for name in names}):
            raise ValueError("Damaged or case-colliding archive")
        return {safe_name(name): archive.read(name) for name in names}


class Inputs:
    def __init__(self):
        self.records = {}
        self.runtime_roles = {}

    def read(self, path):
        path = Path(path).absolute()
        if any(part.exists() and (part.is_symlink() or part.is_junction()) for part in (path, *path.parents)):
            raise ValueError("Linked input refused: " + str(path))
        path = path.resolve()
        if path not in self.records:
            if not path.is_file():
                raise ValueError("Missing required source/build input: " + str(path))
            data = path.read_bytes()
            if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                raise ValueError("Unmaterialized Git LFS source input: " + str(path))
            self.records[path] = data
        return self.records[path]

    def runtime(self, path, magic, role):
        original = Path(path)
        path = original.resolve()
        target = (ROOT / "target").resolve()
        if target not in path.parents or "references" in path.relative_to(target).parts:
            raise ValueError("Runtime input must be an explicit target build result, not a frozen reference: " + role)
        data = self.read(original)
        if len(data) < 24 or not data.startswith(magic):
            raise ValueError("Unexpected input header: " + role)
        self.runtime_roles[role] = {"path": path.relative_to(ROOT.resolve()).as_posix(),
                                    "sha256": sha(data), "bytes": len(data)}
        return data

    def verify(self):
        for path, data in self.records.items():
            if not path.is_file() or path.read_bytes() != data:
                raise ValueError("Input changed during packaging: " + str(path))


def tracked_source(inputs, include_host):
    result = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True, check=True)
    names = [name.decode("utf-8") for name in result.stdout.split(b"\0") if name]
    required = SOURCE_FILES | (HOST_SOURCES if include_host else set())
    selected = sorted(name for name in names if name.startswith(SOURCE_PREFIXES) or name in required)
    if not required.issubset(selected) or not any(name.startswith("src/main/cpp/") for name in selected):
        raise ValueError("Current source hierarchy/packager must be tracked (stage src/ before packaging)")
    files = {"claw/" + source_name(name): inputs.read(ROOT / name) for name in selected}
    native = {name: sha(files["claw/" + name]) for name in selected
              if name == "CMakeLists.txt" or name.startswith(("src/main/cpp/", "src/test/cpp/"))}
    commit = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(ROOT), "diff", "--quiet", "HEAD", "--"],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    selection = {"scope": "Native DLL, matrix configuration and included Papyrus components; not full body authoring",
                 "gitHead": commit.stdout.strip() if commit.returncode == 0 else None,
                 "worktreeHasTrackedChanges": dirty.returncode != 0,
                 "workingFilePinsAreAuthoritative": True,
                 "selected": {name: {"sha256": sha(files["claw/" + name]), "bytes": len(files["claw/" + name])}
                              for name in selected},
                 "omittedTrackedSource": {name: {"bytes": (ROOT / name).stat().st_size}
                     for name in names if name.startswith("src/") and name not in selected and (ROOT / name).is_file()}}
    return files, native, commit.stdout.strip() if commit.returncode == 0 else None, selection


def companion(inputs, directory, native_sha, native_sources, commonlib_commit):
    manifest_data = inputs.read(Path(directory) / "companion-manifest.json")
    root = Path(directory).resolve()
    manifest = json.loads(manifest_data)
    if manifest.get("schemaVersion") != 1 or manifest.get("kind") != "claw-native-source-companion":
        raise ValueError("Expected a reviewed source-only companion directory manifest")
    review = manifest.get("review", {})
    commonlib = manifest.get("commonlib", {})
    if (review.get("status") != "source-closure-reviewed" or not review.get("reviewId") or
            review.get("nativeDllSha256") != native_sha or review.get("nativeSources") != native_sources):
        raise ValueError("Companion review does not bind this DLL and current native source bytes")
    if not re.fullmatch(r"[0-9a-f]{40}", commonlib_commit) or commonlib.get("commit") != commonlib_commit:
        raise ValueError("CommonLib source commit differs from the explicit build pin")
    if not isinstance(commonlib.get("repository"), str) or not commonlib["repository"].startswith("https://github.com/"):
        raise ValueError("CommonLib source repository must be explicitly recorded")
    source_root = safe_name(commonlib.get("sourceRoot", ""))
    files, licenses = {}, {}
    for row in manifest.get("files", []):
        name = source_name(row["path"])
        if name == "companion-manifest.json" or name.casefold() in {key.casefold() for key in files} or row.get("role") not in {"source", "license"}:
            raise ValueError("Duplicate companion path or unsupported role")
        data = inputs.read(root / name)
        if len(data) != row.get("bytes") or sha(data) != row.get("sha256"):
            raise ValueError("Companion source/license hash mismatch: " + name)
        files[name] = data
        if row["role"] == "license":
            licenses[name] = data
    inventory = set()
    for current, directories, names in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(current) / name
            if path.is_symlink() or path.is_junction() or name == ".git":
                raise ValueError("Linked/Git companion directory refused")
        inventory.update((Path(current) / name).relative_to(root).as_posix() for name in names)
    if inventory != set(files) | {"companion-manifest.json"}:
        raise ValueError("Companion inventory differs from the reviewed complete file list")
    if not licenses or commonlib.get("license") not in licenses:
        raise ValueError("Reviewed CommonLib license and dependency notices are required")
    if not {source_root + "/CMakeLists.txt", source_root + "/include/SKSE/Version.h"}.issubset(files):
        raise ValueError("Missing declared CommonLib source/build inputs")
    public = {"schemaVersion": 1, "commonlib": commonlib, "review": review,
              "manifestSha256": sha(inputs.read(root / "companion-manifest.json")),
              "scope": "Caller-supplied source-closure review; packaging verifies bindings/inventory, not a new dependency build."}
    return files, licenses, public


MALE_FAMILIES = ("HIMBO", "Vanilla")
FEMALE_FAMILIES = ("CBBE", "3BA", "Vanilla")


def profiles(data, family, male_family="HIMBO"):
    if family not in FEMALE_FAMILIES or male_family not in MALE_FAMILIES:
        raise ValueError("Select exactly one supported male and female body family")
    if b"<!" in data:
        raise ValueError("Declarations/entities are not supported in profile XML")
    tree = ET.fromstring(data)
    rows = tree.findall("Profile")
    inventory = {(row.get("sex"), row.get("family")) for row in rows}
    if (tree.tag != "MorphLinkProfiles" or len(rows) != 5 or inventory !=
            {("male", "HIMBO"), ("female", "CBBE"), ("female", "3BA"),
             ("male", "Vanilla"), ("female", "Vanilla")}):
        raise ValueError("Expected the canonical five sex-specific body-family matrices")
    if any(not row.get('id') for row in rows) or len({row.get('id') for row in rows}) != 5:
        raise ValueError("Canonical matrices require five distinct explicit profile identifiers")
    for old in tree.findall("Defaults"):
        tree.remove(old)
    selected = {("male", male_family), ("female", family)}
    male = next(row.get("id") for row in rows if (row.get("sex"), row.get("family")) == ("male", male_family))
    female = next(row.get("id") for row in rows if (row.get("sex"), row.get("family")) == ("female", family))
    if not male or not female or male == female:
        raise ValueError("Selected matrices must have distinct explicit profile identifiers")
    for row in rows:
        if (row.get("sex"), row.get("family")) not in selected:
            tree.remove(row)
    tree.insert(0, ET.Element("Defaults", male=male, female=female))
    ET.indent(tree)
    return ET.tostring(tree, encoding="utf-8") + b"\n"


def installer(template, entries):
    config = ET.fromstring(template)
    config.find("moduleName").text = NAME
    required = config.find("requiredInstallFiles")
    required.clear()
    destinations = {"CLAW.esp"} | {MESH + "/" + sex + "bodywerewolf" + ending
        for sex in ("male", "female") for ending in ("_0.nif", "_1.nif", ".tri")}
    for destination in sorted(destinations):
        source = "00 Base/" + destination
        if source not in entries:
            source = source.replace("bodywerewolf_1.nif", "bodywerewolf_0.nif")
        ET.SubElement(required, "file", source=source, destination=destination)
    old = config.find("moduleDependencies")
    if old is not None:
        config.remove(old)
    dependencies = ET.Element("moduleDependencies", operator="And")
    ET.SubElement(dependencies, "fileDependency", file="RaceMenu.esp", state="Active")
    config.insert(1, dependencies)
    steps = config.find("installSteps")
    steps[0].set("name", "Required bodies and human morph linkage")
    option = steps[0].find("optionalFileGroups/group/plugins/plugin")
    option.set("name", "Required human morph linkage")
    option.find("description").text = "Carries human body morphs and declared NPC weight inputs into werewolf form. Requires matching SKSE, RaceMenu and Address Library. Select the actual human bodies in the next step."
    descriptor = option.find("typeDescriptor")
    descriptor.clear()
    ET.SubElement(descriptor, "type", name="Required")
    family_step = steps[1]
    family_step.set("name", "Select your actual male and female bodies")
    visible = family_step.find("visible")
    if visible is not None:
        family_step.remove(visible)
    groups = family_step.find("optionalFileGroups")
    groups.clear(); groups.set("order", "Explicit")
    def marker_pattern(parent, markers, kind):
        pattern = ET.SubElement(parent, "pattern")
        required = ET.SubElement(pattern, "dependencies", operator="And")
        for marker in markers:
            ET.SubElement(required, "fileDependency", file=marker, state="Active")
        ET.SubElement(pattern, "type", name=kind)
    for sex, families in (("male", MALE_FAMILIES), ("female", FEMALE_FAMILIES)):
        group = ET.SubElement(groups, "group", name=sex.title()+" human body", type="SelectExactlyOne")
        options = ET.SubElement(group, "plugins", order="Explicit")
        for family in families:
            choice = ET.SubElement(options, "plugin", name=family)
            ET.SubElement(choice, "description").text = (
                "Uses this sex's actual NPC weight as the only human input. No replacement human body mod is required."
                if family == "Vanilla" else
                "Select only when these human meshes are installed. Plugin markers recommend or gate the choice; they cannot verify winning meshes or the full dependency chain. Human bodies and physics are not bundled.")
            ET.SubElement(ET.SubElement(choice, "conditionFlags"), "flag", name=sex+"Family").text = family
            dependent = ET.SubElement(ET.SubElement(choice, "typeDescriptor"), "dependencyType")
            ET.SubElement(dependent, "defaultType", name="Recommended" if family == "Vanilla" else "NotUsable")
            patterns = ET.SubElement(dependent, "patterns")
            if family == "HIMBO": marker_pattern(patterns, ("HIMBO.esp",), "Recommended")
            elif family == "CBBE":
                marker_pattern(patterns, ("CBBE.esp", "3BBB.esp"), "Optional")
                marker_pattern(patterns, ("CBBE.esp",), "Recommended")
            elif family == "3BA": marker_pattern(patterns, ("CBBE.esp", "3BBB.esp"), "Recommended")
            else: marker_pattern(patterns, ("HIMBO.esp",) if sex == "male" else ("CBBE.esp",), "Optional")
    old = config.find("conditionalFileInstalls")
    if old is not None: config.remove(old)
    patterns = ET.SubElement(ET.SubElement(config, "conditionalFileInstalls"), "patterns")
    for male in MALE_FAMILIES:
        for female in FEMALE_FAMILIES:
            pattern = ET.SubElement(patterns, "pattern")
            dependencies = ET.SubElement(pattern, "dependencies", operator="And")
            ET.SubElement(dependencies, "flagDependency", flag="maleFamily", value=male)
            ET.SubElement(dependencies, "flagDependency", flag="femaleFamily", value=female)
            ET.SubElement(ET.SubElement(pattern, "files"), "folder",
                          source="20 Human Family/"+male+"-and-"+female, destination="", priority="0")
    if not any(name.startswith("30 OBody Source/") for name in entries):
        for step in list(steps):
            if any(row.get("source") == "30 OBody Source" for row in step.findall(".//files/folder")):
                steps.remove(step)
    ET.indent(config)
    return ET.tostring(config, encoding="utf-8", xml_declaration=True)


def selection_audit(entries):
    spec = importlib.util.spec_from_file_location("claw_source_fomod_reader", ROOT / "src/main/python/build-tools/build-unified-release.py")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    config = ET.fromstring(entries["fomod/ModuleConfig.xml"])
    required = config.find("requiredInstallFiles")
    if required is None or len(required) != 7 or any(row.tag != "file" for row in required):
        raise ValueError("Literal serialized FOMOD must contain seven explicit base file mappings")
    rows = []
    for male, family in ((male, female) for male in MALE_FAMILIES for female in FEMALE_FAMILIES):
        for host in (False, True):
            if host and not any(name.startswith("30 OBody Source/") for name in entries):
                continue
            active = ({"HIMBO.esp"} if male == "HIMBO" else set())
            active |= ({"CBBE.esp"} if family in {"CBBE", "3BA"} else set())
            active |= ({"3BBB.esp"} if family == "3BA" else set())
            installed = reader.resolve_selection(config, entries, native=True, male_family=male,
                                                family=family, host=host, additional_active=active)
            for item in required:
                source, destination = safe_name(item.get("source", "")), safe_name(item.get("destination", ""))
                if source not in entries or destination in installed:
                    raise ValueError("Missing source or duplicate required destination")
                installed[destination] = source
            expected = reader.BASE_RUNTIME | reader.NATIVE_RUNTIME | {reader.FAMILY_DEST} | (reader.HOST_RUNTIME if host else set())
            if set(installed) != expected or len(installed) != (12 if host else 10):
                raise ValueError("Nonminimal/incomplete selected runtime")
            matrix = ET.fromstring(entries[installed[reader.FAMILY_DEST]])
            selected = {(row.get("sex"), row.get("family")) for row in matrix.findall("Profile")}
            defaults = matrix.find("Defaults")
            ids = {row.get("sex"): row.get("id") for row in matrix.findall("Profile")}
            if (selected != {("male", male), ("female", family)} or len(matrix.findall("Profile")) != 2 or
                    defaults is None or defaults.get("male") != ids["male"] or defaults.get("female") != ids["female"]):
                raise ValueError("Selected body matrices/defaults differ from the independent choices")
            rows.append({"maleFamily": male, "family": family, "obody": host, "runtimeFiles": len(installed),
                         "files": [{"path": name, "source": source, "sha256": sha(entries[source])}
                                   for name, source in sorted(installed.items())]})
    return rows


def source_reference(own, requested):
    repository = "https://github.com/Vhodnoylogin/claw"
    result = {"repository": repository, "commit": None, "url": repository,
              "localCommitValidated": False, "publicAvailabilityChecked": False}
    if requested is None:
        return result
    if not re.fullmatch(r"[0-9a-f]{40}", requested):
        raise ValueError("Source commit must be a full lowercase Git commit ID")
    kind = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-t", requested], capture_output=True)
    if kind.returncode or kind.stdout.strip() != b"commit":
        raise ValueError("Source commit is not available as a local commit")
    for name, actual in own.items():
        relative = name.removeprefix("claw/")
        recorded = subprocess.run(["git", "-C", str(ROOT), "show", requested + ":" + relative], capture_output=True)
        if recorded.returncode or recorded.stdout.replace(b"\r\n", b"\n") != actual.replace(b"\r\n", b"\n"):
            raise ValueError("Source commit differs from validated build source: " + relative)
    result.update(commit=requested, url=repository + "/tree/" + requested, localCommitValidated=True)
    return result


def runtime_notices(licenses, review):
    entries, excluded, aliases, seen = {}, {}, {}, {}
    source_extensions = {".h", ".hpp", ".cpp", ".c", ".py", ".ps1", ".psc", ".cmake"}
    internal_records = {"NOTICES/CLAW-donor-permission-record.md", "NOTICES/OBODY-API-NOTICE.md"}
    for name in sorted(licenses, key=lambda value: (not value.startswith("NOTICES/"), value)):
        data = licenses[name]
        if Path(name).suffix.lower() in source_extensions or name in internal_records:
            excluded[name] = "Source/header or internal authoring record retained in external validation only"
            continue
        digest = sha(data)
        if digest in seen:
            aliases[name] = seen[digest]
            continue
        destination = "NOTICES/" + name.removeprefix("NOTICES/")
        if destination in entries and entries[destination] != data:
            raise ValueError("Conflicting normalized notice destination: " + destination)
        entries[destination] = data
        seen[digest] = destination
    commonlib_license = review["commonlib"]["license"]
    if sha(licenses[commonlib_license]) not in seen:
        raise ValueError("The reviewed CommonLib license must be included in runtime notices")
    entries["NOTICES/THIRD-PARTY.txt"] = (
        "CLAW uses CommonLibSSE-NG and its dependencies. Their license notices are included here.\n"
        "CommonLib source: " + review["commonlib"]["repository"] + "/tree/" + review["commonlib"]["commit"] + "\n"
        "RaceMenu/SKEE interface by expired6978:\n"
        "https://github.com/expired6978/SKSE64Plugins/blob/9ebcb733e17be695f994cd2e9cc383043446bc02/skee64/IPluginInterface.h\n"
        "OBody NG public interface:\n"
        "https://github.com/Aietos/OBody-NG/blob/13513609145313f721970c2ebe113290f6add6e8/include/API/API.h\n"
    ).encode("utf-8")
    return entries, {"excludedSourceInputs": excluded, "identicalLicenseAliases": aliases}


def build(*, native_dll, bodies_dir, game_esp, native_pex, source_companion_dir,
          commonlib_commit, out, obody_esp=None, obody_pex=None, version=VERSION, source_commit=None):
    original_output = Path(out).absolute()
    if any(part.exists() and (part.is_symlink() or part.is_junction()) for part in (original_output, *original_output.parents)):
        raise ValueError("Linked output ancestry refused")
    output = Path(out).resolve()
    target = (ROOT / "target").resolve()
    if output.exists() or target not in output.parents:
        raise ValueError("Choose a new output directory below ignored target/")
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){2,3}", version):
        raise ValueError("Use an explicit numeric internal product version")
    if (obody_esp is None) != (obody_pex is None):
        raise ValueError("OBody host ESP and PEX must be supplied together")
    inputs = Inputs()
    entries = {"00 Base/CLAW.esp": inputs.runtime(game_esp, b"TES4", "game ESP"),
               "10 Native/SKSE/Plugins/CLAWDistribution.dll": inputs.runtime(native_dll, b"MZ", "native DLL"),
               "10 Native/Scripts/CLAWDistributionNative.pex": inputs.runtime(native_pex, b"\xfa\x57\xc0\xde", "native PEX")}
    for sex in ("male", "female"):
        body = {}
        for ending in ("_0.nif", "_1.nif", ".tri"):
            name = sex + "bodywerewolf" + ending
            body[ending] = inputs.runtime(Path(bodies_dir) / name, b"PIRT" if ending == ".tri" else b"Gamebryo", name)
        for ending, data in body.items():
            if ending == "_1.nif" and data == body["_0.nif"]:
                continue
            entries["00 Base/" + MESH + "/" + sex + "bodywerewolf" + ending] = data
    if obody_esp is not None:
        entries["30 OBody Source/CLAW - OBody Integration.esp"] = inputs.runtime(obody_esp, b"TES4", "OBody ESP")
        entries["30 OBody Source/Scripts/CLAWOBodySourceHost.pex"] = inputs.runtime(obody_pex, b"\xfa\x57\xc0\xde", "OBody PEX")
    matrix = inputs.read(ROOT / "src/main/resources/profiles/MorphLinks.xml")
    for male in MALE_FAMILIES:
        for family in FEMALE_FAMILIES:
            entries["20 Human Family/"+male+"-and-"+family+"/SKSE/Plugins/CLAW/MorphLinks.xml"] = profiles(matrix, family, male)
    template = ROOT / "src/main/resources/publication/unified-installer"
    entries["fomod/ModuleConfig.xml"] = installer(inputs.read(template / "ModuleConfig.xml"), entries)
    info = ET.fromstring(inputs.read(template / "info.xml"))
    info.find("Name").text = NAME
    info.find("Version").text = version
    info.find("Description").text = "Links human body morphs to werewolf bodies."
    entries["fomod/info.xml"] = ET.tostring(info, encoding="utf-8", xml_declaration=True)
    own, native_sources, commit, source_selection = tracked_source(inputs, obody_esp is not None)
    native_sha = sha(entries["10 Native/SKSE/Plugins/CLAWDistribution.dll"])
    external, licenses, review = companion(inputs, source_companion_dir, native_sha, native_sources, commonlib_commit)
    validate_no_nested_archives(external)
    reference = source_reference(own, source_commit)
    notices, notice_selection = runtime_notices(licenses, review)
    entries.update(notices)
    entries["README.md"] = ("# " + NAME + "\n\n"
        "Human body morphs carried into werewolf shape.\n"
        "Install through FOMOD: choose HIMBO or Vanilla for males and CBBE, 3BA or Vanilla for females.\n"
        "Requires Elegant textures, XP32 and matching SKSE/RaceMenu/Address Library. Replacement human bodies are required only for their selected matrix.\n"
        "Vanilla matrices use NPC weight. OBody integration supplies morph inputs to eligible born wolves using a morph-based matrix.\n\nSource code: " + reference["url"] + "\n").encode("utf-8")
    validate_no_nested_archives(entries)
    selections = selection_audit(read_zip(zip_bytes(entries)))
    receipt = {"schemaVersion": 1, "status": "packaged-explicit-build-inputs-not-game-qualified-not-published",
               "name": NAME, "version": version, "sourceCommit": reference["commit"],
               "sourceCheckoutHead": commit, "sourceReference": reference, "nativeDllSha256": native_sha,
               "sourceWorktreeHasTrackedChanges": source_selection["worktreeHasTrackedChanges"],
               "commonlibCommit": commonlib_commit, "selections": selections,
               "sourceFilesIncluded": 0, "packageLayout": "runtime-results-only", "noticeFiles": len(notices),
               "sourceFilesValidatedExternally": len(own) + len(external),
               "nestedArchivePayloads": False,
               "sourceSelection": source_selection,
               "runtimeInputsCompiledByThisCommand": False, "gameOrManagerExecuted": False,
               "runtimeInputProvenance": inputs.runtime_roles,
               "historicalArchiveUsedAsSource": False, "iniInstalled": False,
               "configuration": "canonical MorphLinks.xml family defaults; runtime has no INI reader",
               "payloads": {name: {"sha256": sha(data), "bytes": len(data)} for name, data in sorted(entries.items())}}
    packed = zip_bytes(entries)
    validate_no_nested_archives(read_zip(packed))
    if read_zip(packed) != entries or selection_audit(read_zip(packed)) != selections:
        raise ValueError("Literal ZIP/readback installation differs from the recorded payload")
    inputs.verify()
    output.mkdir(parents=True, exist_ok=False)
    archive = output / ARCHIVE_NAME
    archive.write_bytes(packed)
    receipt.update(archive=str(archive), sha256=sha(packed), bytes=len(packed), archiveFiles=len(entries),
                   inputs={str(path): {"sha256": sha(data), "bytes": len(data)} for path, data in inputs.records.items()})
    (output / "build-receipt.json").write_bytes(encoded(receipt))
    (output / "source-validation.json").write_bytes(encoded({"schemaVersion": 1, "review": review,
        "sourceReference": reference, "noticeSelection": notice_selection, "sourceIncludedInGameArchive": False,
        "validatedFiles": {**{name: {"sha256": sha(data), "bytes": len(data)} for name, data in own.items()},
                           **{"dependencies/" + name: {"sha256": sha(data), "bytes": len(data)} for name, data in external.items()}}}))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("native-dll", "bodies-dir", "game-esp", "native-pex", "source-companion-dir", "out"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--commonlib-commit", required=True)
    parser.add_argument("--obody-esp", type=Path)
    parser.add_argument("--obody-pex", type=Path)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--source-commit", help="Optional exact local commit matching reviewed source; verify public availability before publishing")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(**vars(args)), indent=2))
    except (OSError, ValueError, KeyError, ET.ParseError, subprocess.CalledProcessError) as error:
        parser.exit(2, "CLAW source package: " + str(error) + "\n")


if __name__ == "__main__":
    main()
