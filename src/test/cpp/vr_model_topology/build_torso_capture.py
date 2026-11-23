"""Build a CLAW skin observer extension to the pinned private R06 source."""
from argparse import ArgumentParser
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from shutil import copyfile
import subprocess


HERE = Path(__file__).resolve().parent
R06_RECEIPT = "3637bdf0251903d7add1df144497424b2008a6cf9b3be6a083be151e419df4b4"
R06_COMMANDS = "ec2547ae1c73074fceecd8ecec5035e0a5aae8e127b17d1b523c7d005aaa2359"
SKEE_HEADER = "875410dd22230f76a014a6841004e7d346f5fa1c748cfff695f9f495234da277"
BUILD_ENVIRONMENT = "28131403690b16b8256b5d85c37cf88511c7e0330b23ac77664c2555787cc1c5"
EQUIPPED_MODULE = "CLAWVREquippedEarPose"
TOPOLOGY_MODULE = "CLAWVRModelTopology"


def pin(path, expected=None):
    path = Path(path).resolve(strict=True)
    data = path.read_bytes()
    digest = sha256(data).hexdigest()
    if expected is not None and digest != expected:
        raise ValueError(f"Unexpected SHA-256 for {path}")
    return {"path": str(path), "bytes": len(data), "sha256": digest}


def verify(record):
    actual = pin(record["path"], record["sha256"])
    if actual["bytes"] != record["bytes"]:
        raise ValueError(f"Unexpected byte count for {record['path']}")
    return Path(actual["path"])


def replace(text, old, new):
    if text.count(old) != 1:
        raise ValueError("R06 patch anchor is missing or ambiguous: " + old.splitlines()[0])
    return text.replace(old, new)


def morph_source_overlay(source, refusal):
    source = replace(source, "        if (gate.loading()) return reply(nonce,", f"""        if (!torsoMorphSource.load()) return reply(nonce, "refused", diagnostics(), "{refusal}").dump();
        if (gate.loading()) return reply(nonce,""")
    return replace(source, "        auto* messaging = SKSE::GetMessagingInterface();", """        auto* messaging = SKSE::GetMessagingInterface();
        InterfaceExchangeMessage exchange;
        constexpr auto exchangeMessage = static_cast<std::uint32_t>(InterfaceExchangeMessage::kMessage_ExchangeInterface);
        if (messaging->Dispatch(exchangeMessage, &exchange, sizeof(exchange), "skee") && exchange.interfaceMap) {
            auto* bodyMorph = exchange.interfaceMap->QueryInterface("BodyMorph");
            if (bodyMorph && bodyMorph->GetVersion() >= IBodyMorphInterface::kPluginVersion4)
                torsoMorphSource.store(static_cast<IBodyMorphInterface*>(bodyMorph));
        }""")


