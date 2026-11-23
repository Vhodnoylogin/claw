#pragma once

#include "claw/MaterialLease.h"
#include "claw/PhysicsContactRoute.h"
#include "claw/TargetModelAvailability.h"
#include <RE/Skyrim.h>

namespace claw {

// Both coat and contact use the same equipped world clone. The outfit remains
// eligible for its coat when optional physics support is not built or enabled.
inline bool isEquippedPlayerWolfBody(RE::Actor* actor, const RE::BipedAnim& biped, bool female) {
    const auto& body = biped.objects[RE::BIPED_OBJECTS::kBody];
    if (actor != RE::PlayerCharacter::GetSingleton() || !body.item || !body.addon ||
        (body.item->GetFormID() & 0xFFFFFF) != equippedContactItem) return false;

    constexpr auto plugin = equippedContactPlugin.data();
    auto* data = RE::TESDataHandler::GetSingleton();
    if (!data) return false;
    const auto* file = data->LookupModByName(plugin);
    const auto* item = data->LookupForm<RE::TESObjectARMO>(equippedContactItem, plugin);
    const auto* addon = data->LookupForm<RE::TESObjectARMA>(equippedContactAddon, plugin);
    if (!file || !item || !addon || item->GetFile(0) != file || addon->GetFile(0) != file ||
        item->armorAddons.size() != 1 || item->armorAddons[0] != addon) return false;

    const auto& buffered = biped.bufferedObjects[RE::BIPED_OBJECTS::kBody];
    const auto* bufferedPath = buffered.part ? buffered.part->GetModel() : nullptr;
    const bool bufferedEmpty = !buffered.item && !buffered.addon && !buffered.partClone &&
        (!bufferedPath || !*bufferedPath) && !buffered.partHandle;
    const auto* path = body.part ? body.part->GetModel() : nullptr;
    return contactRoute({body.item->GetFormID(), body.addon->GetFormID()},
        ContactArmorForms{item->GetFormID(), addon->GetFormID()}, true, bufferedEmpty,
        path ? std::string_view{path} : std::string_view{}, female) == PhysicsContactRoute::equipped;
}

struct EquippedWolfGeometry {
    RE::BSGeometry* ear{};
    RE::NiAVObject* marker{};
};

inline std::optional<EquippedWolfGeometry> observeEquippedWolfGeometry(RE::NiAVObject& clone, bool female) {
    EquippedWolfGeometry result;
    const auto probe = collectTargetModel(&clone, [&](RE::NiAVObject* object) {
        auto* geometry = object->AsGeometry();
        const auto* raw = object->name.c_str();
        const std::string_view name = raw ? std::string_view{raw} : std::string_view{};
        if (name == equippedEarShape) {
            result.ear = geometry;
            return TargetModelObject{geometry != nullptr, 0};
        }
        if (name.starts_with(dispatchMarkerPrefix)) {
            result.marker = object;
            return TargetModelObject{geometry != nullptr, 1};
        }
        return TargetModelObject{geometry != nullptr};
    }, [](RE::NiAVObject* object, auto&& push) {
        if (const auto* node = object->AsNode()) for (const auto& child : node->GetChildren())
            if (!push(child.get())) return false;
        return true;
    });
    const auto* marker = result.marker ? result.marker->AsNode() : nullptr;
    if (probe.collection != TargetModelCollection::complete || probe.roleObjects[0] != 1 || !result.ear ||
        probe.roleObjects[1] != 1 || !marker || marker == &clone || !marker->GetChildren().empty() ||
        std::string_view(marker->name.c_str()) != equippedWorldMarker(female) ||
        !appearance::isMaterialGeometryAttached(result.marker, &clone, 48) ||
        !appearance::isMaterialGeometryAttached(static_cast<RE::NiAVObject*>(result.ear), &clone, 48)) return std::nullopt;
    return result;
}

} // namespace claw
