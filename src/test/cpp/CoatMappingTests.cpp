#include "claw/CoatMapping.h"
#include "claw/CoatMatrix.h"
#include <fstream>
#include <iostream>
#include <iterator>

namespace {
using namespace claw::appearance;
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
        require(evaluate(hair, 0) == 0, "known black hair changed lower endpoint");
        hair.hair = {1, 0, 0};
        require(std::abs(evaluate(hair, 0) - .187088F) < 1e-6F, "red hair coefficient changed");
        require(std::abs(evaluate(hair, UINT64_MAX) - .307088F) < 1e-6F, "known-hair seed contribution changed");
        hair.hair = {1, 1, 1};
        require(evaluate(hair, UINT64_MAX) == 1, "known white hair changed upper endpoint");
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
        // Real NPC record input, not a claim that the photo run retained rendered RGB:
        // Skyrim.esm HousecarlRiften 0A2C91 -> HairColor06Auburn 0A0431 CNAM 30 23 21 00.
        const RGB auburn{48.F / 255, 35.F / 255, 33.F / 255};
        const float luminance = .2126F * auburn[0] + .7152F * auburn[1] + .0722F * auburn[2];
        std::set<std::string> warmVariants;
        for (unsigned step = 0; step <= 256; ++step) {
            const auto seed = step == 256 ? UINT64_MAX : std::uint64_t(step) << 56;
            hair.hair = auburn;
            const auto outputs = matrix.evaluate(hair, seed);
            require(outputs.at("coat.red") == auburn[0] && outputs.at("coat.green") == auburn[1] &&
                outputs.at("coat.blue") == auburn[2], "matrix discarded source hue");
            const auto selected = actual.selectOutputs({}, outputs, true);
            require(selected.pool == "warm-brown", "auburn escaped its warm colour group");
            require(actual.material(selected.pattern) == "randomized/timber-dark" ||
                actual.material(selected.pattern) == "randomized/valley-brown" || actual.material(selected.pattern) == "randomized/brown",
                "seed escaped eligible warm variants");
            warmVariants.insert(selected.pattern);
            const auto record = AutomaticCoatRecord{7, 9, 0, {1, seed ? seed : 1, {selected.pool, selected.pattern}}};
            require(readAutomaticCoat(writeAutomaticCoat(record)).automatic == record.automatic, "group choice codec changed");
            hair.hair = {luminance, luminance, luminance};
            require(actual.selectOutputs({}, matrix.evaluate(hair, seed), true).pool == "dark-neutral",
                "same-luminance neutral and auburn lost hue distinction");
            for (unsigned grey = 0; grey <= 255; ++grey) {
                hair.hair = {grey / 255.F, grey / 255.F, grey / 255.F};
                const auto neutral = actual.selectOutputs({}, matrix.evaluate(hair, seed), true);
                require(neutral.pool == "dark-neutral" || neutral.pool == "grey" || neutral.pool == "white",
                    "neutral grey selected a warm coat");
            }
        }
        require(warmVariants.size() == 3, "within-group seed diversity lost");
        hair.hair = {.25F, .24F, .24F};
        require(actual.selectOutputs({}, matrix.evaluate(hair, 0), true).pool == "grey" &&
            actual.selectOutputs({}, matrix.evaluate(hair, UINT64_MAX), true).pool == "grey", "low-saturation grey became warm");
        require(actual.selectOutputs("elegant-2k-2.1/coal", {}, true).pattern == "elegant-2k-2.1/coal", "manual alias lost with colour mapping");
        require(actual.selectOutputs({}, matrix.evaluate({}, UINT64_MAX), false).pattern == "elegant-2k-2.1/white", "hairless upper fallback changed");
        std::cout << "Legacy scalar/manual compatibility, named RGB groups and all-seed neutral/auburn checks passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