def torso_overlay(source):
    source = replace(source, '#include "higgsinterface001.h"', '#include "higgsinterface001.h"\n#include "TorsoPose.h"')
    source = replace(source, "Json collect(Clock::time_point deadline,",
        r"""std::atomic<IBodyMorphInterface*> torsoMorphSource{};

std::string torsoBodyTri(const RE::BSGeometry& torso) {
    const auto* extra = netimmerse_cast<RE::NiStringExtraData*>(torso.GetExtraData("BODYTRI"));
    const auto path = extra ? bounded(extra->value) : std::string{};
    require(path == R"(actors\werewolfbeast\claw\firstperson\male\body.tri)",
            "Retained torso must use the admitted male BODYTRI route");
    return path;
}

Json collect(Clock::time_point deadline,""")
    source = replace(source, "    Json shapes = Json::array();", """    Json shapes = Json::array();
    RE::NiPointer<RE::BSGeometry> retainedTorso;""")
    source = replace(source, "        const auto& bound = object.worldBound;", """        const std::string_view shapeName = object.name;
        if (shapeName == "HEAD" || shapeName == "head") {
            require(!retainedTorso, "Ambiguous retained HEAD torso");
            retainedTorso.reset(geometry);
        }
        const auto& bound = object.worldBound;""")
    source = replace(source, "    std::size_t index{};", """    auto* morphs = torsoMorphSource.load();
    require(retainedTorso && morphs, "Retained HEAD torso or effective SKEE source unavailable");
    const auto bodyTri = torsoBodyTri(*retainedTorso);
    const auto measured = claw::vr_diagnostic::captureTorsoPose(*player, *root, *clone, *retainedTorso, *morphs, deadline);
    Json torsoBones = Json::object(), effectiveMorphs = Json::object();
    for (const auto& bone : measured.bones) torsoBones[bone.name] = {{"world", pose(bone.world)}};
    for (const auto& morph : measured.effectiveMorphs) effectiveMorphs[morph.name] = morph.value;
    require(torsoBodyTri(*retainedTorso) == bodyTri, "Retained torso BODYTRI changed during capture");
    std::size_t index{};""")
    source = replace(source, '            {"nearLeft", nearLeft}, {"renderedPixelsVerified", false}};',
        '''            {"nearLeft", nearLeft}, {"torsoCaptureVersion", 1}, {"torsoBodyTri", bodyTri},
            {"torsoBones", std::move(torsoBones)}, {"effectiveMorphs", std::move(effectiveMorphs)},
            {"renderedPixelsVerified", false}};''')
    return morph_source_overlay(source, "torso_skee_unavailable")


