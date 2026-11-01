#pragma once
#include "claw/ColourMath.h"
#include "claw/CoatLibrary.h"
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <IPluginInterface.h>
#include <map>
#include <memory>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

// Engine graph mutations are game-thread only. Distribution owns the state
// lock for every entry point, including read-only status and serialization.
// No persistent SKEE overrides, NPC-base writes or shared texture mutations.
namespace claw::appearance {
class Runtime final {
public:
    Runtime() = default;
    Runtime(const Runtime&) = delete;
    Runtime& operator=(const Runtime&) = delete;
    Runtime(Runtime&&) = delete;
    Runtime& operator=(Runtime&&) = delete;

    void reset();
    void forget(RE::FormID id);
    void restore(RE::Actor* actor);
    void captureHuman(RE::Actor* actor);
    void setLibrary(CoatLibrary library, std::filesystem::path dataRoot);
    [[nodiscard]] std::vector<std::string> patterns() const { return library_.names(); }
    [[nodiscard]] bool knowsPattern(std::string_view id) const { return library_.find(id) != nullptr; }
    bool setPattern(RE::Actor* actor, std::string id);
    void clearPattern(RE::Actor* actor);
    [[nodiscard]] std::string pattern(RE::FormID id) const;
    [[nodiscard]] std::string appliedPattern(RE::FormID id) const;
    [[nodiscard]] std::string patternStatus(RE::FormID id) const;
    bool applyWolf(RE::Actor* actor, IOverrideInterface* provider);
    void save(SKSE::SerializationInterface* serial) const;
    bool loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length);
    [[nodiscard]] std::string_view status(RE::FormID id) const;
    template<class Keep> void retainIf(Keep&& keep);

private:
    struct Surface {
        RE::NiPointer<RE::BSGeometry> geometry;
        RE::NiPointer<RE::BSShaderProperty> original, own;
        std::uint32_t expectedTint{};
        bool tinted{};
        // Retain initialized identities: a later replacement cannot recycle an
        // old pointer into a false match while this surface lease is active.
        RE::BSTSmartPointer<RE::BSShaderMaterial> material;
        RE::NiPointer<RE::NiBooleanExtraData> guard;
        RE::NiPointer<RE::BSTextureSet> textureSet;
        RE::NiPointer<RE::NiSourceTexture> diffuseTexture;
        std::array<std::string, RE::BSTextureSet::Texture::kTotal> texturePaths;
        bool patterned{};
    };
    struct Entry {
        RE::FormID base{};
        std::uint32_t sex{};
        Colours colours;
        RE::NiPointer<RE::NiAVObject> root; // Retain generation identity; prevents recycled-root pointer aliases.
        RE::ActorHandle handle;
        bool loaded{}, yielded{};
        std::vector<Surface> surfaces;
        std::string status;
        std::string explicitPattern, appliedPattern, attemptedPattern;
    };
    template<class F> static void visit(RE::NiAVObject* object, F&& f);
    static void unbind(Entry& entry);
    static std::string_view prepareTintMaterial(RE::BSShaderProperty* copy,
        const RE::BSShaderProperty* original, std::uint32_t tint);
    static bool protectPrivateTint(RE::BSShaderProperty* copy, const RE::BSShaderProperty* original);
    static bool healthyPrivateTint(const Surface& surface);
    static std::string texturePath(RE::BSTextureSet* set, RE::BSTextureSet::Texture slot);
    std::string resolvedPattern(const Entry& entry) const;
    bool preparePattern(RE::BSShaderProperty* property, const CoatTexture& texture, const CoatDDSInfo& expected, std::string& reason) const;
    struct PatternAssets { bool valid{}; std::map<std::string, CoatDDSInfo, std::less<>> dimensions; };
    const PatternAssets& validatePattern(const std::string& key, const CoatPattern& pattern);
    Entry* entryFor(RE::Actor* actor);
    inline static constexpr std::uint32_t record = 0x524C4343; // CCLR
    inline static constexpr std::uint32_t patternRecord = 0x54504343; // CCPT
    std::map<RE::FormID, Entry> entries_;
    std::set<RE::FormID> colourRecords_, patternRecords_, rejectedRecords_;
    CoatLibrary library_;
    std::filesystem::path dataRoot_;
    std::map<std::string, PatternAssets, std::less<>> validatedPatterns_;
};
// Distribution owns synchronization and explicit game-safe reset/revert.
inline Runtime runtime;

