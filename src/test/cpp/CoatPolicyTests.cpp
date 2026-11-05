#include "claw/CoatPolicy.h"
#include <fstream>
#include <iostream>
#include <iterator>

namespace {
void require(bool value, const char* text) { if (!value) throw std::runtime_error(text); }
template<class F> void rejects(F action) {
    bool failed{}; try { action(); } catch (const std::invalid_argument&) { failed = true; }
    require(failed, "Invalid policy/record was accepted");
}
std::string pattern(std::string id, std::string palette) {
    std::string xml = "<Pattern id=\"" + id + "\" label=\"Fixture\"" + palette + ">";
    std::set<std::string_view> names;
    for (const auto& surface : claw::appearance::coatSurfaces) names.insert(surface.texture);
    for (const auto name : names) xml += "<Texture name=\"" + std::string(name) +
        "\" path=\"textures/actors/character/werewolf/claw/test/" + id + "/" + std::string(name) +
        "\" bytes=\"128\" sha256=\"" + std::string(64, 'a') + "\"/>";
    return xml + "</Pattern>";
}
claw::appearance::CoatLibrary library(bool reverse = false, bool extra = false) {
    std::string xml = "<CoatLibrary schemaVersion=\"1\" id=\"test\" sourceArchiveSha256=\"" + std::string(64, 'a') + "\"><Surfaces>";
    for (const auto& s : claw::appearance::coatSurfaces) xml += "<Surface name=\"" + std::string(s.name) +
        "\" texture=\"" + std::string(s.texture) + "\" group=\"" + std::string(s.group) + "\"/>";
    const auto dark = pattern("black", " furR=\".05\" furG=\".05\" furB=\".05\"") + pattern("coal", " furR=\".1\" furG=\".1\" furB=\".1\"");
    const auto light = pattern("white", " furR=\".95\" furG=\".95\" furB=\".95\"");
    return claw::appearance::CoatLibrary::parse(xml + "</Surfaces><Patterns>" + (reverse ? light + dark : dark + light) +
        (extra ? pattern("new", " furR=\".08\" furG=\".08\" furB=\".08\"") : "") + "</Patterns></CoatLibrary>");
}
std::string policy(bool reverse = false, bool extra = false) {
    const auto dark = "<Pool id=\"dark\" use=\"hair\">" + std::string(reverse ?
        "<Pattern id=\"test/coal\"/><Pattern id=\"test/black\"/>" : "<Pattern id=\"test/black\"/><Pattern id=\"test/coal\"/>") +
        (extra ? "<Pattern id=\"test/new\"/>" : "") + "</Pool>";
    const std::string light = "<Pool id=\"light\" use=\"hair\"><Pattern id=\"test/white\"/></Pool>";
    return "<CoatPolicy schemaVersion=\"1\" tintMode=\"original\" fallbackPool=\"natural\"><Pools>" +
        (reverse ? light + dark : dark + light) +
        "<Pool id=\"natural\" use=\"fallback\"><Pattern id=\"test/black\"/><Pattern id=\"test/coal\"/><Pattern id=\"test/white\"/></Pool></Pools></CoatPolicy>";
}
std::string replace(std::string s, std::string_view before, std::string_view after) {
    const auto at = s.find(before); require(at != s.npos, "Fixture mutation failed");
    s.replace(at, before.size(), after); return s;
}
struct HairProbe { std::string pool, pattern; };
void savedSourceLifecycle(const claw::appearance::CoatLibrary& catalog,
    const claw::appearance::CoatPolicy& parsed, const std::vector<HairProbe>& probes) {
    using namespace claw::appearance;
    // Execute the production selector and both production codecs. The fixture
    // supplies source availability/manual clear at this pure boundary; it does
    // not impersonate Runtime, SKSE remapping or an engine material witness.
    for (std::uint32_t sex : {0U, 1U}) for (std::uint64_t identity : {1ULL, 17ULL, 64ULL}) {
        AutomaticCoatRecord record{0xFF000123, 0xFE00A802, sex, {identity, coatSeed(42, identity)}};
        const auto born = parsed.select(catalog, {}, std::nullopt, record.automatic.seed, record.automatic);
        require(born.origin == CoatOrigin::fallback && catalog.find(born.pattern), "Lifecycle fallback unavailable");
        record.automatic.fallback = {born.pool, born.pattern};
        const auto retainedFallback = record.automatic.fallback;
        const auto unchanged = record.automatic;
        const auto unavailable = CoatPolicy::unavailable("fixture policy unavailable");
        const CoatLibrary missing;
        require(unavailable.select(catalog, {}, std::nullopt, record.automatic.seed, record.automatic).pattern.empty(),
            "Invalid policy broadened the fallback");
        require(parsed.select(missing, {}, std::nullopt, record.automatic.seed, record.automatic).pattern.empty(),
            "Missing library retained a nonexistent fallback");
        require(parsed.select(catalog, "missing/pattern", std::nullopt, record.automatic.seed, record.automatic).pattern.empty(),
            "Missing manual pattern silently became automatic");
        require(record.automatic == unchanged, "Unavailable data changed saved selection state");

        for (const auto& probe : probes) {
            const auto* donor = catalog.find(probe.pattern);
            require(donor && donor->fur, "Lifecycle hair probe lacks measured source");
            const auto arrived = parsed.select(catalog, {}, donor->fur, record.automatic.seed, record.automatic);
            require(arrived.origin == CoatOrigin::hairPool && arrived.pool == probe.pool && catalog.find(arrived.pattern),
                "Real hair arrival or migration selected the wrong pool");
            record.automatic.hair = {arrived.pool, arrived.pattern};
            require(record.automatic.fallback == retainedFallback, "Hair migration erased the independent fallback cache");

            const auto manual = readCoatSelection(writeCoatSelection({record.actor, record.base, sex, probe.pattern}));
            record = readAutomaticCoat(writeAutomaticCoat(record));
            const auto saved = record.automatic;
            const auto forced = parsed.select(catalog, manual.pattern, std::nullopt, saved.seed, saved);
            require(forced.origin == CoatOrigin::manual && forced.pattern == manual.pattern, "Loaded manual override lost precedence");
            require(unavailable.select(catalog, manual.pattern, donor->fur, saved.seed, saved).pattern == manual.pattern,
                "Invalid automatic policy blocked a loaded manual choice");
            // Empty override represents manual clear after the two codec loads.
            const auto cleared = parsed.select(catalog, {}, donor->fur, saved.seed, saved);
            require(cleared.origin == CoatOrigin::hairPool && cleared.pool == arrived.pool && cleared.pattern == arrived.pattern,
                "Manual clear after codec load lost the eligible hair choice");
            const auto removed = parsed.select(catalog, {}, std::nullopt, saved.seed, saved);
            require(removed.origin == CoatOrigin::fallback && removed.pool == born.pool && removed.pattern == born.pattern,
                "Hair removal after codec load rerolled fallback");
            require(parsed.select(missing, {}, donor->fur, saved.seed, saved).pattern.empty(),
                "Missing library retained a nonexistent hair choice");
            require(parsed.select(catalog, {}, donor->fur, saved.seed, saved).pattern == arrived.pattern,
                "Library recovery rerolled eligible hair choice");
            require(record.automatic == saved, "Manual or missing-data selection mutated automatic caches");

            // FormIDs are codec metadata, not a selector input. These are two
            // explicit persisted IDs, not a claim to execute ResolveFormID.
            record.actor = 0xFF001234; record.base = 0xFE00B803;
            record = readAutomaticCoat(writeAutomaticCoat(record));
            require(record.automatic == saved &&
                parsed.select(catalog, {}, donor->fur, record.automatic.seed, record.automatic).pattern == arrived.pattern,
                "Reference/base FormID metadata changed saved marking or seed");
        }
    }
}
}
int main(int argc, char** argv) {
    using namespace claw::appearance;
    try {
        const auto catalog = library(); const auto parsed = CoatPolicy::parse(policy(), catalog);
        require(parsed.tintMode() == TintMode::original && CoatPolicy{}.tintMode() == TintMode::linked, "Mode defaults changed");
        require(coatSeed(42, 17) == 2628339332895557876ULL, "Versioned seed bytes changed");
        require(coatSeed(42, 17) != coatSeed(42, 18), "Distinct reference identities collapsed");
        const auto seed = coatSeed(42, 17);
        require(coatScore(seed, "dark", "test/black") == 5136789385173906885ULL, "Versioned rendezvous bytes changed");
        AutomaticCoatState saved{17, seed};
        const auto dark = parsed.select(catalog, {}, RGB{.07F, .07F, .07F}, seed, saved);
        require(dark.origin == CoatOrigin::hairPool && dark.pool == "dark" && catalog.find(dark.pattern), "Real hair did not choose measured pool");
        const auto reordered = CoatPolicy::parse(policy(true), library(true));
        require(reordered.select(library(true), {}, RGB{.07F, .07F, .07F}, seed, saved).pattern == dark.pattern, "XML ordering changed marking");
        saved.hair = {dark.pool, dark.pattern};
        const auto expanded = CoatPolicy::parse(policy(false, true), library(false, true));
        require(expanded.select(library(false, true), {}, RGB{.09F, .09F, .09F}, seed, saved).pattern == dark.pattern, "Eligible saved choice rerolled after library growth");
        const auto white = parsed.select(catalog, {}, RGB{1, 1, 1}, seed, saved);
        require(white.pattern == "test/white" && white.pool == "light", "Changed real colour did not change eligible pool");
        const auto born = parsed.select(catalog, {}, std::nullopt, seed, saved);
        require(born.origin == CoatOrigin::fallback && born.pool == "natural", "Missing hair did not use declared fallback");
        saved.fallback = {born.pool, born.pattern};
        std::set<std::string> differentReferences;
        for (std::uint64_t id = 1; id <= 64; ++id) {
            const AutomaticCoatState own{id, coatSeed(42, id)};
            differentReferences.insert(parsed.select(catalog, {}, std::nullopt, own.seed, own).pattern);
        }
        require(differentReferences.size() > 1, "Distinct references produced no actual fallback variation");
        const auto manual = parsed.select(catalog, "test/white", std::nullopt, seed, saved);
        require(manual.origin == CoatOrigin::manual && manual.pattern == "test/white", "Manual priority failed");
        require(parsed.select(catalog, {}, std::nullopt, seed, saved).pattern == born.pattern, "Clear/source transition lost cached fallback");
        require(parsed.select(catalog, "test/missing", RGB{1, 1, 1}, seed, saved).pattern.empty(), "Unknown manual choice silently became automatic");
        require(parsed.select(catalog, {}, RGB{-1, 0, 0}, seed, saved).pattern.empty(), "Invalid hair invented a fallback colour");
        require(!CoatPolicy{}.select(catalog, {}, std::nullopt, seed, saved).pattern.size(), "Legacy missing source became random");
        require(CoatPolicy{}.select(catalog, {}, RGB{1, 1, 1}, seed, saved).origin == CoatOrigin::legacyHair, "Absent policy broke legacy selection");
        require(CoatPolicy::unavailable("bad policy").select(catalog, {}, RGB{1, 1, 1}, seed, saved).pattern.empty(), "Invalid policy used unrestricted auto catalog");
        require(CoatPolicy::unavailable("bad policy").select(catalog, "test/white", std::nullopt, seed, saved).pattern == "test/white", "Policy failure erased valid manual compatibility");
        const auto noFallback = CoatPolicy::parse(replace(policy(), "fallbackPool=\"natural\"", "fallbackPool=\"\""), catalog);
        require(noFallback.select(catalog, {}, std::nullopt, seed, saved).pattern.empty(), "Explicit empty fallback was ignored");
        const auto omittedFallback = CoatPolicy::parse(replace(policy(), " fallbackPool=\"natural\"", ""), catalog);
        require(omittedFallback.select(catalog, {}, std::nullopt, seed, saved).pattern.empty(), "Absent fallback was ignored");
        savedSourceLifecycle(catalog, parsed, {{"dark", "test/coal"}, {"light", "test/white"}, {"dark", "test/black"}});
        // A saved pattern can still exist in the catalog but cease to belong
        // to the eligible pool. Both caches must obey current membership.
        const auto reducedHair = CoatPolicy::parse(replace(policy(), "<Pattern id=\"test/coal\"/>", ""), catalog);
        const AutomaticCoatState staleHair{17, seed, {"dark", "test/coal"}, {"natural", "test/white"}};
        require(reducedHair.select(catalog, {}, RGB{.07F, .07F, .07F}, seed, staleHair).pattern == "test/black",
            "Catalog presence allowed an ineligible saved hair marking");
        const auto reducedFallback = CoatPolicy::parse(replace(policy(),
            "<Pool id=\"natural\" use=\"fallback\"><Pattern id=\"test/black\"/>", "<Pool id=\"natural\" use=\"fallback\">"), catalog);
        const AutomaticCoatState staleFallback{17, seed, {"dark", "test/coal"}, {"natural", "test/black"}};
        const auto reselection = reducedFallback.select(catalog, {}, std::nullopt, seed, staleFallback);
        require(reselection.origin == CoatOrigin::fallback && catalog.find(reselection.pattern) && reselection.pattern != "test/black",
            "Catalog presence allowed an ineligible saved fallback marking");
        require(CoatPolicy::parse("<CoatPolicy schemaVersion=\"1\" tintMode=\"original\"><Pools/></CoatPolicy>", catalog).select(catalog, {}, RGB{1, 1, 1}, seed, saved).pattern.empty(), "Manual-only policy was not respected");
        for (const auto xml : {
            replace(policy(), "tintMode=\"original\"", "tintMode=\"unknown\""),
            replace(policy(), "fallbackPool=\"natural\"", "fallbackPool=\"missing\""),
            replace(policy(), "fallbackPool=\"natural\"", "fallbackPool=\"dark\""),
            replace(policy(), "test/coal", "test/missing"),
            replace(policy(), "test/coal", "test/black"),
            replace(policy(), "test/white", "test/black"),
            replace(policy(), "schemaVersion=\"1\"", "schemaVersion=\"2\""),
            replace(policy(), "<Pools>", "<Pools extra=\"yes\">"),
            policy() + "<CoatPolicy/>"}) rejects([&] { CoatPolicy::parse(xml, catalog); });
        rejects([&] { CoatPolicy::parse(std::string(65537, 'x'), catalog); });

        const AutomaticCoatRecord record{0xFF000123, 0xFE00A802, 0, saved};
        const auto bytes = writeAutomaticCoat(record); const auto loaded = readAutomaticCoat(bytes);
        require(loaded.actor == record.actor && loaded.base == record.base && loaded.sex == record.sex && loaded.automatic == saved, "CCAS changed saved seed/reference/choices");
        auto bad = bytes; bad[8] = 2; rejects([&] { readAutomaticCoat(bad); });
        bad = bytes; for (unsigned i = 12; i < 20; ++i) bad[i] = 0; rejects([&] { readAutomaticCoat(bad); });
        bad = bytes; for (unsigned i = 20; i < 28; ++i) bad[i] = 0; rejects([&] { readAutomaticCoat(bad); });
        bad = bytes; bad.pop_back(); rejects([&] { readAutomaticCoat(bad); });
        bad = bytes; bad.push_back('x'); rejects([&] { readAutomaticCoat(bad); });
        bad = bytes; bad[28] = static_cast<char>(255); rejects([&] { readAutomaticCoat(bad); });
        auto invalid = record; invalid.automatic.hair = {"", "test/black"}; rejects([&] { writeAutomaticCoat(invalid); });
        // Existing explicit record codec remains byte-compatible and independent.
        const CoatSelection old{record.actor, record.base, record.sex, "test/white"};
        const auto prior = readCoatSelection(writeCoatSelection(old)); require(prior.pattern == old.pattern && prior.actor == old.actor, "CCPT v1 compatibility changed");
        if (argc == 3) {
            const auto read = [](const char* path) {
                std::ifstream input(path, std::ios::binary); require(bool(input), "Actual input unavailable");
                return std::string((std::istreambuf_iterator<char>(input)), {});
            };
            const auto actualLibrary = CoatLibrary::parse(read(argv[1]));
            const auto actualPolicy = CoatPolicy::parse(read(argv[2]), actualLibrary);
            require(actualLibrary.names().size() == 34 && actualPolicy.tintMode() == TintMode::original, "Actual default policy/catalog differs");
            savedSourceLifecycle(actualLibrary, actualPolicy, {
                {"dark", "elegant-2k-2.1/coal"}, {"dark-brown", "elegant-2k-2.1/umber"},
                {"brown", "elegant-2k-2.1/brown"}, {"red-gold", "elegant-2k-2.1/ginger"},
                {"grey", "elegant-2k-2.1/grey"}, {"light", "elegant-2k-2.1/white"},
                {"dark", "elegant-2k-2.1/coal"}});
            for (const auto& id : actualLibrary.names())
                require(actualPolicy.select(actualLibrary, id, std::nullopt, seed, saved).pattern == id, "Automatic pools hid a manual catalog choice");
            for (std::uint64_t id = 1; id <= 64; ++id) {
                const AutomaticCoatState own{id, coatSeed(42, id)};
                const auto chosen = actualPolicy.select(actualLibrary, {}, std::nullopt, own.seed, own);
                require(chosen.origin == CoatOrigin::fallback && actualLibrary.find(chosen.pattern), "Actual declared fallback did not resolve");
                require(chosen.pattern != "elegant-2k-2.1/hyena-spotted" && chosen.pattern != "elegant-2k-2.1/khajiit", "Stylized pattern escaped natural fallback policy");
            }
            std::cout << "Actual library/policy:34 manual patterns; six hair pools, source transitions, codec-load clear and missing-data recovery validated\n";
        } else require(argc == 1, "Supply both actual catalog and policy paths");
        std::cout << "Coat pools, saved marking selection and additive CCAS compatibility passed\n"; return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
