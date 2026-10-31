#pragma once

#include <cstddef>
#include <cstdint>
#include <limits>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <utility>

namespace claw {
// Process-local ownership only. Neither pointers nor these serials are save IDs.
struct RequestToken {
    std::uint64_t epoch{}, serial{}, owner{};
    bool operator==(const RequestToken&) const = default;
};
struct RequestBinding {
    RequestToken token{};
    std::uint64_t runtime{};
};

inline bool mayBindRestoredIdentity(std::uint64_t saved, std::uint64_t current, bool quarantined) {
    return !quarantined && saved && current && saved == current;
}

inline bool sameRuntimeActor(const void* bound, const void* resolved, const void* current) {
    return bound && bound == resolved && bound == current;
}
inline bool mayRunActorRequest(const void* pinned, const void* registered, bool sameID, bool deleted) {
    return pinned && pinned == registered && sameID && !deleted;
}

// Shared ownership policy only; caller owns the required release-thread contract.
template<class Key, class Value>
std::size_t collectUnshared(std::map<Key, std::shared_ptr<Value>>& owners) {
    std::size_t collected{};
    for (auto it = owners.begin(); it != owners.end();) {
        if (it->second.use_count() == 1) { it = owners.erase(it); ++collected; }
        else ++it;
    }
    return collected;
}

template<class Owner>
class RequestLedger {
public:
    struct Request { RequestToken token; Owner owner; std::string error; };
    explicit RequestLedger(std::size_t limit) : limit_(limit) {}

    std::optional<RequestToken> begin(std::uint32_t id, std::uint64_t epoch, std::uint64_t owner, Owner pin) {
        if (!id || !epoch || !owner || next_ == std::numeric_limits<std::uint64_t>::max() ||
            (rows_.size() >= limit_ && !rows_.contains(id))) return std::nullopt;
        const RequestToken token{epoch, next_++, owner};
        rows_.insert_or_assign(id, Request{token, std::move(pin), {}});
        return token;
    }
    const Request* find(std::uint32_t id, std::uint64_t owner, std::uint64_t epoch) const {
        const auto row = rows_.find(id);
        return row != rows_.end() && row->second.token.owner == owner && row->second.token.epoch == epoch ? &row->second : nullptr;
    }
    bool owns(std::uint32_t id, RequestToken token, std::uint64_t epoch) const {
        const auto* row = find(id, token.owner, epoch);
        return row && token.epoch == epoch && row->token == token;
    }
    // Compare-and-finish: stale work cannot erase or set an error on newer work.
    bool finish(std::uint32_t id, RequestToken token, std::uint64_t epoch, std::string error = {}) {
        if (!owns(id, token, epoch)) return false;
        if (error.empty()) rows_.erase(id);
        else {
            auto& row = rows_.at(id);
            row.error = std::move(error);
            row.owner = Owner{}; // Completed errors must not retain engine pins.
        }
        return true;
    }
    bool eraseOwner(std::uint32_t id, std::uint64_t owner) {
        const auto row = rows_.find(id);
        if (row == rows_.end() || row->second.token.owner != owner) return false;
        rows_.erase(row);
        return true;
    }
    void clear() { rows_.clear(); } // Never reuse a process-local request serial.
private:
    std::size_t limit_;
    std::uint64_t next_{1};
    std::map<std::uint32_t, Request> rows_;
};

// Pending calls use their pool owner. Completed errors need no intrusive pin:
// a validated State keeps only this token and its runtime binding serial.
template<class Owner>
const typename RequestLedger<Owner>::Request* resolveActorRequest(
    const RequestLedger<Owner>& ledger, std::uint32_t id, std::uint64_t epoch,
    std::uint64_t poolOwner, const RequestBinding* bound, std::uint64_t runtime) {
    if (poolOwner) if (const auto* row = ledger.find(id, poolOwner, epoch)) return row;
    if (!bound || !runtime || bound->runtime != runtime || !ledger.owns(id, bound->token, epoch)) return nullptr;
    return ledger.find(id, bound->token.owner, epoch);
}
}
