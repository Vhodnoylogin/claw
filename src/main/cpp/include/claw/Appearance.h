#pragma once
#include "claw/ColourMath.h"
#include "claw/CoatMapping.h"
#include "claw/MaterialLease.h"
#include "claw/CoatSurfaceAudit.h"
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <IPluginInterface.h>
#include <map>
#include <memory>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>
#include <chrono>

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
    void setPolicy(std::string_view xml);
    void unavailablePolicy(std::string reason);
    void setCoatMapping(CoatMapping mapping);
    void unavailableCoatMapping(std::string reason);
    [[nodiscard]] std::string_view coatOutputName() const { return mapping_ ? std::string_view(mapping_->output()) : std::string_view{}; }
    [[nodiscard]] Colours humanColours(RE::FormID id) const;
    [[nodiscard]] std::vector<std::string> patterns() const { return mapping_ ? mapping_->names() : library_.names(); }
    [[nodiscard]] bool knowsPattern(std::string_view id) const {
        return mapping_ ? !mapping_->material(id).empty() : library_.find(id) != nullptr;
    }
    bool setPattern(RE::Actor* actor, std::string id);
    void clearPattern(RE::Actor* actor);
    [[nodiscard]] std::string pattern(RE::FormID id) const;
    [[nodiscard]] std::string appliedPattern(RE::FormID id) const;
    [[nodiscard]] std::string patternStatus(RE::FormID id) const;
    // begin/read/invalidate/cancel touch plain cached state only. sample is an
    // explicit read-only game-task boundary, independent of material apply.
    std::uint64_t beginSurfaceAudit(RE::FormID id);
    void invalidateSurfaceAudit(RE::FormID id);
    void cancelSurfaceAudit(RE::FormID id, std::uint64_t token);
    bool sampleSurfaceAudit(RE::Actor* actor, std::uint64_t token);
    [[nodiscard]] std::string surfaceAudit(RE::FormID id) const;
    bool applyWolf(RE::Actor* actor, IOverrideInterface* provider,
        std::uint64_t saveNamespace, std::uint64_t identity, std::optional<float> coatOutput);
    void save(SKSE::SerializationInterface* serial) const;
    bool loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length);
    [[nodiscard]] std::string_view status(RE::FormID id) const;
    template<class Keep> void retainIf(Keep&& keep);

private:
    struct Surface {
        RE::NiPointer<RE::BSGeometry> geometry;
        RE::NiPointer<RE::BSShaderProperty> original, own;
        std::optional<std::uint32_t> expectedTint;
        bool tinted{};
        // Retain initialized identities: a later replacement cannot recycle an
        // old pointer into a false match while this surface lease is active.
        RE::BSTSmartPointer<RE::BSShaderMaterial> material;
        RE::NiPointer<RE::NiBooleanExtraData> guard;
        RE::NiPointer<RE::BSTextureSet> textureSet;
        RE::NiPointer<RE::NiSourceTexture> diffuseTexture;
        std::array<RE::NiPointer<RE::NiSourceTexture>, 3> otherTextures;
        RE::BSTSmartPointer<RE::BSEffectShaderData> effectData;
        std::optional<MaterialLeaseState> materialLease;
        std::array<std::string, RE::BSTextureSet::Texture::kTotal> texturePaths;
        bool patterned{};
        std::optional<std::int32_t> initializedFeature;
        std::optional<RGB> initializedTint;
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
        AutomaticCoatState automatic;
        std::optional<float> coatOutput;
        TintMode attemptedMode{TintMode::linked};
        CoatSurfaceAuditCache audit;
        RE::NiPointer<RE::NiAVObject> auditRoot; // Turnover/release occurs only in game tasks.
        std::uint64_t auditGeneration{};
        CoatSurfaceAuditCache yieldAudit; // Separate plain diagnostic cache; public request tokens unchanged.
        RE::NiPointer<RE::NiAVObject> yieldReportedRoot; // First diagnostic only per retained model root.
    };
    template<class F> static void visit(RE::NiAVObject* object, F&& f);
    static void unbind(Entry& entry);
    static std::string_view prepareMaterial(RE::BSShaderProperty* copy,
        const RE::BSShaderProperty* original, std::optional<std::uint32_t> tint);
    static bool protectPrivateTint(RE::BSShaderProperty* copy, const RE::BSShaderProperty* original);
    static bool healthyPrivateTint(const Surface& surface);
    static bool inspectPrivateTint(const Surface& surface, std::vector<MaterialLeaseDifference>* differences);
    struct SurfaceLeaseFailure { std::string name; std::vector<MaterialLeaseDifference> differences; };
    static MaterialLeaseState materialLeaseState(const RE::BSShaderProperty& property);
    static std::optional<RGB> observedTint(const RE::BSShaderMaterial* material);
    static void reportYieldDifferences(RE::FormID actor, const Entry& entry, const std::vector<SurfaceLeaseFailure>& failures);
    static std::string texturePath(RE::BSTextureSet* set, RE::BSTextureSet::Texture slot);
    CoatDecision decision(const Entry& entry) const;
    bool preparePattern(RE::BSShaderProperty* property, const CoatTexture& texture, const CoatDDSInfo& expected, std::string& reason) const;
    struct PatternAssets { bool valid{}; std::map<std::string, CoatDDSInfo, std::less<>> dimensions; };
    const PatternAssets& validatePattern(const std::string& key, const CoatPattern& pattern);
    Entry* entryFor(RE::Actor* actor);
    bool sampleSurfaceAudit(RE::Actor* actor, std::uint64_t token, CoatSurfaceAuditCache& cache);
    static std::uint64_t auditClock();
    inline static constexpr std::uint32_t record = 0x524C4343; // CCLR
    inline static constexpr std::uint32_t patternRecord = 0x54504343; // CCPT
    inline static constexpr std::uint32_t automaticRecord = 0x53414343; // CCAS, additive v1
    std::map<RE::FormID, Entry> entries_;
    std::set<RE::FormID> colourRecords_, patternRecords_, automaticRecords_, rejectedRecords_;
    CoatLibrary library_;
    CoatPolicy policy_;
    std::optional<CoatMapping> mapping_;
    std::filesystem::path dataRoot_;
    std::map<std::string, PatternAssets, std::less<>> validatedPatterns_;
    std::uint64_t nextAuditRequest_{1}, nextAuditGeneration_{1}; // Never saved or reused on reset.
};
// Distribution owns synchronization and explicit game-safe reset/revert.
inline Runtime runtime;

