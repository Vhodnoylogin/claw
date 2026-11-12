#pragma once

#include <cstdint>
#include <filesystem>
#include <functional>
#include <map>
#include <string>
#include <string_view>
#include <vector>

namespace claw {
enum class Sex : std::uint8_t { male, female };
inline constexpr auto morphKey = "CLAW.Distribution";
inline constexpr auto presetRelativePath = "CalienteTools/BodySlide/SliderPresets/CLAW";

struct Endpoints {
    float low{};
    float high{};
};
// Provider-bound names follow SKEE identity; keep the first authored spelling.
// This belongs to the morph adapter, not the semantic-neutral numerical kernel.
struct MorphNameLess {
    using is_transparent = void;
    static constexpr unsigned char fold(unsigned char value) noexcept {
        return value >= 'A' && value <= 'Z' ? static_cast<unsigned char>(value + ('a' - 'A')) : value;
    }
    bool operator()(std::string_view left, std::string_view right) const noexcept {
        const auto count = left.size() < right.size() ? left.size() : right.size();
        for (std::size_t index = 0; index < count; ++index) {
            const auto a = fold(static_cast<unsigned char>(left[index]));
            const auto b = fold(static_cast<unsigned char>(right[index]));
            if (a != b) return a < b;
        }
        return left.size() < right.size();
    }
};
using Morphs = std::map<std::string, float, MorphNameLess>;

struct Preset {
    std::string name;
    Sex sex{};
    std::map<std::string, Endpoints, MorphNameLess> sliders;
    std::string source;
};

struct Diagnostic {
    std::string source;
    std::string reason;
};

class Catalog {
public:
    // A catalog containing any invalid file/preset is unusable (fail closed).
    bool loadDirectory(const std::filesystem::path& directory);
    bool loadXml(std::string_view xml, std::string source);
    void clear();
    [[nodiscard]] const Preset* find(std::string_view name, Sex sex) const;
    [[nodiscard]] const Preset* choose(std::string_view identity, Sex sex) const;
    [[nodiscard]] std::vector<std::string> names(Sex sex) const;
    [[nodiscard]] const std::vector<Diagnostic>& diagnostics() const { return errors_; }
    [[nodiscard]] bool valid() const { return errors_.empty() && !presets_.empty(); }
    [[nodiscard]] std::size_t size() const { return valid() ? presets_.size() : 0; }
private:
    bool fail(std::string source, std::string reason);
    std::map<std::string, Preset, std::less<>> presets_;
    std::vector<Diagnostic> errors_;
};

[[nodiscard]] bool recognizedMorph(std::string_view name, Sex sex);
[[nodiscard]] std::vector<std::string_view> recognizedMorphs(Sex sex);
[[nodiscard]] Morphs interpolate(const Preset& preset, float actorWeight);
// Verify the entire owned public allowlist; omitted/sparse values must read zero.
[[nodiscard]] bool verifyOwnMorphs(const Morphs& expected,
    const std::function<float(std::string_view)>& read, float tolerance = 0.0001F);
[[nodiscard]] std::uint64_t stableHash(std::string_view identity);
[[nodiscard]] std::string jsonString(std::string_view value);
}
