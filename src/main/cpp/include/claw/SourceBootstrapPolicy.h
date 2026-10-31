#pragma once

namespace claw {
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
