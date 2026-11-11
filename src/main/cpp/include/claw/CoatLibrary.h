#pragma once
#include "claw/ColourMath.h"
#include <pugixml.hpp>
#include <array>
#include <charconv>
#include <cstdint>
#include <map>
#include <limits>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>
#include <span>

namespace claw::appearance {
inline constexpr std::string_view coatLibraryRelativePath = "SKSE/Plugins/CLAW/CoatLibrary.xml";
struct CoatSurface { std::string_view name, texture, group; };
inline constexpr std::array<CoatSurface, 12> coatSurfaces{{
    {"body", "body.dds", "undercoat"}, {"head", "head.dds", "undercoat"},
    {"fur_arms", "furarms.dds", "fur"}, {"fur_back", "furback.dds", "fur"},
    {"fur_belly", "furbelly.dds", "fur"}, {"fur_chest", "furchest.dds", "fur"},
    {"fur_face", "furface.dds", "fur"}, {"fur_shoulders", "furshoulders.dds", "fur"},
    {"fur_tailtip", "furtail.dds", "fur"}, {"ChestBlend", "furback.dds", "fur"},
    {"FurfaceBlend", "furface.dds", "fur"}, {"ScalpFurBlend", "furback.dds", "fur"}}};
inline bool coatToken(std::string_view value) {
    const auto stem = value.substr(0, value.find('.'));
    const bool reserved = stem == "con" || stem == "prn" || stem == "aux" || stem == "nul" ||
        (stem.size() == 4 && (stem.starts_with("com") || stem.starts_with("lpt")) && stem[3] >= '1' && stem[3] <= '9');
    return !reserved && !value.empty() && value.size() <= 64 && value.front() != '.' && value.back() != '.' &&
        value.find("..") == value.npos && std::all_of(value.begin(), value.end(), [](unsigned char c) {
            return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_' || c == '.';
        });
}
inline bool coatKey(std::string_view value) {
    const auto slash = value.find('/');
    return slash != value.npos && coatToken(value.substr(0, slash)) && coatToken(value.substr(slash + 1));
}
inline bool externalCoatPath(std::string_view path, std::string_view basename) {
    if (!path.starts_with("textures/") || path.size() > 240 || !path.ends_with("/" + std::string(basename))) return false;
    while (!path.empty()) {
        const auto next = path.find('/');
        std::string component(path.substr(0, next));
        for (auto& c : component) if (c >= 'A' && c <= 'Z') c += 'a' - 'A';
        if (!coatToken(component)) return false;
        if (next == path.npos) break;
        path.remove_prefix(next + 1);
    }
    return true;
}
inline bool coatDigest(std::string_view value) {
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](unsigned char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}
struct CoatSelection { std::uint32_t actor{}, base{}, sex{}; std::string pattern; };
inline std::vector<char> writeCoatSelection(const CoatSelection& value) {
    if (!value.actor || !value.base || value.sex > 1 || !coatKey(value.pattern)) throw std::invalid_argument("Invalid coat selection record");
    std::vector<char> bytes;
    for (const auto word : {value.actor, value.base, value.sex, static_cast<std::uint32_t>(value.pattern.size())})
        for (unsigned i = 0; i != 4; ++i) bytes.push_back(static_cast<char>((word >> (8 * i)) & 255));
    bytes.insert(bytes.end(), value.pattern.begin(), value.pattern.end()); return bytes;
}
inline CoatSelection readCoatSelection(std::span<const char> bytes) {
    if (bytes.size() <= 16 || bytes.size() > 145) throw std::invalid_argument("Invalid coat selection length");
    const auto word = [&](unsigned offset) {
        std::uint32_t value{};
        for (unsigned i = 0; i != 4; ++i) value |= std::uint32_t(static_cast<unsigned char>(bytes[offset + i])) << (8 * i);
        return value;
    };
    CoatSelection value{word(0), word(4), word(8), std::string(bytes.data() + 16, bytes.size() - 16)};
    if (word(12) != value.pattern.size() || !value.actor || !value.base || value.sex > 1 || !coatKey(value.pattern))
        throw std::invalid_argument("Invalid coat selection payload");
    return value;
}
struct CoatTexture { std::string path, sha256; std::uint32_t bytes{}; };
// Keep portable catalog/VFS paths separate from engine-bound texture names.
inline std::string coatEngineTexturePath(std::string_view path) {
    std::string result(path);
    std::replace(result.begin(), result.end(), '/', '\\');
    return result;
}
struct CoatDDSInfo {
    std::uint32_t width{}, height{}, mipLevels{};
    std::uint32_t headerBytes{128};
    std::optional<std::uint64_t> bytes;
};
inline std::optional<CoatDDSInfo> coatDDSHeader(std::span<const char> data) {
    if (data.size() < 128 || std::string_view(data.data(), 4) != "DDS ") return std::nullopt;
    const auto word = [&](unsigned offset) {
        std::uint32_t value{};
        for (unsigned i = 0; i != 4; ++i) value |= std::uint32_t(static_cast<unsigned char>(data[offset + i])) << (i * 8);
        return value;
    };
    CoatDDSInfo result{word(16), word(12), std::max(1U, word(28))};
    if (word(4) != 124 || word(76) != 32 || result.width == 0 || result.height == 0 ||
        result.width > 16384 || result.height > 16384 || (word(8) & 0x1007) != 0x1007 ||
        !(word(108) & 0x1000) || !word(80) ||
        word(24) > 1 || (word(8) & 0x800000) || (word(112) & (0xFE00 | 0x200000))) return std::nullopt;
    unsigned maxMips = 1;
    for (auto edge = std::max(result.width, result.height); edge > 1; edge /= 2) ++maxMips;
    if (result.mipLevels > maxMips) return std::nullopt;
    constexpr auto fourCC = [](char a, char b, char c, char d) {
        return std::uint32_t(a) | (std::uint32_t(b) << 8) | (std::uint32_t(c) << 16) | (std::uint32_t(d) << 24);
    };
    std::uint32_t blockBytes{};
    const auto format = word(84);
    if ((word(80) & 4) && format == fourCC('D', 'X', '1', '0')) {
        if (data.size() < 148 || word(132) != 3 || word(140) != 1 || (word(136) & 4)) return std::nullopt;
        switch (word(128)) {
            case 71: case 72: case 80: case 81: blockBytes = 8; break; // Typed BC1/BC4.
            case 74: case 75: case 77: case 78: case 83: case 84:
            case 95: case 96: case 98: case 99: blockBytes = 16; break; // Typed BC2/3/5/6/7.
            default: break; // The engine owns support for other pixel formats.
        }
        result.headerBytes = 148;
    } else if (word(80) & 4) {
        if (format == fourCC('D', 'X', 'T', '1')) blockBytes = 8;
        else if (format == fourCC('D', 'X', 'T', '3') || format == fourCC('D', 'X', 'T', '5')) blockBytes = 16;
    }
    if (!blockBytes) return result;
    result.bytes = result.headerBytes;
    auto width = result.width, height = result.height;
    for (unsigned level = 0; level < result.mipLevels; ++level) {
        *result.bytes += std::uint64_t((width + 3) / 4) * ((height + 3) / 4) * blockBytes;
        width = std::max(1U, width / 2); height = std::max(1U, height / 2);
    }
    // Bounded dimensions/mips above make the sum safe and permit any supported
    // resolution, including partial mip chains. No archive-specific size gate.
    return result;
}
inline std::optional<CoatDDSInfo> coatDDSMatches(std::uintmax_t bytes, std::span<const char> header) {
    const auto info = coatDDSHeader(header);
    return info && bytes > info->headerBytes && (!info->bytes || *info->bytes == bytes) ? info : std::nullopt;
}
struct CoatPattern {
    std::string id, label;
    std::optional<RGB> fur;
    std::map<std::string, CoatTexture, std::less<>> textures;
};
using CoatDimensions = std::map<std::string, CoatDDSInfo, std::less<>>;
// Every map must pass before any surface changes. Valid mixed resolutions are
// supported; catalog byte counts/digests remain source provenance only.
template<class Observe> std::optional<CoatDimensions> coatPatternDimensions(
    const CoatPattern& pattern, Observe&& observe) {
    if (pattern.textures.size() != 9) return std::nullopt;
    CoatDimensions dimensions;
    for (const auto& [name, texture] : pattern.textures) {
        const auto info = observe(texture);
        if (!info) return std::nullopt;
        dimensions.emplace(name, *info);
    }
    return dimensions;
}
// Source and measured palette coordinates are normalized sRGB. Compare in
// linear RGB, never compare a linear DDS mean with an encoded source directly.
inline double coatLinear(double value) {
    return value <= .04045 ? value / 12.92 : std::pow((value + .055) / 1.055, 2.4);
}
inline double coatDistance(const RGB& left, const RGB& right) {
    double sum{};
    for (unsigned i = 0; i < 3; ++i) { const auto delta = coatLinear(left[i]) - coatLinear(right[i]); sum += delta * delta; }
    return sum;
}
class CoatLibrary final {
public:
    static CoatLibrary parse(std::string_view xml) {
        if (xml.empty() || xml.size() > 1024 * 1024 || xml.find('&') != xml.npos ||
            xml.find("<!") != xml.npos || xml.find("<?") != xml.npos) fail("Expected bounded generated coat XML");
        for (const unsigned char ch : xml)
            if ((ch < 32 && ch != 9 && ch != 10 && ch != 13) || ch >= 127) fail("Coat XML must be printable ASCII");
        pugi::xml_document doc;
        if (!doc.load_buffer(xml.data(), xml.size(), pugi::parse_default, pugi::encoding_utf8)) fail("Malformed coat XML");
        const auto root = doc.document_element();
        const std::string_view schema = root.attribute("schemaVersion").value();
        if (std::string_view(root.name()) != "CoatLibrary" || !attributes(root, {"schemaVersion", "id", "sourceArchiveSha256"}) ||
            (schema != "1" && schema != "2")) fail("Unsupported coat schema");
        unsigned roots{}; for (const auto node : doc.children()) if (node.type() == pugi::node_element) ++roots;
        if (roots != 1) fail("Coat XML requires one root");
        CoatLibrary result; result.id_ = root.attribute("id").value();
        if (!coatToken(result.id_) || !coatDigest(root.attribute("sourceArchiveSha256").value())) fail("Invalid coat identity/digest");
        const auto surfaces = root.child("Surfaces"), patterns = root.child("Patterns");
        if (!surfaces || !patterns || root.first_child() != surfaces || surfaces.next_sibling() != patterns || patterns.next_sibling() ||
            surfaces.first_attribute() || patterns.first_attribute()) fail("Expected exact Surfaces and Patterns groups");
        std::set<std::string> surfaceNames;
        for (const auto node : surfaces.children()) {
            if (std::string_view(node.name()) != "Surface" || !attributes(node, {"name", "texture", "group"}) || node.first_child()) fail("Invalid coat surface");
            const std::string_view name = node.attribute("name").value();
            const auto found = std::find_if(coatSurfaces.begin(), coatSurfaces.end(), [name](const auto& value) { return value.name == name; });
            if (found == coatSurfaces.end() || found->texture != node.attribute("texture").value() ||
                found->group != node.attribute("group").value() || !surfaceNames.emplace(name).second) fail("Unsupported/duplicate coat surface map");
        }
        if (surfaceNames.size() != coatSurfaces.size()) fail("Incomplete coat surface map");
        std::set<std::string_view> textureNames; for (const auto& surface : coatSurfaces) textureNames.emplace(surface.texture);
        for (const auto node : patterns.children()) {
            const bool palette = bool(node.attribute("furR"));
            if (std::string_view(node.name()) != "Pattern" ||
                !(palette ? attributes(node, {"id", "label", "furR", "furG", "furB"}) : attributes(node, {"id", "label"}))) fail("Invalid coat pattern attributes");
            CoatPattern pattern; pattern.id = node.attribute("id").value(); pattern.label = node.attribute("label").value();
            if (!coatToken(pattern.id) || pattern.label.empty() || pattern.label.size() > 128) fail("Invalid coat pattern identity");
            if (palette) {
                pattern.fur = RGB{number(node.attribute("furR").value()), number(node.attribute("furG").value()), number(node.attribute("furB").value())};
                if (!valid(*pattern.fur)) fail("Invalid measured coat palette");
            }
            for (const auto texture : node.children()) {
                if (std::string_view(texture.name()) != "Texture" || !attributes(texture, {"name", "path", "bytes", "sha256"}) || texture.first_child()) fail("Invalid coat texture entry");
                const std::string name = texture.attribute("name").value();
                const std::string path = texture.attribute("path").value();
                const auto expected = "textures/actors/character/werewolf/claw/" + result.id_ + "/" + pattern.id + "/" + name;
                if (!textureNames.contains(name) || !(schema == "1" ? path == expected : externalCoatPath(path, name)) ||
                    !coatDigest(texture.attribute("sha256").value())) fail("Invalid coat DDS namespace/digest");
                std::uint32_t bytes{}; const std::string_view text = texture.attribute("bytes").value();
                const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), bytes);
                if (text.empty() || ec != std::errc{} || end != text.data() + text.size() || bytes < 128 || bytes > 64 * 1024 * 1024) fail("Invalid coat DDS size");
                if (!pattern.textures.emplace(name, CoatTexture{path, texture.attribute("sha256").value(), bytes}).second) fail("Duplicate coat texture");
            }
            if (pattern.textures.size() != textureNames.size()) fail("Incomplete coat textures");
            const auto key = result.id_ + "/" + pattern.id;
            if (!result.patterns_.emplace(key, std::move(pattern)).second || result.patterns_.size() > 64) fail("Duplicate/excessive coat patterns");
        }
        if (result.patterns_.empty()) fail("Empty coat library");
        return result;
    }
    [[nodiscard]] const CoatPattern* find(std::string_view key) const {
        const auto found = patterns_.find(key); return found == patterns_.end() ? nullptr : &found->second;
    }
    [[nodiscard]] std::string nearest(const RGB& hair) const {
        if (!valid(hair)) return {};
        std::string key; double best = std::numeric_limits<double>::infinity();
        // Ordered IDs supply a stable tie break, independent of manifest order.
        for (const auto& [candidate, pattern] : patterns_) if (pattern.fur) {
            const auto distance = coatDistance(hair, *pattern.fur);
            if (distance < best) { best = distance; key = candidate; }
        }
        return key;
    }
    [[nodiscard]] std::vector<std::string> names() const {
        std::vector<std::string> result; for (const auto& [key, value] : patterns_) { (void)value; result.push_back(key); } return result;
    }
private:
    std::string id_;
    std::map<std::string, CoatPattern, std::less<>> patterns_;
    [[noreturn]] static void fail(const char* message) { throw std::invalid_argument(message); }
    static float number(std::string_view text) {
        float value{}; const auto [end, ec] = std::from_chars(text.data(), text.data() + text.size(), value);
        if (text.empty() || ec != std::errc{} || end != text.data() + text.size() || !std::isfinite(value)) fail("Invalid finite palette coordinate");
        return value;
    }
    static bool attributes(pugi::xml_node node, std::initializer_list<std::string_view> expected) {
        std::set<std::string_view> found;
        for (const auto attr : node.attributes()) if (!found.emplace(attr.name()).second || std::find(expected.begin(), expected.end(), attr.name()) == expected.end()) return false;
        return found.size() == expected.size();
    }
};
}
