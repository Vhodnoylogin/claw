#include "claw/Preset.h"
#include <pugixml.hpp>
#include <algorithm>
#include <array>
#include <charconv>
#include <cctype>
#include <cmath>
#include <fstream>
#include <iterator>
#include <optional>
#include <set>
#include <stdexcept>

namespace claw {
namespace {
constexpr std::array commonMorphs{
    "CLAWArmClawLong", "CLAWArmGirth", "CLAWArmPawSize", "CLAWHeadEarSize",
    "CLAWHeadEarTilt", "CLAWHeadMuzzleLong", "CLAWHeadMuzzleWide", "CLAWHeadSize",
    "CLAWLegCalfGirth", "CLAWLegClawLong", "CLAWLegDigitigrade", "CLAWLegPawSize",
    "CLAWLegThighGirth", "CLAWTailFluff", "CLAWTailLength", "CLAWTailLift",
    "CLAWTorsoBackWide", "CLAWTorsoBellyRound", "CLAWTorsoChestSize", "CLAWTorsoFlankWidth",
    "CLAWTorsoGirth", "CLAWTorsoNeckGirth", "CLAWTorsoShoulderGirth", "CLAWTorsoWaistNarrow",
    "CLAWArmLean", "CLAWLegThighLean", "CLAWLegCalfLean", "CLAWTorsoLean"
};
constexpr std::size_t maxFileBytes = 1024 * 1024;
constexpr std::size_t maxPresets = 4096;

float percentage(std::string_view text) {
    float value{};
    const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
    if (text.empty() || error != std::errc{} || end != text.data() + text.size() ||
        !std::isfinite(value) || value < 0 || value > 100) {
        throw std::invalid_argument("slider value must be a finite percentage in 0..100");
    }
    return value / 100.0F;
}

bool validName(std::string_view name) {
    if (name.empty() || name.size() > 160) return false;
    constexpr std::string_view trim = " \t\r\n\f\v";
    if (trim.find(name.front()) != trim.npos || trim.find(name.back()) != trim.npos) return false;
    return std::none_of(name.begin(), name.end(), [](unsigned char ch) { return ch < 32 || ch == 127; });
}

bool xmlCharacter(std::uint32_t value) {
    return value == 9 || value == 10 || value == 13 || (value >= 0x20 && value <= 0xD7FF) ||
        (value >= 0xE000 && value <= 0xFFFD) || (value >= 0x10000 && value <= 0x10FFFF);
}

bool strictUtf8Xml(std::string_view text) {
    for (std::size_t index = 0; index < text.size();) {
        const auto lead = static_cast<unsigned char>(text[index++]);
        std::uint32_t value = lead, minimum{}; int continuation{};
        if (lead < 0x80) {}
        else if (lead >= 0xC2 && lead <= 0xDF) { value = lead & 0x1F; continuation = 1; minimum = 0x80; }
        else if (lead >= 0xE0 && lead <= 0xEF) { value = lead & 0x0F; continuation = 2; minimum = 0x800; }
        else if (lead >= 0xF0 && lead <= 0xF4) { value = lead & 7; continuation = 3; minimum = 0x10000; }
        else return false;
        for (int count = 0; count < continuation; ++count) {
            if (index >= text.size()) return false;
            const auto next = static_cast<unsigned char>(text[index++]);
            if ((next & 0xC0) != 0x80) return false;
            value = (value << 6) | (next & 0x3F);
        }
        if (value < minimum || !xmlCharacter(value)) return false;
    }
    // Pugixml is deliberately permissive about references. Validate references
    // outside comments/CDATA/processing instructions before decoded NULs or
    // undeclared entities can be accepted as an ordinary preset name.
    for (std::size_t start = 0; start < text.size();) {
        if (text.substr(start, 4) == "<!--") {
            const auto end = text.find("-->", start + 4); if (end == text.npos) return false;
            start = end + 3; continue;
        }
        if (text.substr(start, 9) == "<![CDATA[") {
            const auto end = text.find("]]>", start + 9); if (end == text.npos) return false;
            start = end + 3; continue;
        }
        if (text.substr(start, 2) == "<?") {
            const auto end = text.find("?>", start + 2); if (end == text.npos) return false;
            start = end + 2; continue;
        }
        if (text[start] != '&') { ++start; continue; }
        const auto end = text.find(';', start + 1);
        if (end == text.npos) return false;
        const auto reference = text.substr(start + 1, end - start - 1);
        if (!reference.empty() && reference.front() == '#') {
            auto first = start + 2; int base = 10;
            if (first < end && text[first] == 'x') { ++first; base = 16; }
            std::uint32_t value{};
            const auto [parsed, error] = std::from_chars(text.data() + first, text.data() + end, value, base);
            if (first == end || error != std::errc{} || parsed != text.data() + end || !xmlCharacter(value)) return false;
        } else if (reference != "amp" && reference != "lt" && reference != "gt" && reference != "apos" && reference != "quot") return false;
        start = end + 1;
    }
    return true;
}

void attributes(pugi::xml_node node, std::initializer_list<std::string_view> allowed) {
    std::set<std::string_view> seen;
    for (const auto attribute : node.attributes()) {
        if (!seen.emplace(attribute.name()).second) throw std::invalid_argument("duplicate XML attribute");
        if (std::find(allowed.begin(), allowed.end(), attribute.name()) == allowed.end()) {
            throw std::invalid_argument("unexpected attribute: " + std::string(attribute.name()));
        }
    }
}
}

std::uint64_t stableHash(std::string_view identity) {
    std::uint64_t hash = 14695981039346656037ULL;
    for (const unsigned char ch : identity) { hash ^= ch; hash *= 1099511628211ULL; }
    return hash;
}

std::vector<std::string_view> recognizedMorphs(Sex sex) {
    std::vector<std::string_view> names(commonMorphs.begin(), commonMorphs.end());
    if (sex == Sex::female) names.push_back("CLAWTorsoBreastSize");
    return names;
}

bool recognizedMorph(std::string_view name, Sex sex) {
    const auto names = recognizedMorphs(sex);
    return std::find(names.begin(), names.end(), name) != names.end();
}

bool Catalog::fail(std::string source, std::string reason) {
    errors_.push_back({std::move(source), std::move(reason)});
    return false;
}

void Catalog::clear() { presets_.clear(); errors_.clear(); }

bool Catalog::loadXml(std::string_view xml, std::string source) {
    if (xml.size() > maxFileBytes) return fail(source, "XML exceeds 1 MiB");
    if (!strictUtf8Xml(xml)) return fail(source, "XML must be strict UTF-8 with legal XML characters");
    if (xml.find("<!DOCTYPE") != std::string_view::npos || xml.find("<!ENTITY") != std::string_view::npos)
        return fail(source, "DTD/entities are unsupported");
    pugi::xml_document document;
    const auto parsed = document.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8);
    if (!parsed) return fail(source, "invalid XML: " + std::string(parsed.description()));
    const auto root = document.document_element();
    if (std::string_view(root.name()) != "SliderPresets") return fail(source, "root must be SliderPresets");
    try {
        std::size_t roots{};
        for (const auto node : document.children()) {
            if (node.type() == pugi::node_element) ++roots;
            else if (node.type() == pugi::node_pcdata || node.type() == pugi::node_cdata)
                throw std::invalid_argument("text outside document root");
        }
        if (roots != 1) throw std::invalid_argument("exactly one document root is required");
        attributes(root, {"version"});
        bool foundPreset = false;
        for (const auto node : root.children()) {
            if (node.type() != pugi::node_element) throw std::invalid_argument("unexpected text in SliderPresets");
            if (std::string_view(node.name()) != "Preset") throw std::invalid_argument("unexpected SliderPresets child");
            attributes(node, {"name", "set"});
            Preset preset;
            preset.name = node.attribute("name").value();
            preset.source = source;
            const std::string_view family = node.attribute("set").value();
            if (family == "CLAW Male") preset.sex = Sex::male;
            else if (family == "CLAW Female") preset.sex = Sex::female;
            else throw std::invalid_argument("set must be CLAW Male or CLAW Female");
            if (!validName(preset.name)) throw std::invalid_argument("preset name must be trimmed, nonempty, at most 160 UTF-8 bytes and without controls");
            if (presets_.contains(preset.name)) throw std::invalid_argument("duplicate preset name: " + preset.name);
            std::set<std::pair<std::string, bool>> seen;
            for (const auto slider : node.children()) {
                if (slider.type() != pugi::node_element) throw std::invalid_argument("unexpected text in Preset");
                const std::string_view element = slider.name();
                if (element == "Group") {
                    attributes(slider, {"name"});
                    if (!slider.attribute("name") || slider.first_child()) throw std::invalid_argument("invalid Group element");
                    continue;
                }
                if (element != "SetSlider") throw std::invalid_argument("unexpected Preset child: " + std::string(element));
                attributes(slider, {"name", "size", "value"});
                const std::string morph = slider.attribute("name").value();
                if (!recognizedMorph(morph, preset.sex)) throw std::invalid_argument("unknown, adult or wrong-sex morph: " + morph);
                const std::string_view size = slider.attribute("size").value();
                if (size != "small" && size != "big") throw std::invalid_argument("size must be small or big");
                const bool high = size == "big";
                if (!seen.emplace(morph, high).second) throw std::invalid_argument("duplicate slider endpoint: " + morph);
                auto& endpoint = preset.sliders[morph];
                (high ? endpoint.high : endpoint.low) = percentage(slider.attribute("value").value());
                if (slider.first_child()) throw std::invalid_argument("SetSlider must have no children");
            }
            // A typed BodySlide preset with no SetSlider is the neutral body.
            if (presets_.size() >= maxPresets) throw std::invalid_argument("too many presets");
            presets_.emplace(preset.name, std::move(preset));
            foundPreset = true;
        }
        if (!foundPreset) throw std::invalid_argument("XML has no presets");
    } catch (const std::exception& error) { return fail(source, error.what()); }
    return true;
}

