#pragma once
#include "claw/CoatPolicy.h"

namespace claw::appearance {
inline constexpr std::string_view coatMappingRelativePath = "SKSE/Plugins/CLAW/CoatMapping.xml";
inline constexpr std::string_view installedCoatMaterial = "installed";

// Only this adapter knows how a numeric output relates to coat identifiers.
// The resource of a logical choice may be shared by any number of choices.
class CoatMapping final {
public:
    static CoatMapping parse(std::string_view xml) {
        if (xml.empty() || xml.size() > 65536 || xml.find('&') != xml.npos ||
            xml.find("<!") != xml.npos || xml.find("<?") != xml.npos ||
            std::any_of(xml.begin(), xml.end(), [](unsigned char c) { return (c < 32 && c != 9 && c != 10 && c != 13) || c == 127; }))
            throw std::invalid_argument("Invalid coat mapping XML");
        pugi::xml_document doc;
        if (!doc.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8))
            throw std::invalid_argument("Malformed coat mapping XML");
        const auto root = doc.document_element();
        if (std::string_view(root.name()) != "CoatMapping" || root.next_sibling() ||
            !coatXmlAttributes(root, {"schemaVersion", "output"}) || std::string_view(root.attribute("schemaVersion").value()) != "1")
            throw std::invalid_argument("Unsupported coat mapping schema");
        CoatMapping result;
        result.output_ = root.attribute("output").value();
        if (!coatToken(result.output_)) throw std::invalid_argument("Invalid coat matrix output name");
        float lower{};
        for (const auto node : root.children()) {
            const auto tag = std::string_view(node.name());
            const bool range = tag == "Range";
            if (node.first_child() || !(range ? coatXmlAttributes(node, {"id", "min", "max", "material"}) :
                (tag == "Manual" || tag == "Alias") && coatXmlAttributes(node, {"id", "material"})))
                throw std::invalid_argument("Invalid coat mapping entry");
            const std::string id = node.attribute("id").value(), resource = node.attribute("material").value();
            if (!coatKey(id) || (resource != installedCoatMaterial && !coatKey(resource)) ||
                !result.resources_.emplace(id, resource).second || result.resources_.size() > 128)
                throw std::invalid_argument("Invalid or duplicate coat mapping identity");
            if (tag == "Alias") result.aliases_.insert(id);
            if (range) {
                const float minimum = bound(node.attribute("min").value()), maximum = bound(node.attribute("max").value());
                if (minimum != lower || maximum <= minimum)
                    throw std::invalid_argument("Coat ranges must be ascending, contiguous and disjoint");
                result.ranges_.push_back({maximum, id});
                lower = maximum;
            }
        }
        if (lower != 1.0F) throw std::invalid_argument("Coat ranges must cover [0,1]");
        return result;
    }

    [[nodiscard]] const std::string& output() const { return output_; }
    [[nodiscard]] bool usesExternalMaterials() const {
        return std::any_of(resources_.begin(), resources_.end(), [](const auto& entry) {
            return entry.second != installedCoatMaterial;
        });
    }
    void checkMaterials(const CoatLibrary& catalog) const {
        for (const auto& [id, resource] : resources_) {
            if (resource != installedCoatMaterial && !catalog.find(resource))
                throw std::invalid_argument("Unknown catalog material for coat " + id);
        }
    }
    [[nodiscard]] std::vector<std::string> names() const {
        std::vector<std::string> result;
        for (const auto& [id, resource] : resources_) if (!aliases_.contains(id)) result.push_back(id);
        return result;
    }
    [[nodiscard]] std::string_view material(std::string_view id) const {
        const auto found = resources_.find(id);
        return found == resources_.end() ? std::string_view{} : std::string_view(found->second);
    }
    [[nodiscard]] CoatDecision select(std::string_view manual, std::optional<float> output, bool hasHair) const {
        if (!manual.empty()) {
            if (!material(manual).empty()) return {std::string(manual), {}, CoatOrigin::manual, {}};
            return {{}, {}, CoatOrigin::manual, "manual pattern unavailable"};
        }
        if (!output || !std::isfinite(*output) || *output < 0.0F || *output > 1.0F || ranges_.empty())
            return {{}, {}, CoatOrigin::none, "coat matrix output unavailable or outside [0,1]"};
        // Internal upper edges belong to the next range. The last includes 1.
        const auto range = std::upper_bound(ranges_.begin(), ranges_.end(), *output,
            [](float value, const Range& row) { return value < row.maximum; });
        return {(range == ranges_.end() ? ranges_.back() : *range).id, "matrix",
            hasHair ? CoatOrigin::hairPool : CoatOrigin::fallback, {}};
    }
private:
    struct Range { float maximum; std::string id; };
    static float bound(std::string_view text) {
        float value{};
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
        if (error != std::errc{} || end != text.data() + text.size() || !std::isfinite(value) || value < 0 || value > 1)
            throw std::invalid_argument("Invalid normalized coat range boundary");
        return value;
    }
    std::string output_;
    std::vector<Range> ranges_;
    std::set<std::string, std::less<>> aliases_;
    std::map<std::string, std::string, std::less<>> resources_;
};
}
