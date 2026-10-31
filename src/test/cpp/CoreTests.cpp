// Offline contracts only. Built/run explicitly after the coordinator opens testing.
#include "claw/Preset.h"
#include "claw/RequestOwnership.h"
#include "claw/MorphLink.h"
#include "claw/MorphProfiles.h"
#include <cmath>
#include <filesystem>
#include <fstream>
#include <functional>
#include <iostream>
#include <limits>
#include <random>
#include <stdexcept>

namespace {
void require(bool condition, const char* reason) { if (!condition) throw std::runtime_error(reason); }
std::string xml(std::string sliders, std::string name = "Example", std::string family = "CLAW Male") {
    return "<?xml version=\"1.0\" encoding=\"UTF-8\"?><SliderPresets version=\"1\"><Preset name=\"" + name +
        "\" set=\"" + family + "\"><Group name=\"CLAW\"/>" + sliders + "</Preset></SliderPresets>";
}
const std::string small = "<SetSlider name=\"CLAWArmGirth\" size=\"small\" value=\"20\"/>";
const std::string big = "<SetSlider name=\"CLAWArmGirth\" size=\"big\" value=\"80\"/>";
void invalid(const std::string& input) {
    claw::Catalog catalog;
    require(!catalog.loadXml(input, "fixture.xml"), "bad XML was accepted");
    require(!catalog.valid() && !catalog.diagnostics().empty(), "bad catalog lacks diagnostics");
    require(catalog.names(claw::Sex::male).empty(), "invalid catalog exposed selectable presets");
}
}

