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
        std::ifstream libraryFile(argv[3], std::ios::binary);
        require(libraryFile.good(), "shipped external library unreadable");
        const auto library = CoatLibrary::parse(std::string((std::istreambuf_iterator<char>(libraryFile)), {}));
        require(actual.usesExternalMaterials() && library.names().size() == 10, "missing external material set");
        actual.checkMaterials(library);
        require(actual.output() == "coat.selector" && actual.names().size() == 10, "unexpected mapping contract");
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
        std::cout << "Ten automatic ranges, external materials and manual migration passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