template<class F> void Runtime::visit(RE::NiAVObject* object, F&& f) {
    if (!object) return;
    f(object);
    if (auto* node = object->AsNode()) for (auto& child : node->GetChildren()) if (child) visit(child.get(), f);
}
inline void Runtime::unbind(Entry& entry) {
    entry.audit.invalidate();
    for (auto& surface : entry.surfaces) {
        auto& current = surface.geometry->GetGeometryRuntimeData().shaderProperty;
        // A later writer can replace the property OR mutate coat content in
        // place. Finite per-geometry fade is carried onto rollback separately.
        if (current.get() == surface.own.get() && (!surface.tinted || healthyPrivateTint(surface))) {
            RE::BSTSmartPointer<RE::BSShaderMaterial> restorationMaterial;
            const bool restored = restoreMaterialWithAlpha(current, surface.own, surface.original,
                [&](const auto& donor) {
                    RE::NiPointer<RE::BSShaderProperty> copy{static_cast<RE::BSShaderProperty*>(donor->Clone())};
                    if (copy && copy.get() != donor.get() && copy.get() != surface.own.get() && donor->material)
                        copy->SetMaterial(donor->material, true);
                    if (copy) restorationMaterial.reset(copy->material); // Retain exact post-setup identity witness.
                    return copy;
                }, [&](const auto& copy) { return copy->FinishSetupGeometry(surface.geometry.get()); });
            if (!restored) SKSE::log::warn("CLAW coat rollback: surface={} donor restoration unavailable; private/later binding retained",
                coatAuditQuote(surface.geometry->name.c_str() ? surface.geometry->name.c_str() : ""));
        }
    }
    entry.surfaces.clear(); entry.root.reset(); entry.yielded = false; entry.appliedPattern.clear();
}
inline void Runtime::reset() {
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    entries_.clear(); colourRecords_.clear(); patternRecords_.clear(); automaticRecords_.clear(); rejectedRecords_.clear();
}
inline void Runtime::forget(RE::FormID id) {
    if (auto found = entries_.find(id); found != entries_.end()) { unbind(found->second); entries_.erase(found); }
}
inline void Runtime::restore(RE::Actor* actor) {
    if (!actor) return;
    if (auto found = entries_.find(actor->formID); found != entries_.end()) {
        auto& entry = found->second; unbind(entry);
        const auto* currentRoot = actor->Is3DLoaded() ? actor->Get3D(false) : nullptr;
        if (entry.auditRoot.get() != currentRoot) { entry.auditRoot.reset(); entry.auditGeneration = 0; }
        if (entry.yieldReportedRoot.get() != currentRoot) { entry.yieldReportedRoot.reset(); entry.yieldAudit.invalidate(); }
    }
}
inline std::string_view Runtime::status(RE::FormID id) const {
    const auto found = entries_.find(id);
    return found == entries_.end() ? std::string_view{"human appearance unavailable"} : found->second.status;
}
inline void Runtime::setLibrary(CoatLibrary library, std::filesystem::path dataRoot) {
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    library_ = std::move(library); dataRoot_ = std::move(dataRoot); validatedPatterns_.clear(); policy_ = {}; mapping_.reset();
}
inline void Runtime::setCoatMapping(CoatMapping mapping) {
    mapping.checkMaterials(library_);
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); entry.coatOutput.reset(); }
    mapping_ = std::move(mapping);
}
inline void Runtime::unavailableCoatMapping(std::string reason) {
    // An explicitly requested but invalid mapping must leave the model alone.
    unavailablePolicy(std::move(reason));
    mapping_.emplace();
}
inline Colours Runtime::humanColours(RE::FormID id) const {
    const auto found = entries_.find(id);
    return found == entries_.end() ? Colours{} : found->second.colours;
}
inline void Runtime::setPolicy(std::string_view xml) {
    auto policy = CoatPolicy::parse(xml, library_);
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    policy_ = std::move(policy);
}
inline void Runtime::unavailablePolicy(std::string reason) {
    for (auto& [id, entry] : entries_) { (void)id; unbind(entry); }
    policy_ = CoatPolicy::unavailable(std::move(reason));
}
inline Runtime::Entry* Runtime::entryFor(RE::Actor* actor) {
    if (!actor || !actor->GetActorBase()) return nullptr;
    auto* base = actor->GetActorBase();
    if (!actor->formID || !base->formID || rejectedRecords_.contains(actor->formID)) return nullptr;
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
    if (!knowsPattern(id)) return false;
    auto* entry = entryFor(actor); if (!entry) return false;
    validatedPatterns_.erase(mapping_ ? std::string(mapping_->material(id)) : id);
    unbind(*entry); entry->explicitPattern = std::move(id); entry->status = "coat selection pending"; return true;
}
inline void Runtime::clearPattern(RE::Actor* actor) {
    if (!actor) return;
    if (auto found = entries_.find(actor->formID); found != entries_.end()) {
        unbind(found->second); found->second.explicitPattern.clear();
        // Clear only the manual layer. Keep both automatic caches, seed and
        // genuine source availability, including for a source-less born wolf.
    }
}
inline CoatDecision Runtime::decision(const Entry& entry) const {
    if (mapping_) return mapping_->select(entry.explicitPattern, entry.coatOutput, entry.colours.hasHair);
    return policy_.select(library_, entry.explicitPattern,
        entry.colours.hasHair ? std::optional{entry.colours.hair} : std::nullopt,
        entry.automatic.seed, entry.automatic);
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
    const auto selected = decision(entry);
    const std::string origin = selected.origin == CoatOrigin::manual ? "explicit" :
        selected.origin == CoatOrigin::hairPool ? "automatic hair pool " + selected.pool :
        selected.origin == CoatOrigin::legacyHair ? "automatic legacy hair" :
        selected.origin == CoatOrigin::fallback ? "automatic fallback pool " + selected.pool : "no automatic pattern";
    return origin + (mapping_ || policy_.tintMode() == TintMode::original ? " [original]: " : " [linked]: ") + entry.status;
}
inline std::uint64_t Runtime::auditClock() {
    return static_cast<std::uint64_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}