def ear_overlay(source):
    source = replace(source, '#include "higgsinterface001.h"', '#include "higgsinterface001.h"\n#include "EarStereoPose.h"')
    source = replace(source, '"claw-vr-vrik-world-avatar/1"', '"claw-vr-vrik-ear-stereo/1"')
    source = replace(source, 'claw::vr_diagnostic::Body32Predicates predicates(', r'''bool femaleBodyPath(std::string_view path) {
    constexpr std::string_view expected = R"(Actors\WerewolfBeast\Character Assets\FemaleBodyWereWolf_1.NIF)";
    return std::ranges::equal(path, expected, {}, claw::vr_diagnostic::modelPathChar, claw::vr_diagnostic::modelPathChar);
}

claw::vr_diagnostic::Body32Predicates predicates(''')
    source = replace(source, 'claw::vr_diagnostic::isStockMaleBodyPath(slot.model),',
                     'claw::vr_diagnostic::isStockMaleBodyPath(slot.model) || femaleBodyPath(slot.model),')
    source = replace(source, 'Json collect(Clock::time_point deadline,', r'''std::atomic<IBodyMorphInterface*> torsoMorphSource{};

std::string earBodyTri(const RE::BSGeometry& ears) {
    const auto* extra = netimmerse_cast<RE::NiStringExtraData*>(ears.GetExtraData("BODYTRI"));
    return extra ? bounded(extra->value) : std::string{};
}

Json collect(Clock::time_point deadline,''')
    source = replace(source, '    require(sex == 0 && weight == 0.f, "exact male weight-zero fixture required");',
                     '    require(sex <= 1 && std::isfinite(weight) && weight >= 0.f && weight <= 100.f, "exact fixture sex/weight required");')
    source = replace(source, '    require(root && biped && biped->root && vr && vr->HmdNode && vr->LeftWandNode && vr->RightWandNode,',
                     '    require(root && biped && biped->root && biped->actorRef.get().get() == player && vr && vr->HmdNode && vr->LeftWandNode && vr->RightWandNode,')
    source = replace(source, '    require(predicates(slot, root.get(), bipedRoot).qualified(), "exact engine-managed world Body32 required");',
                     '''    require(predicates(slot, root.get(), bipedRoot).qualified() &&
            (sex == 1 ? femaleBodyPath(slot.model) : claw::vr_diagnostic::isStockMaleBodyPath(slot.model)),
            "exact sex-specific engine-managed world Body32 required");''')
    source = replace(source, '''    const auto& opticData = optic.GetVRRuntimeData();
    const auto* nearFrustum = opticData.viewFrustumArray;
    require(readable(nearFrustum) && std::isfinite(nearFrustum->fNear) && nearFrustum->fNear > 0.f,
            "positive engine left near clip unavailable");
    const float nearLeft = nearFrustum->fNear;''', '''    const auto cameraRoot = camera->cameraRoot;
    RE::NiPointer<RE::NiCamera> retainedOptic{&optic};
    const auto hmdNode = vr->HmdNode;
    const auto hmdWorld = hmdNode->world;
    auto* provider = RE::BSOpenVR::GetIVRSystem();
    require(provider && readable(provider) && Clock::now() < deadline, "Skyrim OpenVR system unavailable");
    const auto readStereo = [&] {
        return claw::vr_diagnostic::captureStereoOptics(optic, *provider, [](const auto* ptr) { return readable(ptr); });
    };
    const auto stereo = readStereo();
    const float nearLeft = stereo.eyes[0].engineFrustum[4];''')
    source = replace(source, '    Json shapes = Json::array();', '''    Json shapes = Json::array();
    RE::NiPointer<RE::BSGeometry> ears;''')
    source = replace(source, '        const auto& bound = object.worldBound;', '''        if (std::string_view(object.name.c_str()) == claw::vr_diagnostic::earShapeName) {
            require(!ears, "ambiguous world ear skin");
            ears.reset(geometry);
        }
        const auto& bound = object.worldBound;''')
    source = replace(source, '    std::size_t index{};', r'''    auto* morphs = torsoMorphSource.load();
    require(ears && morphs && ownsReciprocalRoute(*ears, *clone), "owned active ear skin or effective SKEE source unavailable");
    const auto earTri = earBodyTri(*ears);
    require(earTri == claw::vr_diagnostic::earTriPath(sex == 1), "wrong sex-specific ear BODYTRI");
    const auto* earShape = ears->AsTriShape();
    require(earShape, "ear geometry is not a triangle shape");
    const auto& extent = earShape->GetTrishapeRuntimeData();
    const auto vertices = extent.vertexCount;
    const auto triangles = extent.triangleCount;
    require((vertices == 0 || vertices == 1354) && (triangles == 0 || triangles == 2394), "unexpected native ear topology counts");
    const auto measured = claw::vr_diagnostic::captureSkinPose(*player, *root, *clone, *ears, *morphs, deadline,
        {claw::vr_diagnostic::earBones, claw::vr_diagnostic::earMorphs});
    Json earBones = Json::object(), earMorphs = Json::object();
    for (const auto& bone : measured.bones) earBones[bone.name] = {{"world", pose(bone.world)}};
    for (const auto& morph : measured.effectiveMorphs) earMorphs[morph.name] = morph.value;
    std::size_t index{};''')
    source = replace(source, '    routeEvidence["stableChildCount"] = childIdentities.size();', '''    require(Clock::now() < deadline && player->GetVRNodeData() == vr && vr->HmdNode == hmdNode && hmdNode->world == hmdWorld &&
            biped->actorRef.get().get() == player && earTri == earBodyTri(*ears) && ownsReciprocalRoute(*ears, *clone) &&
            extent.vertexCount == vertices && extent.triangleCount == triangles && !parentCull(*ears) &&
            camera->cameraRoot == cameraRoot && &activeCamera(*camera, deadline) == retainedOptic.get() &&
            RE::BSOpenVR::GetIVRSystem() == provider && provider && readable(provider) && readStereo() == stereo && Clock::now() < deadline,
            "ear route, stereo optics or HMD pose changed during capture");
    Json eyeOptics = Json::array();
    for (std::size_t eye = 0; eye < stereo.eyes.size(); ++eye) {
        const auto& value = stereo.eyes[eye];
        eyeOptics.push_back({{"eye", eye == 0 ? "left" : "right"}, {"engineFrustumLTRB_NF", value.engineFrustum},
            {"engineOrthographic", value.engineOrthographic}, {"engineViewportLTRB", value.engineViewport},
            {"openVrProjectionRawLTRB", value.providerProjection}, {"openVrEyeToHeadRows", value.providerEyeToHead}});
    }
    routeEvidence["stableChildCount"] = childIdentities.size();''')
    source = replace(source, '{"hmd", pose(vr->HmdNode->world)}', '{"hmd", pose(hmdWorld)}')
    source = replace(source, '{"camera", pose(optic.world)}', '{"camera", pose(stereo.opticWorld)}')
    source = replace(source, '            {"nearLeft", nearLeft}, {"renderedPixelsVerified", false}};', '''            {"nearLeft", nearLeft}, {"earStereoCaptureVersion", 1}, {"earBodyTri", earTri},
            {"earVerticesObserved", vertices}, {"earTrianglesObserved", triangles},
            {"earBones", std::move(earBones)}, {"earEffectiveMorphs", std::move(earMorphs)}, {"eyeOptics", std::move(eyeOptics)},
            {"eyeProjectionQualified", false}, {"atomicRenderSnapshot", false}, {"renderedPixelsVerified", false}};''')
    return morph_source_overlay(source, "ear_skee_unavailable")


