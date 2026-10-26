#include "claw/Preset.h"
#include "claw/MorphProfiles.h"
#include <charconv>
#include <iostream>

int main(int argc, char** argv) {
    if (argc == 3 && std::string_view(argv[1]) == "families") {
        claw::MorphProfileCatalog profiles;
        if (!profiles.loadFile(argv[2])) { std::cerr << profiles.error() << '\n'; return 2; }
        std::cout << "{\"profiles\":["; bool first = true;
        for (const auto sex : {claw::Sex::male, claw::Sex::female}) {
            for (const auto& id : profiles.names(sex)) {
                const auto* profile = profiles.find(id, sex);
                if (!first) std::cout << ','; first = false;
                std::cout << "{\"id\":" << claw::jsonString(id) << ",\"family\":" << claw::jsonString(profile->sourceFamily)
                    << ",\"sex\":" << claw::jsonString(sex == claw::Sex::male ? "male" : "female")
                    << ",\"rules\":" << profile->link.rules.size() << '}';
            }
        }
        std::cout << "],\"defaults\":{"; first = true;
        for (const auto sex : {claw::Sex::male, claw::Sex::female}) if (const auto* profile = profiles.defaultFor(sex)) {
            if (!first) std::cout << ','; first = false;
            std::cout << claw::jsonString(sex == claw::Sex::male ? "male" : "female") << ':' << claw::jsonString(profile->id);
        }
        std::cout << "}}\n"; return 0;
    }
    if (argc != 3 && argc != 6) {
        std::cerr << "claw-preset-tool validate <CLAW-preset-directory>\n"
                     "claw-preset-tool families <MorphLinks.xml>\n"
                     "claw-preset-tool interpolate <directory> <preset> <male|female> <weight>\n";
        return 2;
    }
    claw::Catalog catalog;
    if (!catalog.loadDirectory(argv[2])) {
        for (const auto& error : catalog.diagnostics()) std::cerr << error.source << ": " << error.reason << '\n';
        return 2;
    }
    const std::string_view command = argv[1];
    if (command == "validate" && argc == 3) {
        std::cout << "{\"presets\":" << catalog.size() << ",\"male\":[";
        bool first = true;
        for (const auto& name : catalog.names(claw::Sex::male)) { if (!first) std::cout << ','; first = false; std::cout << claw::jsonString(name); }
        std::cout << "],\"female\":["; first = true;
        for (const auto& name : catalog.names(claw::Sex::female)) { if (!first) std::cout << ','; first = false; std::cout << claw::jsonString(name); }
        std::cout << "]}\n";
        return 0;
    }
    if (command == "interpolate" && argc == 6) {
        const std::string_view sex = argv[4];
        if (sex != "male" && sex != "female") return 2;
        const auto* preset = catalog.find(argv[3], sex == "female" ? claw::Sex::female : claw::Sex::male);
        float weight{};
        const std::string_view text = argv[5];
        const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), weight);
        if (!preset || error != std::errc{} || end != text.data() + text.size()) return 2;
        try {
            const auto morphs = claw::interpolate(*preset, weight);
            std::cout << '{'; bool first = true;
            for (const auto& [name, value] : morphs) { if (!first) std::cout << ','; first = false; std::cout << claw::jsonString(name) << ':' << value; }
            std::cout << "}\n";
            return 0;
        } catch (const std::exception& error) { std::cerr << error.what() << '\n'; }
    }
    return 2;
}