inline std::uint64_t Runtime::beginSurfaceAudit(RE::FormID id) {
    const auto found = entries_.find(id);
    if (found == entries_.end() || nextAuditRequest_ == std::numeric_limits<std::uint64_t>::max()) return 0;
    const auto token = nextAuditRequest_++;
    return found->second.audit.begin(token) ? token : 0;
}
inline void Runtime::invalidateSurfaceAudit(RE::FormID id) {
    if (auto found = entries_.find(id); found != entries_.end()) found->second.audit.invalidate();
}
inline void Runtime::cancelSurfaceAudit(RE::FormID id, std::uint64_t token) {
    if (auto found = entries_.find(id); found != entries_.end()) found->second.audit.cancel(token);
}
inline std::string Runtime::surfaceAudit(RE::FormID id) const {
    const auto found = entries_.find(id);
    return found == entries_.end() ? std::string{} : found->second.audit.read(auditClock());
}
inline bool Runtime::sampleSurfaceAudit(RE::Actor* actor, std::uint64_t token) {
    if (!actor) return false;
    const auto found = entries_.find(actor->formID);
    return found != entries_.end() && sampleSurfaceAudit(actor, token, found->second.audit);
}
inline bool Runtime::sampleSurfaceAudit(RE::Actor* actor, std::uint64_t token, CoatSurfaceAuditCache& cache) {
    // Called only after Distribution validates its pinned actor/runtime/world.
    // The private diagnostic destination cannot publish/cancel a public request.
    if (!actor) return false;
    const auto found = entries_.find(actor->formID);
    if (found == entries_.end() || !cache.pending(token)) return false;
    auto& entry = found->second;
    const auto fail = [&] { cache.cancel(token); return false; };
    RE::NiPointer<RE::NiAVObject> root{actor->Is3DLoaded() ? actor->Get3D(false) : nullptr};
    if (!root || !actor->GetActorBase() || entry.base != actor->GetActorBase()->formID ||
        entry.sex != static_cast<std::uint32_t>(actor->GetActorBase()->GetSex())) return fail();
    if (entry.auditRoot.get() != root.get() || !entry.auditGeneration) {
        if (nextAuditGeneration_ == std::numeric_limits<std::uint64_t>::max()) return fail();
        entry.auditRoot = root; entry.auditGeneration = nextAuditGeneration_++;
    }
    const auto text = [](const char* value, std::size_t limit) -> std::optional<std::string> {
        if (!value) return std::nullopt;
        std::size_t length{}; while (length <= limit && value[length]) ++length;
        if (length > limit) return std::nullopt;
        return std::string(value, length);
    };
    std::vector<CoatSurfaceObservation> rows;
    std::vector<RE::NiAVObject*> objects{root.get()};
    std::size_t visited{};
    while (!objects.empty()) {
        auto* object = objects.back(); objects.pop_back();
        if (++visited > coatAuditMaxObjects) return fail();
        if (auto* node = object->AsNode()) for (const auto& child : node->GetChildren()) if (child) {
            if (objects.size() >= coatAuditMaxObjects) return fail();
            objects.push_back(child.get());
        }
        auto* geometry = object->AsGeometry(); if (!geometry) continue;
        if (rows.size() >= coatAuditMaxSurfaces) return fail();
        CoatSurfaceObservation row;
        const auto name = text(object->name.c_str() ? object->name.c_str() : "", coatAuditMaxName);
        if (!name) return fail();
        row.name = *name;
        row.managed = std::any_of(coatSurfaces.begin(), coatSurfaces.end(), [object](const auto& spec) {
            return object->name == RE::BSFixedString{spec.name.data()};
        });
        const auto lease = std::find_if(entry.surfaces.begin(), entry.surfaces.end(), [geometry](const auto& surface) {
            return surface.geometry.get() == geometry;
        });
        row.tracked = lease != entry.surfaces.end();
        if (row.tracked && lease->original) {
            row.originalPropertyAlpha = lease->original->alpha;
            row.originalShaderFlags = lease->original->flags.underlying();
        }
        auto* property = geometry->GetGeometryRuntimeData().shaderProperty.get();
        if (property) {
            row.propertyAlpha = property->alpha; row.shaderFlags = property->flags.underlying();
            row.hasFadeNode = property->fadeNode != nullptr;
            if (row.tracked && lease->original) {
                row.originalHasFadeNode = lease->original->fadeNode != nullptr;
                row.sameFadeNode = property->fadeNode == lease->original->fadeNode;
            }
            const auto* extra = property->GetExtraData("NO_TINT");
            const auto* boolean = netimmerse_cast<RE::NiBooleanExtraData*>(extra);
            row.noTint = boolean ? (boolean->data ? 2 : 1) : extra ? 3 : 0;
            if (const auto* material = property->material) {
                row.materialType = static_cast<std::int32_t>(material->GetType());
                row.feature = static_cast<std::int32_t>(material->GetFeature());
                if (material->GetType() == RE::BSShaderMaterial::Type::kLighting) {
                    const auto* lighting = static_cast<const RE::BSLightingShaderMaterialBase*>(material);
                    row.materialAlpha = lighting->materialAlpha;
                    if (lighting->textureSet) {
                        const auto* path = lighting->textureSet->GetTexturePath(RE::BSTextureSet::Texture::kDiffuse);
                        if (path) { row.diffusePath = text(path, coatAuditMaxPath); if (!row.diffusePath) return fail(); }
                    }
                    if (lighting->diffuseTexture) {
                        row.diffuseResource = text(lighting->diffuseTexture->name.c_str() ? lighting->diffuseTexture->name.c_str() : "", coatAuditMaxPath);
                        if (!row.diffuseResource) return fail();
                    }
                    if (material->GetFeature() == RE::BSShaderMaterial::Feature::kFaceGenRGBTint) {
                        const auto& rgb = static_cast<const RE::BSLightingShaderMaterialFacegenTint*>(material)->tintColor;
                        row.tint = RGB{rgb.red, rgb.green, rgb.blue};
                    } else if (material->GetFeature() == RE::BSShaderMaterial::Feature::kHairTint) {
                        const auto& rgb = static_cast<const RE::BSLightingShaderMaterialHairTint*>(material)->tintColor;
                        row.tint = RGB{rgb.red, rgb.green, rgb.blue};
                    }
                }
            }
            if (row.tracked) {
                row.ownProperty = property == lease->own.get();
                row.ownMaterial = lease->material && property->material == lease->material.get();
                row.ownGuard = lease->guard && extra == lease->guard.get();
                if (property->material && property->material->GetType() == RE::BSShaderMaterial::Type::kLighting) {
                    const auto* material = static_cast<const RE::BSLightingShaderMaterialBase*>(property->material);
                    row.ownTextureSet = lease->textureSet && material->textureSet.get() == lease->textureSet.get();
                    row.ownDiffuse = lease->diffuseTexture && material->diffuseTexture.get() == lease->diffuseTexture.get();
                }
                row.healthyLease = row.ownProperty && healthyPrivateTint(*lease);
            }
        }
        rows.push_back(std::move(row));
    }
    // No apply/refresh/SKEE call occurs during this observation.
    return cache.publish(token, entry.auditGeneration, auditClock(), entry.root.get() == root.get(), rows);
}
inline std::string Runtime::texturePath(RE::BSTextureSet* set, RE::BSTextureSet::Texture slot) {
    const auto* value = set ? set->GetTexturePath(slot) : nullptr; return value ? value : "";
}
inline const Runtime::PatternAssets& Runtime::validatePattern(const std::string& key, const CoatPattern& pattern) {
    const auto [found, inserted] = validatedPatterns_.try_emplace(key);
    auto& result = found->second;
    if (!inserted) return result;
    if (dataRoot_.empty()) return result;
    const auto dimensions = coatPatternDimensions(pattern, [&](const CoatTexture& texture) -> std::optional<CoatDDSInfo> {
        const auto path = dataRoot_ / std::filesystem::path(texture.path);
        std::error_code ec;
        const auto bytes = std::filesystem::file_size(path, ec);
        if (ec) return std::nullopt;
        std::ifstream input(path, std::ios::binary); std::array<char, 148> header{};
        input.read(header.data(), header.size());
        return coatDDSMatches(bytes, std::span(header).first(static_cast<std::size_t>(input.gcount())));
    });
    if (!dimensions) return result;
    result.dimensions = *dimensions;
    result.valid = true;
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
    if (!source->rendererTexture || !source->rendererTexture->resourceView)
        return fail("engine texture has no renderer resource view");
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
        if (keep(it->first, it->second.automatic.identity, it->second.automatic.seed)) ++it;
        else { unbind(it->second); rejectedRecords_.insert(it->first); it = entries_.erase(it); }
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
inline std::string_view Runtime::prepareMaterial(RE::BSShaderProperty* copy,
    const RE::BSShaderProperty* original, std::optional<std::uint32_t> tint) {
    using Base = RE::BSLightingShaderMaterialBase;
    using Feature = RE::BSShaderMaterial::Feature;
    // Original coat colours need no tint material. The engine updates all
    // FaceGenRGBTint/HairTint materials during actor appearance refresh, even
    // when NO_TINT is present. A neutral tint is therefore not an untinted coat.
    const auto feature = !tint ? Feature::kDefault :
        original->material->GetFeature() == Feature::kHairTint ? Feature::kHairTint : Feature::kFaceGenRGBTint;
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
    copy->SetFlags(RE::BSShaderProperty::EShaderPropertyFlag8::kFace, false);
    copy->SetFlags(RE::BSShaderProperty::EShaderPropertyFlag8::kHairTint, feature == Feature::kHairTint);
    copy->SetFlags(RE::BSShaderProperty::EShaderPropertyFlag8::kFaceGenRGBTint, feature == Feature::kFaceGenRGBTint);
    if (feature == Feature::kHairTint) {
        const auto rgb = unpack(*tint);
        static_cast<RE::BSLightingShaderMaterialHairTint*>(temporary.get())->tintColor = {rgb[0], rgb[1], rgb[2]};
    } else if (feature == Feature::kFaceGenRGBTint) {
        const auto rgb = unpack(*tint);
        static_cast<RE::BSLightingShaderMaterialFacegenTint*>(temporary.get())->tintColor = {rgb[0], rgb[1], rgb[2]};
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
    return inspectPrivateTint(surface, nullptr);
}
inline bool Runtime::inspectPrivateTint(const Surface& surface, std::vector<MaterialLeaseDifference>* differences) {
    const auto fail = [&](std::string_view field, const auto& expected, const auto& observed) {
        if (differences) differences->push_back({std::string(field), materialLeaseDiagnosticValue(expected), materialLeaseDiagnosticValue(observed)});
        return false;
    };
    if (!surface.own || !surface.original || !surface.own->material)
        return fail("privateSurface", "retained private/original property and material", "unavailable");
    if (surface.own->material == surface.original->material)
        return fail("materialIsolation", "private material distinct from donor", "aliases donor material");
    if (!std::isfinite(surface.own->alpha)) return fail("propertyAlpha", "finite live fade", surface.own->alpha);
    const auto* material = surface.own->material;
    const auto* guardData = surface.own->GetExtraData("NO_TINT");
    // Preserve identity-first validation: diagnostics never dereference an old
    // replaced witness or reclassify its current owner's material as our lease.
    if (surface.tinted && material != surface.material.get())
        return fail("materialIdentity", reinterpret_cast<std::uintptr_t>(surface.material.get()),
            reinterpret_cast<std::uintptr_t>(material));
    if (surface.tinted && guardData != surface.guard.get())
        return fail("guardIdentity", reinterpret_cast<std::uintptr_t>(surface.guard.get()),
            reinterpret_cast<std::uintptr_t>(guardData));
    if (material->GetType() != RE::BSShaderMaterial::Type::kLighting)
        return fail("materialType", "lighting", static_cast<std::int32_t>(material->GetType()));
    if (!surface.initializedFeature || static_cast<std::int32_t>(material->GetFeature()) != *surface.initializedFeature)
        return fail("feature", surface.initializedFeature.value_or(-1), static_cast<std::int32_t>(material->GetFeature()));
    if (surface.tinted) {
        if (!surface.materialLease) return fail("materialLease", "initialized retained witness", "unavailable");
        const auto current = materialLeaseState(*surface.own);
        if (!mayRestoreMaterial(*surface.materialLease, current)) {
            if (differences) *differences = materialLeaseDifferences(*surface.materialLease, current);
            return false;
        }
    }
    const auto* guard = netimmerse_cast<RE::NiBooleanExtraData*>(guardData);
    if (!guard || !guard->data) return fail("noTint", "true boolean", guard ? "false boolean" : "missing/nonboolean");
    const auto actual = observedTint(material);
    if (surface.expectedTint ? !actual : material->GetFeature() != RE::BSShaderMaterial::Feature::kDefault)
        return fail("feature", surface.expectedTint ? "tint material" : "original-colour default material",
            static_cast<std::int32_t>(material->GetFeature()));
    if (surface.tinted && static_cast<const RE::BSLightingShaderMaterialBase*>(material)->textureSet.get() != surface.textureSet.get())
        return fail("textureSetIdentity", reinterpret_cast<std::uintptr_t>(surface.textureSet.get()),
            reinterpret_cast<std::uintptr_t>(static_cast<const RE::BSLightingShaderMaterialBase*>(material)->textureSet.get()));
    const auto* lighting = static_cast<const RE::BSLightingShaderMaterialBase*>(material);
    if ((surface.tinted || surface.patterned) && lighting->diffuseTexture.get() != surface.diffuseTexture.get())
        return fail("diffuseTextureIdentity", reinterpret_cast<std::uintptr_t>(surface.diffuseTexture.get()),
            reinterpret_cast<std::uintptr_t>(lighting->diffuseTexture.get()));
    if (surface.patterned) {
        if (lighting->textureSet.get() != surface.textureSet.get())
            return fail("textureSetIdentity", reinterpret_cast<std::uintptr_t>(surface.textureSet.get()),
                reinterpret_cast<std::uintptr_t>(lighting->textureSet.get()));
        for (std::uint32_t i = 0; i < RE::BSTextureSet::Texture::kTotal; ++i) {
            const auto current = texturePath(lighting->textureSet.get(), static_cast<RE::BSTextureSet::Texture>(i));
            if (current != surface.texturePaths[i]) {
                if (differences) fail("texturePath[" + std::to_string(i) + ']',
                    surface.texturePaths[i].substr(0, coatAuditMaxPath) + (surface.texturePaths[i].size() > coatAuditMaxPath ? " [truncated]" : ""),
                    current.substr(0, coatAuditMaxPath) + (current.size() > coatAuditMaxPath ? " [truncated]" : ""));
                return false;
            }
        }
    }
    if (surface.expectedTint && !matchesPackedTint(*actual, *surface.expectedTint)) {
        if (differences) for (unsigned i = 0; i < 3; ++i)
            differences->push_back({"tint[" + std::to_string(i) + ']',
                materialLeaseDiagnosticValue(surface.initializedTint ? (*surface.initializedTint)[i] : unpack(*surface.expectedTint)[i]),
                materialLeaseDiagnosticValue((*actual)[i])});
        return false;
    }
    return true;
}
inline MaterialLeaseState Runtime::materialLeaseState(const RE::BSShaderProperty& property) {
    // The caller has already validated this private lighting/tint material.
    const auto& material = *static_cast<const RE::BSLightingShaderMaterialBase*>(property.material);
    MaterialLeaseState result;
    for (unsigned i = 0; i != 2; ++i) {
        result.uvOffset[i * 2] = material.texCoordOffset[i].x;
        result.uvOffset[i * 2 + 1] = material.texCoordOffset[i].y;
        result.uvScale[i * 2] = material.texCoordScale[i].x;
        result.uvScale[i * 2 + 1] = material.texCoordScale[i].y;
    }
    result.specularColour = {material.specularColor.red, material.specularColor.green, material.specularColor.blue};
    result.materialAlpha = material.materialAlpha; result.refractionPower = material.refractionPower;
    result.specularPower = material.specularPower; result.specularScale = material.specularColorScale;
    result.subSurfaceRolloff = material.subSurfaceLightRolloff; result.rimPower = material.rimLightPower;
    result.propertyAlpha = property.alpha; result.flags = property.flags.underlying();
    result.diffuseTarget = material.diffuseRenderTargetSourceIndex; result.clampMode = material.textureClampMode;
    result.textures = {reinterpret_cast<std::uintptr_t>(material.diffuseTexture.get()),
        reinterpret_cast<std::uintptr_t>(material.normalTexture.get()),
        reinterpret_cast<std::uintptr_t>(material.rimSoftLightingTexture.get()),
        reinterpret_cast<std::uintptr_t>(material.specularBackLightingTexture.get())};
    result.textureSet = reinterpret_cast<std::uintptr_t>(material.textureSet.get());
    result.effectData = reinterpret_cast<std::uintptr_t>(property.effectData.get());
    return result;
}
inline std::optional<RGB> Runtime::observedTint(const RE::BSShaderMaterial* material) {
    if (!material || material->GetType() != RE::BSShaderMaterial::Type::kLighting) return {};
    if (material->GetFeature() == RE::BSShaderMaterial::Feature::kFaceGenRGBTint) {
        const auto& rgb = static_cast<const RE::BSLightingShaderMaterialFacegenTint*>(material)->tintColor;
        return RGB{rgb.red, rgb.green, rgb.blue};
    }
    if (material->GetFeature() == RE::BSShaderMaterial::Feature::kHairTint) {
        const auto& rgb = static_cast<const RE::BSLightingShaderMaterialHairTint*>(material)->tintColor;
        return RGB{rgb.red, rgb.green, rgb.blue};
    }
    return {};
}
inline void Runtime::reportYieldDifferences(RE::FormID actor, const Entry& entry, const std::vector<SurfaceLeaseFailure>& failures) {
    // These plain differences were captured by the actual failed predicate,
    // before cleanup and without a second later read of the changed fields.
    SKSE::log::warn("CLAW coat lease {:08X}: first yield root={} failedSurfaces={}; writer unobserved",
        actor, static_cast<const void*>(entry.root.get()), failures.size());
    for (const auto& failure : failures) for (const auto& difference : failure.differences)
        SKSE::log::warn("CLAW coat lease {:08X}: surface={} field={} expected={} observed={}",
            actor, coatAuditQuote(failure.name), difference.field, coatAuditQuote(difference.expected), coatAuditQuote(difference.observed));
}
inline bool Runtime::applyWolf(RE::Actor* actor, IOverrideInterface* provider,
    std::uint64_t saveNamespace, std::uint64_t identity, std::optional<float> coatOutput) {
    if (!actor || !actor->GetActorBase() || (!mapping_ && !provider)) return false;
    if (!saveNamespace || !identity) return false;
    auto found = entries_.find(actor->formID);
    auto* owned = found == entries_.end() ? entryFor(actor) : &found->second;
    if (!owned) return false;
    auto& entry = *owned;
    const auto seed = coatSeed(saveNamespace, identity);
    if (entry.automatic.identity && (entry.automatic.identity != identity || entry.automatic.seed != seed)) {
        unbind(entry); entry.status = "saved automatic coat identity mismatch"; return false;
    }
    entry.automatic.identity = identity; entry.automatic.seed = seed;
    auto* base = actor->GetActorBase();
    if (entry.base != base->formID || entry.sex != static_cast<std::uint32_t>(base->GetSex()) ||
        (!entry.loaded && entry.handle.get().get() != actor) || !valid(entry.colours)) {
        unbind(entry); entry.status = "source identity unavailable"; return false;
    }
    if (entry.loaded) { entry.handle = actor->GetHandle(); entry.loaded = false; }
    auto* root = actor->Get3D(false);
    if (entry.yieldReportedRoot && entry.yieldReportedRoot.get() != root) {
        entry.yieldReportedRoot.reset(); entry.yieldAudit.invalidate();
    }
    if (entry.auditRoot && entry.auditRoot.get() != root) {
        entry.audit.invalidate(); entry.auditRoot.reset(); entry.auditGeneration = 0;
    }
    if (!root) { unbind(entry); entry.status = "unloaded"; return false; }
    entry.coatOutput = coatOutput;
    const auto selectedChoice = decision(entry);
    if (selectedChoice.origin == CoatOrigin::hairPool && !selectedChoice.pattern.empty())
        entry.automatic.hair = {selectedChoice.pool, selectedChoice.pattern};
    if (selectedChoice.origin == CoatOrigin::fallback && !selectedChoice.pattern.empty())
        entry.automatic.fallback = {selectedChoice.pool, selectedChoice.pattern};
    const auto requestedPattern = entry.explicitPattern.empty() ? selectedChoice.pattern : entry.explicitPattern;
    const auto resource = mapping_ ? mapping_->material(selectedChoice.pattern) : std::string_view(selectedChoice.pattern);
    if (mapping_ && (resource.empty() || resource == installedCoatMaterial)) {
        if (!entry.surfaces.empty()) unbind(entry);
        if (resource == installedCoatMaterial && entry.root.get() == root && entry.attemptedPattern == selectedChoice.pattern)
            return true;
        entry.root.reset(root);
        entry.attemptedPattern = selectedChoice.pattern;
        entry.appliedPattern.clear(); // Public getter describes an actually bound private material.
        entry.status = resource.empty() ? selectedChoice.reason :
            "logical coat " + selectedChoice.pattern + "; installed model material retained";
        return !resource.empty();
    }
    const auto mode = mapping_ ? TintMode::original : policy_.tintMode();
    if (root == entry.root.get() && entry.attemptedPattern == requestedPattern && entry.attemptedMode == mode && !entry.surfaces.empty()) {
        const bool stillInScene = std::all_of(entry.surfaces.begin(), entry.surfaces.end(), [root](const auto& surface) {
            return root->GetObjectByName(surface.geometry->name) == surface.geometry.get();
        });
        const bool firstReport = entry.yieldReportedRoot.get() != root;
        std::vector<SurfaceLeaseFailure> failures;
        bool stillTinted = true;
        if (firstReport && stillInScene) {
            for (const auto& surface : entry.surfaces) {
                std::vector<MaterialLeaseDifference> differences;
                const auto* current = surface.geometry->GetGeometryRuntimeData().shaderProperty.get();
                bool healthy = current == surface.own.get();
                if (!healthy) differences.push_back({"propertyIdentity",
                    materialLeaseDiagnosticValue(reinterpret_cast<std::uintptr_t>(surface.own.get())),
                    materialLeaseDiagnosticValue(reinterpret_cast<std::uintptr_t>(current))});
                else healthy = inspectPrivateTint(surface, &differences);
                if (!healthy) {
                    stillTinted = false;
                    const auto* name = surface.geometry->name.c_str();
                    failures.push_back({std::string(name ? name : "").substr(0, coatAuditMaxName), std::move(differences)});
                }
            }
        } else {
            const bool stillOwned = std::all_of(entry.surfaces.begin(), entry.surfaces.end(), [](const auto& surface) {
                return surface.geometry->GetGeometryRuntimeData().shaderProperty.get() == surface.own.get();
            });
            stillTinted = stillOwned && std::all_of(entry.surfaces.begin(), entry.surfaces.end(), healthyPrivateTint);
        }
        if (stillInScene && stillTinted) return true;
        // A later provider wins until model generation changes; no override war.
        if (stillInScene) {
            if (firstReport) { entry.yieldReportedRoot.reset(root); reportYieldDifferences(actor->formID, entry, failures); }
            unbind(entry); entry.root.reset(root); entry.yielded = true; entry.status = "yielded to later coat writer";
            if (firstReport) {
                // Observe AFTER cleanup into a separate plain cache. Do not
                // alter public request tokens or re-publish known-stale leases.
                entry.yieldAudit.invalidate();
                const auto token = nextAuditRequest_ == std::numeric_limits<std::uint64_t>::max() ? 0 : nextAuditRequest_++;
                const bool sampled = token && entry.yieldAudit.begin(token) && sampleSurfaceAudit(actor, token, entry.yieldAudit);
                const auto payload = sampled ? entry.yieldAudit.read(auditClock()) : std::string{};
                SKSE::log::warn("CLAW coat lease {:08X}: post-yield diagnostic cached audit available={} payload={}",
                    actor->formID, !payload.empty(), payload.empty() ? "unavailable" : payload);
            }
            return false;
        }
    }
    if (root == entry.root.get() && entry.yielded) return false;
    if (root == entry.root.get() && entry.attemptedPattern == requestedPattern && entry.attemptedMode == mode && entry.surfaces.empty()) return false;
    unbind(entry);
    std::vector<Surface> prepared;
    const auto* selected = library_.find(resource);
    std::string patternFailure = !requestedPattern.empty() && !selected ? "library or pattern unavailable" : "";
    const PatternAssets* assets{};
    if (selected) {
        assets = &validatePattern(std::string(resource), *selected);
        if (!assets->valid) { selected = nullptr; patternFailure = "DDS missing or header/size mismatch"; }
    }
    // Resource failure is resolved before any live binding. A human retains the
    // already-working tint, and a source-less born wolf retains its donor.
    for (unsigned attempt = 0; attempt < 2; ++attempt) {
    prepared.clear(); bool retryWithoutPattern{};
    for (const auto& surfaceSpec : coatSurfaces) {
        const auto name = surfaceSpec.name;
        const bool skin = name == "body" || name == "head";
        const bool hasColour = mode == TintMode::linked && (skin ? entry.colours.hasSkin : entry.colours.hasHair);
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
        // Keep the legacy linked mode's neutral fallback when a colour is
        // unavailable; original/discrete coats deliberately have no tint.
        const std::optional<std::uint32_t> tint = mode == TintMode::original ? std::nullopt :
            std::optional{hasColour ? pack(coatTint(skin ? entry.colours.skin : entry.colours.hair, !skin)) : 0xFFFFFFU};
        if (const auto failure = prepareMaterial(copy.get(), original, tint); !failure.empty()) return isolationFailure(failure);
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
        staged.initializedFeature = static_cast<std::int32_t>(material->GetFeature());
        staged.patterned = selected != nullptr; staged.diffuseTexture = material->diffuseTexture;
        if (selected) {
            staged.textureSet = material->textureSet;
            for (std::uint32_t i = 0; i < RE::BSTextureSet::Texture::kTotal; ++i)
                staged.texturePaths[i] = texturePath(material->textureSet.get(), static_cast<RE::BSTextureSet::Texture>(i));
        }
    }
    if (!retryWithoutPattern) break;
    }
    entry.attemptedPattern = requestedPattern; entry.attemptedMode = mode;
    if (prepared.empty()) {
        entry.root.reset(root); entry.status = patternFailure.empty() ?
            "original material retained; " + selectedChoice.reason : "coat unavailable: " + patternFailure; return false;
    }
    // All surfaces were validated and cloned before any live binding changes.
    entry.surfaces = std::move(prepared); entry.root.reset(root);
    for (auto& surface : entry.surfaces) {
        surface.geometry->GetGeometryRuntimeData().shaderProperty = surface.own;
        // CommonLib's virtual FinishSetupGeometry calls the engine shader
        // initializer on this property; unlike a private relocation it uses the
        // active runtime's own vtable on SE/AE/VR.
        auto& current = surface.geometry->GetGeometryRuntimeData().shaderProperty;
        if (!initializePrivateMaterial(current, surface.own, surface.original, surface.original->alpha,
                [&](const auto& copy) { return copy->FinishSetupGeometry(surface.geometry.get()); }) || !healthyPrivateTint(surface)) {
            unbind(entry); entry.status = "private tint initialization failed"; return false;
        }
        surface.material.reset(surface.own->material);
        surface.guard.reset(netimmerse_cast<RE::NiBooleanExtraData*>(surface.own->GetExtraData("NO_TINT")));
        surface.textureSet = static_cast<RE::BSLightingShaderMaterialBase*>(surface.own->material)->textureSet;
        const auto* accepted = static_cast<RE::BSLightingShaderMaterialBase*>(surface.own->material);
        surface.diffuseTexture = accepted->diffuseTexture;
        surface.otherTextures = {accepted->normalTexture, accepted->rimSoftLightingTexture, accepted->specularBackLightingTexture};
        surface.effectData = surface.own->effectData;
        // Snapshot initialized public state, never pre-initialization scratch
        // values. Retained references make compared pointer identities stable.
        surface.materialLease = materialLeaseState(*surface.own);
        surface.initializedTint = observedTint(surface.own->material);
        surface.tinted = true;
    }
    entry.appliedPattern = selected ? requestedPattern : "";
    entry.status = selected ? "applied private coat " + requestedPattern + " with " +
        (mode == TintMode::linked && (entry.colours.hasSkin || entry.colours.hasHair) ? "skin/fur tint" : "neutral original colours") : "applied private skin/fur tint";
    if (!patternFailure.empty()) entry.status += "; coat unavailable: " + patternFailure;
    SKSE::log::info("CLAW appearance {:08X}: {} ({} surfaces; hair source {})", actor->formID, entry.status,
        entry.surfaces.size(), entry.colours.renderedHair ? "rendered" : "record");
    return true;
}
// CCLR/CCPT v1 bytes remain unchanged. Additive CCAS stores the stable saved
// reference seed and actual automatic choices, never renderer pointers or RGB
// invented for actors without an observed human source.
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
        if (entry.automatic.identity && entry.automatic.seed) {
            const auto data = writeAutomaticCoat({id, entry.base, entry.sex, entry.automatic});
            if (!serial->WriteRecord(automaticRecord, 1, data.data(), static_cast<std::uint32_t>(data.size())))
                SKSE::log::error("CLAW actor {:08X}: CCAS automatic coat serialization failed", id);
        }
    }
}
inline bool Runtime::loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length) {
    if (type != record && type != patternRecord && type != automaticRecord) return false;
    std::array<std::uint32_t, 6> data{}; std::string choice; AutomaticCoatState automatic;
    if (version != 1) { SKSE::log::warn("CLAW appearance: unsupported record version"); return true; }
    if (type == record) {
        if (length != sizeof(data) || serial->ReadRecordData(data.data(), sizeof(data)) != sizeof(data)) {
            SKSE::log::warn("CLAW appearance: invalid CCLR record"); return true;
        }
        if (data[3] > 7 || data[4] > 0xFFFFFF || data[5] > 0xFFFFFF) return true;
    } else if (type == patternRecord) {
        if (length <= 16 || length > 145) { SKSE::log::warn("CLAW appearance: invalid CCPT record length"); return true; }
        std::vector<char> bytes(length);
        if (serial->ReadRecordData(bytes.data(), length) != length) { SKSE::log::warn("CLAW appearance: truncated CCPT record"); return true; }
        try {
            const auto selection = readCoatSelection(bytes);
            data[0] = selection.actor; data[1] = selection.base; data[2] = selection.sex; choice = selection.pattern;
        } catch (const std::exception& error) {
            SKSE::log::warn("CLAW appearance: invalid CCPT record: {}", error.what()); return true;
        }
    } else {
        if (length < 44 || length > 430) { SKSE::log::warn("CLAW appearance: invalid CCAS record length"); return true; }
        std::vector<char> bytes(length);
        if (serial->ReadRecordData(bytes.data(), length) != length) { SKSE::log::warn("CLAW appearance: truncated CCAS record"); return true; }
        try {
            const auto selection = readAutomaticCoat(bytes);
            data[0] = selection.actor; data[1] = selection.base; data[2] = selection.sex; automatic = selection.automatic;
        } catch (const std::exception& error) {
            SKSE::log::warn("CLAW appearance: invalid CCAS record: {}", error.what()); return true;
        }
    }
    RE::FormID actor{}, base{};
    if (!serial->ResolveFormID(data[0], actor) || !serial->ResolveFormID(data[1], base) || !actor || !base || data[2] > 1 ||
        rejectedRecords_.contains(actor)) return true;
    auto& seen = type == record ? colourRecords_ : type == patternRecord ? patternRecords_ : automaticRecords_;
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
    } else if (type == patternRecord) entry.explicitPattern = std::move(choice);
    else entry.automatic = std::move(automatic);
    return true;
}
}