int main() {
    std::size_t passed{};
    const std::vector<std::pair<const char*, std::function<void()>>> cases{
        {"morph linkage combines signed actual values before one clamp", [] {
            claw::MorphLink link{"Explicit-v1", {{"HumanA", "CLAWTorsoGirth", .5F, .25F}, {"HumanB", "CLAWTorsoGirth", .5F, .25F}}, {}, false};
            require(link.valid(claw::Sex::female), "explicit scalar profile rejected");
            link.capture([](std::string_view name) { return name == "HumanA" ? 10.0F : -10.0F; });
            auto result = link.compose(claw::Sex::female);
            require(result.at("CLAWTorsoGirth") == 0, "sources clamped separately or cancellation lost");
            require(result.at("CLAWHeadEarSize") == 0 && result.at("CLAWTailLength") == 0, "unmapped traits were not neutral");
            link.capture([](std::string_view) { return .5F; });
            result = link.compose(claw::Sex::female);
            require(result.at("CLAWTorsoGirth") == .125F && result.at("CLAWTorsoBreastSize") == 0, "weight applied twice or female exclusion lost");
            link.capture([](std::string_view) { return 0.0F; });
            require(link.compose(claw::Sex::male).at("CLAWTorsoGirth") == 0, "cleared human source resurrected cache");
        }},
        {"linked output ignores old independent choices weights and absent catalog", [] {
            claw::Catalog catalog;
            require(catalog.loadXml(xml(small + big + "<SetSlider name=\"CLAWHeadEarSize\" size=\"small\" value=\"30\"/>", "Old A"), "a"), "old A rejected");
            require(catalog.loadXml(xml(big + "<SetSlider name=\"CLAWTailLength\" size=\"big\" value=\"70\"/>", "Old B"), "b"), "old B rejected");
            std::size_t independentCalls{};
            auto oldA = [&] { ++independentCalls; return claw::interpolate(*catalog.find("Old A", claw::Sex::male), 0); };
            auto oldB = [&] { ++independentCalls; return claw::interpolate(*catalog.find("Old B", claw::Sex::male), 100); };
            require(oldA() != oldB(), "old choices/weights do not distinguish regression inputs");
            independentCalls = 0;
            claw::MorphLink link{"Explicit-v1", {{"Human", "CLAWTorsoGirth", 1, .25F}}, {}, false};
            link.capture([](std::string_view) { return .5F; });
            const auto first = claw::resolveMorphs(link, claw::Sex::male, oldA);
            require(first == claw::resolveMorphs(link, claw::Sex::male, oldB), "old independent choice/weight changed linked output");
            claw::Catalog absent;
            require(!absent.valid(), "absent catalog unexpectedly valid");
            const auto noCatalog = claw::resolveMorphs(link, claw::Sex::male, [&]() -> claw::Morphs {
                ++independentCalls;
                throw std::runtime_error("absent catalog and saved preset must not be read");
            });
            require(first == noCatalog && independentCalls == 0, "linked mode consulted independent catalog/weight");
            require(first.size() == claw::recognizedMorphs(claw::Sex::male).size(), "linked cache omitted neutral public morphs");
            for (const auto name : claw::recognizedMorphs(claw::Sex::male))
                require(first.at(std::string(name)) == (name == "CLAWTorsoGirth" ? .125F : 0.F), "unmapped linked trait was nonzero");
            const auto female = claw::resolveMorphs(link, claw::Sex::female, oldA);
            require(female.size() == claw::recognizedMorphs(claw::Sex::female).size() && female.at("CLAWTorsoBreastSize") == 0, "female neutral breast/cache lost");
            require(claw::verifyOwnMorphs(first, [&](std::string_view name) {
                const auto found = first.find(name); return found == first.end() ? 0.F : found->second;
            }), "complete male own-key readback failed");
            claw::MorphLink disabled;
            require(claw::resolveMorphs(disabled, claw::Sex::male, oldA) != first && independentCalls == 1,
                    "disabled linkage did not restore independent selection/interpolation");
        }},
        {"morph linkage cannot feed back its own beast values", [] {
            claw::MorphLink link{"Explicit-v1", {{"CLAWTorsoGirth", "CLAWTorsoGirth", 1, .25F}}, {}, false};
            require(!link.valid(claw::Sex::male), "CLAW source feedback accepted");
            link.rules[0] = {"Human", "CLAWHeadEarSize", 1, .25F};
            require(link.valid(claw::Sex::male), "generic head target refused");
            link.rules[0].target = "CLAWTorsoBreastSize";
            require(link.valid(claw::Sex::female), "explicit female body-resource breast link refused");
            require(link.valid(claw::Sex::male), "generic target interpretation was incorrectly inferred from its name");
        }},
        {"morph linkage rejects ambiguous or unbounded profiles", [] {
            claw::MorphLink link{"Explicit-v1", {{"HumanA", "CLAWTorsoGirth", 1, .25F}, {"HumanB", "CLAWTorsoGirth", 1, .5F}}, {}, false};
            require(!link.valid(claw::Sex::male), "inconsistent caps accepted");
            link.rules[1] = link.rules[0];
            require(!link.valid(claw::Sex::male), "duplicate mapping row accepted");
            link.rules.resize(1); link.rules[0].gain = std::numeric_limits<float>::infinity();
            require(!link.valid(claw::Sex::male), "nonfinite gain accepted");
            require(claw::morphLinkIdentifier("\xD0\x92\xD0\xBE\xD0\xBB\xD0\xBA"), "valid UTF8 identifier rejected");
        }},
        {"resource families are explicit and retain sparse many-to-many signed rules", [] {
            claw::MorphProfileCatalog families;
            const std::string input = "<MorphLinkProfiles schemaVersion=\"1\"><Profile id=\"3BA-2.48-v1\" family=\"3BA\" version=\"2.48\" sex=\"female\" calibration=\"measured-v1\">"
                "<Rule source=\"Arms\" target=\"CLAWArmGirth\" gain=\"-0.5\" cap=\"1\"/>"
                "<Rule source=\"ChubbyArms\" target=\"CLAWArmGirth\" gain=\"0.2\" cap=\"1\"/>"
                "<Rule source=\"Breasts\" target=\"CLAWTorsoBreastSize\" gain=\"0.6\" cap=\"1\"/></Profile></MorphLinkProfiles>";
            require(families.loadXml(input), "typed resource profile rejected");
            require(!families.find("3BA-2.48-v1", claw::Sex::male), "family guessed from mismatched sex");
            require(!families.defaultFor(claw::Sex::female), "undeclared resource default guessed");
            auto link = families.find("3BA-2.48-v1", claw::Sex::female)->link;
            link.capture([](std::string_view source) { return source == "Arms" ? -1.F : .5F; });
            const auto values = link.compose(claw::Sex::female);
            require(std::abs(values.at("CLAWArmGirth") - .6F) < 1e-6F, "source geometry sign or many-to-one composition lost");
            require(std::abs(values.at("CLAWTorsoBreastSize") - .3F) < 1e-6F, "female resource breast coefficient lost");
            require(values.at("CLAWHeadEarSize") == 0, "unmeasured human ear source fabricated");
            require(!families.loadXml(input + input) && !families.valid(), "malformed family reload exposed old policies");
            require(!families.loadXml("<!DOCTYPE MorphLinkProfiles>" + input), "family DTD accepted");
            auto bad = input; bad.replace(bad.find("-0.5"), 4, "nan");
            require(!families.loadXml(bad), "nonfinite family gain accepted");
            auto bound = input;
            bound.insert(bound.find('>') + 1, "<Defaults male=\"\" female=\"3BA-2.48-v1\"/>");
            require(families.loadXml(bound) && families.defaultFor(claw::Sex::female), "declared family default refused");
            require(!families.defaultFor(claw::Sex::male), "empty male resource binding guessed");
            auto wrong = input;
            wrong.insert(wrong.find('>') + 1, "<Defaults male=\"3BA-2.48-v1\" female=\"\"/>");
            require(!families.loadXml(wrong) && !families.defaultFor(claw::Sex::female), "wrong-sex default partially activated");
        }},
        {"expanded family maps remain finitely bounded", [] {
            claw::MorphLink link;
            link.profile = "family-128";
            for (int index = 0; index < 128; ++index)
                link.rules.push_back({"Human" + std::to_string(index), "CLAWTorsoGirth", .001F, 1.F});
            require(link.valid(claw::Sex::male), "128-row resource map rejected");
            link.capture([](std::string_view) { return .5F; });
            require(std::abs(link.compose(claw::Sex::male).at("CLAWTorsoGirth") - .064F) < 1e-6F, "family expansion changed scalar composition");
            link.rules.push_back({"Excess", "CLAWTorsoGirth", 1, 1});
            require(!link.valid(claw::Sex::male), "family rule bound bypassed");
        }},
        {"failed source read preserves the last complete snapshot", [] {
            claw::MorphLink link{"Explicit-v1", {{"Human", "CLAWTorsoGirth", 1, .25F}}, {}, false};
            link.capture([](std::string_view) { return -.5F; });
            bool refused = false;
            try { link.capture([](std::string_view) { return std::numeric_limits<float>::quiet_NaN(); }); }
            catch (const std::exception&) { refused = true; }
            require(refused && link.sourceValues.at("Human") == -.5F, "failed read partly replaced snapshot");
            link.sourceValues.emplace("Unlisted", 1);
            require(!link.valid(claw::Sex::male), "corrupt persisted source accepted");
        }},
        {"bound wrong-sex request error survives pool release and automatic refresh", [] {
            claw::RequestLedger<std::shared_ptr<int>> ledger{1};
            std::map<int, std::shared_ptr<int>> pool;
            auto pin = std::make_shared<int>(7); std::weak_ptr<int> weak = pin;
            pool.emplace(1, pin);
            const auto token = *ledger.begin(1, 3, 101, pin);
            const claw::RequestBinding state{token, 77}; // Attached after validated main-task state lookup.
            require(ledger.finish(1, token, 3, "preset family does not match actor sex"), "owned failure refused");
            pin.reset(); require(claw::collectUnshared(pool) == 1 && weak.expired(), "terminal error pinned actor payload");
            const auto* error = claw::resolveActorRequest(ledger, 1, 3, 0, &state, 77);
            require(error && error->error == "preset family does not match actor sex", "pool collection hid terminal failure");
            // Automatic application status is deliberately not a resolver input.
            require(claw::resolveActorRequest(ledger, 1, 3, 0, &state, 77) == error, "automatic refresh lost request witness");
        }},
        {"new accepted request supersedes terminal error without stale completion", [] {
            claw::RequestLedger<int> ledger{1};
            const auto old = *ledger.begin(1, 4, 101, 1);
            claw::RequestBinding state{old, 77};
            require(ledger.finish(1, old, 4, "wrong family"), "first error refused");
            const auto latest = *ledger.begin(1, 4, 202, 2); state = {latest, 77};
            const auto* pending = claw::resolveActorRequest(ledger, 1, 4, 202, &state, 77);
            require(pending && pending->error.empty() && pending->token == latest, "new request retained old error");
            require(!ledger.finish(1, old, 4, "stale error"), "stale error overwrote new request");
            require(ledger.finish(1, latest, 4), "latest success refused");
            require(!claw::resolveActorRequest(ledger, 1, 4, 0, &state, 77), "success retained terminal error");
        }},
        {"terminal fallback rejects other runtime owner stale serial and world reset", [] {
            claw::RequestLedger<int> ledger{1};
            const auto token = *ledger.begin(1, 3, 101, 1); const claw::RequestBinding a{token, 77};
            require(ledger.finish(1, token, 3, "failed"), "failure refused");
            require(!claw::resolveActorRequest(ledger, 1, 3, 0, nullptr, 88), "unbound B saw A error");
            require(!claw::resolveActorRequest(ledger, 1, 3, 0, &a, 88), "different runtime serial saw A error");
            require(!claw::resolveActorRequest(ledger, 1, 4, 0, &a, 77), "new world saw old error");
            const auto b = *ledger.begin(1, 3, 202, 2);
            require(!claw::resolveActorRequest(ledger, 1, 3, 0, &a, 77), "A fallback saw B ledger row");
            require(ledger.owns(1, b, 3), "A fallback changed B ownership");
            ledger.clear(); require(!claw::resolveActorRequest(ledger, 1, 3, 0, &a, 77), "reset retained error");
        }},
        {"queued actor registry replacement rejects intent even without newer request", [] {
            int a{}, b{};
            require(claw::mayRunActorRequest(&a, &a, true, false), "live pinned owner refused");
            require(!claw::mayRunActorRequest(&a, &b, true, false), "registry B received A intent");
            require(!claw::mayRunActorRequest(&a, &a, true, true), "deleted original actor accepted");
            require(!claw::mayRunActorRequest(&a, &a, false, false), "changed FormID accepted");
            require(!claw::mayRunActorRequest(&a, nullptr, true, false), "missing registry owner accepted");
        }},
        {"weak runtime witness rejects expired and replaced references", [] {
            int a{}, b{};
            require(claw::sameRuntimeActor(&a, &a, &a), "same reference identity refused");
            require(!claw::sameRuntimeActor(&a, nullptr, &a), "expired witness accepted");
            require(!claw::sameRuntimeActor(&a, &b, &b), "replacement reference inherited identity");
            require(!claw::sameRuntimeActor(&a, &a, &b), "current registry owner ignored");
        }},
        {"completed request error releases pending owner payload", [] {
            claw::RequestLedger<std::shared_ptr<int>> ledger{1};
            auto owner = std::make_shared<int>(7); std::weak_ptr<int> weak = owner;
            const auto ticket = *ledger.begin(1, 1, 7, owner); owner.reset();
            require(!weak.expired(), "pending owner was not retained");
            require(ledger.finish(1, ticket, 1, "failed"), "owned failure refused");
            require(weak.expired(), "completed error retained pending owner");
            require(ledger.find(1, 7, 1)->error == "failed", "error metadata disappeared");
        }},
        {"pool retains owner when task finishes before native callback", [] {
            std::map<int, std::shared_ptr<int>> pool;
            auto native = std::make_shared<int>(7); std::weak_ptr<int> weak = native;
            pool.emplace(1, native); auto task = native;
            task.reset();
            require(claw::collectUnshared(pool) == 0 && !weak.expired(), "task completion released native owner");
            native.reset();
            require(!weak.expired(), "last native copy released pooled owner");
            require(claw::collectUnshared(pool) == 1 && weak.expired(), "explicit pool collection failed");
        }},
        {"reused ID old actor completion cannot alter new actor request", [] {
            claw::RequestLedger<std::string> ledger{2};
            const auto a = *ledger.begin(0xFF001234, 1, 101, "actor A");
            const auto b = *ledger.begin(0xFF001234, 1, 202, "actor B");
            require(!ledger.finish(0xFF001234, a, 1, "A failed"), "old A replaced B error");
            require(!ledger.finish(0xFF001234, a, 1), "old A erased B pending");
            const auto* row = ledger.find(0xFF001234, 202, 1);
            require(row && row->owner == "actor B" && row->error.empty() && row->token == b, "B pending changed");
            require(!ledger.find(0xFF001234, 101, 1), "A getter exposed B request");
        }},
        {"same actor newer serial supersedes delayed work", [] {
            claw::RequestLedger<int> ledger{1};
            const auto old = *ledger.begin(1, 4, 7, 7);
            const auto latest = *ledger.begin(1, 4, 7, 7);
            require(!ledger.owns(1, old, 4) && ledger.owns(1, latest, 4), "request serial ignored");
            require(!ledger.finish(1, old, 4, "old error"), "stale same-actor error accepted");
            require(ledger.finish(1, latest, 4, "latest error"), "owned error refused");
            require(ledger.find(1, 7, 4)->error == "latest error", "owned error lost");
        }},
        {"world epoch invalidates pending work without serial reuse", [] {
            claw::RequestLedger<int> ledger{1};
            const auto old = *ledger.begin(1, 3, 8, 8);
            require(!ledger.finish(1, old, 4, "old world"), "wrong epoch completed a request");
            ledger.clear();
            const auto restored = *ledger.begin(1, 4, 8, 8);
            require(restored.serial != old.serial, "request serial reused after clear");
            require(!ledger.finish(1, old, 4), "pre-load task erased restored request");
            require(ledger.owns(1, restored, 4), "restored pending lost");
        }},
        {"old deletion receipt cannot erase another runtime owner", [] {
            claw::RequestLedger<int> ledger{1};
            const auto b = *ledger.begin(9, 2, 202, 202);
            require(!ledger.eraseOwner(9, 101), "A deletion erased B request");
            require(ledger.owns(9, b, 2), "B no longer owns its request");
            require(ledger.eraseOwner(9, 202), "matching deletion owner refused");
        }},
        {"request limit bounds distinct actors but permits replacement", [] {
            claw::RequestLedger<int> ledger{2};
            require(ledger.begin(1, 1, 1, 1).has_value() && ledger.begin(2, 1, 2, 2).has_value(), "capacity unavailable");
            require(!ledger.begin(3, 1, 3, 3), "request bound bypassed");
            require(ledger.begin(1, 1, 4, 4).has_value(), "same-ID replacement rejected");
            require(!ledger.find(1, 1, 1) && ledger.find(1, 4, 1), "replaced owner leaked");
        }},
        {"restored VM identity requires successful nonempty remap", [] {
            require(claw::mayBindRestoredIdentity(123, 123, false), "matching restored identity refused");
            require(!claw::mayBindRestoredIdentity(0, 123, false), "failed remap became fresh identity");
            require(!claw::mayBindRestoredIdentity(123, 0, false), "missing current VM identity accepted");
            require(!claw::mayBindRestoredIdentity(123, 456, false), "changed VM identity silently rebound");
            require(!claw::mayBindRestoredIdentity(123, 123, true), "quarantined identity escaped");
        }},
        {"weight endpoints and midpoint", [] {
            claw::Catalog catalog; require(catalog.loadXml(xml(small + big), "fixture"), "valid preset rejected");
            const auto* preset = catalog.find("Example", claw::Sex::male); require(preset != nullptr, "missing male preset");
            require(std::abs(claw::interpolate(*preset, 0).at("CLAWArmGirth") - .2F) < 1e-6, "low endpoint lost");
            require(std::abs(claw::interpolate(*preset, 50).at("CLAWArmGirth") - .5F) < 1e-6, "weight interpolated incorrectly");
            require(std::abs(claw::interpolate(*preset, 100).at("CLAWArmGirth") - .8F) < 1e-6, "high endpoint lost");
        }},
        {"omitted endpoints use BodySlide zero semantics", [] {
            claw::Catalog catalog; require(catalog.loadXml(xml(big), "fixture"), "sparse preset rejected");
            const auto* preset = catalog.find("Example", claw::Sex::male);
            require(claw::interpolate(*preset, 0).at("CLAWArmGirth") == 0, "omitted small endpoint was not zero");
            require(std::abs(claw::interpolate(*preset, 25).at("CLAWArmGirth") - .2F) < 1e-6, "sparse interpolation wrong");
        }},
        {"typed neutral presets and full owned-key readback", [] {
            claw::Catalog catalog;
            require(catalog.loadXml(xml("", "Neutral male"), "male"), "neutral male rejected");
            require(catalog.loadXml(xml("", "Neutral female", "CLAW Female"), "female"), "neutral female rejected");
            const auto empty = claw::interpolate(*catalog.find("Neutral male", claw::Sex::male), 50);
            require(empty.empty(), "neutral preset gained a nonzero morph");
            std::size_t visited{};
            require(claw::verifyOwnMorphs(empty, [&](std::string_view) { ++visited; return 0.F; }), "zero neutral readback failed");
            require(visited == claw::recognizedMorphs(claw::Sex::female).size(), "neutral readback skipped recognized morphs");
            require(!claw::verifyOwnMorphs(empty, [](std::string_view name) { return name == "CLAWTailFluff" ? .4F : 0.F; }),
                    "neutral readback accepted an unexpected own value");
            const claw::Morphs sparse{{"CLAWArmGirth", .5F}};
            require(claw::verifyOwnMorphs(sparse, [](std::string_view name) { return name == "CLAWArmGirth" ? .5F : 0.F; }),
                    "matching sparse readback failed");
            require(!claw::verifyOwnMorphs(sparse, [](std::string_view name) {
                if (name == "CLAWArmGirth") return .5F;
                return name == "CLAWTorsoBreastSize" ? .2F : 0.F;
            }), "sparse readback skipped omitted female-only owned morph");
            require(!claw::verifyOwnMorphs(empty, [](std::string_view) { return std::numeric_limits<float>::quiet_NaN(); }),
                    "nonfinite readback was accepted");
        }},
        {"preset names use trimmed 160-byte strict UTF-8 contract", [] {
            invalid(xml(big, " Leading")); invalid(xml(big, "Trailing "));
            invalid(xml(big, std::string("Control") + char(127)));
            invalid(xml(big, std::string(161, 'a')));
            invalid(xml(big, std::string("Broken") + char(0xC0) + char(0xAF)));
            invalid(xml(big, std::string("Surrogate") + char(0xED) + char(0xA0) + char(0x80)));
            invalid(xml(big, std::string("Truncated") + char(0xE2) + char(0x82)));
            invalid(xml(big, "Embedded&#0;Nul"));
            invalid(xml(big, "Unknown&bogus;Entity"));
            claw::Catalog catalog;
            require(catalog.loadXml(xml(big, std::string(160, 'a')), "boundary"), "160-byte ASCII name rejected");
            std::string unicode;
            for (int index = 0; index < 80; ++index) unicode += "\xC3\xA9";
            require(catalog.loadXml(xml(big, unicode), "unicode"), "160-byte UTF-8 name rejected");
            invalid(xml(big, unicode + "\xC3\xA9"));
        }},
        {"typed families and adult exclusion", [] {
            invalid(xml("<SetSlider name=\"CLAWTorsoBreastSize\" size=\"big\" value=\"50\"/>"));
            invalid(xml("<SetSlider name=\"CLAWCrotchVulva\" size=\"big\" value=\"50\"/>", "Adult", "CLAW Female"));
            invalid(xml("<SetSlider name=\"HIMBOChest\" size=\"big\" value=\"50\"/>"));
            invalid(xml(big, "Fake", "HIMBO"));
            claw::Catalog catalog;
            require(catalog.loadXml(xml(big, "Female", "CLAW Female"), "fixture"), "female preset rejected");
            require(!catalog.find("Female", claw::Sex::male), "female leaked into male catalog");
        }},
        {"duplicate endpoint and preset names fail closed", [] {
            invalid(xml(big + big));
            claw::Catalog catalog; require(catalog.loadXml(xml(big), "first"), "first preset rejected");
            require(!catalog.loadXml(xml(small), "second"), "duplicate name accepted across files");
            require(!catalog.valid() && catalog.size() == 0, "duplicate catalog remained usable");
        }},
        {"invalid numbers and malformed XML rejected", [] {
            for (const std::string value : {"nan", "inf", "1e1000", "50junk", "", "-1", "101"})
                invalid(xml("<SetSlider name=\"CLAWArmGirth\" size=\"big\" value=\"" + value + "\"/>"));
            invalid("<SliderPresets><Preset>");
            invalid(xml(big) + "<Other/>");
            invalid(xml(big + "<Unexpected/>"));
            invalid(xml(big + "unrecognized text"));
            invalid("<!DOCTYPE SliderPresets [<!ENTITY x SYSTEM 'file:///private'>]>" + xml(big));
        }},
        {"stable choice ignores file load order", [] {
            claw::Catalog first, second;
            require(first.loadXml(xml(big, "One"), "one") && first.loadXml(xml(small, "Two"), "two"), "first catalog failed");
            require(second.loadXml(xml(small, "Two"), "two") && second.loadXml(xml(big, "One"), "one"), "second catalog failed");
            for (int index = 0; index < 100; ++index) {
                const auto identity = "save-namespace/reference-" + std::to_string(index);
                require(first.choose(identity, claw::Sex::male)->name == second.choose(identity, claw::Sex::male)->name, "choice depends on traversal order");
            }
            require(!first.choose("id", claw::Sex::female), "wrong-sex fallback occurred");
        }},
        {"invalid actor weight refused", [] {
            claw::Catalog catalog; catalog.loadXml(xml(big), "fixture");
            for (float weight : {-1.F, 101.F, std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
                bool failed{}; try { (void)claw::interpolate(*catalog.find("Example", claw::Sex::male), weight); }
                catch (const std::invalid_argument&) { failed = true; }
                require(failed, "invalid actor weight was accepted");
            }
        }},
        {"nested third-party directory and unreadable catalog", [] {
            const auto folder = std::filesystem::temp_directory_path() / ("claw-core-" + std::to_string(std::random_device{}()));
            std::filesystem::create_directories(folder / "Author");
            try {
                std::ofstream(folder / "Author" / "one.xml") << xml(big, "Nested");
                claw::Catalog catalog; require(catalog.loadDirectory(folder), "nested author preset missed");
                require(catalog.find("Nested", claw::Sex::male) != nullptr, "nested preset missing");
                std::ofstream(folder / "bad.xml") << "not XML";
                require(!catalog.loadDirectory(folder), "bad file silently ignored");
                require(!catalog.valid(), "catalog did not fail closed");
                require(!catalog.loadDirectory(folder / "missing"), "missing directory accepted");
            } catch (...) { std::filesystem::remove_all(folder); throw; }
            std::filesystem::remove_all(folder);
        }}
    };
    for (const auto& [name, run] : cases) {
        try { run(); ++passed; std::cout << "PASS " << name << '\n'; }
        catch (const std::exception& error) { std::cerr << "FAIL " << name << ": " << error.what() << '\n'; return 1; }
    }
    std::cout << passed << " offline contract cases passed\n";
}
