#pragma once

#include "claw/ColourMath.h"
#include "claw/MorphProfiles.h"

namespace claw::appearance {
inline constexpr auto coatMatrixRelativePath = "SKSE/Plugins/CLAW/CoatMatrix.xml";

inline Morphs coatInputs(const Colours& colours, std::uint64_t seed) {
    const float unitSeed = static_cast<float>(seed >> 40) / 16777215.F;
    return {
        {"hair.red", colours.hasHair ? colours.hair[0] : 0.F},
        {"hair.green", colours.hasHair ? colours.hair[1] : 0.F},
        {"hair.blue", colours.hasHair ? colours.hair[2] : 0.F},
        {"seed.withHair", colours.hasHair ? unitSeed : 0.F},
        {"seed.withoutHair", colours.hasHair ? 0.F : unitSeed}
    };
}

class CoatMatrix {
public:
    static CoatMatrix parse(std::string_view xml) {
        pugi::xml_document document;
        if (!document.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8))
            throw std::invalid_argument("Malformed coat matrix");
        const auto root = document.document_element();
        if (std::string_view(root.name()) != "CoatMatrix" || root.next_sibling() ||
            std::string_view(root.attribute("schemaVersion").value()) != "1" ||
            root.first_attribute().next_attribute())
            throw std::invalid_argument("Unsupported coat matrix schema");
        const auto sources = coatInputs({}, 0);
        CoatMatrix result;
        std::set<std::pair<std::string, std::string>> edges;
        std::map<std::string, float> caps;
        for (auto node : root.children()) {
            auto rule = MorphProfileCatalog::parseRule(node);
            if (!morphRuleWellFormed(rule) || (!rule.constant() && !sources.contains(rule.source)))
                throw std::invalid_argument("Unknown coat matrix input or invalid rule");
            if (!rule.active()) continue;
            if (!edges.emplace(rule.source, rule.target).second)
                throw std::invalid_argument("Duplicate coat matrix edge");
            const auto [it, added] = caps.emplace(rule.target, rule.cap);
            if (it->second != rule.cap || caps.size() > CLAW_MATRIX_MAX_TARGETS ||
                result.rules_.size() >= CLAW_MATRIX_MAX_RULES)
                throw std::invalid_argument("Invalid coat matrix dimensions or target cap");
            result.rules_.push_back(std::move(rule));
        }
        if (result.rules_.empty()) throw std::invalid_argument("Empty coat matrix");
        return result;
    }

    Morphs evaluate(const Colours& colours, std::uint64_t seed) const {
        return evaluateNamed(rules_, coatInputs(colours, seed));
    }

private:
    std::vector<MorphLinkRule> rules_;
};
}
