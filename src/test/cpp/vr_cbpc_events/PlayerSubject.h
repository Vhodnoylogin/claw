#pragma once

#include <RE/Skyrim.h>
#include <cstdint>
#include "Window.h"
#include "claw/PhysicsContactRoute.h"
#include "claw/TargetModelAvailability.h"

namespace cbpc {
struct PlayerIdentity {
    RE::FormID base{};
    claw::ContactArmorForms forms;
    std::uint32_t handle{};
    bool female{};
    std::uintptr_t sender{}, root{}, clone{}, ear{};
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

inline RE::PlayerCharacter* ownedWorldPlayer(Key key) {
    auto* ui = RE::UI::GetSingleton();
    auto* player = RE::PlayerCharacter::GetSingleton();
    if (!ui || ui->IsMenuOpen(RE::LoadingMenu::MENU_NAME) || ui->IsMenuOpen(RE::MainMenu::MENU_NAME) ||
        !player || key.actor != 0x14 || player->GetFormID() != key.actor || player->IsDisabled() ||
        player->IsDeleted() || !player->Is3DLoaded()) return nullptr;
    return player;
}

inline bool emptyBodyBuffer(const RE::BIPOBJECT& buffer) {
    const auto* path = buffer.part ? buffer.part->GetModel() : nullptr;
    return !buffer.item && !buffer.addon && !buffer.partClone && !buffer.partHandle && (!path || !*path);
}

inline PlayerIdentity equippedPlayer(Key key) {
    auto* player = ownedWorldPlayer(key);
    if (!player) return {};
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
    const claw::ContactArmorForms forms{item->GetFormID(), addon->GetFormID()};
    if (claw::contactRoute(forms, forms, true, emptyBodyBuffer(buffer), path ? path : "", female) !=
        claw::PhysicsContactRoute::equipped) return {};
    const auto handle = player->GetHandle().native_handle();
    if (!handle) return {};
    return {base->GetFormID(), forms, handle, female, reinterpret_cast<std::uintptr_t>(static_cast<const RE::TESForm*>(player)),
            reinterpret_cast<std::uintptr_t>(root), reinterpret_cast<std::uintptr_t>(clone)};
}

inline bool hasStockSplitEarExtent(RE::BSTriShape& ear) {
    constexpr unsigned vertices = 1354, triangles = 2394;
    const auto& extent = ear.GetTrishapeRuntimeData();
    if ((extent.vertexCount && extent.vertexCount != vertices) ||
        (extent.triangleCount && extent.triangleCount != triangles)) return false;
    if (extent.vertexCount && extent.triangleCount) return true;

    const auto skin = ear.GetGeometryRuntimeData().skinInstance;
    const auto partition = skin ? skin->skinPartition : RE::NiPointer<RE::NiSkinPartition>{};
    if (!partition || partition->vertexCount != vertices || !partition->numPartitions ||
        partition->numPartitions > 256 || partition->numPartitions != partition->partitions.size()) return false;
    std::size_t count{};
    for (std::size_t index = 0; index < partition->numPartitions; ++index) {
        const auto& part = partition->partitions[index];
        if (part.strips || !part.triangles || !part.triList) return false;
        count += part.triangles;
    }
    return count == triangles;
}

inline RE::BSTriShape* stockSplitEarGeometry(RE::NiAVObject& clone) {
    RE::BSTriShape* ear{};
    const auto scan = claw::collectTargetModel(&clone, [&](RE::NiAVObject* object) {
        auto* geometry = object->AsGeometry();
        const auto* name = object->name.c_str();
        if (name && std::string_view{name} == claw::equippedEarShape) {
            ear = geometry ? geometry->AsTriShape() : nullptr;
            return claw::TargetModelObject{geometry != nullptr, 0};
        }
        return claw::TargetModelObject{geometry != nullptr};
    }, [](RE::NiAVObject* object, auto&& push) {
        if (const auto* node = object->AsNode()) for (const auto& child : node->GetChildren())
            if (!push(child.get())) return false;
        return true;
    });
    if (scan.collection != claw::TargetModelCollection::complete || scan.roleObjects[0] != 1 ||
        !ear || ear == &clone || ear->GetAppCulled() || !attachedTo(ear, &clone)) return nullptr;
    constexpr std::string_view triPath = R"(actors\werewolfbeast\claw\firstperson\male\earworldtrial.tri)";
    const auto* tri = netimmerse_cast<RE::NiStringExtraData*>(ear->GetExtraData("BODYTRI"));
    return tri && tri->value && claw::samePhysicsAssetPath(tri->value, triPath) && hasStockSplitEarExtent(*ear)
        ? ear : nullptr;
}

inline PlayerIdentity stockSplitEarPlayer(Key key) {
    auto* player = ownedWorldPlayer(key);
    if (!player) return {};
    auto* cell = player->GetParentCell();
    auto* base = player->GetActorBase();
    auto* race = player->GetRace();
    auto* root = player->Get3D(false);
    const auto biped = player->GetBiped(false);
    if (!cell || cell->GetFormID() != key.cell || !cell->IsAttached() || !base || base->GetFormID() != 7 ||
        base->GetSex() != RE::SEX::kMale || !race || race->GetFormID() != 0xCDD84 || !root || !biped ||
        biped->actorRef.get().get() != player) return {};

    const auto& active = biped->objects[RE::BIPED_OBJECTS::kBody];
    const auto& buffer = biped->bufferedObjects[RE::BIPED_OBJECTS::kBody];
    auto* clone = active.partClone.get();
    const auto* path = active.part ? active.part->GetModel() : nullptr;
    constexpr std::string_view modelPath = R"(Actors\WerewolfBeast\Character Assets\MaleBodyWereWolf_1.NIF)";
    if (!active.item || !active.addon ||
        claw::ContactArmorForms{active.item->GetFormID(), active.addon->GetFormID()} != claw::stockContactForms ||
        !clone || clone == root || !attachedTo(clone, root) || !emptyBodyBuffer(buffer) ||
        !path || !claw::samePhysicsAssetPath(path, modelPath)) return {};

    const auto* ear = stockSplitEarGeometry(*clone);
    const auto handle = player->GetHandle().native_handle();
    if (!ear || !handle) return {};
    return {base->GetFormID(), claw::stockContactForms, handle, false,
            reinterpret_cast<std::uintptr_t>(static_cast<const RE::TESForm*>(player)),
            reinterpret_cast<std::uintptr_t>(root), reinterpret_cast<std::uintptr_t>(clone),
            reinterpret_cast<std::uintptr_t>(ear)};
}
}