def equipped_ear_overlay(source):
    source = ear_overlay(source)
    source = replace(source, f'constexpr auto name = "{TOPOLOGY_MODULE}";',
                     f'constexpr auto name = "{EQUIPPED_MODULE}";')
    source = replace(source, 'claw-vr-vrik-ear-stereo/1', 'claw-vr-vrik-ear-stereo/2')
    source = replace(source, '{"earStereoCaptureVersion", 1}', '{"earStereoCaptureVersion", 2}')
    source = replace(source, 'Json& routeEvidence) {', '''Json& routeEvidence) {
    LARGE_INTEGER qpcBegin{}, qpcEnd{}, qpcFrequency{};
    require(QueryPerformanceFrequency(&qpcFrequency) && qpcFrequency.QuadPart > 0 &&
            QueryPerformanceCounter(&qpcBegin) && qpcBegin.QuadPart > 0, "ear clock unavailable");''')
    source = replace(source, '        return reply(nonce, "pending", diagnostics()).dump();', '''        const auto armed = diagnostics();
        armedAfter = armed["postPhaseCount"].get<std::uint64_t>();
        return reply(nonce, "pending", armed).dump();''')
    source = replace(source, '        if (!busy || sampling || gate.loading()) return;',
                     '        if (!busy || sampling || gate.loading() || frame <= armedAfter) return;')
    source = replace(source, '    std::atomic<std::uint64_t> sequence{};',
                     '    std::atomic<std::uint64_t> sequence{};\n    std::uint64_t armedAfter{};')
    start = source.index('bool femaleBodyPath(')
    end = source.index('Json slotDiagnostic(', start)
    source = source[:start] + r"""struct ExpectedBodySlot {
    RE::FormID item{}, addon{};
    std::string_view model, marker;
};

std::array<ExpectedBodySlot, 2> equippedEarRoutes(bool female) {
    constexpr auto fileName = "test_CLAW - VR Player Body32.esp";
    auto* data = RE::TESDataHandler::GetSingleton();
    require(data, "fixture data unavailable");
    const auto* file = data->LookupModByName(fileName);
    const auto* item = data->LookupForm<RE::TESObjectARMO>(0x801, fileName);
    const auto* addon = data->LookupForm<RE::TESObjectARMA>(0x800, fileName);
    require(file && item && addon && item->GetFile(0) == file && addon->GetFile(0) == file &&
            item->armorAddons.size() == 1 && item->armorAddons[0] == addon, "owned Body32 fixture forms unavailable");
    const auto index = form(item) >> 24;
    require(index > 0 && index < 0xFE && (form(addon) >> 24) == index &&
            (form(item) & 0xFFFFFF) == 0x801 && (form(addon) & 0xFFFFFF) == 0x800,
            "Body32 fixture form IDs or plugin index differ");
    return {{
        {form(item), form(addon),
         female ? R"(Actors\WerewolfBeast\CLAW\FirstPerson\female\EarWorldTrial.nif)" :
                  R"(Actors\WerewolfBeast\CLAW\FirstPerson\male\EarWorldTrial.nif)", female ? "W_F" : "W_M"},
        {form(item), form(addon),
         female ? R"(Actors\WerewolfBeast\CLAW\FirstPerson\female\Body_1.nif)" :
                  R"(Actors\WerewolfBeast\CLAW\FirstPerson\male\Body_1.nif)", female ? "P_F" : "P_M"}
    }};
}

claw::vr_diagnostic::Body32Predicates predicates(const BodySlot& slot, const Object* actorRoot, const Object* bipedRoot,
                                                 const ExpectedBodySlot& expected) {
    using claw::vr_diagnostic::modelPathChar;
    return {bool(slot.clone), slot.clone && actorRoot && ownsReciprocalRoute(*slot.clone, *actorRoot),
            slot.clone && bipedRoot && ownedUnder(*slot.clone, *bipedRoot),
            std::ranges::equal(slot.model, expected.model, {}, modelPathChar, modelPathChar),
            slot.item == expected.item, slot.addon == expected.addon};
}

struct EquippedMarker {
    static constexpr std::string_view prefix = "CLAW_VR_DISPATCH_PROBE_";
    RE::NiPointer<Object> object;
    const Object* parent{};

    static std::string_view name(const Object& candidate) {
        const auto* text = candidate.name.c_str();
        return text ? std::string_view(text) : std::string_view{};
    }

    void observe(Object& candidate, std::string_view wanted) {
        const auto label = name(candidate);
        if (!label.starts_with(prefix)) return;
        require(!object && label.substr(prefix.size()) == wanted, "ambiguous or wrong Body32 dispatch marker");
        object.reset(&candidate);
        parent = candidate.parent;
    }

    bool attachedTo(const Object& clone, std::string_view wanted) const {
        if (!object || !parent || object->parent != parent) return false;
        const auto label = name(*object);
        const auto* node = object->AsNode();
        return node && node->GetChildren().empty() && label.starts_with(prefix) &&
               label.substr(prefix.size()) == wanted && ownsReciprocalRoute(*object, clone);
    }
};

""" + source[end:]
    source = replace(source, '''Json slotDiagnostic(const BodySlot& slot, const Object* actorRoot, const Object* bipedRoot) {
    const auto p = predicates(slot, actorRoot, bipedRoot);''',
        '''Json slotDiagnostic(const BodySlot& slot, const Object* actorRoot, const Object* bipedRoot,
                    const ExpectedBodySlot& expected) {
    const auto p = predicates(slot, actorRoot, bipedRoot, expected);''')
    source = replace(source, '''Json routeDiagnostic(const RE::BipedAnim* biped, const Object* actorRoot, const BodySlot& active, const BodySlot& buffered) {''',
        '''Json routeDiagnostic(const RE::BipedAnim* biped, const Object* actorRoot, const BodySlot& active,
                     const BodySlot& buffered, const ExpectedBodySlot& expected) {''')
    source = replace(source, '''{"active", slotDiagnostic(active, actorRoot, root)}, {"buffered", slotDiagnostic(buffered, actorRoot, root)}''',
        '''{"active", slotDiagnostic(active, actorRoot, root, expected)}, {"buffered", slotDiagnostic(buffered, actorRoot, root, expected)}''')
    source = replace(source, '''    auto topology = Json{{"slot", 32}, {"viewThirdPerson", routeDiagnostic(biped.get(), root.get(), slot, buffered)},
                         {"viewFirstPerson", routeDiagnostic(first.get(), firstRoot.get(), firstActive, firstBuffered)},''',
        '''    const auto [worldExpected, firstExpected] = equippedEarRoutes(sex == 1);
    auto topology = Json{{"slot", 32}, {"viewThirdPerson", routeDiagnostic(biped.get(), root.get(), slot, buffered, worldExpected)},
                         {"viewFirstPerson", routeDiagnostic(first.get(), firstRoot.get(), firstActive, firstBuffered, firstExpected)},''')
    source = replace(source, '''    require(predicates(slot, root.get(), bipedRoot).qualified() &&
            (sex == 1 ? femaleBodyPath(slot.model) : claw::vr_diagnostic::isStockMaleBodyPath(slot.model)),
            "exact sex-specific engine-managed world Body32 required");''',
        '''    require(predicates(slot, root.get(), bipedRoot, worldExpected).qualified(),
            "exact equipped world Body32 required");''')
    source = replace(source, '''    const auto alternate = firstRoot && first && first.get() != biped.get() && firstRoot.get() != root.get() &&
                           alternateCull.effective() == true && firstActive.empty() && firstBuffered.empty();''',
        '''    const auto firstHidden = firstActive.empty() || (first && first->actorRef.get().get() == player &&
        firstActive.clone.get() != clone.get() && predicates(firstActive, firstRoot.get(), firstBipedRoot, firstExpected).qualified() &&
        parentCull(*firstActive.clone));
    const auto alternate = firstRoot && first && first.get() != biped.get() && firstRoot.get() != root.get() &&
                           alternateCull.effective() == true && firstHidden && firstBuffered.empty();''')
    source = replace(source, '    const auto* currentCameraState = camera->currentState.get();', '''    EquippedMarker worldMarker, firstMarker;
    if (firstActive.clone) {
        traverse(*firstActive.clone, maxShapeNodes, deadline,
                 [&](Object& object) { firstMarker.observe(object, firstExpected.marker); }, true);
        require(firstMarker.attachedTo(*firstActive.clone, firstExpected.marker), "first-person Body32 marker unavailable");
    }
    const auto* currentCameraState = camera->currentState.get();''')
    source = replace(source, 'std::string_view(object.name.c_str()) == claw::vr_diagnostic::earShapeName',
                     'EquippedMarker::name(object) == claw::vr_diagnostic::earShapeName')
    source = replace(source, '        childIdentities.push_back(&object);', '''        childIdentities.push_back(&object);
        worldMarker.observe(object, worldExpected.marker);''')
    source = replace(source, '    auto* morphs = torsoMorphSource.load();', '''    require(worldMarker.attachedTo(*clone, worldExpected.marker), "world Body32 marker unavailable");
    auto* morphs = torsoMorphSource.load();''')
    source = replace(source, '''    routeEvidence["stableChildCount"] = childIdentities.size();''',
        '''    require(Clock::now() < deadline && biped->root == bipedRoot && biped->actorRef.get().get() == player &&
            bodySlotRecord(biped->bufferedObjects[bodySlot]) == buffered &&
            player->Get3D(true) == firstRoot.get() && player->GetBiped(true).get() == first.get() &&
            first->root == firstBipedRoot && bodySlotRecord(first->objects[bodySlot]) == firstActive &&
            bodySlotRecord(first->bufferedObjects[bodySlot]) == firstBuffered &&
            worldMarker.attachedTo(*clone, worldExpected.marker) &&
            (!firstActive.clone || (first->actorRef.get().get() == player && ownsReciprocalRoute(*firstActive.clone, *firstRoot) &&
                                    parentCull(*firstActive.clone) &&
                                    firstMarker.attachedTo(*firstActive.clone, firstExpected.marker))) && Clock::now() < deadline,
            "equipped Body32 routes or markers changed during capture");
    routeEvidence["worldDispatchMarker"] = worldExpected.marker;
    routeEvidence["firstPersonDispatchMarker"] = firstActive.clone ? Json(firstExpected.marker) : Json(nullptr);
    routeEvidence["stableChildCount"] = childIdentities.size();''')
    source = replace(source, '    return {{"phase", "PostVrikPostHiggs"},', '''    require(QueryPerformanceCounter(&qpcEnd) && qpcEnd.QuadPart > qpcBegin.QuadPart && Clock::now() < deadline,
            "ear capture exceeded native clock bracket");
    return {{"qpcBegin", qpcBegin.QuadPart}, {"qpcEnd", qpcEnd.QuadPart}, {"qpcFrequency", qpcFrequency.QuadPart},
            {"phase", "PostVrikPostHiggs"},''')
    return replace(source, '{"item", bodyItem}, {"addon", bodyAddon}', '{"item", slot.item}, {"addon", slot.addon}')


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def build(r06, skee, environment, output, *, subject="torso", papyrus=None):
    equipped = subject == "equipped-ears"
    if equipped and papyrus is None:
        raise ValueError("The equipped ear observer requires the Papyrus compiler for its separate script class")
    module = EQUIPPED_MODULE if equipped else TOPOLOGY_MODULE
    papyrus_pin = pin(papyrus) if equipped else None
    receipt_pin = pin(r06 / "RECEIPT.json", R06_RECEIPT)
    commands_pin = pin(r06 / "commands.json", R06_COMMANDS)
    skee_pin = pin(skee, SKEE_HEADER)
    environment_pin = pin(environment, BUILD_ENVIRONMENT)
    base = read_json(Path(receipt_pin["path"]))
    source_files = [verify(row) for row in base["sources"]]
    original = next(path for path in source_files if path.name == "Plugin.cpp")
    header = pin(HERE / "TorsoPose.h")
    if subject in ("ears", "equipped-ears"):
        extra_headers = [pin(HERE / name) for name in ("EarStereoPose.h", "StereoOptics.h")]
        overlay = equipped_ear_overlay if equipped else ear_overlay
        version = 2 if equipped else 1
        capture_version = {"schema": f"claw-vr-vrik-ear-stereo/{version}", "earStereoCaptureVersion": version}
    elif subject == "torso":
        extra_headers = []
        overlay = torso_overlay
        capture_version = {"schema": "claw-vr-vrik-world-avatar/1", "torsoCaptureVersion": 1}
    else:
        raise ValueError("Unknown R06 observer subject")
    pex = HERE / (module + ".psc") if equipped else verify(base["pex"])
    dependencies = read_json(verify(base["referenceDependencies"]))["files"]
    trusted = {Path(name).resolve(): digest for name, digest in dependencies.items()}
    for row in base["inputs"]:
        trusted[verify(row)] = row["sha256"]
    trusted[Path(skee_pin["path"])] = skee_pin["sha256"]
    trusted[Path(header["path"])] = header["sha256"]
    trusted.update((Path(row["path"]), row["sha256"]) for row in extra_headers)

    recipe = read_json(Path(commands_pin["path"]))
    baseline_compile = next(command for command in recipe if "/c" in command)
    baseline_link = next(command for command in recipe if Path(command[0]).name.casefold() == "link.exe")
    compiler, linker = verify(base["cl"]), verify(base["link"])
    if (Path(baseline_compile[0]).resolve(), Path(baseline_link[0]).resolve()) != (compiler, linker):
        raise ValueError("R06 tool paths differ from the sealed compiler and linker")
    for argument in baseline_link[1:]:
        library = Path(argument)
        if library.is_absolute() and library.suffix.casefold() == ".lib":
            pin(library, trusted[library.resolve()])

    output = output.resolve()
    output.mkdir()
    source = output / "Plugin.cpp"
    source.write_bytes(overlay(original.read_text(encoding="utf-8")).encode("utf-8"))
    obj = output / "Plugin.obj"
    dll = output / (module + ".dll")
    depfile = output / "compiler-dependencies.json"
    compile_args = baseline_compile[:baseline_compile.index("/sourceDependencies")]
    compile_args = [arg for arg in compile_args
                    if arg != "/WX-" and not arg.casefold().startswith("/fo") and not arg.casefold().endswith(".cpp")]
    compile_args.extend(("/WX", "/I" + str(original.parent), "/I" + str(HERE), "/external:I", str(skee.resolve().parent),
                         "/Fo" + str(obj), str(source), "/sourceDependencies", str(depfile)))
    link_args = [arg for arg in baseline_link if not arg.casefold().endswith(".obj")
                 and not arg.casefold().startswith(("/out:", "/pdb:", "/implib:"))]
    link_args.extend(("/OUT:" + str(dll), "/IMPLIB:" + str(output / (module + ".lib")), str(obj)))

    env = os.environ.copy()
    startup = subprocess.run(["cmd.exe", "/d", "/c", environment_pin["path"]], capture_output=True,
                             text=True, check=True)
    for line in startup.stdout.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.upper() in {"PATH", "INCLUDE", "LIB", "LIBPATH", "VCTOOLSINSTALLDIR", "WINDOWSSDKDIR"}:
            env[key] = value
    stages = []

    def run(name, command):
        result = subprocess.run(command, cwd=output, env=env, capture_output=True, text=True)
        log = output / (name + ".log")
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode:
            raise RuntimeError(f"{name} failed ({result.returncode}). See {log}")
        stages.append({"command": command, "exitCode": result.returncode, "log": pin(log)})

    run("compile", compile_args)
    observed = []
    for name in read_json(depfile)["Data"]["Includes"]:
        path = Path(name).resolve(strict=True)
        observed.append(pin(path, trusted[path]))
    run("link", link_args)
    run("exports", [str(linker.with_name("dumpbin.exe")), "/exports", str(dll)])
    exports = (output / "exports.log").read_text(encoding="utf-8")
    if not all(name in exports for name in ("SKSEPlugin_Query", "SKSEPlugin_Load")):
        raise ValueError("Missing legacy Skyrim VR loader exports")
    installed_pex = output / (module + ".pex")
    if equipped:
        run("papyrus", [papyrus_pin["path"], str(pex), "-o=" + str(output), "-i=" + str(HERE)])
    else:
        copyfile(pex, installed_pex)
    report = {"utc": datetime.now(timezone.utc).isoformat(), "baseline": receipt_pin,
              "baselineCommands": commands_pin, "environment": environment_pin, "builder": pin(Path(__file__)),
              "source": pin(source), "torsoPose": header, "skee": skee_pin, "includes": observed,
              "dll": pin(dll), "pex": pin(installed_pex, None if equipped else base["pex"]["sha256"]), "stages": stages,
              **capture_version, "runtimeChecked": False}
    if equipped:
        report.update({"papyrusCompiler": papyrus_pin, "papyrusSource": pin(pex), "script": module,
                       "coDeployWith": TOPOLOGY_MODULE, "captureClock": "QueryPerformanceCounter"})
    if extra_headers:
        report["additionalHeaders"] = extra_headers
    (output / "RECEIPT.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report["dll"]


if __name__ == "__main__":
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--r06", type=Path, required=True, help="Sealed native-r06 build directory")
    parser.add_argument("--skee", type=Path, required=True, help="Pinned external RaceMenu IPluginInterface.h")
    parser.add_argument("--environment", type=Path, required=True, help="Retained MSVC capture-environment.cmd")
    parser.add_argument("--out", type=Path, required=True, help="New external build directory")
    parser.add_argument("--subject", choices=("torso", "ears", "equipped-ears"), default="torso")
    parser.add_argument("--papyrus", type=Path, help="Bethesda PapyrusCompiler.exe for the equipped ear script")
    args = parser.parse_args()
    print(json.dumps(build(args.r06, args.skee, args.environment, args.out,
                           subject=args.subject, papyrus=args.papyrus), indent=2))
