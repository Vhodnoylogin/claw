#pragma once
#include <cstdint>

namespace claw {
// Human-source provenance requires a known non-beast NPC race. Other creature
// forms and unresolved races cannot establish human history or replace it.
inline constexpr bool humanSourceEligible(std::uint32_t beastRace, std::uint32_t currentRace, bool actorTypeNPC) {
    return beastRace && currentRace && currentRace != beastRace && actorTypeNPC;
}

// State provenance, not a guess based on a zero-valued preset/morph sum.
// Runtime/root/provider/name-presence witnesses are checked by the main adapter.
struct SourceBootstrapPolicy {
    bool freshDefault{}, firstSeenBeast{}, observedHuman{}, humanWeightKnown{};
    bool revoked{}, suppressed{}, quarantined{}, claimed{}, pendingRequest{};
    bool providerSources{true};
    bool allows() const {
        return providerSources && freshDefault && firstSeenBeast && !observedHuman && !humanWeightKnown &&
            !revoked && !suppressed && !quarantined && !claimed && !pendingRequest;
    }
};
}
