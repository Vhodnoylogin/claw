// Offline contracts only. Built/run explicitly after the coordinator opens testing.
#include "claw/Preset.h"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>

namespace {
void require(bool condition, const char* reason) { if (!condition) throw std::runtime_error(reason); }
std::string xml(std::string sliders, std::string name = "Example", std::string family = "CLAW Male") {
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><SliderPresets version=\"1\"><Preset name=\"" + name +
        "\" set=\"" + family + "\"><Group name=\"CLAW\"/>" + sliders + "</Preset></SliderPresets>";
}
const std::string small = "<SetSlider name=\"CLAWArmGirth\" size=\"small\" value=\"20\"/>";
const std::string big = "<SetSlider name=\"CLAWArmGirth\" size=\"big\" value=\"80\"/>";
void invalid(const std::string& input) {
    claw::Catalog catalog;
    require(!catalog.loadXml(input, "fixture.xml"), "bad XML was accepted");
    require(!catalog.valid() && !catalog.diagnostics().empty(), "bad catalog lacks diagnostics");
    require(catalog.names(claw::Sex::male).empty(), "invalid catalog exposed selectable presets");
}
}

int main() {
    std::size_t passed{};
    const std::vector<std::pair<const char*, std::function<void()>>> cases{
        {"weight endpoints and midpoint", [] {
            claw::Catalog catalog; require(catalog.loadXml(xml(small + big), "fixture"), "valid preset rejected");
            const auto* preset = catalog.find("Example", claw::Sex::male); require(preset != nullptr, "missing male preset");
            require(std::abs(claw::interpolate(*preset, 0).at("CLAWArmGirth") - .2F) < 1e-6, "low endpoint lost");
            require(std::abs(claw::interpolate(*preset, 50).at("CLAWArmGirth") - .5F) < 1e-6, "weight interpolated incorrectly");
            require(std::abs(claw::interpolate(*preset, 100).at("CLAWArmGirth") - .8F) < 1e-6, "high endpoint lost");
        }},
        {"omitted endpoints use BodySlide zero semantics", [] {
            claw::Catalog catalog; require(catalog.loadXml(xml(big), "fixture"), "sparse preset rejected");
            const auto* preset = catalog.find("Example", claw::Sex::male);
            require(claw::interpolate(*preset, 0).at("CLAWArmGirth") == 0, "omitted small endpoint was not zero");
            require(std::abs(claw::interpolate(*preset, 25).at("CLAWArmGirth") - .2F) < 1e-6, "sparse interpolation wrong");
        }},
        {"typed neutral presets and full owned-key readback", [] {
            claw::Catalog catalog;
            require(catalog.loadXml(xml("", "Neutral male"), "male"), "neutral male rejected");
            require(catalog.loadXml(xml("", "Neutral female", "CLAW Female"), "female"), "neutral female rejected");
            const auto empty = claw::interpolate(*catalog.find("Neutral male", claw::Sex::male), 50);
            require(empty.empty(), "neutral preset gained a nonzero morph");
            std::size_t visited{};
            require(claw::verifyOwnMorphs(empty, [&](std::string_view) { ++visited; return 0.F; }), "zero neutral readback failed");
            require(visited == 25, "neutral readback skipped recognized morphs");
            require(!claw::verifyOwnMorphs(empty, [](std::string_view name) { return name == "CLAWTailFluff" ? .4F : 0.F; }),
                    "neutral readback accepted an unexpected own value");
            const claw::Morphs sparse{{"CLAWArmGirth", .5F}};
            require(claw::verifyOwnMorphs(sparse, [](std::string_view name) { return name == "CLAWArmGirth" ? .5F : 0.F; }),
                    "matching sparse readback failed");
            require(!claw::verifyOwnMorphs(sparse, [](std::string_view name) {
                if (name == "CLAWArmGirth") return .5F;
                return name == "CLAWTorsoBreastSize" ? .2F : 0.F;
            }), "sparse readback skipped omitted female-only owned morph");
            require(!claw::verifyOwnMorphs(empty, [](std::string_view) { return std::numeric_limits<float>::quiet_NaN(); }),
                    "nonfinite readback was accepted");
        }},
        {"preset names use trimmed 160-byte strict UTF-8 contract", [] {
            invalid(xml(big, " Leading")); invalid(xml(big, "Trailing "));
            invalid(xml(big, std::string("Control") + char(127)));
            invalid(xml(big, std::string(161, 'a')));
            invalid(xml(big, std::string("Broken") + char(0xC0) + char(0xAF)));
            invalid(xml(big, std::string("Surrogate") + char(0xED) + char(0xA0) + char(0x80)));
            invalid(xml(big, std::string("Truncated") + char(0xE2) + char(0x82)));
            invalid(xml(big, "Embedded&#0;Nul"));
            invalid(xml(big, "Unknown&bogus;Entity"));
            claw::Catalog catalog;
            require(catalog.loadXml(xml(big, std::string(160, 'a')), "boundary"), "160-byte ASCII name rejected");
            std::string unicode;
            for (int index = 0; index < 80; ++index) unicode += "\xC3\xA9";
            require(catalog.loadXml(xml(big, unicode), "unicode"), "160-byte UTF-8 name rejected");
            invalid(xml(big, unicode + "\xC3\xA9"));
        }},
        {"typed families and adult exclusion", [] {
            invalid(xml("<SetSlider name=\"CLAWTorsoBreastSize\" size=\"big\" value=\"50\"/>"));
            invalid(xml("<SetSlider name=\"CLAWCrotchVulva\" size=\"big\" value=\"50\"/>", "Adult", "CLAW Female"));
            invalid(xml("<SetSlider name=\"HIMBOChest\" size=\"big\" value=\"50\"/>"));
            invalid(xml(big, "Fake", "HIMBO"));
            claw::Catalog catalog;
            require(catalog.loadXml(xml(big, "Female", "CLAW Female"), "fixture"), "female preset rejected");
            require(!catalog.find("Female", claw::Sex::male), "female leaked into male catalog");
        }},
        {"duplicate endpoint and preset names fail closed", [] {
            invalid(xml(big + big));
            claw::Catalog catalog; require(catalog.loadXml(xml(big), "first"), "first preset rejected");
            require(!catalog.loadXml(xml(small), "second"), "duplicate name accepted across files");
            require(!catalog.valid() && catalog.size() == 0, "duplicate catalog remained usable");
        }},
        {"invalid numbers and malformed XML rejected", [] {
            for (const std::string value : {"nan", "inf", "1e1000", "50junk", "", "-1", "101"})
                invalid(xml("<SetSlider name=\"CLAWArmGirth\" size=\"big\" value=\"" + value + "\"/>"));
            invalid("<SliderPresets><Preset>");
            invalid(xml(big) + "<Other/>");
            invalid(xml(big + "<Unexpected/>"));
            invalid(xml(big + "unrecognized text"));
            invalid("<!DOCTYPE SliderPresets [<!ENTITY x SYSTEM 'file:///private'>]>" + xml(big));
        }},
        {"stable choice ignores file load order", [] {
            claw::Catalog first, second;
            require(first.loadXml(xml(big, "One"), "one") && first.loadXml(xml(small, "Two"), "two"), "first catalog failed");
            require(second.loadXml(xml(small, "Two"), "two") && second.loadXml(xml(big, "One"), "one"), "second catalog failed");
            for (int index = 0; index < 100; ++index) {
                const auto identity = "save-namespace/reference-" + std::to_string(index);
                require(first.choose(identity, claw::Sex::male)->name == second.choose(identity, claw::Sex::male)->name, "choice depends on traversal order");
            }
            require(!first.choose("id", claw::Sex::female), "wrong-sex fallback occurred");
        }},
        {"invalid actor weight refused", [] {
            claw::Catalog catalog; catalog.loadXml(xml(big), "fixture");
            for (float weight : {-1.F, 101.F, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
                bool failed{}; try { (void)claw::interpolate(*catalog.find("Example", claw::Sex::male), weight); }
                catch (const std::invalid_argument&) { failed = true; }
                require(failed, "invalid actor weight was accepted");
            }
        }},
        {"nested third-party directory and unreadable catalog", [] {
            const auto folder = std::filesystem::temp_directory_path() / ("claw-core-" + std::to_string(std::random_device{}()));
            std::filesystem::create_directories(folder / "Author");
            try {
                std::ofstream(folder / "Author" / "one.xml") << xml(big, "Nested");
                claw::Catalog catalog; require(catalog.loadDirectory(folder), "nested author preset missed");
                require(catalog.find("Nested", claw::Sex::male) != nullptr, "nested preset missing");
                std::ofstream(folder / "bad.xml") << "not XML";
                require(!catalog.loadDirectory(folder), "bad file silently ignored");
                require(!catalog.valid(), "catalog did not fail closed");
                require(!catalog.loadDirectory(folder / "missing"), "missing directory accepted");
            } catch (...) { std::filesystem::remove_all(folder); throw; }
            std::filesystem::remove_all(folder);
        }}
    };
    for (const auto& [name, run] : cases) {
        try { run(); ++passed; std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& error) { std::cerr << "FAIL " << name << ": " << error.what() << '\n'; return 1; }
    }
    std::cout << passed << " offline contract cases passed\n";
}
