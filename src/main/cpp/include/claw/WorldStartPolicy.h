#pragma once
#include <cstdint>

namespace claw {
enum class WorldStart { newGame, postLoadGame };

// SKSE SE/AE/VR encodes the returned LoadGame bool in the pointer VALUE,
// dataLen=1: 0 is failure, 1 is success. It is not bool* storage.
// NewGame instead carries a quest pointer and has no load-success payload.
constexpr bool mayActivateWorld(WorldStart start, std::uint32_t dataLength, std::uintptr_t dataValue) {
    return start == WorldStart::newGame ||
        (start == WorldStart::postLoadGame && dataLength == 1 && dataValue == 1);
}
}
