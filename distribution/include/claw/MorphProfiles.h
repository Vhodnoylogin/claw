#pragma once
#include "claw/MorphLink.h"
#include <pugixml.hpp>
#include <charconv>
#include <filesystem>
#include <fstream>
#include <iterator>

namespace claw {
inline constexpr auto morphProfilesRelativePath = "SKSE/Plugins/CLAW/MorphLinks.xml";

struct MorphFamilyProfile {
    std::string id, sourceFamily, sourceVersion, calibration;
    Sex sex{};
    MorphLink link;
};

// Explicit resource-family bindings, never independent werewolf presets.
// The v1 generated interchange uses printable ASCII identifiers and decimal
// numbers. XML entities/declarations are intentionally outside that format.
class MorphProfileCatalog {
public:
    bool loadFile(const std::filesystem::path& path) {
        std::error_code ec;
        const auto bytes = std::filesystem::file_size(path, ec);
        if (ec || bytes > 1024 * 1024) return fail("Morph family file unavailable or exceeds 1 MiB");
        std::ifstream input(path, std::ios::binary);
        if (!input) return fail("Morph family file is unreadable");
        std::string xml((std::istreambuf_iterator<char>(input)), {});
        if (input.bad()) return fail("Morph family read failed");
        return loadXml(xml);
    }

    bool loadXml(std::string_view xml) {
        clear();
        if (xml.empty() || xml.size() > 1024 * 1024 || xml.find('&') != xml.npos ||
            xml.find("<!") != xml.npos || xml.find("<?") != xml.npos)
            return fail("Expected generated ASCII family XML without entities/declarations");
        for (const unsigned char value : xml)
            if ((value < 32 && value != 9 && value != 10 && value != 13) || value >= 127)
                return fail("Family interchange must contain printable ASCII");
        pugi::xml_document document;
        if (!document.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8))
            return fail("Malformed family XML");
        const auto root = document.document_element();
        if (std::string_view(root.name()) != "MorphLinkProfiles" ||
            !attributes(root, {"schemaVersion"}) || std::string_view(root.attribute("schemaVersion").value()) != "1")
            return fail("Unknown family document/schema");
        std::size_t roots{};
        for (const auto node : document.children()) if (node.type() == pugi::node_element) ++roots;
        if (roots != 1) return fail("Family file must contain one root");
        std::map<std::string, MorphFamilyProfile, std::less<>> staged;
        std::map<Sex, std::string> defaults;
        for (const auto node : root.children()) {
            if (node.type() == pugi::node_element && std::string_view(node.name()) == "Defaults") {
                if (!defaults.empty() || !attributes(node, {"male", "female"}) || node.first_child())
                    return fail("Duplicate or malformed explicit resource defaults");
                const std::string male = node.attribute("male").value(), female = node.attribute("female").value();
                if (male.empty() && female.empty()) return fail("Empty resource default declaration");
                defaults.emplace(Sex::male, male); defaults.emplace(Sex::female, female);
                continue;
            }
            if (node.type() != pugi::node_element || std::string_view(node.name()) != "Profile" ||
                !attributes(node, {"id", "family", "version", "sex", "calibration"}))
                return fail("Unexpected family node/attribute");
            MorphFamilyProfile profile;
            profile.id = node.attribute("id").value();
            profile.sourceFamily = node.attribute("family").value();
            profile.sourceVersion = node.attribute("version").value();
            profile.calibration = node.attribute("calibration").value();
            for (const auto* value : {&profile.id, &profile.sourceFamily, &profile.sourceVersion, &profile.calibration})
                if (!morphLinkIdentifier(*value)) return fail("Invalid family metadata");
            const std::string_view sex = node.attribute("sex").value();
            if (sex != "male" && sex != "female") return fail("Invalid family sex");
            profile.sex = sex == "male" ? Sex::male : Sex::female;
            profile.link.profile = profile.id;
            try {
                for (const auto rule : node.children()) {
                    if (rule.type() != pugi::node_element || std::string_view(rule.name()) != "Rule" ||
                        !attributes(rule, {"source", "target", "gain", "cap"}) || rule.first_child())
                        return fail("Unexpected family rule/attribute/content");
                    profile.link.rules.push_back({rule.attribute("source").value(), rule.attribute("target").value(),
                        number(rule.attribute("gain").value()), number(rule.attribute("cap").value())});
                }
            } catch (const std::invalid_argument&) { return fail("Invalid family coefficient"); }
            if (!profile.link.valid(profile.sex)) return fail("Family mapping violates MorphLink contract");
            const auto key = profile.id;
            if (!staged.emplace(key, std::move(profile)).second || staged.size() > 64)
                return fail("Duplicate family id or excessive catalog");
        }
        if (staged.empty()) return fail("Empty family catalog");
        for (const auto& [sex, id] : defaults) {
            if (id.empty()) continue;
            const auto profile = staged.find(id);
            if (profile == staged.end() || profile->second.sex != sex)
                return fail("Resource default references an absent or wrong-sex family");
        }
        profiles_ = std::move(staged);
        defaults_ = std::move(defaults);
        return true;
    }

    const MorphFamilyProfile* find(std::string_view id, Sex sex) const {
        if (!valid()) return nullptr;
        const auto found = profiles_.find(id);
        return found != profiles_.end() && found->second.sex == sex ? &found->second : nullptr;
    }
    std::vector<std::string> names(Sex sex) const {
        std::vector<std::string> result;
        if (valid()) for (const auto& [name, profile] : profiles_) if (profile.sex == sex) result.push_back(name);
        return result;
    }
    const MorphFamilyProfile* defaultFor(Sex sex) const {
        const auto id = defaults_.find(sex);
        return id == defaults_.end() || id->second.empty() ? nullptr : find(id->second, sex);
    }
    void clear() { profiles_.clear(); defaults_.clear(); error_.clear(); }
    bool valid() const { return error_.empty() && !profiles_.empty(); }
    const std::string& error() const { return error_; }
private:
    std::map<std::string, MorphFamilyProfile, std::less<>> profiles_;
    std::map<Sex, std::string> defaults_;
    std::string error_;
    bool fail(std::string reason) { profiles_.clear(); defaults_.clear(); error_ = std::move(reason); return false; }
    static float number(std::string_view text) {
        float result{};
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), result);
        if (text.empty() || end != text.data() + text.size() || error != std::errc{} || !std::isfinite(result))
            throw std::invalid_argument("Invalid finite family coefficient");
        return result;
    }
    static bool attributes(pugi::xml_node node, std::initializer_list<std::string_view> expected) {
        std::set<std::string_view> found;
        for (const auto item : node.attributes())
            if (!found.insert(item.name()).second || std::find(expected.begin(), expected.end(), item.name()) == expected.end()) return false;
        return found.size() == expected.size();
    }
};
}
