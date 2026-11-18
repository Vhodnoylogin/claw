#include "claw/HumanTraits.h"
#include "claw/MorphRuleSerialization.h"
#include "claw/SourceBootstrapPolicy.h"
#include <array>
#include <iostream>
#include <limits>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct Record {
    std::vector<std::uint32_t> integers;
    std::vector<std::string> strings;
    std::size_t ii{}, si{};
    std::uint32_t u32() { return integers.at(ii++); }
    std::string string() { return strings.at(si++); }
};
void beastRaceTraits() {
    using claw::Sex;
    struct Source {
        const char* name;
        std::uint32_t race;
        std::array<float, 5> face;
    };
    // Authored regression inputs over the same five NAM9 slots. The normal
    // cases use inspected preset values; vampire cases reuse those inputs to
    // test policy, without asserting a particular vampire NPC's appearance.
    const std::array sources{
        Source{"Khajiit", 0x13745, {0.F, 0.F, 0.F, -.6F, 0.F}},
        Source{"Khajiit vampire", 0x88845, {0.F, 0.F, 0.F, -.6F, 0.F}},
        Source{"Argonian", 0x13740, {.4F, .6F, 0.F, 0.F, .8F}},
        Source{"Argonian vampire", 0x8883A, {.4F, .6F, 0.F, 0.F, .8F}}
    };
    constexpr std::uint32_t wolfRace = 0xCDD84, npc = 0x01000800, faceNPC = 0x02000801;
    for (const auto& source : sources) for (const auto sex : {Sex::male, Sex::female}) {
        const auto check = [&](bool value, const char* message) {
            if (!value) throw std::runtime_error(std::string(source.name) + ": " + message);
        };
        claw::HumanTraits traits;
        unsigned faceReads{};
        const auto observeCurrent = [&](std::uint32_t race, bool npcKeyword, std::uint32_t face,
                                        std::optional<float> height) {
            if (!claw::humanSourceEligible(wolfRace, race, npcKeyword)) return;
            traits.observe(race, npc, face, sex, height, [&](std::uint32_t slot) -> std::optional<float> {
                ++faceReads;
                for (std::size_t i = 0; i < claw::humanFaceChannels.size(); ++i)
                    if (claw::humanFaceChannels[i].second == slot) return source.face[i];
                throw std::runtime_error("unexpected FaceGen slot");
            });
        };
        // No human snapshot may be invented from the base NPC of a born wolf.
        observeCurrent(wolfRace, true, faceNPC, 2.F);
        check(!traits.observed() && traits.values.empty() && faceReads == 0, "born wolf invented a source snapshot");
        observeCurrent(source.race, true, faceNPC, 1.125F);
        check(traits.valid() && traits.race == source.race && traits.npc == npc && traits.faceNPC == faceNPC &&
            traits.sex == sex && faceReads == 5, "capture lost beast-race source provenance");
        for (std::size_t i = 0; i < claw::humanFaceChannels.size(); ++i) {
            const auto name = claw::humanFaceChannels[i].first;
            check(traits.available(name, sex) && traits.input(name, sex) == source.face[i],
                "supported FaceGen value, including zero, was lost");
        }
        check(traits.available("$human.height", sex) && traits.input("$human.height", sex) == 1.125F,
            "stature capture was lost");
        const auto captured = traits.values;
        observeCurrent(wolfRace, false, 0x03000802, 3.F);
        observeCurrent(0x131F7, false, 0x03000802, 3.F);
        observeCurrent(0, true, 0x03000802, 3.F);
        check(traits.race == source.race && traits.faceNPC == faceNPC && traits.values == captured && faceReads == 5,
            "wolf, creature or unresolved race replaced the retained source");
        Record saved;
        claw::writeHumanTraits(traits, [&](auto value) { saved.integers.push_back(value); },
            [&](const auto& value) { saved.strings.push_back(value); });
        auto restored = claw::readHumanTraits(saved);
        // Reader/writer preserve opaque FormIDs, including different file
        // prefixes. Engine ResolveFormID is an adapter boundary, not simulated.
        check(restored.race == source.race && restored.npc == npc && restored.faceNPC == faceNPC &&
            restored.sex == sex && restored.values == captured, "co-save roundtrip changed source identity or availability");
        const auto otherSex = sex == Sex::male ? Sex::female : Sex::male;
        check(!restored.available("$human.face.noseLength", otherSex) &&
            !restored.available("$human.height", otherSex), "source snapshot leaked across sexes");
        // A new eligible source form replaces race and face provenance. Missing
        // face/height is unavailable, even though arithmetic uses neutral 0/1.
        const auto nextRace = source.race == 0x13745 || source.race == 0x88845 ? 0x13740U : 0x13745U;
        restored.observe(nextRace, npc, 0, sex, std::nullopt,
            [](auto) -> std::optional<float> { throw std::runtime_error("missing face was read"); });
        check(restored.race == nextRace && restored.npc == npc && restored.faceNPC == 0 && restored.values.empty(),
            "recapture retained stale face, race or channel availability");
        check(!restored.available("$human.face.noseLength", sex) && restored.input("$human.face.noseLength", sex) == 0.F &&
            !restored.available("$human.height", sex) && restored.input("$human.height", sex) == 1.F,
            "missing channels became available arithmetic neutrals");
        Record unavailableSaved;
        claw::writeHumanTraits(restored, [&](auto value) { unavailableSaved.integers.push_back(value); },
            [&](const auto& value) { unavailableSaved.strings.push_back(value); });
        restored = claw::readHumanTraits(unavailableSaved);
        check(restored.race == nextRace && restored.npc == npc && restored.faceNPC == 0 && restored.values.empty() &&
            !restored.available("$human.face.noseLength", sex) && !restored.available("$human.height", sex),
            "co-save revived unavailable face or stature after recapture");
        restored.observe(nextRace, npc, 0x03000802, sex, 1.F, [](auto) { return std::optional<float>{0.F}; });
        check(restored.faceNPC == 0x03000802 && restored.available("$human.face.noseLength", sex) &&
            restored.input("$human.face.noseLength", sex) == 0.F && restored.available("$human.height", sex),
            "new face provenance with supported zero failed to replace unavailable channels");
        Record zeroSaved;
        claw::writeHumanTraits(restored, [&](auto value) { zeroSaved.integers.push_back(value); },
            [&](const auto& value) { zeroSaved.strings.push_back(value); });
        const auto zeroRestored = claw::readHumanTraits(zeroSaved);
        check(zeroRestored.race == nextRace && zeroRestored.faceNPC == 0x03000802 &&
            zeroRestored.available("$human.face.noseLength", sex) && zeroRestored.values == restored.values,
            "co-save confused supported zero with unavailable after recapture");
    }
}
}
int main() {
    try {
        using claw::Sex;
        using claw::MorphFunction;
        beastRaceTraits();
        for (const auto& [source, slot] : claw::humanFaceChannels) {
            (void)slot;
            require(claw::morphSourceKind(source) == 2, "face source not recognized by shared kernel");
        }
        require(claw::morphSourceKind("$human.height") == 3, "height source not recognized");
        require(claw_matrix_source_neutral(3) == 1.F && claw_matrix_source_neutral(2) == 0.F, "shared human arithmetic neutrals changed");
        for (const auto source : {"$HUMAN.height", "$human.Height", "$human.face.ears", "$human.face.noselength", "$human."})
            require(claw::morphSourceKind(source) == -1, "unsupported human namespace fell through to SKEE");
        require(claw::sourceValueWellFormed("$human.face.noseLength", -.7F) &&
            !claw::sourceValueWellFormed("$human.face.noseLength", std::numeric_limits<float>::max()), "face sentinel interpreted as anatomy");
        require(!claw::sourceValueWellFormed("$human.height", 0.F) && !claw::sourceValueWellFormed("$human.height", -1.F), "invalid human height accepted");
        require(claw::humanReferenceHeight(1.125F, 1.25F, 100.F) == 1.40625F,
            "default reference scale changed NPC/race height");
        require(claw::humanReferenceHeight(1.125F, 1.25F, 150.F) == 2.109375F,
            "NPC/race/reference terms were omitted or multiplied twice");
        require(claw::humanReferenceHeight(1.F, 1.F, 75.F) == .75F &&
            claw::humanReferenceHeight(1.F, 1.F, 125.F) == 1.25F,
            "distinct references sharing one NPC/race lost their stature difference");
        for (const auto bad : {0.F, -1.F, std::numeric_limits<float>::infinity(),
                -std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
            require(!claw::humanReferenceHeight(bad, 1.F, 100.F) && !claw::humanReferenceHeight(1.F, bad, 100.F) &&
                !claw::humanReferenceHeight(1.F, 1.F, bad), "invalid raw stature input gained an available value");
        }
        require(!claw::humanReferenceHeight(std::numeric_limits<float>::max(), 2.F, 100.F) &&
            !claw::humanReferenceHeight(std::numeric_limits<float>::denorm_min(), .5F, 100.F),
            "overflow/underflow stature result was accepted");
        {
            claw::HumanTraits scaled;
            scaled.observe(0x13746, 0x7, 0, Sex::male, claw::humanReferenceHeight(1.F, 1.F, 125.F),
                [](auto) -> std::optional<float> { throw std::runtime_error("absent face was read"); });
            Record saved;
            claw::writeHumanTraits(scaled, [&](auto value) { saved.integers.push_back(value); }, [&](const auto& value) { saved.strings.push_back(value); });
            auto restored = claw::readHumanTraits(saved);
            require(restored.available("$human.height", Sex::male) && restored.input("$human.height", Sex::male) == 1.25F,
                "saved scaled stature was lost or scaled again on load");
            // A different current wolf scale cannot reinterpret the retained
            // value. Only the next eligible human observe replaces the snapshot.
            require(claw::humanReferenceHeight(1.F, 1.F, 200.F) == 2.F && restored.input("$human.height", Sex::male) == 1.25F,
                "current scale changed retained human stature without recapture");
            restored.observe(0x13746, 0x7, 0, Sex::male, claw::humanReferenceHeight(1.F, 1.F, 75.F), [](auto) { return std::optional<float>{}; });
            require(restored.input("$human.height", Sex::male) == .75F, "next human capture did not replace saved stature");
            restored.observe(0x13746, 0x7, 0, Sex::male, claw::humanReferenceHeight(1.F, 1.F, 0.F), [](auto) { return std::optional<float>{}; });
            require(!restored.available("$human.height", Sex::male) && restored.input("$human.height", Sex::male) == 1.F,
                "unavailable reference scale revived old stature or an available neutral");
        }
        claw::MorphLink link{"HumanHead", {
            {"$human.face.noseLength", "CLAWHeadMuzzleLong", .5F, 1},
            {"$human.height", "CLAWTailLength", 2.F, 1},
            {"", "CLAWTailLength", -2.F, 1, MorphFunction::constant, 2, 1},
            {"$actor.weight", "Body", 1.F, 1},
            {"ActualProviderMorph", "Body", .2F, 1}
        }, {}, false};
        require(link.valid(Sex::male), "mixed human/SKEE matrix rejected");
        claw::HumanTraits traits;
        require(traits.valid() && !traits.observed(), "born wolf gained invented human history");
        unsigned providerReads{};
        const auto capture = [&] {
            link.captureActor([&](std::string_view name) {
                require(name == "ActualProviderMorph", "explicit scalar sent to SKEE"); ++providerReads; return .5F;
            }, 40, [&](std::string_view source) { return traits.input(source, Sex::male); });
        };
        capture();
        require(!traits.unavailable(link, Sex::male).empty() && traits.values.empty(), "unavailable traits were converted into present zeros");
        require(link.compose(Sex::male).at("CLAWTailLength") == 0 && link.compose(Sex::male).at("CLAWHeadMuzzleLong") == 0,
            "born wolf did not retain neutral head/tail");
        traits.observe(0x13746, 0x7, 0x7, Sex::male, 1.125F, [](auto slot) -> std::optional<float> {
            return slot == 0 ? .6F : 0.F;
        });
        capture();
        require(traits.unavailable(link, Sex::male).empty() && traits.available("$human.face.jawWidth", Sex::male), "present neutral FaceGen value lost availability");
        const auto expected = link.compose(Sex::male);
        require(expected.at("CLAWHeadMuzzleLong") == .3F && expected.at("CLAWTailLength") == .25F && providerReads == 2,
            "human face/height conversion or explicit source routing changed");
        const auto oldSources = link.sourceValues;
        bool refused{};
        try { link.captureActor([](auto) { return .1F; }, 50); } catch (const std::exception&) { refused = true; }
        require(refused && link.sourceValues == oldSources, "legacy scalar adapter read a fake SKEE face control");
        require(!traits.available("$human.height", Sex::female) && traits.input("$human.height", Sex::female) == 1,
            "snapshot of a different sex was reused");
        Record record;
        claw::writeHumanTraits(traits, [&](auto value) { record.integers.push_back(value); }, [&](const auto& value) { record.strings.push_back(value); });
        const auto loaded = claw::readHumanTraits(record);
        require(loaded.race == traits.race && loaded.npc == traits.npc && loaded.faceNPC == traits.faceNPC && loaded.values == traits.values,
            "human snapshot co-save roundtrip lost provenance/availability");
        require(claw::legacyActorInputNeedsRebind(link, 6) && !claw::legacyActorInputNeedsRebind(link, 7), "old SKEE names silently reinterpreted as human fields");
        auto weightOnly = link; weightOnly.rules = {{"$actor.weight", "Wolf", 1, 1}}; weightOnly.sourceValues.clear(); weightOnly.captured = false;
        require(!claw::legacyActorInputNeedsRebind(weightOnly, 6) && claw::legacyActorInputNeedsRebind(weightOnly, 5), "v7 suppressed established v6 weight semantics");
        // Returning human with changed race/missing FaceData replaces the full
        // snapshot. It cannot resurrect a previous valid face value.
        traits.observe(0x13747, 0x7, 0, Sex::male, 1.F, [](auto) -> std::optional<float> { throw std::runtime_error("missing FaceData was read"); });
        capture();
        require(traits.race == 0x13747 && !traits.available("$human.face.noseLength", Sex::male) && link.compose(Sex::male).at("CLAWHeadMuzzleLong") == 0,
            "new human race/missing face reused stale anatomy");
        traits.observe(0x13747, 0x7, 0x7, Sex::male, std::nullopt, [](auto) -> std::optional<float> { return std::numeric_limits<float>::max(); });
        require(traits.observed() && traits.values.empty() && traits.valid(), "default sentinel/missing height became supported anatomy");
        record.ii = record.si = 0; record.integers[3] = 256;
        refused = false;
        try { (void)claw::readHumanTraits(record); } catch (const std::exception&) { refused = true; }
        require(refused, "corrupt human snapshot sex truncated into a valid value");
        std::cout << "Human trait source, availability, routing, lifecycle and co-save checks passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
