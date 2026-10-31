#include "claw/MorphProfiles.h"
#include "claw/MorphRuleSerialization.h"
#include "claw/MorphOwnership.h"
#include <bit>
#include <iostream>
#include <limits>
#include <cmath>

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
            // Retained/default and custom matrices have the same binding
            // contract. A different installed default must not replace either.
            claw::MorphProfileCatalog profiles;
            auto defaultXml = document("<Rule source=\"Human\" target=\"Wolf\" gain=\"0.5\" cap=\"1\"/>");
            defaultXml.insert(defaultXml.find('>') + 1, "<Defaults male=\"Matrix\" female=\"\"/>");
            for (const bool custom : {false, true}) {
                require(profiles.loadXml(defaultXml), "sex-binding fixture default rejected");
                auto saved = profiles.defaultFor(claw::Sex::male)->link;
                if (custom) saved.profile = "Owner.Custom";
                saved.captureActor([](std::string_view) { return .8F; }, 50.F, claw::Sex::male, claw::Sex::male);
                const auto originalSources = saved.sourceValues, originalOutput = saved.compose(claw::Sex::male);
                const auto originalProfile = saved.profile;
                auto revisedXml = defaultXml;
                revisedXml.replace(revisedXml.find("gain=\"0.5\""), std::string("gain=\"0.5\"").size(), "gain=\"0.9\"");
                require(profiles.loadXml(revisedXml), "revised default fixture rejected");
                unsigned reads{}; bool refused = false;
                try { saved.captureActor([&](std::string_view) { ++reads; return .1F; }, 20.F, claw::Sex::male, claw::Sex::female); }
                catch (const std::exception& error) { refused = std::string_view(error.what()).find("explicitly rebind") != std::string_view::npos; }
                require(refused && reads == 0 && saved.sourceValues == originalSources && saved.profile == originalProfile,
                        "changed sex read a different body's sources or silently replaced the retained matrix");
                require(saved.rules[0].gain == .5F && saved.compose(claw::Sex::male) == originalOutput,
                        "sex mismatch or revised installed default corrupted the saved matrix/source authority");
                // A mismatch is not a sticky replacement/suppression: returning
                // to the original sex recaptures through the original policy.
                saved.captureActor([](std::string_view) { return .6F; }, 50.F, claw::Sex::male, claw::Sex::male);
                require(saved.profile == originalProfile && saved.compose(claw::Sex::male).at("Wolf") == .3F,
                        "restored original sex could not resume its retained matrix");
                // Explicit configure binds the new current sex, even for an
                // opaque custom profile which has no catalog sex metadata.
                auto explicitLink = saved; explicitLink.profile = custom ? "Owner.Rebound" : "NewFemaleFamily";
                const auto reboundSex = claw::Sex::female;
                explicitLink.captureActor([](std::string_view) { return .2F; }, 50.F, reboundSex, claw::Sex::female);
                require(explicitLink.bindingError(reboundSex, claw::Sex::female).empty() && explicitLink.compose(reboundSex).at("Wolf") == .1F,
                        "explicit policy adoption did not restore a usable new-sex binding");
                require(!explicitLink.bindingError(reboundSex, claw::Sex::male).empty(), "explicit adoption retained the obsolete bound sex");
            }
            claw::MorphLink independent;
            require(independent.bindingError(claw::Sex::male, claw::Sex::female).empty(), "linked guard changed independent preset sex selection");
        }
        {
            const auto kind = [](std::string_view name) { return claw_matrix_source_kind(name.data(), static_cast<std::uint32_t>(name.size())); };
            require(kind("$actor.weight") == 1 && kind("Weight") == 0 && kind("CLAWCustomHuman") == 0,
                    "shared source binding changed ordinary morph names");
            for (const auto name : {"$actor.Weight", "$ACTOR.weight", "$actor.height", "$actor.", "", " leading", "trailing "})
                require(kind(name) == -1, "unknown/noncanonical actor input or malformed name accepted");
            require(claw_matrix_source_kind(nullptr, 1) == -1, "null actor input name accepted");
            for (const float value : {0.F, .25F, 1.F}) require(claw_matrix_source_value_valid(1, value), "normalized actor weight rejected");
            for (const float value : {-.01F, 1.01F, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()})
                require(!claw_matrix_source_value_valid(1, value), "invalid actor weight domain accepted");
            require(claw_matrix_source_value_valid(0, -2.F) && claw_matrix_source_value_valid(0, 3.F) &&
                    !claw_matrix_source_value_valid(-1, 0.F), "scalar domain leaked into ordinary morphs");
            for (const auto sex : {claw::Sex::male, claw::Sex::female}) {
                claw::MorphLink link{"Mixed", {{"$actor.weight", "Wolf", 1, .8F}, {"Human", "Wolf", .2F, .8F}}, {}, false};
                unsigned reads{};
                for (const float raw : {0.F, 25.F, 50.F, 100.F}) {
                    link.captureActor([&](std::string_view name) { require(name == "Human", "actor scalar read from fake SKEE morph"); ++reads; return .5F; }, raw);
                    const auto expected = static_cast<float>(std::min(1.0, static_cast<double>(raw / 100.F) + static_cast<double>(.5F) * .2F) * .8F);
                    require(link.sourceValues.at("$actor.weight") == raw / 100.F && link.compose(sex).at("Wolf") == expected,
                            "actor weight normalized twice or multiplied the applied human morph");
                }
                require(reads == 4 && link.hasProviderSources(), "mixed source capture duplicated/skipped provider input");
                const auto old = link.sourceValues;
                for (const float bad : {-1.F, 101.F, std::numeric_limits<float>::quiet_NaN()}) {
                    bool rejected = false;
                    try { link.captureActor([](std::string_view) { return .5F; }, bad); } catch (const std::exception&) { rejected = true; }
                    require(rejected && link.sourceValues == old, "invalid actor weight mutated a prior source snapshot");
                }
                require(link.sourceConflict({{"$actor.weight", 0.F}}).empty(), "actor scalar was confused with an old SKEE output");
                auto scalar = claw::MorphLink{"Vanilla", {{"$actor.weight", "Wolf", 1, 1}}, {}, false};
                scalar.captureActor([](std::string_view) -> float { throw std::runtime_error("vanilla read SKEE source"); }, 65.F);
                require(!scalar.hasProviderSources() && scalar.compose(sex).at("Wolf") == .65F, "born-beast/vanilla scalar capture requires human history");
                auto mixed = scalar; mixed.sourceValues.at("$actor.weight") = 65.F;
                require(!mixed.canonicalize(sex), "corrupt saved scalar was silently clamped/normalized");
                Record record;
                claw::writeMorphRule(scalar.rules[0], [&](const auto& text) { record.strings.push_back(text); }, [&](auto value) { record.integers.push_back(value); });
                const auto savedSources = scalar.sourceValues;
                auto restored = scalar; restored.rules = {claw::readMorphRule(record, claw::actorMatrixRecordVersion)};
                restored.sourceValues = savedSources;
                require(!claw::legacyActorInputNeedsRebind(restored, 6) && restored.canonicalize(sex) && restored.compose(sex) == scalar.compose(sex),
                        "v6 same-layout scalar roundtrip changed saved authority");
                require(claw::legacyActorInputNeedsRebind(restored, 5), "pre-v6 same-token SKEE source was silently reinterpreted");
                claw::MorphLink ordinary{"Old", {{"Weight", "Custom", 1, 1}}, {}, false};
                ordinary.captureActor([](std::string_view) { return .3F; }, std::numeric_limits<float>::quiet_NaN());
                require(!claw::legacyActorInputNeedsRebind(ordinary, 5) && ordinary.compose(sex).at("Custom") == .3F,
                        "old generic Weight source was renamed or gained hidden scalar dependence");
                claw::MorphLink neutral{"Empty", {}, {}, false};
                neutral.captureActor([](std::string_view) -> float { throw std::runtime_error("empty link read provider"); }, std::numeric_limits<float>::quiet_NaN());
                require(neutral.valid(sex) && neutral.sourceValues.empty(), "empty link acquired an implicit weight input");
                claw::MorphLink constant{"Constant", {{"", "Fixed", .5F, 1, F::constant, 2, .8F}}, {}, false};
                constant.captureActor([](std::string_view) -> float { throw std::runtime_error("constant read provider"); }, std::numeric_limits<float>::quiet_NaN());
                require(!constant.hasProviderSources() && constant.compose(sex).at("Fixed") == .4F, "constant input acquired actor weight");
            }
            claw::MorphProfileCatalog scalarCatalog;
            require(scalarCatalog.loadXml(document("<Rule source=\"$actor.weight\" target=\"Wolf\" gain=\"1\" cap=\"1\"/>")), "explicit scalar XML rejected");
            require(scalarCatalog.loadXml(
                "<MorphLinkProfiles schemaVersion=\"1\"><Defaults male=\"CLAW.VanillaMale.Weight1\" female=\"CLAW.VanillaFemale.Weight1\"/>"
                "<Profile id=\"CLAW.VanillaMale.Weight1\" family=\"Vanilla\" version=\"game-weight-v1\" sex=\"male\" calibration=\"test\">"
                "<Rule source=\"$actor.weight\" target=\"Wolf\" gain=\"0.8\" cap=\"1\"/></Profile>"
                "<Profile id=\"CLAW.VanillaFemale.Weight1\" family=\"Vanilla\" version=\"game-weight-v1\" sex=\"female\" calibration=\"test\">"
                "<Rule source=\"$actor.weight\" target=\"Wolf\" gain=\"0.6\" cap=\"1\" function=\"power\" exponent=\"2\"/></Profile></MorphLinkProfiles>"),
                "both-sex vanilla family defaults rejected");
            for (const auto sex : {claw::Sex::male, claw::Sex::female}) {
                const auto* profile = scalarCatalog.defaultFor(sex);
                require(profile && profile->sourceFamily == "Vanilla", "vanilla sex default was inferred as a human body");
                auto link = profile->link;
                link.captureActor([](std::string_view) -> float { throw std::runtime_error("vanilla default read SKEE input"); }, 50.F);
                require(link.compose(sex).at("Wolf") == (sex == claw::Sex::male ? .4F : .15F),
                        "vanilla default/nonlinear scalar did not use shared matrix math");
            }
            for (const auto& rule : {
                "<Rule source=\"$actor.Weight\" target=\"Wolf\" gain=\"1\" cap=\"1\"/>",
                "<Rule source=\"$actor.height\" target=\"Wolf\" gain=\"0\" cap=\"1\"/>",
                "<Rule source=\"Human\" target=\"$actor.weight\" gain=\"1\" cap=\"1\"/>",
                "<Rule source=\"Human\" target=\"$ACTOR.height\" gain=\"0\" cap=\"1\"/>"})
                require(!scalarCatalog.loadXml(document(rule)), "reserved namespace was confused with an ordinary SKEE source/output");
        }
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
        {
            const float cutoff = claw_matrix_gain_epsilon();
            const float below = std::nextafter(cutoff, 0.F), above = std::nextafter(cutoff, 1.F);
            require(cutoff == 1e-6F, "gain cutoff is not float32 1e-6");
            for (const float gain : {0.F, -0.F, below, -below, cutoff, -cutoff}) {
                require(!claw_matrix_gain_active(gain), "inclusive signed cutoff failed");
                CLAWMatrixRule rule{0, 0, 2, std::numeric_limits<float>::max(), gain, .5F, 0};
                float value{42}; double sum{42};
                require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 0 && value == 0 && sum == 0,
                        "inactive edge was multiplied by a large source");
                require(claw_matrix_contribution(&rule) == 0, "contribution diagnostic retained absent edge");
            }
            require(claw_matrix_gain_active(above) && claw_matrix_gain_active(-above), "adjacent active float was lost");
            CLAWMatrixRule rule{0, 0, 2, -1, -above, 1, 0};
            float value{}; double sum{};
            require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 0 && value == above && sum == above,
                    "active negative gain changed");
            require(claw_matrix_evaluate(nullptr, 0, nullptr, nullptr, 0) == 0, "zero-dimension neutral kernel rejected");
            require(claw_matrix_evaluate(nullptr, 0, &value, &sum, 1) == 0 && value == 0 && sum == 0,
                    "empty matrix was not neutral");
            rule.gain = 0;
            for (const float invalid : {std::numeric_limits<float>::infinity(), -std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
                rule.input = invalid;
                require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 2, "nonfinite input hidden by pruning");
                rule.input = 0; rule.gain = invalid;
                require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 2, "nonfinite gain hidden by pruning");
                rule.gain = 0; rule.value = invalid;
                require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 2, "nonfinite parameter hidden by pruning");
                rule.value = 0;
            }
            rule.input = rule.gain = std::numeric_limits<float>::max();
            require(claw_matrix_evaluate(&rule, 1, &value, &sum, 1) == 0 && std::isfinite(sum) && value == 1,
                    "finite float32 maximum multiplication overflowed before double accumulation");
            CLAWMatrixRule edges[]{{0, 0, 2, 1, 0, .8F, 0}, {0, 0, 2, 1, .5F, .2F, 0}};
            require(claw_matrix_evaluate(edges, 2, &value, &sum, 1) == 0 && value == .1F,
                    "inactive edge claimed target cap");
        }
        {
            const auto generic = document("<Rule source=\"CLAWCustomHuman\" target=\"Ear.Size\" gain=\"0.5\" cap=\"1\"/>"
                                          "<Rule source=\"Human\" target=\"Tail.Size\" gain=\"1\" cap=\"1\"/>");
            require(catalog.loadXml(generic), "generic authored target/source spelling rejected");
            auto link = catalog.find("Matrix", claw::Sex::male)->link;
            link.capture([](std::string_view source) { return source == "Human" ? .25F : .5F; });
            const auto values = link.compose(claw::Sex::male);
            require(values.at("Ear.Size") == .25F && values.at("Tail.Size") == .25F, "generic authored spelling changed");
            require(values.at("CLAWTailLength") == 0, "legacy neutral metadata changed");
            require(link.sourceConflict({{"CLAWCustomHuman", 0.F}}) == "CLAWCustomHuman", "old zero-valued own source collision missed");
            require(link.sourceConflict({{"clawcustomhuman", .5F}}) == "CLAWCustomHuman", "provider case alias bypassed old-output conflict");
            require(!catalog.loadXml(document("<Rule source=\"Human\" target=\"Ear.Size\" gain=\"1\" cap=\"1\"/>"
                                              "<Rule source=\"Other\" target=\"ear.size\" gain=\"1\" cap=\"1\"/>")) &&
                    catalog.error().find("case-ambiguous") != std::string::npos, "case-only target aliases were accepted");
            require(!catalog.loadXml(document("<Rule source=\"Human\" target=\"Ear\" gain=\"1\" cap=\"1\"/>"
                                              "<Rule source=\"human\" target=\"Tail\" gain=\"1\" cap=\"1\"/>")),
                    "case-only source aliases were accepted");
            require(!catalog.loadXml(document("<Rule source=\"Human\" target=\"human\" gain=\"1\" cap=\"1\"/>")),
                    "folded source/output alias bypassed feedback rejection");
            require(claw::morphNameIdentifier("Custom.FUR-Size") && !claw::morphNameIdentifier("\xD0\x92\xD0\xBE\xD0\xBB\xD0\xBA"),
                    "provider-bound name domain is not deterministic printable ASCII");
            const auto cross = document("<Rule source=\"HumanA\" target=\"HumanB\" gain=\"1\" cap=\"1\"/>"
                                        "<Rule source=\"HumanB\" target=\"Wolf\" gain=\"1\" cap=\"1\"/>");
            require(!catalog.loadXml(cross) && catalog.error().find("overlaps") != std::string::npos,
                    "cross-edge source/output feedback lacked clear rejection");
            claw::MorphLink caseVariant{"Case", {{"Human", "clawarmgirth", 1, 1}}, {}, false};
            caseVariant.capture([](std::string_view) { return .5F; });
            const auto variantValues = caseVariant.compose(claw::Sex::male);
            require(!variantValues.contains("CLAWArmGirth") && variantValues.at("clawarmgirth") == .5F &&
                    claw::validMorphCache(variantValues, claw::Sex::male, true), "active spelling collided with legacy neutral metadata");
        }
        {
            const auto pruned = document("<Rule source=\"Unobservable\" target=\"Discarded\" gain=\"0.000001\" cap=\"0.3\"/>"
                                         "<Rule source=\"Unobservable\" target=\"Discarded\" gain=\"-0.000001\" cap=\"0.8\"/>");
            require(catalog.loadXml(pruned), "inactive duplicate/cap rules affected semantic validation");
            auto link = catalog.find("Matrix", claw::Sex::male)->link;
            require(link.enabled() && link.rules.empty(), "parser retained absent edges or disabled neutral link");
            link.capture([](std::string_view) -> float { throw std::runtime_error("pruned source must never be read"); });
            const auto values = link.compose(claw::Sex::male);
            require(link.valid(claw::Sex::male) && link.sourceValues.empty() && !values.contains("Discarded"),
                    "absent target/source survived composition");
            require(claw::resolveMorphs(link, claw::Sex::male, []() -> claw::Morphs { throw std::runtime_error("neutral linked mode selected independent preset"); }) == values,
                    "empty link lost linked policy");
            for (const auto& bad : {
                "<Rule source=\"Human\" target=\"Wolf\" gain=\"1e100\" cap=\"1\"/>",
                "<Rule source=\"Human\" target=\"Wolf\" gain=\"0\" cap=\"1e100\"/>",
                "<Rule source=\"\" target=\"Wolf\" gain=\"0\" cap=\"1\" function=\"constant\" value=\"1e100\"/>",
                "<Rule source=\"Human\" target=\"Wolf\" gain=\"0\" cap=\"1\" function=\"power\" exponent=\"9\"/>"})
                require(!catalog.loadXml(document(bad)), "overflow/invalid syntax was concealed by zero gain");
            require(catalog.loadXml(document("")) && catalog.find("Matrix", claw::Sex::male)->link.enabled(),
                    "explicit empty XML profile rejected");
            for (const auto* gain : {"1e-50", "-1e-50", "1e-9999", "-1e-9999", "0.000000000000000000000000000000000000000000000000001"}) {
                require(catalog.loadXml(document(std::string("<Rule source=\"Absent\" target=\"Absent\" gain=\"") + gain + "\" cap=\"1\"/>")) &&
                        catalog.find("Matrix", claw::Sex::male)->link.rules.empty(), "finite decimal underflow failed to become an absent edge");
            }
            for (const auto* gain : {"1e9999", "-1e9999", "nan", "inf", "1e-50junk", "1e-50 ", "1e--50"})
                require(!catalog.loadXml(document(std::string("<Rule source=\"Human\" target=\"Wolf\" gain=\"") + gain + "\" cap=\"1\"/>")),
                        "underflow handling weakened overflow/nonfinite/syntax rejection");
            require(!catalog.loadXml(document("<Rule source=\"Human\" target=\"Wolf\" gain=\"1\" cap=\"1e-50\"/>")),
                    "underflowed zero cap was accepted");
            const std::string hugeMantissa(400, '9');
            require(!catalog.loadXml(document("<Rule source=\"Human\" target=\"Wolf\" gain=\"" + hugeMantissa + "e-1\" cap=\"1\"/>")),
                    "negative textual exponent concealed overflowing mantissa");
            claw::MorphLink many{"Capacity", {}, {}, false};
            for (unsigned index=0; index<64; ++index) many.rules.push_back({"Human", "Custom"+std::to_string(index), 1, 1});
            require(many.valid(claw::Sex::female), "legacy zero metadata consumed numeric target capacity");
            many.capture([](std::string_view) { return .5F; });
            require(many.compose(claw::Sex::female).size() == claw::maxLinkedCacheMorphs, "64 custom outputs or legacy zeros lost");
            many.rules.push_back({"Human", "Custom64", 1, 1});
            require(!many.valid(claw::Sex::female), "65 active targets accepted");
        }
        {
            claw::MorphLink saved{"Saved-authority", {{"Obsolete", "OldTarget", 1e-6F, 1}, {"Retained", "CustomWolf", .5F, .8F}},
                {{"Obsolete", 2.F}, {"Retained", .25F}}, true};
            require(saved.canonicalize(claw::Sex::male), "old captured source snapshot did not migrate");
            require(saved.profile == "Saved-authority" && saved.rules.size() == 1 && saved.sourceValues.size() == 1 &&
                    !saved.sourceValues.contains("Obsolete") && saved.compose(claw::Sex::male).at("CustomWolf") == .1F,
                    "saved rules were replaced or stale sources retained");
            Record record;
            for (const auto& edge : saved.rules)
                claw::writeMorphRule(edge, [&](const auto& value) { record.strings.push_back(value); }, [&](auto value) { record.integers.push_back(value); });
            require(record.strings == std::vector<std::string>{"Retained", "CustomWolf"}, "canonical v5 serialization retained absent edge");
            auto restored = saved; restored.rules = {claw::readMorphRule(record, 5)};
            require(restored.canonicalize(claw::Sex::male) && restored.compose(claw::Sex::male) == saved.compose(claw::Sex::male),
                    "generic v5 roundtrip changed saved arithmetic");
            auto bad = saved; bad.sourceValues.emplace("Unrelated", 0.F);
            const auto original = bad.sourceValues;
            require(!bad.canonicalize(claw::Sex::male) && bad.sourceValues == original,
                    "normalization silently repaired unrelated snapshot or mutated rejected state");
            bad = saved; bad.sourceValues.clear();
            require(!bad.canonicalize(claw::Sex::male), "migration fabricated missing active source");
            bad = {"Uncaptured", {{"Dropped", "Wolf", 0, 1}}, {{"Dropped", 0.F}}, false};
            require(!bad.canonicalize(claw::Sex::male), "pruning concealed corrupt uncaptured source state");
            bad = {"", {{"Dropped", "Wolf", 0, 1}}, {}, false};
            require(!bad.canonicalize(claw::Sex::male), "pruning concealed corrupt disabled link state");
            require(claw::validMorphCache({{"Arbitrary.Wolf", .5F}}, claw::Sex::male, true), "generic linked cache rejected");
            require(!claw::validMorphCache({{"Arbitrary.Wolf", .5F}}, claw::Sex::male, false), "legacy independent cache validation broadened");
            require(!claw::validMorphCache({{"Arbitrary.Wolf", std::numeric_limits<float>::infinity()}}, claw::Sex::male, true),
                    "nonfinite saved generic cache accepted");
            require(!claw::validMorphCache({{"Ear", .5F}, {"ear", .2F}}, claw::Sex::male, true),
                    "provider-ambiguous saved cache accepted");
        }
        {
            std::map<std::string, std::map<std::string, float>> provider{
                {"CustomRemoved", {{"CLAW.Distribution", .8F}, {"AnotherMod", .4F}}},
                {"AnotherOnly", {{"AnotherMod", .2F}}},
                {"CustomCurrent", {{"CLAW.Distribution", .3F}}},
                {"NonfiniteOld", {{"CLAW.Distribution", std::numeric_limits<float>::quiet_NaN()}}}};
            auto snapshot = [&] {
                claw::Morphs values;
                for (const auto& [name, keys] : provider) for (const auto& [key, value] : keys)
                    claw::observeOwnMorph(values, name, key, value, "CLAW.Distribution");
                return values;
            };
            const auto observed = snapshot();
            require(observed.size() == 3 && !observed.contains("AnotherOnly"), "snapshot claimed another provider's key");
            require(!claw::verifyOwnedMorphs({{"CustomCurrent", .3F}}, observed, .0001F), "stale/nonfinite own outputs passed readback");
            require(claw::clearOwnedMorphs(observed, [&](const std::string& name) { provider.at(name).erase("CLAW.Distribution"); }, snapshot, .0001F),
                    "generic own-key cleanup failed");
            require(provider.at("CustomRemoved").at("AnotherMod") == .4F && provider.at("AnotherOnly").at("AnotherMod") == .2F && snapshot().empty(),
                    "custom cleanup changed another mod's values");
            require(claw::verifyOwnedMorphs({{"NeutralCustom", 0.F}}, {}, .0001F), "unstored neutral output failed readback");
            for (const float residual : {0.F, .00005F}) {
                const claw::Morphs stale{{"Stale", residual}};
                require(!claw::verifyOwnedMorphs({}, stale, .0001F), "unexpected zero/tiny own key passed structural readback");
                require(!claw::clearOwnedMorphs(stale, [](const std::string&) {}, [&] { return stale; }, .0001F),
                        "no-op clear with a zero/tiny own key was accepted");
            }
            require(!claw::verifyOwnedMorphs({{"TinyWanted", .00005F}}, {}, .0001F), "missing nonzero own key passed tolerance readback");
            require(!claw::verifyOwnedMorphs({{"Neutral", 0.F}}, {{"Neutral", 0.F}}, .0001F), "stored neutral key was accepted");
            claw::Morphs foldedOwn;
            claw::observeOwnMorph(foldedOwn, "eAr", "cLaW.Distribution", .4F, "CLAW.Distribution");
            require(claw::verifyOwnedMorphs({{"Ear", .4F}}, foldedOwn, .0001F), "SKEE-interned spelling broke own-key readback");
            require(!claw::verifyOwnedMorphs({{"Ear", .4F}, {"ear", .4F}}, foldedOwn, .0001F),
                    "case-ambiguous expected ownership was accepted");
        }
        std::cout << "Matrix functions, generic targets, shared gain omission, exact-key ownership, v5 roundtrip and old migration passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
