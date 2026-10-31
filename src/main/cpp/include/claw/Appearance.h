#pragma once
#include "claw/ColourMath.h"
#include <RE/Skyrim.h>
#include <SKSE/SKSE.h>
#include <IPluginInterface.h>
#include <map>
#include <string>
#include <vector>

// All entry points are game-thread only, under the Distribution state lock.
// No persistent SKEE overrides, NPC-base writes or shared texture mutations.
namespace claw::appearance {
struct Surface {
    RE::NiPointer<RE::BSGeometry> geometry;
    RE::NiPointer<RE::BSShaderProperty> original, own;
};
struct Entry {
    RE::FormID base{};
    std::uint32_t sex{};
    Colours colours;
    RE::NiPointer<RE::NiAVObject> root; // Retain generation identity; prevents recycled-root pointer aliases.
    RE::ActorHandle handle;
    bool loaded{};
    std::vector<Surface> surfaces;
    std::string status;
};
inline std::map<RE::FormID, Entry> entries;
inline constexpr std::array<std::string_view, 12> surfaces{
    "body", "head", "fur_arms", "fur_back", "fur_belly", "fur_chest",
    "fur_face", "fur_shoulders", "fur_tailtip", "ChestBlend", "FurfaceBlend", "ScalpFurBlend"};
template<class F> void visit(RE::NiAVObject* object, F&& f) {
    if (!object) return;
    f(object);
    if (auto* node = object->AsNode()) for (auto& child : node->GetChildren()) if (child) visit(child.get(), f);
}
inline void unbind(Entry& entry) {
    for (auto& surface : entry.surfaces) {
        auto& current = surface.geometry->GetGeometryRuntimeData().shaderProperty;
        // Cooperate with a later writer: never overwrite somebody else's property.
        if (current.get() == surface.own.get()) current = surface.original;
    }
    entry.surfaces.clear(); entry.root.reset();
}
inline void reset() { for (auto& [id, entry] : entries) unbind(entry); entries.clear(); }
inline void forget(RE::FormID id) {
    if (auto found = entries.find(id); found != entries.end()) { unbind(found->second); entries.erase(found); }
}
inline void restore(RE::Actor* actor) {
    if (!actor) return;
    if (auto found = entries.find(actor->formID); found != entries.end()) unbind(found->second);
}
inline void captureHuman(RE::Actor* actor) {
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
        RGB rgb{material->tintColor.red / 2, material->tintColor.green / 2, material->tintColor.blue / 2};
        if (!valid(rgb)) return;
        if (rendered && *rendered != rgb) ambiguous = true;
        else rendered = rgb;
    });
    if (rendered && !ambiguous) { colours.hair = *rendered; colours.hasHair = true; colours.renderedHair = true; }
    if (!entries.contains(actor->formID) && entries.size() >= 8192) return;
    auto& entry = entries[actor->formID];
    if (entry.base != base->formID || entry.sex != static_cast<std::uint32_t>(base->GetSex()) || entry.colours != colours) unbind(entry);
    entry.base = base->formID; entry.sex = static_cast<std::uint32_t>(base->GetSex()); entry.colours = colours;
    entry.handle = actor->GetHandle(); entry.loaded = false;
    entry.status = ambiguous ? "record-hair-fallback: ambiguous rendered hair" : "human colours captured";
}
class TintValue final : public IOverrideInterface::SetVariant {
public:
    explicit TintValue(std::uint32_t value) : value_(static_cast<skee_i32>(value)) {}
    Type GetType() override { return Type::Int; }
    skee_i32 Int() override { return value_; }
private:
    skee_i32 value_;
};
inline bool applyWolf(RE::Actor* actor, IOverrideInterface* provider) {
    if (!actor || !actor->GetActorBase() || !provider) return false;
    auto found = entries.find(actor->formID);
    if (found == entries.end()) return false; // Born beasts have no fabricated human colours.
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
        const bool stillOwned = std::all_of(entry.surfaces.begin(), entry.surfaces.end(), [](const auto& surface) {
            return surface.geometry->GetGeometryRuntimeData().shaderProperty.get() == surface.own.get();
        });
        if (stillOwned) return true;
        // A later provider wins until model generation changes; no override war.
        unbind(entry); entry.root.reset(root); entry.status = "yielded to later coat writer"; return false;
    }
    if (root == entry.root.get() && entry.status == "yielded to later coat writer") return false;
    unbind(entry);
    std::vector<Surface> prepared;
    for (const auto name : surfaces) {
        const bool skin = name == "body" || name == "head";
        if (skin ? !entry.colours.hasSkin : !entry.colours.hasHair) continue;
        RE::BSGeometry* geometry{}; unsigned count{};
        visit(root, [&](RE::NiAVObject* object) {
            if (object->name.c_str() && name == object->name.c_str()) { ++count; geometry = object->AsGeometry(); }
        });
        if (count != 1 || !geometry) { entry.status = "missing/ambiguous coat surface"; return false; }
        auto* original = geometry->lightingShaderProp_cast();
        if (!original || !original->material) { entry.status = "unsupported coat shader"; return false; }
        const auto feature = original->material->GetFeature();
        if (feature != RE::BSShaderMaterial::Feature::kDefault && feature != RE::BSShaderMaterial::Feature::kFaceGenRGBTint &&
            feature != RE::BSShaderMaterial::Feature::kHairTint) { entry.status = "unsupported coat material"; return false; }
        RE::NiPointer<RE::BSShaderProperty> copy{static_cast<RE::BSShaderProperty*>(original->Clone())};
        if (!copy || copy.get() == original || !copy->material || copy->material == original->material) {
            entry.status = "material isolation failed"; return false;
        }
        prepared.push_back({RE::NiPointer<RE::BSGeometry>{geometry}, RE::NiPointer<RE::BSShaderProperty>{original}, copy});
    }
    if (prepared.empty()) { entry.status = "no human colour sources"; return false; }
    // All surfaces were validated and cloned before any live binding changes.
    entry.surfaces = std::move(prepared); entry.root.reset(root);
    for (auto& surface : entry.surfaces) {
        surface.geometry->GetGeometryRuntimeData().shaderProperty = surface.own;
        const std::string_view name = surface.geometry->name.c_str();
        TintValue tint(pack(coatTint(name == "body" || name == "head" ? entry.colours.skin : entry.colours.hair,
            name != "body" && name != "head")));
        provider->SetNodeProperty(reinterpret_cast<::TESObjectREFR*>(actor), false, surface.geometry->name.c_str(), 7, 0, tint, true);
        // SKEE may replace the clone's material; property ownership remains ours.
        auto* material = surface.own->material;
        if (!material || (material->GetFeature() != RE::BSShaderMaterial::Feature::kFaceGenRGBTint &&
            material->GetFeature() != RE::BSShaderMaterial::Feature::kHairTint)) {
            unbind(entry); entry.status = "tint conversion failed"; return false;
        }
    }
    entry.status = "applied private skin/fur tint";
    SKSE::log::info("CLAW appearance {:08X}: {} ({} surfaces; hair source {})", actor->formID, entry.status,
        entry.surfaces.size(), entry.colours.renderedHair ? "rendered" : "record");
    return true;
}
// Separate fixed-size records; no pointers or geometry properties enter saves.
inline constexpr std::uint32_t record = 0x524C4343; // CCLR
inline void save(SKSE::SerializationInterface* serial) {
    for (const auto& [id, entry] : entries) {
        if (!valid(entry.colours) || !serial->OpenRecord(record, 1)) continue;
        const std::array<std::uint32_t, 6> data{id, entry.base, entry.sex,
            std::uint32_t(entry.colours.hasSkin) | (std::uint32_t(entry.colours.hasHair) << 1) | (std::uint32_t(entry.colours.renderedHair) << 2),
            pack(entry.colours.skin), pack(entry.colours.hair)};
        serial->WriteRecordData(data.data(), sizeof(data));
    }
}
inline bool loadRecord(SKSE::SerializationInterface* serial, std::uint32_t type, std::uint32_t version, std::uint32_t length) {
    if (type != record) return false;
    std::array<std::uint32_t, 6> data{};
    if (version != 1 || length != sizeof(data) || serial->ReadRecordData(data.data(), sizeof(data)) != sizeof(data)) return true;
    RE::FormID actor{}, base{};
    if (!serial->ResolveFormID(data[0], actor) || !serial->ResolveFormID(data[1], base) || data[2] > 1 || data[3] > 7 ||
        data[4] > 0xFFFFFF || data[5] > 0xFFFFFF) return true;
    Entry entry; entry.base = base; entry.sex = data[2]; entry.loaded = true;
    entry.colours = {unpack(data[4]), unpack(data[5]), bool(data[3] & 1), bool(data[3] & 2), bool(data[3] & 4)};
    if (valid(entry.colours) && entries.size() < 8192 && !entries.contains(actor)) entries.emplace(actor, std::move(entry));
    return true;
}
}
