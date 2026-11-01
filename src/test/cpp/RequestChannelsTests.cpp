#include "claw/RequestOwnership.h"
#undef NDEBUG
#include <cassert>
#include <iostream>
#include <memory>

int main() {
    using Pin = std::shared_ptr<int>;
    constexpr std::uint32_t id = 0xFF000800;
    constexpr std::uint64_t epoch = 10, owner = 40, runtime = 7;
    claw::RequestChannels<Pin> channels{2};
    auto pin = std::make_shared<int>(1);

    // Both callback orders must preserve the other independent admitted policy.
    auto body = channels.body().begin(id, epoch, owner, pin);
    auto coat = channels.coat().begin(id, epoch, owner, pin);
    assert(body && coat && channels.body().owns(id, *body, epoch));
    assert(channels.coat().finish(id, *coat, epoch));
    assert(channels.body().finish(id, *body, epoch));
    coat = channels.coat().begin(id, epoch, owner, pin);
    body = channels.body().begin(id, epoch, owner, pin);
    assert(body && coat && channels.coat().owns(id, *coat, epoch));
    assert(channels.body().finish(id, *body, epoch));
    assert(channels.coat().finish(id, *coat, epoch));

    // Latest-wins is retained within each policy. A stale failure cannot replace
    // a newer coat intent, erase its pin, or contaminate the body error channel.
    const auto oldCoat = channels.coat().begin(id, epoch, owner, pin);
    const auto newCoat = channels.coat().begin(id, epoch, owner, pin);
    body = channels.body().begin(id, epoch, owner, pin);
    assert(oldCoat && newCoat && body);
    assert(!channels.coat().finish(id, *oldCoat, epoch, "stale coat failure"));
    assert(channels.coat().owns(id, *newCoat, epoch));
    assert(channels.body().find(id, owner, epoch)->error.empty());
    assert(pin.use_count() == 3);
    const claw::RequestBinding coatBinding{*newCoat, runtime};
    assert(channels.coat().finish(id, *newCoat, epoch, "coat file unavailable"));
    assert(pin.use_count() == 2); // Failed coat row keeps diagnostics, no pin.
    const auto* error = claw::resolveActorRequest(channels.coat(), id, epoch, 0, &coatBinding, runtime);
    assert(error && error->error == "coat file unavailable" && !error->owner);
    assert(!claw::resolveActorRequest(channels.coat(), id, epoch, 0, &coatBinding, runtime + 1));
    assert(channels.body().owns(id, *body, epoch));
    assert(channels.body().finish(id, *body, epoch));
    assert(pin.use_count() == 1);
    coat = channels.coat().begin(id, epoch, owner, pin);
    assert(coat && !claw::resolveActorRequest(channels.coat(), id, epoch, 0, &coatBinding, runtime));
    assert(channels.coat().find(id, owner, epoch)->error.empty());

    // Owner-qualified deletion clears both policies, while a late deletion for
    // an old physical actor cannot cancel a new owner with a reused FormID.
    body = channels.body().begin(id, epoch, owner + 1, pin);
    channels.eraseOwner(id, owner);
    assert(!channels.coat().find(id, owner, epoch));
    assert(body && channels.body().owns(id, *body, epoch));
    coat = channels.coat().begin(id, epoch, owner + 1, pin);
    channels.eraseOwner(id, owner + 1);
    assert(!channels.body().find(id, owner + 1, epoch));
    assert(!channels.coat().find(id, owner + 1, epoch));
    assert(pin.use_count() == 1);

    // Load/revert/new-game clears both channels without reusing request tokens.
    body = channels.body().begin(id, epoch, owner, pin);
    coat = channels.coat().begin(id, epoch, owner, pin);
    assert(body && coat && pin.use_count() == 3);
    channels.clear();
    assert(pin.use_count() == 1);
    assert(!channels.body().owns(id, *body, epoch));
    assert(!channels.coat().owns(id, *coat, epoch));
    const auto nextBody = channels.body().begin(id, epoch + 1, owner, pin);
    const auto nextCoat = channels.coat().begin(id, epoch + 1, owner, pin);
    assert(nextBody && nextCoat && nextBody->serial > body->serial && nextCoat->serial > coat->serial);
    assert(!channels.body().finish(id, *body, epoch + 1, "old world"));
    assert(!channels.coat().finish(id, *coat, epoch + 1, "old world"));
    channels.clear();
    assert(pin.use_count() == 1);
    std::cout << "Independent body/coat admission, stale work, errors and pin lifecycles passed\n";
}
