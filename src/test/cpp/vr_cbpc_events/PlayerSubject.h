#pragma once

#include <RE/Skyrim.h>
#include <cstdint>
#include "Window.h"
#include "claw/PhysicsContactRoute.h"

namespace cbpc {
struct PlayerIdentity {
    RE::FormID base{};
    claw::ContactArmorForms forms;
    std::uint32_t handle{};
    bool female{};
    std::uintptr_t sender{}, root{}, clone{};
    bool operator==(const PlayerIdentity&) const = default;
};

inline bool attachedTo(const RE::NiAVObject* object, const RE::NiAVObject* root) {
    for (unsigned depth = 0; object && depth < 48; ++depth) {
        if (object == root) return true;
        const auto* parent = object->parent;
        if (!parent || std::ranges::none_of(parent->GetChildren(),
                [object](const auto& child) { return child.get() == object; })) return false;
        object = parent;
    }
    return false;
}

inline PlayerIdentity equippedPlayer(Key key) {
    auto* ui = RE::UI::GetSingleton();
    auto* player = RE::PlayerCharacter::GetSingleton();
    if (!ui || ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) || ui->IsMenuOpen(RE::MainMenu::MENU_NAME) ||
        !player || key.actor != 0x14 || player->GetFormID() != key.actor || player->IsDisabled() ||
        player->IsDeleted() || !player->Is3DLoaded()) return {};
    auto* cell = player->GetParentCell();
    auto* base = player->GetActorBase();
    auto* race = player->GetRace();
    auto* root = player->Get3D(false);
    const auto biped = player->GetBiped(false);
    if (!cell || cell->GetFormID() != key.cell || !cell->IsAttached() || !base || base->GetFormID() != 7 ||
        !race || race->GetFormID() != 0xCDD84 || !root || !biped || biped->actorRef.get().get() != player) return {};
    const auto sex = base->GetSex();
    if (sex != RE::SEX::kMale && sex != RE::SEX::kFemale) return {};
    const bool female = sex == RE::SEX::kFemale;
    auto* data = RE::TESDataHandler::GetSingleton();
    const auto* file = data ? data->LookupModByName(claw::equippedContactPlugin) : nullptr;
    const auto* item = file ? data->LookupForm<RE::TESObjectARMO>(claw::equippedContactItem, claw::equippedContactPlugin) : nullptr;
    const auto* addon = file ? data->LookupForm<RE::TESObjectARMA>(claw::equippedContactAddon, claw::equippedContactPlugin) : nullptr;
    if (!item || !addon || item->GetFile(0) != file || addon->GetFile(0) != file ||
        item->armorAddons.size() != 1 || item->armorAddons[0] != addon) return {};
    const auto& active = biped->objects[RE::BIPED_OBJECTS::kBody];
    const auto& buffer = biped->bufferedObjects[RE::BIPED_OBJECTS::kBody];
    auto* clone = active.partClone.get();
    if (active.item != item || active.addon != addon || !clone || clone == root || !attachedTo(clone, root)) return {};
    const auto* path = active.part ? active.part->GetModel() : nullptr;
    const auto* bufferedPath = buffer.part ? buffer.part->GetModel() : nullptr;
    const claw::ContactArmorForms forms{item->GetFormID(), addon->GetFormID()};
    const bool bufferedEmpty = !buffer.item && !buffer.addon && !buffer.partClone && !buffer.partHandle &&
        (!bufferedPath || !*bufferedPath);
    if (claw::contactRoute(forms, forms, true, bufferedEmpty, path ? path : "", female) !=
        claw::PhysicsContactRoute::equipped) return {};
    const auto handle = player->GetHandle().native_handle();
    if (!handle) return {};
    return {base->GetFormID(), forms, handle, female, reinterpret_cast<std::uintptr_t>(static_cast<const RE::TESForm*>(player)),
            reinterpret_cast<std::uintptr_t>(root), reinterpret_cast<std::uintptr_t>(clone)};
}
}
