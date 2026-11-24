#pragma once
#include "claw/CoatPolicy.h"
#include "claw/CoatMatrix.h"
#include <sstream>

namespace claw::appearance {
inline constexpr std::string_view coatMappingRelativePath = "SKSE/Plugins/CLAW/CoatMapping.xml";
inline constexpr std::string_view installedCoatMaterial = "installed";

// Only this adapter knows how a numeric output relates to coat identifiers.
// The resource of a logical choice may be shared by any number of choices.
class CoatMapping final {
public:
    static CoatMapping unavailable(std::string reason) {
        CoatMapping result;
        result.error_ = std::move(reason);
        return result;
    }

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
                {"lightnessWeight", "chromaWeight", "available"}) : schema == "1" && coatXmlAttributes(root, {"schemaVersion", "output"})))
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
            if (const auto available = root.attribute("available")) {
                result.available_ = available.value();
                if (!coatToken(result.available_)) throw std::invalid_argument("Invalid colour availability output name");
            }
            if (root.attribute("lightnessWeight")) result.lightnessWeight_ = weight(root.attribute("lightnessWeight").value());
            if (root.attribute("chromaWeight")) result.chromaWeight_ = weight(root.attribute("chromaWeight").value());
            if (result.lightnessWeight_ == 0 && result.chromaWeight_ == 0)
                throw std::invalid_argument("Colour mapping requires a positive distance weight");
        }
        float lower{};
        for (const auto node : root.children()) {
            const auto tag = std::string_view(node.name());
            if (colour && (tag == "Group" || tag == "SkinGroup" || tag == "HairGroup" || tag == "PairRestriction")) continue;
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
        const auto parseGroups = [&](const char* tagName, std::vector<Group>& destination) {
            std::set<std::string> groupIds, members;
            for (const auto node : root.children(tagName)) {
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
                destination.push_back(std::move(group));
            }
        };
        if (colour) {
            parseGroups("Group", result.groups_);
            parseGroups("SkinGroup", result.skinGroups_);
            parseGroups("HairGroup", result.hairGroups_);
            if (result.groups_.empty()) throw std::invalid_argument("Missing colour groups");
            if (result.skinGroups_.empty() != result.hairGroups_.empty())
                throw std::invalid_argument("Regional coats require both skin and hair palettes");
            for (const auto node : root.children("PairRestriction")) {
                if (result.pairRestriction_ || !result.hasRegionalPalettes() ||
                    !coatXmlAttributes(node, {"skinGroups", "hairGroups", "bodyFallback", "hairFallback"}))
                    throw std::invalid_argument("Invalid coat pair restriction");
                auto& rule = result.pairRestriction_.emplace();
                rule.skinGroups = pairGroups(node.attribute("skinGroups").value(), result.skinGroups_);
                rule.hairGroups = pairGroups(node.attribute("hairGroups").value(), result.hairGroups_);
                for (const auto row : node.children()) {
                    const std::string_view id = row.attribute("id").value();
                    const auto resource = result.material(id);
                    if (std::string_view(row.name()) != "Pattern" || row.first_child() ||
                        !coatXmlAttributes(row, {"id"}) || resource.empty() || result.aliases_.contains(id) ||
                        !rule.materials.emplace(resource).second)
                        throw std::invalid_argument("Invalid restricted coat pattern");
                }
                if (rule.materials.empty()) throw std::invalid_argument("Empty coat pair restriction");
                const auto readFallback = [&](const char* name) {
                    const std::string id = node.attribute(name).value();
                    const auto resource = result.material(id);
                    if (resource.empty() || result.aliases_.contains(id) || rule.materials.contains(resource))
                        throw std::invalid_argument("Invalid coat pair fallback");
                    return id;
                };
                rule.bodyFallback = readFallback("bodyFallback");
                rule.hairFallback = readFallback("hairFallback");
            }
        }
        return result;
    }

    [[nodiscard]] const std::string& output() const { return output_; }
    [[nodiscard]] bool hasRegionalPalettes() const { return !skinGroups_.empty(); }
    void checkOutputs(const CoatValues& values) const {
        if (!values.contains(output_) || std::any_of(channels_.begin(), channels_.end(),
            [&](const auto& name) { return !values.contains(name); }))
            throw std::invalid_argument("Coat mapping requests an absent matrix output");
        if (hasRegionalPalettes()) for (const auto& region : {skinChannels, hairChannels})
            for (const auto channel : region) if (!values.contains(channel))
                throw std::invalid_argument("Regional coat mapping requests an absent colour output");
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
        if (!error_.empty())
            return {{}, {}, manual.empty() ? CoatOrigin::none : CoatOrigin::manual, error_};
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
        const auto available = available_.empty() ? values.end() : values.find(available_);
        const bool hasAvailability = available != values.end();
        if (hasAvailability && available->second != 0.F && available->second != 1.F)
            return {{}, {}, CoatOrigin::none, "invalid coat colour availability output"};
        // A separately installed older matrix may lack the optional output.
        const bool useColour = hasAvailability ? available->second == 1.F : hasHair;
        if (!useColour || channels_.empty()) {
            const auto found = values.find(output_);
            return select({}, found == values.end() ? std::optional<float>{} : found->second, useColour);
        }
        std::array<float, 4> input{};
        for (std::size_t i = 0; i < input.size(); ++i) {
            const auto found = values.find(channels_[i]);
            if (found == values.end() || !std::isfinite(found->second) || found->second < 0 || found->second > 1)
                return {{}, {}, CoatOrigin::none, "coat colour output unavailable or outside [0,1]"};
            input[i] = found->second;
        }
        return nearest({input[0], input[1], input[2]}, input[3], groups_, lightnessWeight_, chromaWeight_,
            hasAvailability ? CoatOrigin::colourPool : CoatOrigin::hairPool);
    }
    [[nodiscard]] CoatDecision selectRegional(const CoatValues& values, bool hair) const {
        const auto& groups = hair ? hairGroups_ : skinGroups_;
        if (groups.empty()) return {};
        const auto& names = hair ? hairChannels : skinChannels;
        RGB rgb{};
        for (std::size_t i = 0; i < rgb.size(); ++i) {
            const auto value = values.find(names[i]);
            if (value == values.end() || !std::isfinite(value->second) || value->second < 0.F || value->second > 1.F)
                return {};
            rgb[i] = value->second;
        }
        const auto seed = values.find(channels_.back());
        if (seed == values.end() || !std::isfinite(seed->second) || seed->second < 0.F || seed->second > 1.F) return {};
        return nearest(rgb, seed->second, groups, 1.F, hair ? 12.F : 4.F, CoatOrigin::colourPool);
    }
    [[nodiscard]] CoatDecision selectForAppearance(std::string_view manual, const CoatValues& values,
        const Colours& colours, bool hairRegion = false) const {
        if (!manual.empty()) return selectOutputs(manual, values, colours.hasHair);
        const bool useRegional = hasRegionalPalettes() && (colours.hasSkin || colours.hasHair);
        const bool useHair = hairRegion || (colours.hasHair && !colours.hasSkin);
        auto choice = useRegional ? selectRegional(values, useHair) : selectOutputs({}, values, colours.hasHair);
        if (!pairRestriction_ || !pairRestriction_->materials.contains(material(choice.pattern))) return choice;

        // Numeric outputs for an absent source can be zero. Only real captured
        // colours can satisfy the restriction on both axes.
        const auto& rule = *pairRestriction_;
        if (colours.hasSkin && colours.hasHair &&
            rule.skinGroups.contains(selectRegional(values, false).pool) &&
            rule.hairGroups.contains(selectRegional(values, true).pool)) return choice;
        choice.pattern = useHair ? rule.hairFallback : rule.bodyFallback;
        return choice;
    }
