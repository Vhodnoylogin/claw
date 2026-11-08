#include "claw/HumanTraits.h"
#include "claw/MorphRuleSerialization.h"
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
}
int main() {
    try {
        using claw::Sex;
        using claw::MorphFunction;
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
