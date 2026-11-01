#include "claw/SourceBootstrapPolicy.h"
#include "claw/RequestOwnership.h"
#undef NDEBUG
#include <cassert>
#include <iostream>
#include <memory>

int main() {
    using Pin = std::shared_ptr<int>;
    claw::RequestLedger<Pin> requests{16};
    auto pin = std::make_shared<int>(1);
    constexpr unsigned id = 0xFF000800;
    constexpr std::uint64_t epoch = 10, owner = 40;
    auto pending = [&] { const auto* row = requests.find(id, owner, epoch); return row && row->error.empty(); };
    claw::SourceBootstrapPolicy state{true,true,false,false,false,false,false,false,false};
    assert(state.allows());
    // Native callback accepts manual intent before the first State exists.
    const auto manual = requests.begin(id,epoch,owner,pin); assert(manual);
    // An already-queued scan adopts a default before that manual task executes.
    state.pendingRequest = pending(); assert(!state.allows());
    // The task must repeat revocation on that newly created existing State,
    // even when configuring the very same catalog default profile identifier.
    state.revoked = true; state.freshDefault = false;
    assert(requests.finish(id,*manual,epoch));
    state.pendingRequest = pending(); assert(!state.pendingRequest && !state.allows());
    // Restored/manual state is never promoted merely because source sums are zero.
    state = {}; state.firstSeenBeast = true; assert(!state.allows());
    state = {true,true,false,false,false,false,false,false,false};
    state.observedHuman = true; assert(!state.allows());
    state.observedHuman = false; state.humanWeightKnown = true; assert(!state.allows());
    state.humanWeightKnown = false; state.claimed = true; assert(!state.allows());
    state = {true,true,false,false,false,false,false,false,false};
    state.providerSources = false; assert(!state.allows()); // Vanilla weight is not an OBody source assignment.
    // A stale completion cannot remove a newer matching pending intent gate.
    const auto old = requests.begin(id,epoch,owner,pin);
    const auto newer = requests.begin(id,epoch,owner,pin);
    assert(old && newer && !requests.finish(id,*old,epoch));
    state = {true,true,false,false,false,false,false,false,pending()}; assert(!state.allows());
    std::cout << "Source bootstrap interleaving/provenance contracts passed\n";
}