private:
    struct Range { float maximum; std::string id; };
    struct Group { std::string id; std::vector<std::array<double, 3>> anchors; std::vector<std::string> variants; };
    using NameSet = std::set<std::string, std::less<>>;
    struct PairRestriction {
        NameSet skinGroups, hairGroups, materials;
        std::string bodyFallback, hairFallback;
    };
    static NameSet pairGroups(const char* list, const std::vector<Group>& palette) {
        std::istringstream input{list};
        NameSet result;
        for (std::string id; input >> id;) {
            if (std::none_of(palette.begin(), palette.end(), [&](const Group& group) { return group.id == id; }) ||
                !result.insert(id).second)
                throw std::invalid_argument("Unknown or duplicate coat pair group");
        }
        if (result.empty()) throw std::invalid_argument("Empty coat pair group list");
        return result;
    }
    static constexpr std::array<std::string_view, 3> skinChannels{"dye.body.red", "dye.body.green", "dye.body.blue"};
    static constexpr std::array<std::string_view, 3> hairChannels{"dye.hair.red", "dye.hair.green", "dye.hair.blue"};
    static CoatDecision nearest(const RGB& rgb, float seed, const std::vector<Group>& groups,
        float lightnessWeight, float chromaWeight, CoatOrigin origin) {
        const auto colour = oklab(rgb);
        const Group* selected{};
        double best = std::numeric_limits<double>::infinity();
        // Declared group/anchor order supplies deterministic ties. Seed cannot affect this choice.
        for (const auto& group : groups) for (const auto& anchor : group.anchors) {
            const auto l = colour[0] - anchor[0], a = colour[1] - anchor[1], b = colour[2] - anchor[2];
            const auto distance = lightnessWeight * l * l + chromaWeight * (a * a + b * b);
            if (distance < best) { best = distance; selected = &group; }
        }
        if (!selected) return {{}, {}, CoatOrigin::none, "coat colour group unavailable"};
        const auto index = std::min(static_cast<std::size_t>(double(seed) * selected->variants.size()), selected->variants.size() - 1);
        return {selected->variants[index], selected->id, origin, {}, seed};
    }
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
    std::string error_, output_, available_;
    std::vector<std::string> channels_;
    std::vector<Group> groups_, skinGroups_, hairGroups_;
    std::optional<PairRestriction> pairRestriction_;
    float lightnessWeight_{1}, chromaWeight_{1};
    std::vector<Range> ranges_;
    std::set<std::string, std::less<>> aliases_;
    std::map<std::string, std::string, std::less<>> resources_;
};
}
