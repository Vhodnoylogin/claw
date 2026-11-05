#include "claw/MorphProfiles.h"
#include "claw/HumanTraits.h"
#include <iostream>
#include <stdexcept>

namespace {
void require(bool yes, const char* message) { if (!yes) throw std::runtime_error(message); }
claw::Morphs evaluate(const claw::MorphFamilyProfile& profile, const claw::Morphs& sources, float rawWeight = 50.F) {
    auto link = profile.link;
    link.captureActor([&](std::string_view name) { const auto it = sources.find(name); return it == sources.end() ? 0.F : it->second; },
        rawWeight, [&](std::string_view source) { const auto it = sources.find(source); return it == sources.end() ? claw_matrix_source_neutral(claw::morphSourceKind(source)) : it->second; });
    return link.compose(profile.sex);
}
}
int main(int argc, char** argv) {
    try {
        require(argc == 2, "Pass the canonical MorphLinks.xml source");
        claw::MorphProfileCatalog catalog; require(catalog.loadFile(argv[1]), "v4 canonical catalog rejected");
        require(claw::recognizedMorphs(claw::Sex::male).size() == 30 && claw::recognizedMorphs(claw::Sex::female).size() == 31,
                "biceps/triceps missing from the public sex catalogs");
        const auto* male = catalog.find("CLAW.HIMBO.5.8.Geometry1", claw::Sex::male);
        require(male, "HIMBO profile missing");
        const auto kedr = evaluate(*male, {{"ArmsBiceps", .5F}, {"ArmsBicepsBack", .3F}, {"ArmsBrachio", .4F},
            {"ArmsDelts", .5F}, {"ArmsFore", .4F}, {"Muscle", .2F}, {"TorsoShoulderInc", .2F}});
        const auto grom = evaluate(*male, {{"ArmsSide", .8F}});
        require(kedr.at("CLAWArmBiceps") > 0 && kedr.at("CLAWArmTriceps") > 0 && kedr.at("CLAWArmGirth") == 0,
                "actual Kedr muscle-only inputs still become soft whole-arm mass");
        require(kedr.at("CLAWArmBiceps") < 1 && kedr.at("CLAWArmTriceps") < 1,
                "actual Kedr biceps/triceps immediately blanket-saturate");
        require(grom.at("CLAWArmGirth") > 0 && grom.at("CLAWArmBiceps") == 0 && grom.at("CLAWArmTriceps") == 0,
                "actual Grom soft arm input is mislabeled muscle");
        for (const auto* family : {"CLAW.3BA.2.48.Geometry1", "CLAW.CBBE.2.0.3.Geometry1"}) {
            const auto* female = catalog.find(family, claw::Sex::female); require(female, "female profile missing");
            const auto mira = evaluate(*female, {{"Arms", -.5F}, {"Back", .2F}, {"ChestWidth", .9F},
                {"MuscleArms", 1.F}, {"MuscleMoreArms_v2", 1.F}, {"ShoulderWidth", -1.F}});
            const auto miraSoftOnly = evaluate(*female, {{"Arms", -.5F}});
            const auto runa = evaluate(*female, {{"ChubbyArms", .56F}});
            require(mira.at("CLAWArmGirth") == miraSoftOnly.at("CLAWArmGirth"), "Mira arm muscle still contributes to soft mass");
            require(mira.at("CLAWArmBiceps") > 0 && mira.at("CLAWArmBiceps") < 1 && mira.at("CLAWArmTriceps") > 0 && mira.at("CLAWArmTriceps") < 1,
                    "actual Mira broad muscle inputs do not retain independent local unsaturated fields");
            require(runa.at("CLAWArmGirth") > 0 && runa.at("CLAWArmBiceps") == 0 && runa.at("CLAWArmTriceps") == 0,
                    "actual Runa fat-only arm input is mislabeled muscle");
            require(mira.at("CLAWTailFluff") > 0 && runa.at("CLAWTailFluff") > 0, "real body mass channels cannot differentiate tail radial bulk");
        }
        const auto front = evaluate(*male, {{"ArmsBiceps", .5F}}), rear = evaluate(*male, {{"ArmsBicepsBack", .5F}});
        require(front.at("CLAWArmBiceps") > 0 && front.at("CLAWArmTriceps") == 0 && rear.at("CLAWArmTriceps") > 0 && rear.at("CLAWArmBiceps") == 0,
                "front and rear local muscle controls are conflated");
        const auto face = evaluate(*male, {{"$human.face.chinWidth", .5F}}), fore = evaluate(*male, {{"ArmsFore", .5F}});
        require(face.at("CLAWHeadEarSize") > 0 && face.at("CLAWHeadEarTilt") > 0 && fore.at("CLAWArmClawLong") > 0,
                "declared face/forearm analogies did not add bounded independent variation");
        {
            const auto* bhunp = catalog.find("CLAW.BHUNP.3.34.AdvancedV4", claw::Sex::female);
            require(bhunp && bhunp->sourceFamily == "BHUNP" && bhunp->sourceVersion == "3.34" &&
                    !catalog.find(bhunp->id, claw::Sex::male), "BHUNP resource contract or sex binding lost");
            const auto neutral = evaluate(*bhunp, {});
            // In the actual BHUNP OSD/TRI, these positive deltas SHRINK. The
            // BodySlide baked invert flag is not a runtime SKEE sign switch.
            const auto narrow = evaluate(*bhunp, {{"Arms", 1.F}, {"Legs", 1.F}});
            const auto wide = evaluate(*bhunp, {{"Arms", -1.F}, {"Legs", -1.F}});
            require(narrow.at("CLAWArmLean") > 0 && narrow.at("CLAWArmGirth") == 0 &&
                    wide.at("CLAWArmGirth") > 0 && wide.at("CLAWArmLean") == 0 &&
                    narrow.at("CLAWLegThighLean") > 0 && narrow.at("CLAWLegCalfLean") > 0 &&
                    wide.at("CLAWLegThighGirth") > 0 && wide.at("CLAWLegCalfGirth") > 0,
                    "BHUNP inverted baked sliders were confused with raw runtime delta directions");
            const auto smaller = evaluate(*bhunp, {{"Breasts", .2F}});
            const auto larger = evaluate(*bhunp, {{"Breasts", -.2F}});
            require(smaller.at("CLAWTorsoBreastSize") < neutral.at("CLAWTorsoBreastSize") &&
                    larger.at("CLAWTorsoBreastSize") > neutral.at("CLAWTorsoBreastSize") &&
                    evaluate(*bhunp, {{"BreastsGone", 1.F}}).at("CLAWTorsoBreastSize") == 0,
                    "BHUNP shrinking breast channels were treated as CBBE growth");
            const auto biceps = evaluate(*bhunp, {{"Biceps", 1.F}});
            const auto triceps = evaluate(*bhunp, {{"Triceps", 1.F}});
            const auto fat = evaluate(*bhunp, {{"ChubbyArms", 1.F}});
            require(biceps.at("CLAWArmBiceps") > 0 && biceps.at("CLAWArmTriceps") == 0 && biceps.at("CLAWArmGirth") == 0 &&
                    triceps.at("CLAWArmTriceps") > 0 && triceps.at("CLAWArmBiceps") == 0 &&
                    fat.at("CLAWArmGirth") > 0 && fat.at("CLAWArmBiceps") == 0 && fat.at("CLAWArmTriceps") == 0,
                    "BHUNP local muscle and soft arm mass were conflated");
            const auto low = evaluate(*bhunp, {}, 0.F), high = evaluate(*bhunp, {}, 100.F);
            require(low.at("CLAWTorsoLean") > neutral.at("CLAWTorsoLean") && high.at("CLAWTorsoGirth") > neutral.at("CLAWTorsoGirth") &&
                    low.at("CLAWTorsoBreastSize") == high.at("CLAWTorsoBreastSize"),
                    "BHUNP explicit weight is absent or multiplied into ordinary outputs");
            const auto traits = evaluate(*bhunp, {{"$human.height", 1.1F}, {"$human.face.jawWidth", .3F}});
            require(traits.at("CLAWHeadEarSize") > neutral.at("CLAWHeadEarSize") &&
                    traits.at("CLAWTailLength") > neutral.at("CLAWTailLength") && traits.at("CLAWArmClawLong") > 0,
                    "BHUNP omitted body-independent real source contracts");
            const auto unrelated = evaluate(*bhunp, {{"MuscleMoreArms_v2", 2.F}, {"UNP", 1.F}});
            require(unrelated == neutral, "BHUNP used a CBBE-only key or invented signed full-body runtime name");
            const auto full = evaluate(*bhunp, {{"UNP Low", 1.F}});
            require(full != neutral && bhunp->link.hasProviderSources(), "BHUNP actual Low/High full-body keys were not consumed");
            for (const float value : {-2.F, 2.F}) {
                claw::Morphs sources;
                for (const auto& rule : bhunp->link.rules) if (!rule.constant() && claw::morphSourceKind(rule.source) == 0) sources.emplace(rule.source, value);
                for (const auto& [target, output] : evaluate(*bhunp, sources)) {
                    (void)target; require(std::isfinite(output) && output >= 0 && output <= 1, "BHUNP RaceMenu part range escaped output bounds");
                }
            }
        }
        {
            const auto* unp = catalog.find("CLAW.UNP.4.6.Weight1", claw::Sex::female);
            const auto* vanilla = catalog.find("CLAW.VanillaFemale.Weight1", claw::Sex::female);
            require(unp && vanilla && unp->sourceFamily == "UNP" && unp->sourceVersion == "4.6" &&
                    !catalog.find(unp->id, claw::Sex::male) && !unp->link.hasProviderSources(),
                    "classic UNP lost its female weight-only resource binding");
            const auto low = evaluate(*unp, {}, 0.F), middle = evaluate(*unp, {}, 50.F), high = evaluate(*unp, {}, 100.F);
            require(low.at("CLAWArmLean") > middle.at("CLAWArmLean") && high.at("CLAWArmGirth") > middle.at("CLAWArmGirth") &&
                    low.at("CLAWTorsoBellyRound") < high.at("CLAWTorsoBellyRound"),
                    "classic UNP did not inherit the effective actor weight");
            for (const auto weight : {0.F, 25.F, 50.F, 75.F, 100.F}) {
                const claw::Morphs traits{{"$human.height", 1.1F}, {"$human.face.jawWidth", .3F}};
                require(evaluate(*unp, traits, weight) == evaluate(*vanilla, traits, weight),
                        "classic UNP changed the declared Vanilla weight/generic-trait rules");
                require(evaluate(*unp, {{"Arms", 1.F}, {"UNP Low", 1.F}, {"Breasts", 1.F}}, weight) == evaluate(*unp, {}, weight),
                        "classic UNP invented BodySlide inputs from a different UNP-branded body");
            }
            const auto traits = evaluate(*unp, {{"$human.height", 1.1F}, {"$human.face.jawWidth", .3F}});
            require(traits.at("CLAWHeadEarSize") > middle.at("CLAWHeadEarSize") &&
                    traits.at("CLAWTailLength") > middle.at("CLAWTailLength") && traits.at("CLAWArmClawLong") > 0,
                    "classic UNP lost available generic head/appendage inputs");
            // Classic UNP has no provider TRI. Exercise the real snapshot
            // adapter so partial/unavailable human traits cannot become fake
            // SKEE reads or prevent its independent actor-weight conversion.
            const auto captureUNP = [&](const claw::HumanTraits& human, float weight) {
                auto link = unp->link;
                link.captureActor([](std::string_view) -> float { throw std::runtime_error("classic UNP requested a provider morph"); },
                    weight, [&](std::string_view source) { return human.input(source, claw::Sex::female); });
                return link.compose(claw::Sex::female);
            };
            claw::HumanTraits human;
            for (const float weight : {0.F, 50.F, 100.F})
                require(captureUNP(human, weight) == evaluate(*unp, {}, weight) && !human.unavailable(unp->link, claw::Sex::female).empty(),
                        "born-wolf UNP fabricated available anatomy or lost weight conversion");
            human.observe(0x13746, 0x7, 0x7, claw::Sex::female, std::nullopt,
                [](auto slot) -> std::optional<float> { return slot == 3 ? std::optional<float>{.4F} : std::nullopt; });
            const auto partial = captureUNP(human, 50.F);
            require(human.available("$human.face.jawWidth", claw::Sex::female) &&
                    !human.available("$human.face.noseLength", claw::Sex::female) && !human.available("$human.height", claw::Sex::female) &&
                    partial == evaluate(*unp, {{"$human.face.jawWidth", .4F}}) &&
                    partial.at("CLAWHeadMuzzleWide") > middle.at("CLAWHeadMuzzleWide") &&
                    partial.at("CLAWHeadEarTilt") > middle.at("CLAWHeadEarTilt") && partial.at("CLAWTailLength") == 0 && partial.at("CLAWArmClawLong") == 0,
                    "partial UNP face snapshot blocked available channels or invented unavailable stature");
            std::vector<std::uint32_t> integers; std::vector<std::string> strings;
            claw::writeHumanTraits(human, [&](auto value) { integers.push_back(value); }, [&](const auto& value) { strings.push_back(value); });
            struct SnapshotReader {
                const std::vector<std::uint32_t>& integers; const std::vector<std::string>& strings;
                std::size_t ii{}, si{};
                std::uint32_t u32() { return integers.at(ii++); }
                std::string string() { return strings.at(si++); }
            } reader{integers, strings};
            const auto restored = claw::readHumanTraits(reader);
            require(restored.values == human.values && restored.unavailable(unp->link, claw::Sex::female) == human.unavailable(unp->link, claw::Sex::female) &&
                    captureUNP(restored, 50.F) == partial && reader.ii == integers.size() && reader.si == strings.size(),
                    "persisted partial UNP anatomy lost availability or changed conversion");
            human.observe(0x13746, 0x7, 0x7, claw::Sex::female, 1.F,
                [](auto) -> std::optional<float> { return 0.F; });
            require(human.unavailable(unp->link, claw::Sex::female).empty() && captureUNP(human, 50.F) == middle,
                    "legitimate neutral UNP traits were treated as missing");
            human.observe(0x13746, 0x7, 0x7, claw::Sex::male, 1.1F,
                [](auto) -> std::optional<float> { return .4F; });
            require(captureUNP(human, 100.F) == high && !human.unavailable(unp->link, claw::Sex::female).empty(),
                    "UNP reused a human snapshot of a different bound sex");
        }
        for (const auto sex : {claw::Sex::male, claw::Sex::female}) for (const auto& name : catalog.names(sex)) {
            const auto* profile = catalog.find(name, sex);
            for (const float value : {-1.F, 0.F, 1.F}) {
                claw::Morphs sources;
                for (const auto& rule : profile->link.rules) if (!rule.constant() && claw::morphSourceKind(rule.source) == 0) sources.emplace(rule.source, value);
                for (const auto& [target, output] : evaluate(*profile, sources)) { (void)target; require(std::isfinite(output) && output >= 0 && output <= 1, "matrix endpoint escaped numeric bounds"); }
            }
        }
        std::cout << "V4 public fields, actual muscle/soft separation, independent lobes, appendage variation and endpoints passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
