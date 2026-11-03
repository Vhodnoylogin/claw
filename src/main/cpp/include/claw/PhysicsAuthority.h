#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <initializer_list>
#include <memory>
#include <optional>
#include <string_view>
#include <utility>

namespace claw {
struct PhysicsOwner {
    std::uint64_t world{}, runtime{};
    bool operator==(const PhysicsOwner&) const = default;
};
// CBPC consumes the third-person graph. Keep current/buffered slot identities
// ordered: moving the same clone between slots changes the loaded resource context.
inline constexpr std::size_t physicsBipedSlotCount = 42;
inline constexpr std::size_t physicsBipedPartCount = 2 * physicsBipedSlotCount;
using PhysicsBodyParts = std::array<std::uintptr_t, physicsBipedPartCount>;
struct PhysicsBodyStamp {
    std::uintptr_t race{}, root{};
    int sex{-1};
    bool beast{}, loaded{};
    PhysicsBodyParts partClones{}; // Current slots first, then buffered slots.
    bool operator==(const PhysicsBodyStamp&) const = default;
};
enum class PhysicsAdmission { renewal, qualified, initialPopulation };
enum class PhysicsRejection : unsigned { none=0, domain=1, weight=2, model=4, tokenLimit=8, provider=16, identity=32 };
struct PhysicsAuthorityTicket {
    PhysicsOwner owner;
    std::uint64_t revision{}, request{};
    PhysicsAdmission admission{};
};

// Transient per-runtime authority, independent of replaceable observer bindings.
// It owns no engine objects. The adapter pins each remembered loaded root/part and
// releases that context only after observation/pending/cleanup ownership ends.
class PhysicsAuthority {
public:
    PhysicsAuthority() = default;
    explicit PhysicsAuthority(PhysicsOwner owner) : owner_(owner) {}

    bool matches(PhysicsOwner owner) const { return owner.world && owner.runtime && owner == owner_; }
    bool engaged() const { return !virgin_; }
    bool pending() const { return pending_ != 0; }
    std::uint64_t revision() const { return revision_; }
    const PhysicsBodyStamp* stamp() const { return stamp_.get(); }
    bool rejected() const { return rejection_ != 0; }

    void observe(PhysicsBodyStamp current) {
        // The adapter admits at most sixteen physical contexts. Virgin actors
        // and retired tombstones retain no per-slot allocation.
        // A first context establishes the caller-qualified baseline.
        if (!stamp_) { stamp_ = std::make_unique<PhysicsBodyStamp>(std::move(current)); return; }
        if (*stamp_ == current) return;
        if (!virgin_) {
            if (stamp_->sex != current.sex) rejection_ |= unsigned(PhysicsRejection::identity);
            if (stamp_->beast && current.beast && stamp_->loaded && current.loaded &&
                stamp_->root && current.root &&
                (stamp_->root != current.root || stamp_->partClones != current.partClones))
                rejection_ |= unsigned(PhysicsRejection::model);
        }
        *stamp_ = std::move(current);
        pending_ = 0;
        if (rejected()) qualified_ = false;
        advance(); // Even an observed A -> B -> A cannot revive an admitted ticket.
    }

    void reject(PhysicsRejection reason) {
        if (reason == PhysicsRejection::none) return;
        rejection_ |= unsigned(reason);
        qualified_ = false; virgin_ = false; pending_ = 0;
        advance();
    }

    std::string_view condition() const {
        for (const auto reason : {PhysicsRejection::identity, PhysicsRejection::provider, PhysicsRejection::model,
                 PhysicsRejection::weight, PhysicsRejection::domain, PhysicsRejection::tokenLimit})
            if (rejection_ & unsigned(reason)) switch (reason) {
                case PhysicsRejection::identity: return "identity";
                case PhysicsRejection::provider: return "provider";
                case PhysicsRejection::model: return "model";
                case PhysicsRejection::weight: return "weight";
                case PhysicsRejection::domain: return "domain";
                case PhysicsRejection::tokenLimit: return "token-limit";
                default: break;
            }
        return {};
    }

    bool renewable(PhysicsOwner owner) const {
        return matches(owner) && !exhausted_ && qualified_ && !suspended_ && !rejected() && !pending();
    }
    bool cleanupAllowed(PhysicsOwner owner) const {
        return matches(owner) && !(rejection_ & (unsigned(PhysicsRejection::identity) | unsigned(PhysicsRejection::provider)));
    }
    bool publishable(PhysicsOwner owner, std::uint64_t revision) const { return renewable(owner) && revision == revision_; }

    std::optional<PhysicsAuthorityTicket> admit(PhysicsAdmission admission, PhysicsOwner owner, std::uint64_t request) {
        if (!matches(owner) || !request || exhausted_) return std::nullopt;
        if (admission == PhysicsAdmission::renewal && !renewable(owner)) return std::nullopt;
        if (admission == PhysicsAdmission::initialPopulation && (!virgin_ || suspended_ || rejected() || pending())) return std::nullopt;
        virgin_ = false;
        advance();
        if (exhausted_) return std::nullopt;
        pending_ = request; // Immediately withdraw old snapshots without clearing rejection/cleanup history.
        return PhysicsAuthorityTicket{owner_, revision_, request, admission};
    }

    bool commit(const PhysicsAuthorityTicket& ticket, PhysicsOwner owner, std::uint64_t latestRequest) {
        if (!matches(owner) || ticket.owner != owner || exhausted_ || ticket.revision != revision_ ||
            !pending_ || ticket.request != pending_ || latestRequest != pending_) return false;
        if (ticket.admission == PhysicsAdmission::renewal && (!qualified_ || suspended_ || rejected())) return false;
        if (ticket.admission == PhysicsAdmission::initialPopulation && rejected()) return false;
        pending_ = 0; rejection_ = 0; qualified_ = true; suspended_ = false;
        advance();
        return !exhausted_;
    }

    void cancel(const PhysicsAuthorityTicket& ticket) {
        if (ticket.owner == owner_ && ticket.revision == revision_ && ticket.request == pending_) suspend();
    }

    void suspend() { qualified_ = false; suspended_ = true; virgin_ = false; pending_ = 0; advance(); }
    void forgetStamp() { if (!qualified_ && !pending()) stamp_.reset(); }

private:
    void advance() {
        if (revision_ == std::numeric_limits<std::uint64_t>::max()) exhausted_ = true;
        else ++revision_;
    }
    PhysicsOwner owner_;
    std::unique_ptr<PhysicsBodyStamp> stamp_;
    std::uint64_t revision_{1}, pending_{};
    unsigned rejection_{};
    bool virgin_{true}, qualified_{}, suspended_{}, exhausted_{};
};
}
