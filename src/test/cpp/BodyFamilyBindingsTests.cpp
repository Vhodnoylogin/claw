#include "claw/BodyFamilyBindings.h"
#include <chrono>
#include <iostream>

namespace {
void require(bool condition, const char* message) { if (!condition) throw std::runtime_error(message); }
constexpr auto profiles = R"(<MorphLinkProfiles schemaVersion="1">
<Defaults male="male" female="cbbe"/>
<Profile id="male" family="HIMBO" version="5.8" sex="male" calibration="test"><Rule source="Muscle" target="Wolf" gain="0.2" cap="1"/></Profile>
<Profile id="cbbe" family="CBBE" version="2.0.3" sex="female" calibration="test"><Rule source="Shared" target="Wolf" gain="0.3" cap="1"/></Profile>
<Profile id="bhunp" family="BHUNP" version="3.34" sex="female" calibration="test"><Rule source="Shared" target="Wolf" gain="0.8" cap="1"/></Profile>
</MorphLinkProfiles>)";
constexpr auto bindings = R"(<BodyFamilyBindings schemaVersion="1">
<Bind sex="female" mesh="Actors/Unique/BHUNP/Body_1.nif" profile="bhunp"/>
<Bind sex="female" mesh="actors/unique/bhunp/body_0.nif" profile="bhunp"/>
<Bind sex="female" mesh="actors/unique/cbbe/body_1.nif" profile="cbbe"/>
</BodyFamilyBindings>)";
}
int main() {
    try {
        using claw::Sex;
        using Reason = claw::BodyFamilySelection::Reason;
        claw::MorphProfileCatalog catalog;
        require(catalog.loadXml(profiles), "test catalog rejected");
        claw::BodyFamilyBindings policy;
        const std::vector<std::string> custom{"Meshes\\ACTORS\\Unique\\BHUNP\\Body_1.NIF"};
        require(policy.select(Sex::female, custom, catalog).profile->id == "cbbe", "absent bindings changed installer default");
        require(policy.loadXml(bindings, catalog), "valid bindings rejected");
        auto selected = policy.select(Sex::female, custom, catalog);
        require(selected.profile && selected.profile->id == "bhunp" && selected.reason == Reason::skinBinding, "custom skin not bound");
        require(policy.select(Sex::male, custom, catalog).profile->id == "male", "female override leaked across sex");
        require(policy.select(Sex::female, custom, catalog, false).profile->id == "cbbe", "unobserved former body inferred from wolf resources");
        const std::vector<std::string> ordinary{"actors/character/character assets/femalebody_1.nif"};
        require(policy.select(Sex::female, ordinary, catalog).profile->id == "cbbe", "unmapped common path guessed body family");
        const std::vector<std::string> duplicates{custom[0], "actors/unique/bhunp/body_0.nif", custom[0]};
        require(policy.select(Sex::female, duplicates, catalog).profile->id == "bhunp", "same-family models became ambiguous");
        const std::vector<std::string> conflicting{custom[0], "actors/unique/cbbe/body_1.nif"};
        selected = policy.select(Sex::female, conflicting, catalog);
        require(!selected.profile && selected.blocked() && selected.reason == Reason::ambiguous, "conflicting families silently selected one");
        for (const auto path : {"../body.nif", "/actors/body.nif", "C:\\body.nif", "actors/../body.nif", "actors/./body.nif",
                "actors//body.nif", "actors/body.dds", "actors/body.nif/", " body.nif", "body.nif ", ""})
            require(!claw::bodyMeshIdentity(path), "invalid mesh identity accepted");
        require(claw::bodyMeshIdentity("Meshes\\ACTORS\\Body.NIF") == std::optional<std::string>{"actors/body.nif"}, "mesh normalization changed");
        // Identical named human inputs use exactly one family, not their sum.
        auto cbbe = catalog.defaultFor(Sex::female)->link;
        auto bhunp = policy.select(Sex::female, custom, catalog).profile->link;
        for (auto* link : {&cbbe, &bhunp}) link->captureActor([](auto) { return .5F; }, 50.F, [](auto) { return 0.F; });
        require(cbbe.compose(Sex::female).at("Wolf") == .15F && bhunp.compose(Sex::female).at("Wolf") == .4F, "family projection was mixed");
        // Saved rules remain authoritative: changing a catalog/binding later does
        // not mutate the actor link copied at original human-form adoption.
        require(policy.loadXml("<BodyFamilyBindings schemaVersion=\"1\"/>", catalog), "empty compatibility map rejected");
        require(policy.select(Sex::female, custom, catalog).profile->id == "cbbe" && bhunp.profile == "bhunp" && bhunp.compose(Sex::female).at("Wolf") == .4F,
            "policy update rewrote adopted matrix");
        for (const auto xml : {
                R"(<BodyFamilyBindings schemaVersion="2"/>)",
                R"(<BodyFamilyBindings schemaVersion="1"><Bind sex="female" mesh="body.nif" profile="missing"/></BodyFamilyBindings>)",
                R"(<BodyFamilyBindings schemaVersion="1"><Bind sex="male" mesh="body.nif" profile="bhunp"/></BodyFamilyBindings>)",
                R"(<BodyFamilyBindings schemaVersion="1"><Bind sex="female" mesh="body.nif" profile="cbbe" extra="x"/></BodyFamilyBindings>)",
                R"(<BodyFamilyBindings schemaVersion="1"><Bind sex="female" mesh="body.nif" profile="cbbe">x</Bind></BodyFamilyBindings>)",
                R"(<BodyFamilyBindings schemaVersion="1"><Bind sex="female" mesh="body.nif" profile="cbbe"/><Bind sex="female" mesh="Meshes\BODY.NIF" profile="cbbe"/></BodyFamilyBindings>)",
                R"(<BodyFamilyBindings schemaVersion="1"/><BodyFamilyBindings schemaVersion="1"/>)",
                R"(garbage<BodyFamilyBindings schemaVersion="1"/>)",
                R"(<BodyFamilyBindings schemaVersion="1"/>garbage)",
                R"(<!DOCTYPE x><BodyFamilyBindings schemaVersion="1"/>)"}) {
            require(!policy.loadXml(xml, catalog) && !policy.error().empty(), "malformed compatibility map accepted");
            require(policy.select(Sex::female, custom, catalog).blocked(), "bad config silently reverted custom body to default");
            require(policy.select(Sex::female, custom, catalog, false).blocked(), "bad config silently adopted a default for a fresh wolf");
            require(policy.loadXml(bindings, catalog), "valid reload did not recover");
        }
        // The optional file is different from an installed but broken file.
        struct TemporaryFile {
            std::filesystem::path path = std::filesystem::current_path() /
                ("body-bindings-" + std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()) + ".xml");
            ~TemporaryFile() { std::error_code ec; std::filesystem::remove(path, ec); }
        } file;
        require(!std::filesystem::exists(file.path), "temporary fixture already exists");
        require(policy.loadFile(file.path, catalog) && policy.empty(), "absent optional file became an error");
        { std::ofstream out(file.path); out << bindings; }
        require(policy.loadFile(file.path, catalog) && policy.select(Sex::female, custom, catalog).profile->id == "bhunp", "actual compatibility file not loaded");
        { std::ofstream out(file.path, std::ios::trunc); }
        require(!policy.loadFile(file.path, catalog) && policy.select(Sex::female, custom, catalog).blocked(), "empty present file treated as absent");
        { std::ofstream out(file.path); out << std::string(65537, ' '); }
        require(!policy.loadFile(file.path, catalog), "oversized file accepted");
        std::cout << "Body-family binding contracts passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
