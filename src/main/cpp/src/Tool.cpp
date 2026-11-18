#include "claw/Preset.h"
#include "claw/MorphProfiles.h"
#include "claw/BodyFamilyBindings.h"
#include <charconv>
#include <iostream>
#include <iomanip>
#include <limits>

int main(int argc, char** argv) {
    const auto command = argc > 1 ? std::string_view(argv[1]) : std::string_view{};
    if ((argc == 5 || argc == 6) && command == "body-family") {
        const std::string_view sexName = argv[4];
        if ((sexName != "male" && sexName != "female") ||
            (argc == 6 && std::string_view(argv[5]) != "--source-unobserved")) return 2;
        const bool observed = argc == 5;
        claw::MorphProfileCatalog profiles;
        if (!profiles.loadFile(argv[2])) { std::cerr << profiles.error() << '\n'; return 2; }
        claw::BodyFamilyBindings bindings;
        if (!bindings.loadFile(argv[3], profiles)) { std::cerr << bindings.error() << '\n'; return 2; }
        std::vector<std::string> models;
        std::string line;
        while (std::getline(std::cin, line)) {
            if (line.empty()) continue;
            if (!observed || models.size() == 512 || !claw::bodyMeshIdentity(line)) {
                std::cerr << "Expected at most 512 relative naked-skin NIF paths, or no paths for an unobserved source\n";
                return 2;
            }
            models.push_back(std::move(line));
        }
        if (std::cin.bad()) { std::cerr << "Could not read naked-skin model paths\n"; return 2; }
        const auto selection = bindings.select(sexName == "female" ? claw::Sex::female : claw::Sex::male,
            models, profiles, observed);
        const auto reason = [&] {
            using Reason = claw::BodyFamilySelection::Reason;
            switch (selection.reason) {
            case Reason::defaultFamily: return "default";
            case Reason::skinBinding: return "skin-binding";
            case Reason::ambiguous: return "ambiguous";
            case Reason::invalidBindings: return "invalid-bindings";
            }
            return "unknown";
        }();
        std::cout << "{\"schema\":\"claw-body-family-selection/1\",\"sourceObserved\":" << (observed ? "true" : "false")
            << ",\"modelCount\":" << models.size() << ",\"reason\":" << claw::jsonString(reason)
            << ",\"blocked\":" << (selection.blocked() ? "true" : "false") << ",\"profile\":"
            << (selection.profile ? claw::jsonString(selection.profile->id) : "null") << "}\n";
        return selection.profile && !selection.blocked() ? 0 : 2;
    }
    if ((argc == 4 || argc == 6) && (command == "matrix" || command == "matrix-info")) {
        claw::MorphProfileCatalog profiles;
        if (!profiles.loadFile(argv[2])) { std::cerr << profiles.error() << '\n'; return 2; }
        const claw::MorphFamilyProfile* profile{};
        for (const auto sex : {claw::Sex::male, claw::Sex::female})
            if (const auto* found = profiles.find(argv[3], sex)) profile = found;
        if (!profile) { std::cerr << "Unknown matrix profile\n"; return 2; }
        if (command == "matrix-info") {
            if (argc != 4) return 2;
            std::map<std::string, std::int32_t, claw::MorphNameLess> sources;
            std::set<std::string, claw::MorphNameLess> targets;
            for (const auto& rule : profile->link.rules) if (rule.active()) {
                targets.emplace(rule.target);
                if (!rule.constant()) sources.emplace(rule.source, claw::morphSourceKind(rule.source));
            }
            std::cout << "{\"schema\":\"claw-matrix-input-graph/1\",\"profile\":" << claw::jsonString(profile->id)
                << ",\"sex\":" << claw::jsonString(profile->sex == claw::Sex::male ? "male" : "female")
                << ",\"activeRules\":" << profile->link.rules.size() << ",\"sources\":[";
            bool first = true;
            for (const auto& [name, kind] : sources) {
                if (!first) std::cout << ','; first = false;
                std::cout << "{\"name\":" << claw::jsonString(name) << ",\"kind\":"
                    << claw::jsonString(kind == 1 ? "actor-weight" : kind == 2 ? "human-face" : kind == 3 ? "human-height" : "skee-morph") << '}';
            }
            std::cout << "],\"targets\":["; first = true;
            for (const auto& name : targets) {
                if (!first) std::cout << ','; first = false;
                std::cout << claw::jsonString(name);
            }
            std::cout << "]}\n"; return 0;
        }
        const bool rawWeightInput = argc == 6;
        float rawWeight{};
        if (rawWeightInput) {
            if (std::string_view(argv[4]) != "--actor-weight-raw") return 2;
            const auto text = std::string_view(argv[5]);
            const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), rawWeight);
            if (error != std::errc{} || end != text.data() + text.size()) return 2;
            try { (void)claw::normalizedActorWeight(rawWeight); }
            catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
        }
        claw::Morphs human;
        std::string line;
        // Tab-separated names preserve legitimate embedded spaces.
        while (std::getline(std::cin, line)) {
            if (line.empty()) continue;
            const auto delimiter = line.find('\t');
            if (delimiter == std::string::npos) return 2;
            const auto name = line.substr(0, delimiter), text = line.substr(delimiter + 1);
            float value{};
            const auto [end, error] = std::from_chars(text.data(), text.data() + text.size(), value);
            if (error != std::errc{} || end != text.data() + text.size() ||
                !claw::sourceValueWellFormed(name, value) || !human.emplace(claw::morphProviderIdentity(name), value).second) return 2;
        }
        auto link = profile->link;
        try {
            std::set<std::string> unavailableHuman;
            const auto read = [&](std::string_view source) {
                const auto found = human.find(claw::morphProviderIdentity(source));
                if (found == human.end() && claw::actorWeightSource(source)) throw std::runtime_error("explicit actor weight input is missing");
                if (found == human.end() && claw::humanTraitSource(source)) {
                    unavailableHuman.emplace(source);
                    return claw_matrix_source_neutral(claw::morphSourceKind(source));
                }
                return found == human.end() ? 0.F : found->second;
            };
            if (rawWeightInput) {
                if (human.contains("$actor.weight")) throw std::runtime_error("raw actor weight and normalized scalar stdin cannot be combined");
                link.captureActor(read, rawWeight, read);
            } else link.capture(read);
            for (const auto& source : unavailableHuman) std::cerr << "Unavailable human source uses neutral input: " << source << '\n';
            const auto morphs = link.compose(profile->sex);
            std::cout << std::setprecision(std::numeric_limits<float>::max_digits10) << '{'; bool first = true;
            for (const auto& [target, value] : morphs) { if (!first) std::cout << ','; first = false; std::cout << claw::jsonString(target) << ':' << value; }
            std::cout << "}\n"; return 0;
        } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
    }
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
                     "claw-preset-tool body-family <MorphLinks.xml> <BodyFamilyBindings.xml> <male|female> [--source-unobserved] (one naked-skin NIF path per stdin line)\n"
                     "claw-preset-tool families <MorphLinks.xml>\n"
                     "claw-preset-tool matrix-info <MorphLinks.xml> <profile>\n"
                     "claw-preset-tool matrix <MorphLinks.xml> <profile> [--actor-weight-raw NPC0..100] (NAME<TAB>VALUE lines on stdin)\n"
                     "claw-preset-tool interpolate <directory> <preset> <male|female> <weight>\n";
        return 2;
    }
    claw::Catalog catalog;
    if (!catalog.loadDirectory(argv[2])) {
        for (const auto& error : catalog.diagnostics()) std::cerr << error.source << ": " << error.reason << '\n';
        return 2;
    }
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
