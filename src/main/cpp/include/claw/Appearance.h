#pragma once
#include "claw/ColourMath.h"
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <IPluginInterface.h>
#include <map>
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
        // Retain post-key7 identities: a later replacement cannot recycle an
        // old pointer into a false match while this surface lease is active.
        RE::BSTSmartPointer<RE::BSShaderMaterial> material;
        RE::NiPointer<RE::NiBooleanExtraData> guard;
        RE::NiPointer<RE::BSTextureSet> textureSet;
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
    };
    class TintValue final : public IOverrideInterface::SetVariant {
    public:
        explicit TintValue(std::uint32_t value) : value_(static_cast<skee_i32>(value)) {}
        Type GetType() override { return Type::Int; }
        skee_i32 Int() override { return value_; }
    private:
        skee_i32 value_;
    };
    template<class F> static void visit(RE::NiAVObject* object, F&& f);
    static void unbind(Entry& entry);
    static bool protectPrivateTint(RE::BSShaderProperty* copy, const RE::BSShaderProperty* original);
    static bool healthyPrivateTint(const Surface& surface);
    inline static constexpr std::array<std::string_view, 12> surfaceNames{
        "body", "head", "fur_arms", "fur_back", "fur_belly", "fur_chest",
        "fur_face", "fur_shoulders", "fur_tailtip", "ChestBlend", "FurfaceBlend", "ScalpFurBlend"};
    inline static constexpr std::uint32_t record = 0x524C4343; // CCLR
    std::map<RE::FormID, Entry> entries_;
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
    entry.surfaces.clear(); entry.root.reset(); entry.yielded = false;
}
inline void Runtime::reset() { for (auto& [id, entry] : entries_) unbind(entry); entries_.clear(); }
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
        // RaceMenu's HairTint writer stores linear RGB components scaled by two.
        const auto palette = paletteColour({material->tintColor.red / 2, material->tintColor.green / 2, material->tintColor.blue / 2});
        if (!palette) return;
        const auto& rgb = *palette;
        if (rendered && *rendered != rgb) ambiguous = true;
        else rendered = rgb;
    });
    if (rendered && !ambiguous) { colours.hair = *rendered; colours.hasHair = true; colours.renderedHair = true; }
    if (!entries_.contains(actor->formID) && entries_.size() >= 8192) return;
    auto& entry = entries_[actor->formID];
    if (entry.base != base->formID || entry.sex != static_cast<std::uint32_t>(base->GetSex()) || entry.colours != colours) unbind(entry);
    entry.base = base->formID; entry.sex = static_cast<std::uint32_t>(base->GetSex()); entry.colours = colours;
    entry.handle = actor->GetHandle(); entry.loaded = false;
    entry.status = ambiguous ? "record-hair-fallback: ambiguous rendered hair" : "human colours captured";
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
    if (root == entry.root.get() && !entry.surfaces.empty()) {
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
    unbind(entry);
    std::vector<Surface> prepared;
    for (const auto name : surfaceNames) {
        const bool skin = name == "body" || name == "head";
        if (skin ? !entry.colours.hasSkin : !entry.colours.hasHair) continue;
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
        // A cloned shader property need not own an independent material. Use
        // the engine's unique-material copy operation, as SKEE does, before
        // changing any metadata or exposing the property to the live geometry.
        if (!copy->material || copy->material == original->material) copy->SetMaterial(original->material, true);
        if (!copy->material) return isolationFailure("unique material unavailable");
        if (copy->material == original->material) return isolationFailure("unique material aliases source");
        if (copy->material->GetFeature() != feature) return isolationFailure("unique material changed shader feature");
        if (!protectPrivateTint(copy.get(), original)) { entry.status = "private tint protection failed"; return false; }
        prepared.push_back({RE::NiPointer<RE::BSGeometry>{geometry}, RE::NiPointer<RE::BSShaderProperty>{original}, copy,
            pack(coatTint(skin ? entry.colours.skin : entry.colours.hair, !skin))});
    }
    if (prepared.empty()) { entry.status = "no human colour sources"; return false; }
    // All surfaces were validated and cloned before any live binding changes.
    entry.surfaces = std::move(prepared); entry.root.reset(root);
    for (auto& surface : entry.surfaces) {
        surface.geometry->GetGeometryRuntimeData().shaderProperty = surface.own;
        TintValue tint(surface.expectedTint);
        provider->SetNodeProperty(reinterpret_cast<::TESObjectREFR*>(actor), false, surface.geometry->name.c_str(), 7, 0, tint, true);
        // SKEE may replace the clone's material; property ownership remains ours.
        if (!healthyPrivateTint(surface)) {
            unbind(entry); entry.status = "tint conversion failed"; return false;
        }
        surface.material.reset(surface.own->material);
        surface.guard.reset(netimmerse_cast<RE::NiBooleanExtraData*>(surface.own->GetExtraData("NO_TINT")));
        surface.textureSet = static_cast<RE::BSLightingShaderMaterialBase*>(surface.own->material)->textureSet;
        surface.tinted = true;
    }
    entry.status = "applied private skin/fur tint";
    SKSE::log::info("CLAW appearance {:08X}: {} ({} surfaces; hair source {})", actor->formID, entry.status,
        entry.surfaces.size(), entry.colours.renderedHair ? "rendered" : "record");
    return true;
}
// Separate fixed-size records; no pointers or geometry properties enter saves.
inline void Runtime::save(SKSE::SerializationInterface* serial) const {
    for (const auto& [id, entry] : entries_) {
        if (!valid(entry.colours) || !serial->OpenRecord(record, 1)) continue;
        const std::array<std::uint32_t, 6> data{id, entry.base, entry.sex,
            std::uint32_t(entry.colours.hasSkin) | (std::uint32_t(entry.colours.hasHair) << 1) | (std::uint32_t(entry.colours.renderedHair) << 2),
            pack(entry.colours.skin), pack(entry.colours.hair)};
        serial->WriteRecordData(data.data(), sizeof(data));
    }
}
inline bool Runtime::loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length) {
    if (type != record) return false;
    std::array<std::uint32_t, 6> data{};
    if (version != 1 || length != sizeof(data) || serial->ReadRecordData(data.data(), sizeof(data)) != sizeof(data)) return true;
    RE::FormID actor{}, base{};
    if (!serial->ResolveFormID(data[0], actor) || !serial->ResolveFormID(data[1], base) || data[2] > 1 || data[3] > 7 ||
        data[4] > 0xFFFFFF || data[5] > 0xFFFFFF) return true;
    Entry entry; entry.base = base; entry.sex = data[2]; entry.loaded = true;
    entry.colours = {unpack(data[4]), unpack(data[5]), bool(data[3] & 1), bool(data[3] & 2), bool(data[3] & 4)};
    if (valid(entry.colours) && entries_.size() < 8192 && !entries_.contains(actor)) entries_.emplace(actor, std::move(entry));
    return true;
}
}
