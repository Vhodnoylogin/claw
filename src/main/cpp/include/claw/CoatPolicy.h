#pragma once
#include "claw/CoatLibrary.h"
#include <cstdint>
#include <span>

namespace claw::appearance {
inline constexpr std::string_view coatPolicyRelativePath = "SKSE/Plugins/CLAW/CoatPolicy.xml";
enum class TintMode { original, linked };
enum class CoatOrigin { none, manual, hairPool, legacyHair, fallback };
struct AutomaticChoice {
    std::string pool, pattern;
    bool operator==(const AutomaticChoice&) const = default;
};
struct AutomaticCoatState {
    std::uint64_t identity{}, seed{};
    AutomaticChoice hair, fallback;
    bool operator==(const AutomaticCoatState&) const = default;
};
struct CoatDecision {
    std::string pattern, pool;
    CoatOrigin origin{CoatOrigin::none};
    std::string reason;
};
inline std::uint64_t coatHashByte(std::uint64_t hash, unsigned char byte) {
    return (hash ^ byte) * 1099511628211ULL;
}
inline std::uint64_t coatHashWord(std::uint64_t hash, std::uint64_t value, unsigned bytes) {
    for (unsigned i = 0; i < bytes; ++i) hash = coatHashByte(hash, static_cast<unsigned char>(value >> (8 * i)));
    return hash;
}
inline std::uint64_t coatHashText(std::uint64_t hash, std::string_view value) {
    hash = coatHashWord(hash, value.size(), 4);
    for (const unsigned char byte : value) hash = coatHashByte(hash, byte);
    return hash;
}
// Explicit byte order and versioned domains; no runtime FormID, NPC base,
// pointer, time, global RNG or implementation-defined std::hash enters selection.
inline std::uint64_t coatSeed(std::uint64_t saveNamespace, std::uint64_t identity) {
    auto hash = coatHashText(14695981039346656037ULL, "CLAW.coat.seed.1");
    hash = coatHashWord(coatHashWord(hash, saveNamespace, 8), identity, 8);
    return hash ? hash : 1;
}
inline std::uint64_t coatScore(std::uint64_t seed, std::string_view pool, std::string_view pattern) {
    auto hash = coatHashText(14695981039346656037ULL, "CLAW.coat.choice.1");
    return coatHashText(coatHashText(coatHashWord(hash, seed, 8), pool), pattern);
}
class CoatPolicy final {
public:
    // No policy file preserves 0.8's nearest real hair + linked tint behavior.
    CoatPolicy() = default;
    static CoatPolicy unavailable(std::string reason) {
        CoatPolicy result; result.legacy_ = false; result.mode_ = TintMode::original;
        result.error_ = std::move(reason); return result;
    }
    static CoatPolicy parse(std::string_view xml, const CoatLibrary& library) {
        if (xml.empty() || xml.size() > 65536 || xml.find('&') != xml.npos ||
            xml.find("<!") != xml.npos || xml.find("<?") != xml.npos) fail("Expected bounded coat policy XML");
        for (const unsigned char c : xml) if ((c < 32 && c != 9 && c != 10 && c != 13) || c == 127)
            fail("Invalid coat policy control character");
        pugi::xml_document doc;
        if (!doc.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8)) fail("Malformed coat policy XML");
        const auto root = doc.document_element();
        if (std::string_view(root.name()) != "CoatPolicy" || root.next_sibling() ||
            !attributes(root, {"schemaVersion", "tintMode"}, {"fallbackPool"}) ||
            std::string_view(root.attribute("schemaVersion").value()) != "1") fail("Unsupported coat policy schema");
        CoatPolicy result; result.legacy_ = false;
        const std::string_view mode = root.attribute("tintMode").value();
        if (mode == "original") result.mode_ = TintMode::original;
        else if (mode == "linked") result.mode_ = TintMode::linked;
        else fail("Unknown coat tint mode");
        result.fallback_ = root.attribute("fallbackPool").value();
        const auto pools = root.child("Pools");
        if (!pools || pools.next_sibling() || root.first_child() != pools || !attributes(pools, {})) fail("Expected one coat Pools element");
        std::set<std::string> hairMembers;
        for (const auto node : pools.children()) {
            if (std::string_view(node.name()) != "Pool" || !attributes(node, {"id", "use"})) fail("Invalid coat pool element");
            Pool pool; pool.id = node.attribute("id").value();
            const std::string_view use = node.attribute("use").value();
            if (!coatToken(pool.id) || (use != "hair" && use != "fallback")) fail("Invalid coat pool identity/use");
            pool.hair = use == "hair";
            for (const auto member : node.children()) {
                if (std::string_view(member.name()) != "Pattern" || !attributes(member, {"id"}) || member.first_child()) fail("Invalid coat pool member");
                const std::string id = member.attribute("id").value();
                const auto* pattern = library.find(id);
                if (!pattern || (pool.hair && !pattern->fur)) fail("Unknown coat member or missing measured hair palette");
                if (!pool.members.insert(id).second || pool.members.size() > 64) fail("Duplicate/excessive coat pool members");
                if (pool.hair && !hairMembers.insert(id).second) fail("Overlapping hair coat pools");
            }
            if (pool.members.empty() || !result.pools_.emplace(pool.id, std::move(pool)).second || result.pools_.size() > 16)
                fail("Empty/duplicate/excessive coat pools");
        }
        if (!result.fallback_.empty()) {
            const auto found = result.pools_.find(result.fallback_);
            if (found == result.pools_.end() || found->second.hair) fail("Fallback must name a fallback pool");
        }
        return result;
    }
    [[nodiscard]] TintMode tintMode() const { return mode_; }
    [[nodiscard]] CoatDecision select(const CoatLibrary& library, std::string_view manual,
        const std::optional<RGB>& realHair, std::uint64_t seed, const AutomaticCoatState& saved) const {
        if (!manual.empty()) return library.find(manual) ? CoatDecision{std::string(manual), {}, CoatOrigin::manual, {}} :
            CoatDecision{{}, {}, CoatOrigin::manual, "manual pattern unavailable"};
        if (!error_.empty()) return {{}, {}, CoatOrigin::none, error_};
        if (realHair && !valid(*realHair)) return {{}, {}, CoatOrigin::none, "invalid real hair colour"};
        if (legacy_) {
            const auto choice = realHair ? library.nearest(*realHair) : std::string{};
            return {choice, {}, choice.empty() ? CoatOrigin::none : CoatOrigin::legacyHair,
                choice.empty() ? "legacy hair source or palette unavailable" : "legacy nearest measured hair"};
        }
        const Pool* selected{};
        CoatOrigin origin{CoatOrigin::none};
        if (realHair) {
            double best = std::numeric_limits<double>::infinity();
            for (const auto& [id, pool] : pools_) if (pool.hair) {
                (void)id;
                for (const auto& key : pool.members) if (const auto* pattern = library.find(key); pattern && pattern->fur) {
                    const auto distance = coatDistance(*realHair, *pattern->fur);
                    if (distance < best) { best = distance; selected = &pool; }
                }
            }
            if (!selected) return {{}, {}, CoatOrigin::none, "no eligible measured hair pool"};
            origin = CoatOrigin::hairPool;
        } else {
            if (fallback_.empty()) return {{}, {}, CoatOrigin::none, "human hair unavailable; fallback disabled"};
            const auto found = pools_.find(fallback_);
            if (found == pools_.end()) return {{}, {}, CoatOrigin::none, "fallback pool unavailable"};
            selected = &found->second; origin = CoatOrigin::fallback;
        }
        const auto& prior = origin == CoatOrigin::hairPool ? saved.hair : saved.fallback;
        if (prior.pool == selected->id && selected->members.contains(prior.pattern) && library.find(prior.pattern))
            return {prior.pattern, selected->id, origin, "retained eligible automatic choice"};
        if (!seed) return {{}, selected->id, CoatOrigin::none, "saved reference seed unavailable"};
        std::string choice; std::uint64_t best{};
        for (const auto& key : selected->members) if (library.find(key)) {
            const auto score = coatScore(seed, selected->id, key);
            if (choice.empty() || score > best) { best = score; choice = key; }
        }
        return {choice, selected->id, choice.empty() ? CoatOrigin::none : origin,
            choice.empty() ? "eligible pattern unavailable" : "stable saved-reference selection"};
    }
private:
    struct Pool { std::string id; bool hair{}; std::set<std::string> members; };
    std::map<std::string, Pool, std::less<>> pools_;
    std::string fallback_, error_;
    bool legacy_{true};
    TintMode mode_{TintMode::linked};
    [[noreturn]] static void fail(const char* text) { throw std::invalid_argument(text); }
    static bool attributes(pugi::xml_node node, std::initializer_list<std::string_view> required,
        std::initializer_list<std::string_view> optional = {}) {
        std::set<std::string_view> found;
        for (const auto attr : node.attributes()) {
            const std::string_view name = attr.name();
            if (!found.insert(name).second || (std::find(required.begin(), required.end(), name) == required.end() &&
                std::find(optional.begin(), optional.end(), name) == optional.end())) return false;
        }
        return std::all_of(required.begin(), required.end(), [&](auto name) { return found.contains(name); });
    }
};
struct AutomaticCoatRecord {
    std::uint32_t actor{}, base{}, sex{};
    AutomaticCoatState automatic;
};
inline bool valid(const AutomaticChoice& choice) {
    return (choice.pool.empty() && choice.pattern.empty()) || (coatToken(choice.pool) && coatKey(choice.pattern));
}
inline bool valid(const AutomaticCoatRecord& record) {
    return record.actor && record.base && record.sex <= 1 && record.automatic.identity &&
        record.automatic.identity != std::numeric_limits<std::uint64_t>::max() && record.automatic.seed &&
        valid(record.automatic.hair) && valid(record.automatic.fallback);
}
inline std::vector<char> writeAutomaticCoat(const AutomaticCoatRecord& record) {
    if (!valid(record)) throw std::invalid_argument("Invalid automatic coat record");
    std::vector<char> bytes;
    const auto word = [&](std::uint64_t value, unsigned size) {
        for (unsigned i = 0; i < size; ++i) bytes.push_back(static_cast<char>((value >> (8 * i)) & 255));
    };
    const auto text = [&](std::string_view value) { word(value.size(), 4); bytes.insert(bytes.end(), value.begin(), value.end()); };
    word(record.actor, 4); word(record.base, 4); word(record.sex, 4);
    word(record.automatic.identity, 8); word(record.automatic.seed, 8);
    for (const auto* choice : {&record.automatic.hair, &record.automatic.fallback}) { text(choice->pool); text(choice->pattern); }
    return bytes;
}
inline AutomaticCoatRecord readAutomaticCoat(std::span<const char> bytes) {
    if (bytes.size() < 44 || bytes.size() > 430) throw std::invalid_argument("Invalid automatic coat record length");
    std::size_t at{};
    const auto word = [&](unsigned size) {
        if (size > bytes.size() - at) throw std::invalid_argument("Truncated automatic coat record");
        std::uint64_t value{};
        for (unsigned i = 0; i < size; ++i) value |= std::uint64_t(static_cast<unsigned char>(bytes[at++])) << (8 * i);
        return value;
    };
    const auto text = [&](std::size_t maximum) {
        const auto length = word(4);
        if (length > maximum || length > bytes.size() - at) throw std::invalid_argument("Invalid automatic coat string");
        std::string value(bytes.data() + at, static_cast<std::size_t>(length)); at += length; return value;
    };
    AutomaticCoatRecord result;
    result.actor = static_cast<std::uint32_t>(word(4)); result.base = static_cast<std::uint32_t>(word(4));
    result.sex = static_cast<std::uint32_t>(word(4)); result.automatic.identity = word(8); result.automatic.seed = word(8);
    for (auto* choice : {&result.automatic.hair, &result.automatic.fallback}) { choice->pool = text(64); choice->pattern = text(129); }
    if (at != bytes.size() || !valid(result)) throw std::invalid_argument("Invalid automatic coat payload");
    return result;
}
}
