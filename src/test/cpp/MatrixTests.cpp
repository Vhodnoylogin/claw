#include "claw/MorphProfiles.h"
#include "claw/MorphRuleSerialization.h"
#include <bit>
#include <iostream>
#include <limits>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct Record {
    std::vector<std::string> strings;
    std::vector<std::uint32_t> integers;
    std::size_t si{}, ii{};
    std::string string() { return strings.at(si++); }
    std::uint32_t u32() { return integers.at(ii++); }
};
std::string document(const std::string& rules) {
    return "<MorphLinkProfiles schemaVersion=\"1\"><Profile id=\"Matrix\" family=\"HIMBO\" version=\"5.8\" sex=\"male\" calibration=\"authored\">" + rules + "</Profile></MorphLinkProfiles>";
}
}
int main() {
    try {
        using F = claw::MorphFunction;
        {
            CLAWMatrixRule rules[]{{0, 5, 2, 0, .5F, .8F, .4F}, {0, 2, 2, -.5F, .5F, .8F, 0}};
            float outputs[2]{}; double sums[2]{};
            require(claw_matrix_evaluate(rules, 2, outputs, sums, 2) == 0, "shared kernel rejected mixed matrix");
            require(sums[0] == static_cast<double>(.4F) * .5 + .25 && outputs[0] == static_cast<float>(sums[0] * .8F) && outputs[1] == 0, "shared kernel changed arithmetic order");
            require(claw_matrix_contribution(&rules[1]) == .25, "shared contribution differs");
            rules[1].cap = .9F;
            require(claw_matrix_evaluate(rules, 2, outputs, sums, 2) == 3, "kernel inconsistent caps accepted");
            rules[1].cap = .8F; rules[1].function = 6;
            require(claw_matrix_evaluate(rules, 2, outputs, sums, 2) == 2, "kernel unknown function accepted");
            require(claw_matrix_evaluate(nullptr, 2, outputs, sums, 2) == 1, "kernel null pointer accepted");
        }
        for (const auto function : {F::linear, F::positive, F::negative, F::smoothstep, F::power, F::constant}) {
            claw::MorphLinkRule rule{function == F::constant ? "" : "Human", "CLAWArmLean", .7F, .8F, function, 2, function == F::constant ? .4F : 0.F};
            Record record;
            claw::writeMorphRule(rule, [&](const auto& value) { record.strings.push_back(value); }, [&](auto value) { record.integers.push_back(value); });
            const auto restored = claw::readMorphRule(record, 5);
            require(restored.source == rule.source && restored.target == rule.target && restored.gain == rule.gain && restored.cap == rule.cap && restored.function == rule.function && restored.exponent == rule.exponent && restored.value == rule.value, "v5 function roundtrip failed");
            claw::MorphLink link{"Matrix", {restored}, {}, false};
            require(link.valid(claw::Sex::male), "restored rule invalid");
            std::size_t reads{};
            link.capture([&](std::string_view) { ++reads; return -.5F; });
            require(reads == (function == F::constant ? 0 : 1), "constant read human source");
            require(link.valid(claw::Sex::male), "captured empty source snapshot rejected");
            require(std::isfinite(link.compose(claw::Sex::male).at("CLAWArmLean")), "nonfinite function result");
            if (function == F::constant) {
                const auto first = link.compose(claw::Sex::male);
                link.capture([](std::string_view) -> float { throw std::runtime_error("no humans available"); });
                require(first == link.compose(claw::Sex::male), "constant changed with unavailable humans");
            }
        }
        for (std::uint32_t version : {2, 3, 4}) {
            Record old{{"Human", "CLAWTorsoGirth"}, {std::bit_cast<std::uint32_t>(.7F), std::bit_cast<std::uint32_t>(.25F)}};
            const auto rule = claw::readMorphRule(old, version);
            require(rule.function == F::linear && rule.exponent == 2 && rule.value == 0 && rule.transform(-.5) == -.5, "old rule migration changed linear math");
        }
        claw::MorphLinkRule power{"Human", "CLAWArmLean", 1, 1, F::power, 2};
        require(power.transform(-.5) == -.25 && power.transform(-2) == -1, "power lost sign or bound");
        claw::MorphLinkRule smooth{"Human", "CLAWArmLean", 1, 1, F::smoothstep};
        require(smooth.transform(.25) == .15625 && smooth.transform(-2) == 0 && smooth.transform(2) == 1, "smoothstep contract failed");
        claw::MorphProfileCatalog catalog;
        const auto constant = document("<Rule source=\"\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"constant\" value=\"0.4\"/>");
        require(catalog.loadXml(constant), "constant XML rejected");
        for (const auto& bad : {
            "<Rule source=\"Human\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"eval\"/>",
            "<Rule source=\"Human\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"power\" exponent=\"2.5\"/>",
            "<Rule source=\"Human\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"power\" exponent=\"9\"/>",
            "<Rule source=\"Human\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"constant\" value=\"0.5\"/>",
            "<Rule source=\"Human\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" value=\"0.5\"/>",
            "<Rule source=\"\" target=\"CLAWArmGirth\" gain=\"1\" cap=\"1\" function=\"constant\" value=\"nan\"/>"})
            require(!catalog.loadXml(document(bad)) && !catalog.valid(), "malformed function XML accepted");
        std::cout << "Matrix functions, constant independence, v5 serialization and v2..4 migration passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
