#include "claw/CoatMapping.h"
#include "claw/CoatMatrix.h"
#include "claw/CoatDye.h"
#include <fstream>
#include <iostream>
#include <iterator>

namespace {
using namespace claw::appearance;
constexpr auto middleSeed = std::uint64_t{128} << 56;
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }
std::string manifest(std::string_view rows) {
    return "<CoatMapping schemaVersion=\"1\" output=\"coat.selector\">" + std::string(rows) + "</CoatMapping>";
}
void rejects(std::string_view rows) {
    try { (void)CoatMapping::parse(manifest(rows)); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error("invalid mapping accepted");
}
void rejectsXml(std::string_view xml) {
    try { (void)CoatMapping::parse(xml); } catch (const std::invalid_argument&) { return; }
    throw std::runtime_error("invalid colour mapping accepted");
}
std::string colourManifest(std::string_view groups, std::string_view weights = {}) {
    return R"(<CoatMapping schemaVersion="2" output="fallback" red="r" green="g" blue="b" seed="seed" )" +
        std::string(weights) + R"(><Range min="0" max=".5" id="test/a" material="installed"/>)" +
        R"(<Range min=".5" max="1" id="test/b" material="installed"/>)" + std::string(groups) + "</CoatMapping>";
}
}
int main(int argc, char** argv) {
    try {
        const std::string low = R"(<Range min="0" max=".5" id="test/low" material="installed"/>)";
        const auto mapping = CoatMapping::parse(manifest(low +
            R"(<Range min=".5" max="1" id="test/high" material="external/high"/><Manual id="test/extra" material="installed"/>)"));
        require(mapping.usesExternalMaterials(), "external catalog requirement missed");
        bool unknown{};
        try { mapping.checkMaterials({}); } catch (const std::invalid_argument&) { unknown = true; }
        require(unknown, "mapping accepted an absent external material");
        require(mapping.select({}, 0, true).pattern == "test/low", "lower endpoint lost");
        require(mapping.select({}, std::nextafter(.5F, 0.F), true).pattern == "test/low", "lower range missed");
        require(mapping.select({}, .5F, true).pattern == "test/high", "shared boundary ambiguity");
        require(mapping.select({}, 1, false).pattern == "test/high", "upper endpoint lost");
        require(mapping.material("test/high") == "external/high", "logical choice conflated with material");
        require(mapping.select("test/extra", {}, false).origin == CoatOrigin::manual, "manual precedence lost");
        require(mapping.select("test/missing", 0, true).pattern.empty(), "missing manual choice became automatic");
        for (auto invalid : {-1.F, 1.1F, std::numeric_limits<float>::quiet_NaN()})
            require(mapping.select({}, invalid, true).pattern.empty(), "out-of-domain output accepted");
        require(mapping.select({}, {}, false).pattern.empty(), "missing matrix output fabricated");
        const std::string reason = "Malformed coat mapping XML";
        const auto disabled = CoatMapping::unavailable(reason);
        const CoatValues availableOutput{{"coat.selector", .25F}};
        const auto disabledAutomatic = disabled.selectOutputs({}, availableOutput, true);
        const auto disabledManual = disabled.selectOutputs("test/extra", availableOutput, false);
        require(disabledAutomatic.pattern.empty() && disabledAutomatic.origin == CoatOrigin::none &&
            disabledAutomatic.reason == reason, "configuration failure lost from automatic coat decision");
        require(disabledManual.pattern.empty() && disabledManual.origin == CoatOrigin::manual &&
            disabledManual.reason == reason, "configuration failure lost from manual coat decision");
        rejects(low);
        rejects(low + R"(<Range min=".6" max="1" id="test/high" material="installed"/>)");
        rejects(low + R"(<Range min=".4" max="1" id="test/high" material="installed"/>)");
        rejects(low + R"(<Range min=".5" max="1" id="test/low" material="installed"/>)");
        rejects(R"(<Range min="0" max="nan" id="test/path" material="installed"/>)");
        rejects(R"(<Range min="0" max="1" id="test/path" material="../bad.dds"/>)");
        const std::string groups = R"(<Group id="first"><Anchor red="1" green="0" blue="0"/><Variant id="test/a"/></Group>
            <Group id="second"><Anchor red="0" green="0" blue="1"/><Variant id="test/b"/></Group>)";
        const auto colourMapping = CoatMapping::parse(colourManifest(groups));
        CoatValues colourValues{{"fallback", .75F}, {"r", 1}, {"g", 0}, {"b", 0}, {"seed", 1}};
        colourMapping.checkOutputs(colourValues);
        require(colourMapping.selectOutputs({}, colourValues, true).pattern == "test/a", "colour mapping ignored named RGB");
        require(colourMapping.selectOutputs({}, colourValues, false).pattern == "test/b", "hairless scalar fallback changed");
        require(colourMapping.selectOutputs("test/b", {}, true).origin == CoatOrigin::manual, "manual requires automatic inputs");
        for (const auto& channel : {"r", "g", "b", "seed"}) {
            auto invalid = colourValues; invalid.erase(channel);
            require(colourMapping.selectOutputs({}, invalid, true).pattern.empty(), "absent colour output fabricated");
            bool missing{};
            try { colourMapping.checkOutputs(invalid); } catch (const std::invalid_argument&) { missing = true; }
            require(missing, "absent bound output admitted at configuration load");
            for (const auto value : {-1.F, 1.01F, std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity()}) {
                invalid = colourValues; invalid[channel] = value;
                require(colourMapping.selectOutputs({}, invalid, true).pattern.empty(), "invalid colour output accepted");
            }
        }
        rejectsXml(colourManifest(""));
        rejectsXml(colourManifest(groups, R"(lightnessWeight="0" chromaWeight="0")"));
        rejectsXml(colourManifest(groups, R"(chromaWeight="nan")"));
        rejectsXml(colourManifest(groups, R"(lightnessWeight="-1")"));
        rejectsXml(colourManifest(R"(<Group id="first"><Anchor red="2" green="0" blue="0"/><Variant id="test/a"/></Group>)"));
        rejectsXml(colourManifest(R"(<Group id="first"><Variant id="test/a"/></Group>)"));
        rejectsXml(colourManifest(R"(<Group id="first"><Anchor red="0" green="0" blue="0"/></Group>)"));
        rejectsXml(colourManifest(groups + R"(<Group id="third"><Anchor red="0" green="0" blue="0"/><Variant id="test/a"/></Group>)"));
        rejectsXml(colourManifest(R"(<Group id="first"><Anchor red="0" green="0" blue="0"/><Variant id="test/unknown"/></Group>)"));
        require(argc == 4, "supply the shipped mapping, matrix and external resource catalog");
        std::ifstream matrixFile(argv[2], std::ios::binary);
        require(matrixFile.good(), "shipped coat matrix unreadable");
        const auto matrix = CoatMatrix::parse(std::string((std::istreambuf_iterator<char>(matrixFile)), {}));
        require(!matrix.evaluate({}, 0).contains("COAT.SELECTOR"), "morph identity policy leaked into numeric coat channels");
        bool unknownChannel{};
        try { (void)CoatMatrix::parse(R"(<CoatMatrix schemaVersion="1"><Rule source="HAIR.RED" target="coat.selector" gain="1" cap="1"/></CoatMatrix>)"); }
        catch (const std::invalid_argument&) { unknownChannel = true; }
        require(unknownChannel, "case-insensitive morph binding changed reserved coat inputs");
        const auto evaluate = [&](const Colours& input, std::uint64_t seed) {
            return matrix.evaluate(input, seed).at("coat.selector");
        };
        Colours hair;
        hair.hasHair = true;
        require(evaluate({}, 0) == 0 && evaluate({}, UINT64_MAX) == 1, "seed-only endpoints lost");
        std::ifstream input(argv[1], std::ios::binary);
        require(input.good(), "shipped mapping unreadable");
        const auto actual = CoatMapping::parse(std::string((std::istreambuf_iterator<char>(input)), {}));
        actual.checkOutputs(matrix.evaluate({}, 0));
        std::ifstream libraryFile(argv[3], std::ios::binary);
        require(libraryFile.good(), "shipped external library unreadable");
        const auto library = CoatLibrary::parse(std::string((std::istreambuf_iterator<char>(libraryFile)), {}));
        require(actual.usesExternalMaterials() && library.names().size() == 10, "missing external material set");
        actual.checkMaterials(library);
        require(actual.output() == "coat.selector" && actual.names().size() == 10, "unexpected mapping contract");
        // Every measured anchor must select its declared group, including both seed endpoints.
        std::ifstream groupedFile(argv[1], std::ios::binary);
        const std::string groupedXml((std::istreambuf_iterator<char>(groupedFile)), {});
        pugi::xml_document grouped;
        require(bool(grouped.load_string(groupedXml.c_str())), "shipped group XML unreadable");
        for (const auto group : grouped.document_element().children("Group")) for (const auto anchor : group.children("Anchor")) {
            hair.hair = {anchor.attribute("red").as_float(), anchor.attribute("green").as_float(), anchor.attribute("blue").as_float()};
            for (const auto seed : {std::uint64_t{0}, UINT64_MAX})
                require(actual.selectOutputs({}, matrix.evaluate(hair, seed), true).pool == group.attribute("id").value(),
                    "configured anchor lost its group or seed crossed groups");
        }
        std::set<std::string> seen;
        for (unsigned i = 0; i < 10; ++i) {
            const auto choice = actual.select({}, (float(i) + .5F) / 10.F, true);
            require(choice.origin == CoatOrigin::hairPool && seen.insert(choice.pattern).second, "collapsed scalar interval");
            const AutomaticCoatRecord record{7, 9, 0, {1, coatSeed(8, 1), {choice.pool, choice.pattern}}};
            require(readAutomaticCoat(writeAutomaticCoat(record)).automatic == record.automatic, "automatic codec changed selection");
        }
        for (const auto& id : actual.names()) {
            require(library.find(actual.material(id))->textures.size() == 9, "incomplete external body/head/fur material");
            const auto restored = readCoatSelection(writeCoatSelection({7, 9, 0, id}));
            require(actual.select(restored.pattern, {}, false).pattern == id, "saved manual choice discarded");
        }
        require(actual.select("elegant-2k-2.1/coal", {}, false).pattern == "elegant-2k-2.1/coal" &&
            actual.material("elegant-2k-2.1/coal") == "randomized/black", "saved legacy alias not resolved");
        const RGB auburn{48.F / 255, 35.F / 255, 33.F / 255};
        const RGB ionaSkin{221.F / 255, 221.F / 255, 221.F / 255};
        const Colours darkSkin{{0, 0, 0}, auburn, true, true};
        const Colours lightSkin{{1, 1, 1}, auburn, true, true};
        const Colours hairOnly{{}, auburn, false, true};
        const Colours skinOnly{ionaSkin, {}, true, false};
        const Colours iona{ionaSkin, auburn, true, true};
        const Colours edda{{145.F / 255, 119.F / 255, 111.F / 255}, {90.F / 255, 95.F / 255, 105.F / 255}, true, true};
        const auto select = [&](const Colours& colours, std::uint64_t seed = middleSeed) {
            return actual.selectOutputs({}, matrix.evaluate(colours, seed), colours.hasHair);
        };
        const auto paletteColour = [](float r, float g, float b) -> RGB { return {r / 255.F, g / 255.F, b / 255.F}; };
        const auto region = [&](const RGB& skin, const RGB& hair, bool chooseHair) {
            return actual.selectRegional(matrix.evaluate({skin, hair, true, true}, middleSeed), chooseHair).pattern;
        };
        const auto mediumSkin = paletteColour(185.F, 179.F, 170.F);
        const auto darkHairFixture = paletteColour(20.F, 20.F, 24.F);
        const auto blondFixture = paletteColour(81.F, 77.F, 57.F);
        require(actual.hasRegionalPalettes() && !colourMapping.hasRegionalPalettes(), "regional palettes broke legacy selection");
        require(region(mediumSkin, darkHairFixture, false) == "elegant-2k-2.1/timber" &&
            region(mediumSkin, blondFixture, false) == "elegant-2k-2.1/timber" &&
            region(ionaSkin, darkHairFixture, false) == "elegant-2k-2.1/white",
            "same-skin fixtures disagreed or skin groups collapsed");
        require(region(mediumSkin, darkHairFixture, true) == "elegant-2k-2.1/valley-black" &&
            region(ionaSkin, darkHairFixture, true) == "elegant-2k-2.1/valley-black" &&
            region(ionaSkin, blondFixture, true) == "elegant-2k-2.1/timber" &&
            region(ionaSkin, auburn, true) == "elegant-2k-2.1/brown" &&
            region(ionaSkin, paletteColour(90.F, 95.F, 105.F), true) == "elegant-2k-2.1/grey",
            "hair groups lost neutral, warm, blond or grey discrimination");
        require(actual.selectRegional({}, true).pattern.empty(), "missing hair inputs selected a regional donor");
        const auto forAppearance = [&](const Colours& colours, bool hairRegion = false, std::uint64_t seed = middleSeed) {
            return actual.selectForAppearance({}, matrix.evaluate(colours, seed), colours, hairRegion).pattern;
        };
        const auto deepSkin = paletteColour(67.F, 44.F, 33.F);
        const auto nextDarkSkin = paletteColour(79.F, 69.F, 64.F);
        constexpr std::string_view blackCoat = "elegant-2k-2.1/valley-black";
        constexpr std::string_view grayCoat = "elegant-2k-2.1/valley-grey";
        constexpr std::string_view softDark = "elegant-2k-2.1/timber-dark";
        for (const auto& skin : {deepSkin, nextDarkSkin}) {
            require(forAppearance({skin, darkHairFixture, true, true}, true) == blackCoat,
                "dark hair and dark skin lost their black regional selection");
            require(forAppearance({skin, blondFixture, true, true}, true) == "elegant-2k-2.1/timber",
                "dark skin overrode a nonblack hair palette");
        }
        require(forAppearance({deepSkin, darkHairFixture, true, true}) == blackCoat,
            "deep skin and black hair lost the black body coat");
        require(forAppearance({deepSkin, blondFixture, true, true}) == softDark &&
            forAppearance({deepSkin, {}, true, false}) == softDark,
            "missing or nonblack hair did not soften a deep skin coat");
        for (const auto& skin : {mediumSkin, ionaSkin})
            require(forAppearance({skin, darkHairFixture, true, true}, true) == grayCoat,
                "dark hair alone selected a black coat on an illuminated body");
        require(forAppearance({{}, darkHairFixture, false, true}) == grayCoat,
            "unknown skin was classified as black from zero-filled outputs");
        require(forAppearance({}, false, 0) == softDark &&
            forAppearance({}, false, std::uint64_t{30} << 56) == softDark &&
            forAppearance({}, false, UINT64_MAX) == "elegant-2k-2.1/white",
            "black restrictions changed the wrong source-less seed bands");
        require(actual.selectForAppearance(blackCoat, {}, {}).pattern == blackCoat &&
            actual.selectForAppearance("elegant-2k-2.1/coal", {}, {}).pattern == "elegant-2k-2.1/coal",
            "automatic restriction changed a manual coat or alias");
        const auto restrictionStart = groupedXml.find("<PairRestriction");
        const auto restrictionEnd = groupedXml.find("</PairRestriction>", restrictionStart);
        require(restrictionStart != std::string::npos && restrictionEnd != std::string::npos,
            "shipped mapping lost its pair restriction");
        auto legacyXml = groupedXml;
        legacyXml.erase(restrictionStart, restrictionEnd + std::string_view{"</PairRestriction>"}.size() - restrictionStart);
        const auto previousMapping = CoatMapping::parse(legacyXml);
        const Colours mediumWithBlack{mediumSkin, darkHairFixture, true, true};
        require(previousMapping.selectForAppearance({}, matrix.evaluate(mediumWithBlack, middleSeed), mediumWithBlack, true)
                .pattern == blackCoat,
            "older regional palettes without a restriction changed");
        for (const auto& [from, to] : {std::pair{"skinGroups=\"deep dark\"", "skinGroups=\"invalid\""},
              std::pair{"hairGroups=\"black\"", "hairGroups=\"black black\""},
              std::pair{"hairFallback=\"elegant-2k-2.1/valley-grey\"", "hairFallback=\"elegant-2k-2.1/black\""}}) {
            auto invalidRestriction = groupedXml;
            const auto offset = invalidRestriction.find(from, restrictionStart);
            require(offset != std::string::npos, "missing restriction test mutation target");
            invalidRestriction.replace(offset, std::string_view(from).size(), to);
            rejectsXml(invalidRestriction);
        }
        const auto ionaOutputs = matrix.evaluate(iona, middleSeed);
        const auto onlySkinOutputs = matrix.evaluate(skinOnly, middleSeed);
        const auto onlyHairOutputs = matrix.evaluate(hairOnly, middleSeed);
        const auto ionaDye = coatDyes(ionaOutputs, iona);
        const auto eddaDye = coatDyes(matrix.evaluate(edda, middleSeed), edda);
        require(ionaDye.body.tint && ionaDye.hair.tint && eddaDye.body.tint && eddaDye.hair.tint &&
            ionaDye.body.tint != eddaDye.body.tint && ionaDye.hair.tint != eddaDye.hair.tint,
            "regional dye absent or insensitive to human colours");
        const auto skinContrast = coatDyes(matrix.evaluate(darkSkin, middleSeed), darkSkin);
        require(ionaDye.body.tint != skinContrast.body.tint && ionaDye.hair.tint == skinContrast.hair.tint &&
            ionaDye.hair.opacity == skinContrast.hair.opacity, "skin colour contaminated the hair dye");
        auto hairContrast = iona;
        hairContrast.hair = {1, .3F, .1F};
        const auto hairContrastDye = coatDyes(matrix.evaluate(hairContrast, middleSeed), hairContrast);
        require(ionaDye.body.tint == hairContrastDye.body.tint && ionaDye.body.opacity == 1.F &&
            ionaDye.hair.tint != hairContrastDye.hair.tint && hairContrastDye.hair.opacity > ionaDye.hair.opacity,
            "hair colour did not independently modulate tint and opacity");
        require(coatSurfaceDye(ionaDye, "body").tint == ionaDye.body.tint &&
            coatSurfaceDye(ionaDye, "head").tint == ionaDye.hair.tint &&
            coatSurfaceDye(ionaDye, "ScalpFurBlend").tint == ionaDye.hair.tint,
            "regional routing diverged from the painted mesh parts");
        require(coatDyes(onlySkinOutputs, skinOnly).body.tint && !coatDyes(onlySkinOutputs, skinOnly).hair.tint &&
            coatDyes(onlyHairOutputs, hairOnly).hair.tint && !coatDyes(onlyHairOutputs, hairOnly).body.tint &&
            !coatDyes(ionaOutputs, {}).active() && !coatDyes({}, iona).active(), "missing dye input was fabricated");
        auto invalidDye = ionaOutputs;
        invalidDye["dye.hair.saturation"] = std::numeric_limits<float>::infinity();
        require(!coatDyes(invalidDye, iona).hair.tint && coatDyes(invalidDye, iona).hair.opacity == 1.F,
            "invalid dye affected the coat");
        const std::array<const char*, 3> channels{"coat.red", "coat.green", "coat.blue"};
        for (std::size_t i = 0; i < channels.size(); ++i) {
            const auto key = channels[i];
            require(std::abs(ionaOutputs.at(key) - (.75F * ionaSkin[i] + .25F * auburn[i])) < 1e-6F,
                "primary skin or secondary hair coefficient changed");
            require(onlySkinOutputs.at(key) == ionaSkin[i] && onlyHairOutputs.at(key) == auburn[i],
                "sole known colour was attenuated");
        }
        require(select(darkSkin).pool == "dark-neutral" && select(lightSkin).pool == "white",
            "skin with fixed hair did not change the coat group");
        const Colours darkHair{{110.F/255, 95.F/255, 88.F/255}, {10.F/255, 10.F/255, 10.F/255}, true, true};
        auto fairHair = darkHair;
        fairHair.hair = {1, 1, 1};
        require(select(darkHair).pool == "warm-brown" && select(fairHair).pool == "light-warm",
            "hair did not have a secondary effect with fixed skin");
        require(select(iona).pattern == "elegant-2k-2.1/white" && select(edda).pattern == "elegant-2k-2.1/timber",
            "Iona or Edda record inputs unexpectedly changed");
        require(select(skinOnly).origin == CoatOrigin::colourPool && select(skinOnly).pool == "white" &&
            select(hairOnly).origin == CoatOrigin::colourPool && select(hairOnly).pool == "warm-brown",
            "single available colour bypassed the group mapping");
        std::set<std::string> variants;
        for (unsigned step = 0; step <= 256; ++step) {
            const auto seed = step == 256 ? UINT64_MAX : std::uint64_t(step) << 56;
            const auto selected = select(hairOnly, seed);
            const auto outputs = matrix.evaluate(hairOnly, seed);
            require(selected.pool == "warm-brown" && selected.variation == outputs.at("coat.variation"),
                "seed changed the group or its observed variation was lost");
            variants.insert(selected.pattern);
        }
        require(variants.size() == 3, "within-group seed diversity lost");
        const float auburnLuma = .2126F * auburn[0] + .7152F * auburn[1] + .0722F * auburn[2];
        const Colours neutralAuburn{{}, {auburnLuma, auburnLuma, auburnLuma}, false, true};
        require(select(neutralAuburn).pool == "dark-neutral", "equal-luminance auburn and neutral lost their distinction");
        require(select({{}, {.25F, .24F, .24F}, false, true}).pool == "grey", "low-saturation grey became warm");
        for (const auto known : {false, true}) for (unsigned grey = 0; grey <= 255; ++grey) {
            const float value = grey / 255.F;
            const Colours neutral{{value, value, value}, {value, value, value}, true, known};
            const auto selected = select(neutral);
            require(selected.origin == CoatOrigin::colourPool &&
                (selected.pool == "dark-neutral" || selected.pool == "grey" || selected.pool == "white"),
                "neutral grey selected a warm coat");
        }
        const auto unknownColours = select({});
        require(unknownColours.origin == CoatOrigin::fallback && !unknownColours.variation,
            "no colour did not use the scalar fallback");
        require(matrix.evaluate({{1, 1, 1}, {1, 1, 1}, false, false}, middleSeed) == matrix.evaluate({}, middleSeed),
            "unavailable channels affected the result");
        CoatValues invalid = ionaOutputs;
        invalid.erase("coat.colour-available");
        actual.checkOutputs(invalid);
        require(actual.selectOutputs({}, invalid, true).origin == CoatOrigin::hairPool &&
            actual.selectOutputs({}, invalid, false).origin == CoatOrigin::fallback,
            "updated mapping lost compatibility with an old matrix without colour availability");
        invalid["coat.colour-available"] = .5F;
        require(actual.selectOutputs({}, invalid, true).pattern.empty(), "non-binary availability accepted");
        const auto manual = actual.selectOutputs("elegant-2k-2.1/black", invalid, false);
        require(manual.pattern == "elegant-2k-2.1/black" && !manual.variation,
            "manual coat lost precedence over colour availability");
        rejectsXml(colourManifest(groups, R"(available="invalid/name")"));
        const auto legacy = CoatMatrix::parse(R"(<CoatMatrix schemaVersion="1">
            <Rule source="seed.withHair" target="coat.variation" gain="1" cap="1"/>
            <Rule source="seed.withoutHair" target="coat.selector" gain="1" cap="1"/>
        </CoatMatrix>)");
        require(legacy.evaluate(darkSkin, middleSeed) == legacy.evaluate(lightSkin, middleSeed) &&
            legacy.evaluate(iona, middleSeed).at("coat.variation") == ionaOutputs.at("coat.variation") &&
            legacy.evaluate(skinOnly, middleSeed).at("coat.selector") == evaluate({}, middleSeed),
            "legacy matrix sources or full seed changed");
        const auto selected = select(skinOnly);
        const auto record = AutomaticCoatRecord{7, 9, 0, {1, middleSeed, {selected.pool, selected.pattern}}};
        const auto restored = readAutomaticCoat(writeAutomaticCoat(record));
        require(restored.automatic == record.automatic &&
            select(skinOnly, restored.automatic.seed).pattern == selected.pattern, "save round trip changed the selected skin-only coat");
        require(actual.selectOutputs("elegant-2k-2.1/coal", {}, true).pattern == "elegant-2k-2.1/coal", "manual alias lost with colour mapping");
        require(actual.selectOutputs({}, matrix.evaluate({}, UINT64_MAX), false).pattern == "elegant-2k-2.1/white", "hairless upper fallback changed");
        std::cout << "Legacy/manual compatibility, skin-first RGB groups and deterministic coat variants passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
