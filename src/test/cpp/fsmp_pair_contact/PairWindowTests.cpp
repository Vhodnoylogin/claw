#include "PairWindow.h"

#include <cassert>
#include <limits>
#include <thread>

using namespace claw::contact;

namespace {
constexpr Pair pair{100, 101, 200, 201, 1100, 2200, 501, 502, false};
constexpr Trial trial{1, 12, 2, 1000000};
constexpr Vec3 normal{1, 0, 0}, a{2, 3, 4}, b{5, 6, 7};

void wrongIdentityAndZero() {
    Window window;
    constexpr std::string_view attachment = "(000CDD87)[0]/ (000CDD86) [100%]";
    assert(hasAddonId(attachment, 0x000cdd87));
    assert(!hasAddonId(attachment, 0x000cdd86));
    assert(!hasAddonId("(000CDD8Z)[0]/ (000CDD87) [100%]", 0x000cdd87));
    assert(!hasAddonId("x(000CDD87)[0]", 0x000cdd87));
    auto same = pair;
    same.probeSkeleton = same.surfaceSkeleton;
    assert(!window.arm(trial, same));
    assert(window.arm(trial, pair));
    assert(window.begin(true, 10));
    window.note(pair.surface, 3, 0, 11, 1, {}, {}, {});
    window.end(12);
    assert(window.state() == State::armed && window.count() == 0);
    assert(window.begin(true, 13));
    window.end(14);
    assert(window.state() == State::complete && window.count() == 0);
    assert(window.steps() == 2 && window.first() == 10 && window.last() == 14);
    assert(!window.arm(trial, pair));
}

void normalAndConcurrency() {
    Window window;
    assert(window.arm(trial, pair));
    assert(window.begin(true, 10));
    std::thread writerA([&] {
        for (int i = 0; i < 100; ++i) window.note(pair.surface, pair.probe, 1, 11, -0.2f, normal, a, b);
    });
    std::thread writerB([&] {
        for (int i = 0; i < 100; ++i) window.note(pair.probe, pair.surface, 2, 11, -0.3f, normal, b, a);
    });
    writerA.join();
    writerB.join();
    window.end(12);
    assert(!window.row(0));
    assert(window.begin(true, 13));
    window.end(14);
    assert(window.count() == 200 && !window.row(200));
    std::array<unsigned, 3> seen{};
    for (std::uint32_t i = 0; i < window.count(); ++i) {
        const auto& row = *window.row(i);
        assert(row.step == 1 && row.qpc == 11 && row.surfaceLocal == a && row.probeLocal == b);
        assert(row.depth == (row.driver == 1 ? -0.2f : -0.3f));
        assert(row.normalToSurface[0] == (row.driver == 1 ? 1 : -1));
        ++seen.at(row.driver);
    }
    assert(seen[1] == 100 && seen[2] == 100);
}

void refuseIncompleteOrCorrupt() {
    Window window;
    assert(window.arm(trial, pair));
    assert(!window.begin(false, 10));
    assert(window.state() == State::refused && !window.row(0));
    assert(window.arm({2, 12, 2, 1000000}, pair));
    assert(window.begin(true, 10));
    window.note(pair.surface, pair.probe, 1, 11, std::numeric_limits<float>::quiet_NaN(), normal, a, b);
    window.end(12);
    assert(window.state() == State::refused);
    assert(window.arm({3, 12, 2, 1000000}, pair));
    assert(window.begin(true, 15));
    for (unsigned i = 0; i <= Window::capacity; ++i) window.note(pair.surface, pair.probe, 1, 16, -1, normal, a, b);
    window.end(17);
    assert(window.state() == State::refused && !window.row(0));
    assert(window.arm({4, 12, 1, 1000000}, pair));
    assert(window.begin(true, 20));
    window.note(pair.surface, pair.probe, 1, 23, -1, normal, a, b);
    window.end(22);
    assert(window.state() == State::refused);
}
}

int main() {
    wrongIdentityAndZero();
    normalAndConcurrency();
    refuseIncompleteOrCorrupt();
}
