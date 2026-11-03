#include "claw/WorldStartPolicy.h"
#undef NDEBUG
#include <array>
#include <cassert>
#include <iostream>

int main() {
    using Start = claw::WorldStart;
    // Raw SKSE message contracts: successful load, failed load, and malformed
    // post-load messages. An attempted load alone never admits an active world.
    struct Message { Start kind; std::uint32_t length; std::uintptr_t data; bool activates; };
    constexpr std::array messages{
        Message{Start::postLoadGame, 1, 0, false},
        Message{Start::postLoadGame, 1, 1, true},
        Message{Start::postLoadGame, 0, 0, false},
        Message{Start::postLoadGame, 0, 1, false},
        Message{Start::postLoadGame, 8, 1, false},
        Message{Start::postLoadGame, 1, 2, false},
        Message{Start::postLoadGame, 1, 0x1234, false},
        // New-game notification is independent of load result/quest presence.
        Message{Start::newGame, 0, 0, true},
        Message{Start::newGame, 8, 0x1234, true},
        Message{Start::newGame, 1, 0, true},
    };
    for (const auto& message : messages)
        assert(claw::mayActivateWorld(message.kind, message.length, message.data) == message.activates);

    // Actual dispatch casts bool to void*, emitting only 0/1. A real address is
    // malformed even when the boolean stored at that address happens to be true.
    const bool trueAtAddress = true;
    const auto nonnull = reinterpret_cast<std::uintptr_t>(&trueAtAddress);
    assert(!claw::mayActivateWorld(Start::postLoadGame, 1, nonnull));

    // A successful A -> failed B -> successful A sequence must admit only the
    // successful notifications; no prior success is sticky across an attempt.
    constexpr std::array results{std::uintptr_t{1}, std::uintptr_t{0}, std::uintptr_t{1}};
    unsigned admitted{};
    for (const auto result : results) admitted += claw::mayActivateWorld(Start::postLoadGame, 1, result);
    assert(admitted == 2);
    std::cout << "World start success, failure, payload and new-game contracts passed\n";
}
