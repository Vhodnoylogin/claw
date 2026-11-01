#include "claw/CoatLibrary.h"
#include <fstream>
#include <iostream>
#include <iterator>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
template<class F> void rejects(F&& action, const char* message) {
    bool refused{}; try { action(); } catch (const std::invalid_argument&) { refused = true; }
    require(refused, message);
}
std::string pattern(std::string id, std::string palette) {
    std::string xml = "<Pattern id=\"" + id + "\" label=\"Test pattern\"" + palette + ">";
    std::set<std::string_view> names;
    for (const auto& surface : claw::appearance::coatSurfaces) names.insert(surface.texture);
    for (const auto name : names) xml += "<Texture name=\"" + std::string(name) +
        "\" path=\"textures/actors/character/werewolf/claw/test/" + id + "/" + std::string(name) +
        "\" bytes=\"128\" sha256=\"" + std::string(64, 'a') + "\"/>";
    return xml + "</Pattern>";
}
std::string document(const std::string& patterns) {
    std::string xml = "<CoatLibrary schemaVersion=\"1\" id=\"test\" sourceArchiveSha256=\"" + std::string(64, 'a') + "\"><Surfaces>";
    for (const auto& surface : claw::appearance::coatSurfaces)
        xml += "<Surface name=\"" + std::string(surface.name) + "\" texture=\"" + std::string(surface.texture) + "\" group=\"" + std::string(surface.group) + "\"/>";
    return xml + "</Surfaces><Patterns>" + patterns + "</Patterns></CoatLibrary>";
}
std::string replaced(std::string xml, std::string_view old, std::string_view value) {
    const auto pos = xml.find(old); require(pos != xml.npos, "Test mutation did not match");
    xml.replace(pos, old.size(), value); return xml;
}
}
int main(int argc, char** argv) {
    using namespace claw::appearance;
    try {
        const auto black = pattern("black", " furR=\"0\" furG=\"0\" furB=\"0\"");
        const auto white = pattern("white", " furR=\"1\" furG=\"1\" furB=\"1\"");
        const auto xml = document(white + black);
        const auto catalog = CoatLibrary::parse(xml);
        require(catalog.names() == std::vector<std::string>{"test/black", "test/white"}, "IDs are not stable sorted keys");
        require(catalog.nearest({.1F, .1F, .1F}) == "test/black" && catalog.nearest({.9F, .9F, .9F}) == "test/white", "Real RGB nearest selector failed");
        require(catalog.nearest({-1, 0, 0}).empty() && CoatLibrary{}.nearest({0, 0, 0}).empty(), "Invalid/absent palette invented a selection");
        const auto tied = CoatLibrary::parse(document(pattern("zebra", " furR=\".5\" furG=\".5\" furB=\".5\"") + pattern("amber", " furR=\".5\" furG=\".5\" furB=\".5\"")));
        require(tied.nearest({.5F, .5F, .5F}) == "test/amber", "Palette ties depend on source order");
        const auto manualOnly = CoatLibrary::parse(document(pattern("manual", "")));
        require(manualOnly.find("test/manual") && manualOnly.nearest({.5F, .5F, .5F}).empty(), "Absent measured palette became automatic");
        for (const auto id : {"con", "con.foo", "nul", "aux", "prn", "com1", "lpt9.ext", "trailing.", "..", ".hidden", "x/y", "A", "x:y"})
            require(!coatToken(id), "Unsafe Windows token accepted");
        require(coatToken("elegant-2k-2.1") && coatKey("elegant-2k-2.1/timber") && !coatKey("a/b/c"), "Canonical identity rejected or extra path accepted");
        rejects([&] { CoatLibrary::parse(document(black + black)); }, "Duplicate pattern accepted");
        rejects([&] { CoatLibrary::parse(document(pattern("partial", " furR=\".5\""))); }, "Partial measured palette accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "furR=\"1\"", "furR=\"nan\"")); }, "NaN palette accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "furR=\"1\"", "furR=\"1.1\"")); }, "Unbounded palette accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "/white/body.dds", "/../body.dds")); }, "Path escape accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "group=\"undercoat\"", "group=\"fur\"")); }, "Wrong skin/fur map accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "bytes=\"128\"", "bytes=\"67108865\"")); }, "Excessive DDS size accepted");
        rejects([&] { CoatLibrary::parse(replaced(xml, "label=\"Test pattern\"", "label=\"Test &amp; pattern\"")); }, "Entities outside generated format accepted");
        rejects([&] { CoatLibrary::parse(std::string(1024 * 1024 + 1, 'x')); }, "Excessive document accepted");
        std::string excess; for (unsigned i = 0; i != 65; ++i) excess += pattern("p" + std::to_string(i), "");
        rejects([&] { CoatLibrary::parse(document(excess)); }, "Excessive pattern count accepted");

        const CoatSelection choice{0xFF000123, 0xFE00A802, 0, "test/black"};
        const auto bytes = writeCoatSelection(choice); const auto loaded = readCoatSelection(bytes);
        require(loaded.actor == choice.actor && loaded.base == choice.base && loaded.sex == choice.sex && loaded.pattern == choice.pattern, "CCPT roundtrip changed identity/choice");
        auto malformed = bytes; malformed[8] = 2;
        rejects([&] { readCoatSelection(malformed); }, "Invalid CCPT sex accepted");
        malformed = bytes; malformed[12] += 1;
        rejects([&] { readCoatSelection(malformed); }, "CCPT payload length mismatch accepted");
        rejects([&] { writeCoatSelection({0, choice.base, 0, choice.pattern}); }, "Unowned CCPT identity accepted");
        rejects([&] { writeCoatSelection({choice.actor, choice.base, 0, "test/../x"}); }, "Invalid saved choice accepted");

        std::array<char, 128> header{}; std::copy_n("DDS ", 4, header.data());
        const auto word = [&](unsigned pos, std::uint32_t value) { for (unsigned i = 0; i != 4; ++i) header[pos + i] = static_cast<char>((value >> (8 * i)) & 255); };
        word(4, 124); word(76, 32); word(12, 2048); word(16, 2048); word(28, 12);
        const auto dimensions = coatDDSHeader(header);
        require(dimensions && dimensions->width == 2048 && dimensions->height == 2048 && dimensions->mipLevels == 12, "Real DDS dimension fields not parsed");
        word(16, 0); require(!coatDDSHeader(header), "Zero DDS dimension accepted");
        word(16, 32768); require(!coatDDSHeader(header), "Excessive DDS dimension accepted");
        word(16, 2048); word(76, 0); require(!coatDDSHeader(header), "Malformed DDS pixel format accepted");

        if (argc > 1) {
            std::ifstream input(argv[1], std::ios::binary); require(bool(input), "Real local XML unavailable");
            const std::string actual((std::istreambuf_iterator<char>(input)), {});
            const auto real = CoatLibrary::parse(actual); require(real.names().size() == 34, "Real Elegant library count changed");
            for (const auto& id : real.names()) { const auto* p = real.find(id); require(p && p->fur && p->textures.size() == 9, "Real library omitted measured RGB/DDS"); require(!real.nearest(*p->fur).empty(), "Actual palette not selectable"); }
            std::cout << "Real local library:34 measured patterns /306 DDS metadata entries\n";
        }
        std::cout << "Coat library policy, parser, DDS guards and CCPT tests passed\n"; return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
