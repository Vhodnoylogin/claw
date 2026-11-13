#pragma once
#include "claw/CoatPolicy.h"
#include "claw/CoatMatrix.h"

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
        const std::string_view schema = root.attribute("schemaVersion").value();
        const bool colour = schema == "2";
        if (std::string_view(root.name()) != "CoatMapping" || root.next_sibling() ||
            !(colour ? coatXmlAttributes(root, {"schemaVersion", "output", "red", "green", "blue", "seed"},
                {"lightnessWeight", "chromaWeight"}) : schema == "1" && coatXmlAttributes(root, {"schemaVersion", "output"})))
            throw std::invalid_argument("Unsupported coat mapping schema");
        CoatMapping result;
        result.output_ = root.attribute("output").value();
        if (!coatToken(result.output_)) throw std::invalid_argument("Invalid coat matrix output name");
        if (colour) {
            for (const auto name : {"red", "green", "blue", "seed"}) {
                const std::string value = root.attribute(name).value();
                if (!coatToken(value)) throw std::invalid_argument("Invalid colour mapping output name");
                result.channels_.push_back(value);
            }
            if (root.attribute("lightnessWeight")) result.lightnessWeight_ = weight(root.attribute("lightnessWeight").value());
            if (root.attribute("chromaWeight")) result.chromaWeight_ = weight(root.attribute("chromaWeight").value());
            if (result.lightnessWeight_ == 0 && result.chromaWeight_ == 0)
                throw std::invalid_argument("Colour mapping requires a positive distance weight");
        }
        float lower{};
        for (const auto node : root.children()) {
            const auto tag = std::string_view(node.name());
            if (colour && tag == "Group") continue; // Resolve members only after all logical IDs exist.
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
        if (colour) {
            std::set<std::string> groupIds, members;
            for (const auto node : root.children("Group")) {
                const std::string id = node.attribute("id").value();
                if (!coatXmlAttributes(node, {"id"}) || !coatToken(id) || !groupIds.insert(id).second || groupIds.size() > 16)
                    throw std::invalid_argument("Invalid or duplicate colour group");
                Group group; group.id = id;
                for (const auto row : node.children()) {
                    const std::string_view tag = row.name();
                    if (row.first_child()) throw std::invalid_argument("Nested colour group entry");
                    if (tag == "Anchor" && coatXmlAttributes(row, {"red", "green", "blue"})) {
                        group.anchors.push_back(oklab({bound(row.attribute("red").value()), bound(row.attribute("green").value()),
                            bound(row.attribute("blue").value())}));
                        if (group.anchors.size() > 16) throw std::invalid_argument("Excessive colour group anchors");
                    } else if (tag == "Variant" && coatXmlAttributes(row, {"id"})) {
                        const std::string member = row.attribute("id").value();
                        if (!result.resources_.contains(member) || result.aliases_.contains(member) || !members.insert(member).second)
                            throw std::invalid_argument("Unknown, duplicate or overlapping colour variant");
                        group.variants.push_back(member);
                    } else throw std::invalid_argument("Invalid colour group entry");
                }
                if (group.anchors.empty() || group.variants.empty()) throw std::invalid_argument("Empty colour group");
                result.groups_.push_back(std::move(group));
            }
            if (result.groups_.empty()) throw std::invalid_argument("Missing colour groups");
        }
        return result;
    }

    [[nodiscard]] const std::string& output() const { return output_; }
    void checkOutputs(const CoatValues& values) const {
        if (!values.contains(output_) || std::any_of(channels_.begin(), channels_.end(),
            [&](const auto& name) { return !values.contains(name); }))
            throw std::invalid_argument("Coat mapping requests an absent matrix output");
    }
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
    [[nodiscard]] CoatDecision selectOutputs(std::string_view manual, const CoatValues& values, bool hasHair) const {
        if (!manual.empty()) return select(manual, {}, hasHair);
        if (!hasHair || channels_.empty()) {
            const auto found = values.find(output_);
            return select({}, found == values.end() ? std::optional<float>{} : found->second, hasHair);
        }
        std::array<float, 4> input{};
        for (std::size_t i = 0; i < input.size(); ++i) {
            const auto found = values.find(channels_[i]);
            if (found == values.end() || !std::isfinite(found->second) || found->second < 0 || found->second > 1)
                return {{}, {}, CoatOrigin::none, "coat colour output unavailable or outside [0,1]"};
            input[i] = found->second;
        }
        const auto colour = oklab({input[0], input[1], input[2]});
        const Group* selected{};
        double best = std::numeric_limits<double>::infinity();
        // Declared group/anchor order supplies deterministic ties. Seed cannot affect this choice.
        for (const auto& group : groups_) for (const auto& anchor : group.anchors) {
            const auto l = colour[0] - anchor[0], a = colour[1] - anchor[1], b = colour[2] - anchor[2];
            const auto distance = lightnessWeight_ * l * l + chromaWeight_ * (a * a + b * b);
            if (distance < best) { best = distance; selected = &group; }
        }
        if (!selected) return {{}, {}, CoatOrigin::none, "coat colour group unavailable"};
        const auto index = std::min(static_cast<std::size_t>(double(input[3]) * selected->variants.size()), selected->variants.size() - 1);
        return {selected->variants[index], selected->id, CoatOrigin::hairPool, {}};
    }
private:
    struct Range { float maximum; std::string id; };
    struct Group { std::string id; std::vector<std::array<double, 3>> anchors; std::vector<std::string> variants; };
    // Standard Oklab conversion of normalized encoded sRGB. This material adapter,
    // not the shared numerical matrix, owns colour-space interpretation.
    static std::array<double, 3> oklab(const RGB& rgb) {
        const auto r = coatLinear(rgb[0]), g = coatLinear(rgb[1]), b = coatLinear(rgb[2]);
        const auto l = std::cbrt(.4122214708 * r + .5363325363 * g + .0514459929 * b);
        const auto m = std::cbrt(.2119034982 * r + .6806995451 * g + .1073969566 * b);
        const auto s = std::cbrt(.0883024619 * r + .2817188376 * g + .6299787005 * b);
        return {.2104542553 * l + .7936177850 * m - .0040720468 * s,
            1.9779984951 * l - 2.4285922050 * m + .4505937099 * s,
            .0259040371 * l + .7827717662 * m - .8086757660 * s};
    }
    static float weight(std::string_view text) {
        float value{};
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
        if (error != std::errc{} || end != text.data() + text.size() || !std::isfinite(value) || value < 0 || value > 1024)
            throw std::invalid_argument("Invalid colour distance weight");
        return value;
    }
    static float bound(std::string_view text) {
        float value{};
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
        if (error != std::errc{} || end != text.data() + text.size() || !std::isfinite(value) || value < 0 || value > 1)
            throw std::invalid_argument("Invalid normalized coat range boundary");
        return value;
    }
    std::string output_;
    std::vector<std::string> channels_;
    std::vector<Group> groups_;
    float lightnessWeight_{1}, chromaWeight_{1};
    std::vector<Range> ranges_;
    std::set<std::string, std::less<>> aliases_;
    std::map<std::string, std::string, std::less<>> resources_;
};
}