bool Catalog::loadDirectory(const std::filesystem::path& directory) {
    clear();
    std::vector<std::filesystem::path> files;
    try {
        // Enumeration/open also work through MO2 usvfs; avoid a separate attribute
        // probe which can reject a directory that only exists in the merged view.
        for (const auto& entry : std::filesystem::recursive_directory_iterator(directory)) {
            if (entry.is_symlink()) return fail(entry.path().string(), "symlink entries are unsupported");
            if (!entry.is_regular_file()) continue;
            auto extension = entry.path().extension().string();
            std::transform(extension.begin(), extension.end(), extension.begin(), [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
            if (extension == ".xml") files.push_back(entry.path());
            if (files.size() > maxPresets) return fail(directory.string(), "too many preset files");
        }
        std::sort(files.begin(), files.end());
        for (const auto& file : files) {
            std::ifstream stream(file, std::ios::binary);
            if (!stream) { fail(file.string(), "cannot read preset XML"); continue; }
            std::string xml(maxFileBytes + 1, '\0');
            stream.read(xml.data(), static_cast<std::streamsize>(xml.size()));
            xml.resize(static_cast<std::size_t>(stream.gcount()));
            if (stream.bad()) { fail(file.string(), "failed while reading preset XML"); continue; }
            loadXml(xml, file.string());
        }
        if (files.empty()) fail(directory.string(), "no CLAW XML presets found");
    } catch (const std::exception& error) { fail(directory.string(), error.what()); }
    return valid();
}

const Preset* Catalog::find(std::string_view name, Sex sex) const {
    if (!valid()) return nullptr;
    const auto found = presets_.find(name);
    return found != presets_.end() && found->second.sex == sex ? &found->second : nullptr;
}

std::vector<std::string> Catalog::names(Sex sex) const {
    std::vector<std::string> result;
    if (valid()) for (const auto& [name, preset] : presets_) if (preset.sex == sex) result.push_back(name);
    return result;
}

const Preset* Catalog::choose(std::string_view identity, Sex sex) const {
    const auto candidates = names(sex);
    return candidates.empty() ? nullptr : find(candidates[stableHash(identity) % candidates.size()], sex);
}

Morphs interpolate(const Preset& preset, float weight) {
    if (!std::isfinite(weight) || weight < 0 || weight > 100) throw std::invalid_argument("actor weight must be finite in 0..100");
    Morphs result;
    for (const auto& [name, endpoints] : preset.sliders)
        result.emplace(name, endpoints.low + (endpoints.high - endpoints.low) * weight / 100.0F);
    return result;
}

bool verifyOwnMorphs(const Morphs& expected,
                    const std::function<float(std::string_view)>& read, float tolerance) {
    if (!std::isfinite(tolerance) || tolerance < 0) return false;
    for (const auto& [name, value] : expected)
        if (!recognizedMorph(name, Sex::female) || !std::isfinite(value)) return false;
    for (const auto name : recognizedMorphs(Sex::female)) {
        const auto found = expected.find(name);
        const float wanted = found == expected.end() ? 0 : found->second;
        const float actual = read(name);
        if (!std::isfinite(actual) || std::abs(actual - wanted) > tolerance) return false;
    }
    return true;
}

std::string jsonString(std::string_view value) {
    std::string output = "\"";
    for (const unsigned char ch : value) {
        if (ch == '"' || ch == '\\') { output += '\\'; output += static_cast<char>(ch); }
        else if (ch == '\n') output += "\\n";
        else if (ch == '\r') output += "\\r";
        else if (ch == '\t') output += "\\t";
        else if (ch < 32) output += "?";
        else output += static_cast<char>(ch);
    }
    return output + '"';
}
}