template<class F> void Runtime::visit(RE::NiAVObject* object, F&& f) {
    if (!object) return;
    f(object);
    if (auto* node = object->AsNode()) for (auto& child : node->GetChildren()) if (child) visit(child.get(), f);
}
inline void Runtime::unbind(Entry& entry) {
    for (auto& surface : entry.surfaces) {
        auto& current = surface.geometry->GetGeometryRuntimeData().shaderProperty;
        // A later writer can replace the property OR mutate our clone in place.
        // Incomplete immediate writes still roll back; successfully tinted
        // surfaces are restored only while their complete ownership is intact.
        if (current.get() == surface.own.get() && (!surface.tinted || healthyPrivateTint(surface))) current = surface.original;
    }
    entry.surfaces.clear(); entry.root.reset(); entry.yielded = false; entry.appliedPattern.clear();
}
inline void Runtime::reset() {
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    entries_.clear(); colourRecords_.clear(); patternRecords_.clear(); rejectedRecords_.clear();
}
inline void Runtime::forget(RE::FormID id) {
    if (auto found = entries_.find(id); found != entries_.end()) { unbind(found->second); entries_.erase(found); }
}
inline void Runtime::restore(RE::Actor* actor) {
    if (!actor) return;
    if (auto found = entries_.find(actor->formID); found != entries_.end()) unbind(found->second);
}
inline std::string_view Runtime::status(RE::FormID id) const {
    const auto found = entries_.find(id);
    return found == entries_.end() ? std::string_view{"human appearance unavailable"} : found->second.status;
}
inline void Runtime::setLibrary(CoatLibrary library, std::filesystem::path dataRoot) {
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    library_ = std::move(library); dataRoot_ = std::move(dataRoot); validatedPatterns_.clear();
}
inline Runtime::Entry* Runtime::entryFor(RE::Actor* actor) {
    if (!actor || !actor->GetActorBase()) return nullptr;
    auto* base = actor->GetActorBase();
    if (!actor->formID || !base->formID) return nullptr;
    if (base->GetSex() != RE::SEX::kMale && base->GetSex() != RE::SEX::kFemale) return nullptr;
    if (!entries_.contains(actor->formID) && entries_.size() >= 8192) return nullptr;
    auto& entry = entries_[actor->formID];
    if (entry.base && (entry.base != base->formID || entry.sex != static_cast<std::uint32_t>(base->GetSex()) ||
        (!entry.loaded && entry.handle.get().get() != actor))) {
        unbind(entry); entry = {};
    }
    entry.base = base->formID; entry.sex = static_cast<std::uint32_t>(base->GetSex());
    entry.handle = actor->GetHandle(); entry.loaded = false;
    return &entry;
}
inline bool Runtime::setPattern(RE::Actor* actor, std::string id) {
    if (!library_.find(id)) return false;
    auto* entry = entryFor(actor); if (!entry) return false;
    validatedPatterns_.erase(id);
    unbind(*entry); entry->explicitPattern = std::move(id); entry->status = "coat selection pending"; return true;
}
inline void Runtime::clearPattern(RE::Actor* actor) {
    if (!actor) return;
    if (auto found = entries_.find(actor->formID); found != entries_.end()) {
        unbind(found->second); found->second.explicitPattern.clear();
        if (!found->second.colours.hasSkin && !found->second.colours.hasHair) entries_.erase(found);
    }
}
inline std::string Runtime::resolvedPattern(const Entry& entry) const {
    return !entry.explicitPattern.empty() ? entry.explicitPattern : entry.colours.hasHair ? library_.nearest(entry.colours.hair) : std::string{};
}
inline std::string Runtime::pattern(RE::FormID id) const {
    const auto found = entries_.find(id); return found == entries_.end() ? std::string{} : found->second.explicitPattern;
}
inline std::string Runtime::appliedPattern(RE::FormID id) const {
    const auto found = entries_.find(id); return found == entries_.end() ? std::string{} : found->second.appliedPattern;
}
inline std::string Runtime::patternStatus(RE::FormID id) const {
    const auto found = entries_.find(id);
    if (found == entries_.end()) return "human appearance unavailable";
    const auto& entry = found->second;
    return (!entry.explicitPattern.empty() ? "explicit: " : !resolvedPattern(entry).empty() ? "automatic: " : "tint only: ") + entry.status;
}
inline std::string Runtime::texturePath(RE::BSTextureSet* set, RE::BSTextureSet::Texture slot) {
    const auto* value = set ? set->GetTexturePath(slot) : nullptr; return value ? value : "";
}
inline const Runtime::PatternAssets& Runtime::validatePattern(const std::string& key, const CoatPattern& pattern) {
    const auto [found, inserted] = validatedPatterns_.try_emplace(key);
    auto& result = found->second;
    if (!inserted) return result;
    if (dataRoot_.empty()) return result;
    for (const auto& [name, texture] : pattern.textures) {
        const auto path = dataRoot_ / std::filesystem::path(texture.path);
        std::error_code ec;
        if (std::filesystem::file_size(path, ec) != texture.bytes || ec) return result;
        std::ifstream input(path, std::ios::binary); std::array<char, 128> header{};
        if (!input.read(header.data(), header.size())) return result;
        const auto info = coatDDSHeader(header);
        if (!info) return result;
        result.dimensions.emplace(name, *info);
    }
    result.valid = result.dimensions.size() == 9;
    return result;
}
inline bool Runtime::preparePattern(RE::BSShaderProperty* property, const CoatTexture& texture, const CoatDDSInfo& expected, std::string& reason) const {
    if (!property || !property->material) { reason = "private shader or material unavailable"; return false; }
    auto* material = static_cast<RE::BSLightingShaderMaterialBase*>(property->material);
    const auto donorPath = texturePath(material->textureSet.get(), RE::BSTextureSet::Texture::kDiffuse);
    const auto fail = [&](std::string detail) { reason = std::move(detail) + "; donor diffuse=" + donorPath; return false; };
    const auto enginePath = coatEngineTexturePath(texture.path);
    RE::NiPointer<RE::NiTexture> loaded;
    RE::BSShaderManager::GetTexture(enginePath.c_str(), true, loaded, false);
    if (!loaded) return fail("GetTexture returned null");
    auto* source = loaded ? netimmerse_cast<RE::NiSourceTexture*>(loaded.get()) : nullptr;
    if (!source) {
        const auto* type = loaded->GetRTTI();
        return fail("loaded texture RTTI=" + std::string(type ? type->GetName() : "<none>") + "; NiSourceTexture cast failed");
    }
    std::uint32_t width{}, height{}, levels{}, arraySize{};
    source->GetTextureDimensionsAndMipInfo(&width, &height, &levels, &arraySize);
    if (width != expected.width || height != expected.height || levels == 0 || arraySize != 1) {
        const auto* renderer = source->rendererTexture;
        return fail("loaded dimensions=" + std::to_string(width) + "x" + std::to_string(height) +
            ", mips=" + std::to_string(levels) + ", array=" + std::to_string(arraySize) +
            "; expected=" + std::to_string(expected.width) + "x" + std::to_string(expected.height) +
            ", header mips=" + std::to_string(expected.mipLevels) + ", array=1" +
            "; renderer=" + (renderer ? "yes" : "no") + ", resourceView=" + (renderer && renderer->resourceView ? "yes" : "no"));
    }
    if (!material->textureSet) return fail("donor textureSet unavailable");
    RE::NiPointer<RE::BSTextureSet> set{RE::BSShaderTextureSet::Create()};
    if (!set) return fail("private textureSet creation returned null");
    if (set.get() == material->textureSet.get()) return fail("private textureSet aliases donor");
    for (std::uint32_t i = 0; i < RE::BSTextureSet::Texture::kTotal; ++i) {
        const auto slot = static_cast<RE::BSTextureSet::Texture>(i);
        const auto original = texturePath(material->textureSet.get(), slot);
        set->SetTexturePath(slot, original.c_str());
    }
    set->SetTexturePath(RE::BSTextureSet::Texture::kDiffuse, enginePath.c_str());
    material->SetTextureSet(set); material->diffuseTexture.reset(source);
    if (material->textureSet.get() != set.get()) return fail("private textureSet assignment readback mismatch");
    if (material->diffuseTexture.get() != source) return fail("diffuse texture assignment readback mismatch");
    const auto actualPath = texturePath(set.get(), RE::BSTextureSet::Texture::kDiffuse);
    if (actualPath != enginePath) return fail("private diffuse path readback=" + actualPath + "; expected=" + enginePath);
    return true;
}
template<class Keep> void Runtime::retainIf(Keep&& keep) {
    for (auto it = entries_.begin(); it != entries_.end();) {
        if (keep(it->first)) ++it;
        else { unbind(it->second); it = entries_.erase(it); }
    }
}
inline void Runtime::captureHuman(RE::Actor* actor) {
    if (!actor || !actor->GetActorBase()) return;
    auto* base = actor->GetActorBase();
    auto* face = base->GetRootFaceNPC();
    if (!face) face = base;
    Colours colours;
    colours.skin = {face->bodyTintColor.red / 255.0F, face->bodyTintColor.green / 255.0F, face->bodyTintColor.blue / 255.0F};
    colours.hasSkin = true;
    if (face->headRelatedData && face->headRelatedData->hairColor) {
        const auto& rgb = face->headRelatedData->hairColor->color;
        colours.hair = {rgb.red / 255.0F, rgb.green / 255.0F, rgb.blue / 255.0F};
        colours.hasHair = true;
    }
    std::optional<RGB> rendered;
    bool ambiguous{};
    visit(actor->Get3D(false), [&](RE::NiAVObject* object) {
        auto* geometry = object->AsGeometry();
        auto* property = geometry ? geometry->lightingShaderProp_cast() : nullptr;
        if (!property || !property->material || property->material->GetFeature() != RE::BSShaderMaterial::Feature::kHairTint) return;
        const auto* material = static_cast<RE::BSLightingShaderMaterialHairTint*>(property->material);
        // RaceMenu's preset writer stores normalized RGB bytes scaled by two.
        const auto palette = paletteColour({material->tintColor.red / 2, material->tintColor.green / 2, material->tintColor.blue / 2});
        if (!palette) return;
        const auto& rgb = *palette;
        if (rendered && *rendered != rgb) ambiguous = true;
        else rendered = rgb;
    });
    if (rendered && !ambiguous) { colours.hair = *rendered; colours.hasHair = true; colours.renderedHair = true; }
    auto* target = entryFor(actor); if (!target) return;
    auto& entry = *target;
    if (entry.colours != colours) unbind(entry);
    entry.base = base->formID; entry.sex = static_cast<std::uint32_t>(base->GetSex()); entry.colours = colours;
    entry.handle = actor->GetHandle(); entry.loaded = false;
    entry.status = ambiguous ? "record-hair-fallback: ambiguous rendered hair" : "human colours captured";
}
inline std::string_view Runtime::prepareTintMaterial(RE::BSShaderProperty* copy,
    const RE::BSShaderProperty* original, std::uint32_t tint) {
    using Base = RE::BSLightingShaderMaterialBase;
    using Feature = RE::BSShaderMaterial::Feature;
    const auto feature = original->material->GetFeature() == Feature::kHairTint ? Feature::kHairTint : Feature::kFaceGenRGBTint;
    auto* manager = RE::MemoryManager::GetSingleton();
    auto* heap = manager ? manager->GetThreadScrapHeap() : nullptr;
    if (!heap) return "material scratch heap unavailable";
    // The factory installs the engine's real vtable. A C++-constructed tint
    // material in the stock SKEE key7 conversion has invalid virtual targets on
    // the observed runtime. Never pass through that conversion or adopt this
    // scratch allocation into a long-lived property with SetMaterial(false).
    const auto release = [heap](Base* temporary) {
        if (temporary) { temporary->~BSLightingShaderMaterialBase(); heap->Deallocate(temporary); }
    };
    std::unique_ptr<Base, decltype(release)> temporary{Base::CreateMaterial(feature), release};
    if (!temporary || temporary->GetFeature() != feature) return "engine tint material unavailable";
    temporary->CopyBaseMembers(static_cast<Base*>(original->material));
    const auto rgb = unpack(tint);
    if (feature == Feature::kHairTint) {
        static_cast<RE::BSLightingShaderMaterialHairTint*>(temporary.get())->tintColor = {rgb[0], rgb[1], rgb[2]};
    } else {
        static_cast<RE::BSLightingShaderMaterialFacegenTint*>(temporary.get())->tintColor = {rgb[0], rgb[1], rgb[2]};
        copy->SetFlags(RE::BSShaderProperty::EShaderPropertyFlag8::kFace, false);
        copy->SetFlags(RE::BSShaderProperty::EShaderPropertyFlag8::kFaceGenRGBTint, true);
    }
    // true requests an independent engine-owned copy. Only the temporary is
    // destroyed through the matching captured scratch heap at this scope exit.
    copy->SetMaterial(temporary.get(), true);
    if (!copy->material || copy->material == original->material) return "private tint material unavailable";
    if (copy->material->GetFeature() != feature) return "private tint feature mismatch";
    return {};
}
inline bool Runtime::protectPrivateTint(RE::BSShaderProperty* copy, const RE::BSShaderProperty* original) {
    // Clone extra-data objects may retain references to donor data. Never flip
    // an inherited NO_TINT boolean in place: replace it on the private property.
    // A shared extra-data array is not safe to edit, even with a distinct property.
    if (copy->extra && copy->extra == original->extra) return false;
    const RE::BSFixedString key{"NO_TINT"};
    if (copy->GetExtraData(key) && !copy->RemoveExtraData(key)) return false;
    RE::NiPointer<RE::NiBooleanExtraData> guard{RE::NiBooleanExtraData::Create(key, true)};
    return guard && copy->AddExtraData(guard.get()) && copy->GetExtraData(key) == guard.get();
}
inline bool Runtime::healthyPrivateTint(const Surface& surface) {
    if (!surface.own || !surface.original || !surface.own->material ||
        surface.own->material == surface.original->material) return false;
    const auto* material = surface.own->material;
    const auto* guardData = surface.own->GetExtraData("NO_TINT");
    // Compare identities before inspecting live data. The retained old objects
    // are witnesses, not sources to dereference after another writer replaces
    // the material or its guard. Initial immediate writes have no lease yet.
    if (surface.tinted && (material != surface.material.get() || guardData != surface.guard.get())) return false;
    const auto* guard = netimmerse_cast<RE::NiBooleanExtraData*>(guardData);
    if (!guard || !guard->data) return false;
    RGB actual{};
    if (material->GetFeature() == RE::BSShaderMaterial::Feature::kFaceGenRGBTint) {
        const auto& tint = static_cast<const RE::BSLightingShaderMaterialFacegenTint*>(material)->tintColor;
        actual = {tint.red, tint.green, tint.blue};
    } else if (material->GetFeature() == RE::BSShaderMaterial::Feature::kHairTint) {
        const auto& tint = static_cast<const RE::BSLightingShaderMaterialHairTint*>(material)->tintColor;
        actual = {tint.red, tint.green, tint.blue};
    } else return false;
    if (surface.tinted && static_cast<const RE::BSLightingShaderMaterialBase*>(material)->textureSet.get() != surface.textureSet.get()) return false;
    const auto* lighting = static_cast<const RE::BSLightingShaderMaterialBase*>(material);
    if ((surface.tinted || surface.patterned) && lighting->diffuseTexture.get() != surface.diffuseTexture.get()) return false;
    if (surface.patterned) {
        if (lighting->textureSet.get() != surface.textureSet.get()) return false;
        for (std::uint32_t i = 0; i < RE::BSTextureSet::Texture::kTotal; ++i)
            if (texturePath(lighting->textureSet.get(), static_cast<RE::BSTextureSet::Texture>(i)) != surface.texturePaths[i]) return false;
    }
    return matchesPackedTint(actual, surface.expectedTint);
}
inline bool Runtime::applyWolf(RE::Actor* actor, IOverrideInterface* provider) {
    if (!actor || !actor->GetActorBase() || !provider) return false;
    auto found = entries_.find(actor->formID);
    if (found == entries_.end()) return false; // Born beasts have no fabricated human colours.
    auto& entry = found->second;
    auto* base = actor->GetActorBase();
    if (entry.base != base->formID || entry.sex != static_cast<std::uint32_t>(base->GetSex()) ||
        (!entry.loaded && entry.handle.get().get() != actor) || !valid(entry.colours)) {
        unbind(entry); entry.status = "source identity unavailable"; return false;
    }
    if (entry.loaded) { entry.handle = actor->GetHandle(); entry.loaded = false; }
    auto* root = actor->Get3D(false);
    if (!root) { unbind(entry); entry.status = "unloaded"; return false; }
    const auto requestedPattern = resolvedPattern(entry);
    if (root == entry.root.get() && entry.attemptedPattern == requestedPattern && !entry.surfaces.empty()) {
        const bool stillInScene = std::all_of(entry.surfaces.begin(), entry.surfaces.end(), [root](const auto& surface) {
            return root->GetObjectByName(surface.geometry->name) == surface.geometry.get();
        });
        const bool stillOwned = std::all_of(entry.surfaces.begin(), entry.surfaces.end(), [](const auto& surface) {
            return surface.geometry->GetGeometryRuntimeData().shaderProperty.get() == surface.own.get();
        });
        const bool stillTinted = stillOwned && std::all_of(entry.surfaces.begin(), entry.surfaces.end(), healthyPrivateTint);
        if (stillInScene && stillTinted) return true;
        // A later provider wins until model generation changes; no override war.
        if (stillInScene) {
            unbind(entry); entry.root.reset(root); entry.yielded = true; entry.status = "yielded to later coat writer"; return false;
        }
    }
    if (root == entry.root.get() && entry.yielded) return false;
    if (root == entry.root.get() && entry.attemptedPattern == requestedPattern && entry.surfaces.empty()) return false;
    unbind(entry);
    std::vector<Surface> prepared;
    const auto* selected = library_.find(requestedPattern);
    std::string patternFailure = !requestedPattern.empty() && !selected ? "library or pattern unavailable" : "";
    const PatternAssets* assets{};
    if (selected) {
        assets = &validatePattern(requestedPattern, *selected);
        if (!assets->valid) { selected = nullptr; patternFailure = "DDS missing or header/size mismatch"; }
    }
    // Resource failure is resolved before any live binding. A human retains the
    // already-working tint, and a source-less born wolf retains its donor.
    for (unsigned attempt = 0; attempt < 2; ++attempt) {
    prepared.clear(); bool retryWithoutPattern{};
    for (const auto& surfaceSpec : coatSurfaces) {
        const auto name = surfaceSpec.name;
        const bool skin = name == "body" || name == "head";
        const bool hasColour = skin ? entry.colours.hasSkin : entry.colours.hasHair;
        if (!hasColour && !selected) continue;
        RE::BSGeometry* geometry{}; unsigned count{};
        // NiAVObject uses the engine's case-insensitive interned BSFixedString.
        // Its retained spelling may come from another earlier model. A bytewise
        // comparison can miss a surface that GetObjectByName correctly finds.
        const RE::BSFixedString expected{name.data()};
        visit(root, [&](RE::NiAVObject* object) {
            if (object->name == expected) { ++count; geometry = object->AsGeometry(); }
        });
        if (count != 1 || !geometry) {
            const auto reason = "coat surface " + std::string(name) + ": matches=" + std::to_string(count) +
                ", geometry=" + (geometry ? "yes" : "no");
            if (entry.status != reason) {
                std::size_t objects{}, geometries{}; std::string inventory;
                visit(root, [&](RE::NiAVObject* object) {
                    ++objects;
                    if (object->AsGeometry()) ++geometries;
                    if (objects <= 96) {
                        if (!inventory.empty()) inventory += "; ";
                        inventory += object->name.c_str() ? object->name.c_str() : "<unnamed>";
                        inventory += ":";
                        const auto* type = object->GetRTTI();
                        inventory += type ? type->GetName() : "<no RTTI>";
                    }
                });
                SKSE::log::warn("CLAW appearance {:08X}: {}; visited {} objects / {} geometries; {}",
                    actor->formID, reason, objects, geometries, inventory);
            }
            entry.status = reason; return false;
        }
        auto* original = geometry->lightingShaderProp_cast();
        if (!original || !original->material) { entry.status = "unsupported coat shader"; return false; }
        const auto feature = original->material->GetFeature();
        if (feature != RE::BSShaderMaterial::Feature::kDefault && feature != RE::BSShaderMaterial::Feature::kFaceGenRGBTint &&
            feature != RE::BSShaderMaterial::Feature::kHairTint) { entry.status = "unsupported coat material"; return false; }
        RE::NiPointer<RE::BSShaderProperty> copy{static_cast<RE::BSShaderProperty*>(original->Clone())};
        const auto isolationFailure = [&](std::string_view reason) {
            const auto status = "material isolation failed: " + std::string(name) + ": " + std::string(reason);
            if (entry.status != status) SKSE::log::warn(
                "CLAW appearance {:08X}: {}; property source={} clone={}; material source={} clone={}",
                actor->formID, status, static_cast<const void*>(original), static_cast<const void*>(copy.get()),
                static_cast<const void*>(original->material), static_cast<const void*>(copy ? copy->material : nullptr));
            entry.status = status;
            return false;
        };
        if (!copy) return isolationFailure("property clone unavailable");
        if (copy.get() == original) return isolationFailure("property clone aliases source");
        // Neutral material multiplication does not make a human source available.
        const auto tint = hasColour ? pack(coatTint(skin ? entry.colours.skin : entry.colours.hair, !skin)) : 0xFFFFFFU;
        if (const auto failure = prepareTintMaterial(copy.get(), original, tint); !failure.empty()) return isolationFailure(failure);
        std::string textureFailure;
        if (selected && !preparePattern(copy.get(), selected->textures.at(std::string(surfaceSpec.texture)), assets->dimensions.at(std::string(surfaceSpec.texture)), textureFailure)) {
            const auto& path = selected->textures.at(std::string(surfaceSpec.texture)).path;
            patternFailure = path + ": " + textureFailure;
            SKSE::log::warn("CLAW appearance {:08X}: coat {} asset {}: {}", actor->formID, requestedPattern, path, textureFailure);
            selected = nullptr; retryWithoutPattern = true; break;
        }
        if (!protectPrivateTint(copy.get(), original)) { entry.status = "private tint protection failed"; return false; }
        prepared.push_back({RE::NiPointer<RE::BSGeometry>{geometry}, RE::NiPointer<RE::BSShaderProperty>{original}, copy,
            tint});
        auto& staged = prepared.back();
        auto* material = static_cast<RE::BSLightingShaderMaterialBase*>(copy->material);
        staged.patterned = selected != nullptr; staged.diffuseTexture = material->diffuseTexture;
        if (selected) {
            staged.textureSet = material->textureSet;
            for (std::uint32_t i = 0; i < RE::BSTextureSet::Texture::kTotal; ++i)
                staged.texturePaths[i] = texturePath(material->textureSet.get(), static_cast<RE::BSTextureSet::Texture>(i));
        }
    }
    if (!retryWithoutPattern) break;
    }
    entry.attemptedPattern = requestedPattern;
    if (prepared.empty()) {
        entry.root.reset(root); entry.status = patternFailure.empty() ? "no human colour sources" : "coat unavailable: " + patternFailure; return false;
    }
    // All surfaces were validated and cloned before any live binding changes.
    entry.surfaces = std::move(prepared); entry.root.reset(root);
    for (auto& surface : entry.surfaces) {
        surface.geometry->GetGeometryRuntimeData().shaderProperty = surface.own;
        // CommonLib's virtual FinishSetupGeometry calls the engine shader
        // initializer on this property; unlike a private relocation it uses the
        // active runtime's own vtable on SE/AE/VR.
        if (!surface.own->FinishSetupGeometry(surface.geometry.get()) || !healthyPrivateTint(surface)) {
            unbind(entry); entry.status = "private tint initialization failed"; return false;
        }
        surface.material.reset(surface.own->material);
        surface.guard.reset(netimmerse_cast<RE::NiBooleanExtraData*>(surface.own->GetExtraData("NO_TINT")));
        surface.textureSet = static_cast<RE::BSLightingShaderMaterialBase*>(surface.own->material)->textureSet;
        surface.diffuseTexture = static_cast<RE::BSLightingShaderMaterialBase*>(surface.own->material)->diffuseTexture;
        surface.tinted = true;
    }
    entry.appliedPattern = selected ? requestedPattern : "";
    entry.status = selected ? "applied private coat " + requestedPattern + " with " +
        (entry.colours.hasSkin || entry.colours.hasHair ? "skin/fur tint" : "neutral tint") : "applied private skin/fur tint";
    if (!patternFailure.empty()) entry.status += "; coat unavailable: " + patternFailure;
    SKSE::log::info("CLAW appearance {:08X}: {} ({} surfaces; hair source {})", actor->formID, entry.status,
        entry.surfaces.size(), entry.colours.renderedHair ? "rendered" : "record");
    return true;
}
// Separate colour and explicit-pattern records. Automatic selections are
// recomputed from the retained real source; no material/texture pointers persist.
inline void Runtime::save(SKSE::SerializationInterface* serial) const {
    for (const auto& [id, entry] : entries_) {
        if (valid(entry.colours) && (entry.colours.hasSkin || entry.colours.hasHair)) {
            const std::array<std::uint32_t, 6> data{id, entry.base, entry.sex,
                std::uint32_t(entry.colours.hasSkin) | (std::uint32_t(entry.colours.hasHair) << 1) | (std::uint32_t(entry.colours.renderedHair) << 2),
                pack(entry.colours.skin), pack(entry.colours.hair)};
            if (!serial->OpenRecord(record, 1) || !serial->WriteRecordData(data.data(), sizeof(data)))
                SKSE::log::error("CLAW actor {:08X}: CCLR colour serialization failed", id);
        }
        if (!entry.explicitPattern.empty() && coatKey(entry.explicitPattern)) {
            const auto data = writeCoatSelection({id, entry.base, entry.sex, entry.explicitPattern});
            if (!serial->WriteRecord(patternRecord, 1, data.data(), static_cast<std::uint32_t>(data.size())))
                SKSE::log::error("CLAW actor {:08X}: CCPT coat selection serialization failed", id);
        }
    }
}
inline bool Runtime::loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length) {
    if (type != record && type != patternRecord) return false;
    std::array<std::uint32_t, 6> data{}; std::string choice;
    if (version != 1) { SKSE::log::warn("CLAW appearance: unsupported record version"); return true; }
    if (type == record) {
        if (length != sizeof(data) || serial->ReadRecordData(data.data(), sizeof(data)) != sizeof(data)) {
            SKSE::log::warn("CLAW appearance: invalid CCLR record"); return true;
        }
        if (data[3] > 7 || data[4] > 0xFFFFFF || data[5] > 0xFFFFFF) return true;
    } else {
        if (length <= 16 || length > 145) { SKSE::log::warn("CLAW appearance: invalid CCPT record length"); return true; }
        std::vector<char> bytes(length);
        if (serial->ReadRecordData(bytes.data(), length) != length) { SKSE::log::warn("CLAW appearance: truncated CCPT record"); return true; }
        try {
            const auto selection = readCoatSelection(bytes);
            data[0] = selection.actor; data[1] = selection.base; data[2] = selection.sex; choice = selection.pattern;
        } catch (const std::exception& error) {
            SKSE::log::warn("CLAW appearance: invalid CCPT record: {}", error.what()); return true;
        }
    }
    RE::FormID actor{}, base{};
    if (!serial->ResolveFormID(data[0], actor) || !serial->ResolveFormID(data[1], base) || !actor || !base || data[2] > 1 ||
        rejectedRecords_.contains(actor)) return true;
    auto& seen = type == record ? colourRecords_ : patternRecords_;
    if (seen.size() >= 8192 && !seen.contains(actor)) return true;
    auto existing = entries_.find(actor);
    if (!seen.insert(actor).second || (existing != entries_.end() &&
        (existing->second.base != base || existing->second.sex != data[2]))) {
        if (existing != entries_.end()) entries_.erase(existing);
        rejectedRecords_.insert(actor);
        SKSE::log::warn("CLAW actor {:08X}: duplicate/conflicting appearance records rejected", actor); return true;
    }
    if (existing == entries_.end() && entries_.size() >= 8192) return true;
    auto& entry = entries_[actor]; entry.base = base; entry.sex = data[2]; entry.loaded = true;
    if (type == record) {
        entry.colours = {unpack(data[4]), unpack(data[5]), bool(data[3] & 1), bool(data[3] & 2), bool(data[3] & 4)};
        if (!valid(entry.colours)) { entries_.erase(actor); rejectedRecords_.insert(actor); }
    } else entry.explicitPattern = std::move(choice);
    return true;
}
}
