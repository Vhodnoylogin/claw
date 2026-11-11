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
        const auto vendor = replaced(xml, "textures/actors/character/werewolf/claw/test/white/body.dds",
            "textures/DiverseElegantWerewolves/White/body.dds");
        rejects([&] { CoatLibrary::parse(vendor); }, "v1 private namespace bypass");
        const auto v2 = replaced(vendor, "schemaVersion=\"1\"", "schemaVersion=\"2\"");
        const auto external = CoatLibrary::parse(v2);
        require(external.find("test/white")->textures.at("body.dds").path == "textures/DiverseElegantWerewolves/White/body.dds",
            "v2 changed the installed DDS path");
        for (const auto invalid : {"textures/../White/body.dds", "textures//White/body.dds", "textures/CON/body.dds",
            "textures/Bad:File/body.dds", "textures/White\\Other/body.dds", "textures/White/head.dds", "file:///White/body.dds"})
            rejects([&] { CoatLibrary::parse(replaced(v2, "textures/DiverseElegantWerewolves/White/body.dds", invalid)); },
                "unsafe or wrong external DDS path accepted");
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
        const std::string portable = "textures/actors/character/werewolf/claw/elegant-2k-2.1/black/body.dds";
        const std::string engine = R"(textures\actors\character\werewolf\claw\elegant-2k-2.1\black\body.dds)";
        require(coatEngineTexturePath(portable) == engine && portable.find('\\') == portable.npos, "Engine conversion altered portable catalog path or left forward separators");
        require(coatEngineTexturePath(engine) == engine, "Already native texture path changed");
        require(coatEngineTexturePath("textures/actors\\character/body.dds") == R"(textures\actors\character\body.dds)", "Mixed engine separators were not canonicalized");
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

        std::array<char, 148> header{}; std::copy_n("DDS ", 4, header.data());
        const auto word = [&](unsigned pos, std::uint32_t value) { for (unsigned i = 0; i != 4; ++i) header[pos + i] = static_cast<char>((value >> (8 * i)) & 255); };
        word(4, 124); word(8, 0xA1007); word(76, 32); word(80, 4); word(84, 0x30315844);
        word(108, 0x1000); word(128, 98); word(132, 3); word(140, 1);
        word(12, 2048); word(16, 2048); word(28, 12);
        const auto dimensions = coatDDSHeader(header);
        require(dimensions && dimensions->width == 2048 && dimensions->height == 2048 &&
            dimensions->mipLevels == 12 && dimensions->bytes == 5592580, "Real DDS mip payload not calculated");
        word(16, 0); require(!coatDDSHeader(header), "Zero DDS dimension accepted");
        word(16, 32768); require(!coatDDSHeader(header), "Excessive DDS dimension accepted");
        word(16, 2048); word(76, 0); require(!coatDDSHeader(header), "Malformed DDS pixel format accepted");
        word(76, 32); word(28, 1);
        require(coatDDSMatches(4194452, header).has_value(), "Actual 2K single-mip BC7 size refused");
        word(16, 4096); word(12, 4096); word(28, 13);
        require(coatDDSMatches(22369796, header).has_value(), "Actual 4K full-mip BC7 size refused");
        require(!coatDDSMatches(22369795, header) && !coatDDSMatches(22369797, header), "Truncated or trailing DDS payload accepted");
        require(!coatDDSHeader(std::span(header).first(128)), "Truncated DX10 header accepted");
        for (const auto [offset, invalid] : std::array<std::pair<unsigned, unsigned>, 9>{{
            {28, 14}, {24, 2}, {112, 0x200}, {112, 0x400}, {112, 0x200000},
            {132, 4}, {136, 4}, {140, 2}, {80, 0}}}) {
            const auto valid = header;
            word(offset, invalid);
            require(!coatDDSHeader(header), "Unsupported DDS format, mip chain or resource shape accepted");
            header = valid;
        }
        // A future valid resolution and non-square blocks require no catalog or
        // native name changes; partial chains do not imply a full-chain length.
        word(16, 8192); word(12, 4096); word(28, 1);
        require(coatDDSMatches(33554580, header).has_value(), "Valid unlisted resolution refused");
        word(84, 0x31545844); word(16, 7); word(12, 5); word(28, 3);
        require(coatDDSMatches(176, std::span(header).first(128)).has_value(), "Legacy DXT1 block rounding failed");
        word(84, 0x33545844);
        require(coatDDSMatches(224, std::span(header).first(128)).has_value(), "Legacy DXT3 block sizing failed");
        word(84, 0x35545844);
        require(coatDDSMatches(224, std::span(header).first(128)).has_value(), "Legacy DXT5 block sizing failed");
        const auto compressed = header;
        word(80, 0x41); word(84, 0); word(88, 32);
        word(92, 0xFF); word(96, 0xFF00); word(100, 0xFF0000); word(104, 0xFF000000);
        const auto rgba = coatDDSMatches(296, std::span(header).first(128));
        require(rgba && !rgba->bytes && rgba->headerBytes == 128, "Valid non-BC layout was not delegated to the engine");
        require(!coatDDSMatches(128, std::span(header).first(128)), "Header-only opaque DDS admitted");
        header = compressed;
        word(84, 0x30315844); word(128, 28);
        const auto dx10rgba = coatDDSMatches(316, header);
        require(dx10rgba && !dx10rgba->bytes && dx10rgba->headerBytes == 148, "Other DX10 pixel format was arbitrarily rejected");
        header = compressed;
        // Existing catalog metadata intentionally does not determine runtime
        // file size; the actual file header determines it.
        unsigned observed{};
        const auto complete = coatPatternDimensions(*catalog.find("test/white"), [&](const CoatTexture&) {
            ++observed; return coatDDSMatches(224, std::span(header).first(128));
        });
        require(complete && complete->size() == 9 && observed == 9, "Complete structural preflight failed");
        const auto partial = coatPatternDimensions(*catalog.find("test/white"), [&](const CoatTexture& texture) {
            return coatDDSMatches(texture.path.ends_with("head.dds") ? 223 : 224, std::span(header).first(128));
        });
        require(!partial, "One damaged map admitted a partial coat");

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
