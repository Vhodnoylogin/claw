#pragma once
#include "claw/MorphProfiles.h"
#include <optional>
#include <span>

namespace claw {
inline constexpr auto bodyFamilyBindingsRelativePath = "SKSE/Plugins/CLAW/BodyFamilyBindings.xml";

// Relative game mesh identity, independent of manager roots, textures and outfits.
inline std::optional<std::string> bodyMeshIdentity(std::string_view path) {
    if (path.empty() || path.size() > 1024 || path.front() == ' ' || path.back() == ' ') return {};
    std::string result;
    result.reserve(path.size());
    for (const unsigned char ch : path) {
        if (ch < 32 || ch >= 127 || ch == ':') return {};
        result += ch == '\\' ? '/' : static_cast<char>(MorphNameLess::fold(ch));
    }
    if (result.starts_with('/') || result.ends_with('/')) return {};
    if (result.starts_with("meshes/")) result.erase(0, 7);
    if (!result.ends_with(".nif")) return {};
    std::size_t begin{};
    while (begin < result.size()) {
        const auto end = result.find('/', begin);
        const auto part = std::string_view(result).substr(begin, end == result.npos ? end : end - begin);
        if (part.empty() || part == "." || part == "..") return {};
        if (end == result.npos) break;
        begin = end + 1;
    }
    return result;
}

struct BodyFamilySelection {
    const MorphFamilyProfile* profile{};
    enum class Reason { defaultFamily, skinBinding, ambiguous, invalidBindings } reason{};
    [[nodiscard]] bool blocked() const { return reason == Reason::ambiguous || reason == Reason::invalidBindings; }
};

// Optional explicit compatibility data. Selection is pure; the game adapter
// supplies only the eligible source form's naked-skin body ARMA model paths.
class BodyFamilyBindings {
public:
    bool loadFile(const std::filesystem::path& path, const MorphProfileCatalog& catalog) {
        clear();
        std::error_code ec;
        const auto bytes = std::filesystem::file_size(path, ec);
        if (ec == std::errc::no_such_file_or_directory) return true; // ordinary single-family installation
        if (ec || !bytes || bytes > 65536) return fail("Body family bindings unavailable or exceed 64 KiB");
        std::ifstream input(path, std::ios::binary);
        if (!input) return fail("Body family bindings unreadable");
        std::string xml(static_cast<std::size_t>(bytes), '\0');
        if (!input.read(xml.data(), static_cast<std::streamsize>(bytes)) || input.peek() != std::char_traits<char>::eof())
            return fail("Body family bindings changed or could not be read");
        return loadXml(xml, catalog);
    }

    bool loadXml(std::string_view xml, const MorphProfileCatalog& catalog) {
        clear();
        if (xml.empty() || xml.size() > 65536 || xml.find('&') != xml.npos || xml.find("<!") != xml.npos || xml.find("<?") != xml.npos)
            return fail("Expected bounded ASCII body bindings without declarations/entities");
        for (const unsigned char ch : xml)
            if ((ch < 32 && ch != 9 && ch != 10 && ch != 13) || ch >= 127) return fail("Body bindings must be ASCII");
        pugi::xml_document document;
        // Fragment mode retains outside-root text instead of discarding damaged
        // file prefixes/suffixes as parse_default does. Such text is rejected below.
        if (!document.load_buffer(xml.data(), xml.size(), pugi::parse_default | pugi::parse_fragment))
            return fail("Malformed body family bindings");
        const auto root = document.document_element();
        if (std::string_view(root.name()) != "BodyFamilyBindings" || !attributes(root, {"schemaVersion"}) ||
            std::string_view(root.attribute("schemaVersion").value()) != "1") return fail("Unknown body bindings schema");
        std::size_t roots{};
        for (const auto node : document.children()) {
            if (node.type() != pugi::node_element) return fail("Unexpected content outside body bindings root");
            ++roots;
        }
        if (roots != 1) return fail("Body bindings need one root");
        for (const auto node : root.children()) {
            if (std::string_view(node.name()) != "Bind" || !attributes(node, {"sex", "mesh", "profile"}) || node.first_child())
                return fail("Unexpected body binding node/attributes");
            const std::string_view sexName = node.attribute("sex").value();
            if (sexName != "male" && sexName != "female") return fail("Invalid body binding sex");
            const auto sex = sexName == "female" ? Sex::female : Sex::male;
            const auto mesh = bodyMeshIdentity(node.attribute("mesh").value());
            const std::string profile = node.attribute("profile").value();
            if (!mesh || !catalog.find(profile, sex)) return fail("Body binding mesh/profile unavailable or wrong sex");
            if (!bindings_.emplace(std::pair{sex, *mesh}, profile).second || bindings_.size() > 512)
                return fail("Duplicate or excessive body bindings");
        }
        return true;
    }

    [[nodiscard]] BodyFamilySelection select(Sex sex, std::span<const std::string> skinModels,
        const MorphProfileCatalog& catalog, bool sourceObserved = true) const {
        if (!error_.empty()) return {nullptr, BodyFamilySelection::Reason::invalidBindings};
        if (!sourceObserved) return {catalog.defaultFor(sex), BodyFamilySelection::Reason::defaultFamily};
        const MorphFamilyProfile* selected{};
        for (const auto& model : skinModels) {
            const auto key = bodyMeshIdentity(model);
            if (!key) continue;
            const auto found = bindings_.find({sex, *key});
            if (found == bindings_.end()) continue;
            const auto* profile = catalog.find(found->second, sex);
            if (!profile) return {nullptr, BodyFamilySelection::Reason::invalidBindings};
            if (selected && selected != profile) return {nullptr, BodyFamilySelection::Reason::ambiguous};
            selected = profile;
        }
        return selected ? BodyFamilySelection{selected, BodyFamilySelection::Reason::skinBinding} :
            BodyFamilySelection{catalog.defaultFor(sex), BodyFamilySelection::Reason::defaultFamily};
    }
    [[nodiscard]] bool empty() const { return bindings_.empty() && error_.empty(); }
    [[nodiscard]] bool hasSex(Sex sex) const {
        return std::any_of(bindings_.begin(), bindings_.end(), [sex](const auto& item) { return item.first.first == sex; });
    }
    [[nodiscard]] const std::string& error() const { return error_; }
    void clear() { bindings_.clear(); error_.clear(); }
private:
    std::map<std::pair<Sex, std::string>, std::string> bindings_;
    std::string error_;
    bool fail(std::string reason) { bindings_.clear(); error_ = std::move(reason); return false; }
    static bool attributes(pugi::xml_node node, std::initializer_list<std::string_view> expected) {
        std::set<std::string_view> found;
        for (const auto attr : node.attributes())
            if (!found.insert(attr.name()).second || std::find(expected.begin(), expected.end(), attr.name()) == expected.end()) return false;
        return found.size() == expected.size();
    }
};
}
