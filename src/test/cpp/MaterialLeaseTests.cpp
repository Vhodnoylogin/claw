#include "claw/MaterialLease.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <memory>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
struct Alpha {
    float value{}; bool refuseWrite{};
    operator float() const { return value; }
    Alpha& operator=(float next) { if (!refuseWrite) value = next; return *this; }
};
struct Property { Alpha alpha; const int* material{}; const int* fadeNode{}; };
}
int main() {
    using namespace claw::appearance;
    try {
        MaterialLeaseState initialized;
        initialized.uvScale = {1, 1, 1, 1};
        initialized.specularColour = {0.6F, 0.7F, 0.8F};
        initialized.materialAlpha = initialized.propertyAlpha = 1;
        initialized.specularPower = 0.25F; initialized.specularScale = 1;
        initialized.diffuseTarget = -1; initialized.clampMode = 3;
        initialized.textures = {1, 2, 3, 4}; initialized.textureSet = 5;
        require(mayRestoreMaterial(initialized, initialized), "Unchanged initialized material lost rollback authority");
        require(materialLeaseDifferences(initialized, initialized).empty(), "Unchanged material acquired a fabricated difference");
        // These are same-property, same-material, same-tint/guard takeovers.
        // The earlier ownership test did not inspect any of these mutations,
        // then restored the entire old property and discarded the new value.
        const auto yields = [&](auto change) {
            auto current = initialized; current.propertyAlpha = 0.92416644F; change(current);
            require(!mayRestoreMaterial(initialized, current), "A later in-place material change was overwritten");
            const auto differences = materialLeaseDifferences(initialized, current);
            require(!differences.empty(), "Failed lease comparison lost its diagnostic field/value witness");
            for (const auto& difference : differences)
                require(!difference.field.empty() && !difference.expected.empty() && !difference.observed.empty(),
                    "Lease diagnostic manufactured an unavailable field/value");
        };
        yields([](auto& s) { s.specularPower = 16; });
        yields([](auto& s) { s.specularColour[1] = 0.1F; });
        yields([](auto& s) { s.specularScale = 0.5F; });
        yields([](auto& s) { s.textures[1] = 20; });
        yields([](auto& s) { s.textures[2] = 30; });
        yields([](auto& s) { s.textures[3] = 40; });
        yields([](auto& s) { s.materialAlpha = 0.4F; });
        yields([](auto& s) { s.uvOffset[2] = 0.25F; });
        yields([](auto& s) { s.uvScale[3] = 2; });
        yields([](auto& s) { s.flags ^= 1ULL << 36; }); // two-sided shader flag
        yields([](auto& s) { s.effectData = 60; });
        yields([](auto& s) { s.textureSet = 50; });
        yields([](auto& s) { s.diffuseTarget = 1; });
        yields([](auto& s) { s.clampMode = 0; });
        yields([](auto& s) { s.refractionPower = 0.2F; });
        yields([](auto& s) { s.subSurfaceRolloff = 0.3F; });
        yields([](auto& s) { s.rimPower = 0.7F; });
        yields([](auto& s) { s.specularPower = std::numeric_limits<float>::quiet_NaN(); });
        // Actual Q10 BODY observations. Whole-state equality incorrectly lost
        // the coat lease solely because the actor's property fade finished.
        auto q10 = initialized; q10.propertyAlpha = 0.92416644F;
        auto faded = q10; faded.propertyAlpha = 1.F;
        require(!(q10 == faded), "Q10 regression no longer exercises the old failure");
        require(mayRestoreMaterial(q10, faded), "Finite Q10 property fade still loses coat ownership");
        for (const float alpha : {0.F, 0.1F, 0.6F, 1.F, 1.1F, -0.1F}) {
            auto current = initialized; current.propertyAlpha = alpha;
            require(mayRestoreMaterial(initialized, current), "A finite property fade was mistaken for coat content");
        }
        for (const float alpha : {std::numeric_limits<float>::quiet_NaN(), std::numeric_limits<float>::infinity(),
                 -std::numeric_limits<float>::infinity()}) {
            auto current = initialized; current.propertyAlpha = alpha;
            require(!mayRestoreMaterial(initialized, current) && !mayRestoreMaterial(current, initialized) &&
                !mayRestoreMaterial(current, current), "A nonfinite property fade acquired rollback authority");
        }
        auto invalid = initialized; invalid.propertyAlpha = std::numeric_limits<float>::quiet_NaN();
        require(!mayRestoreMaterial(invalid, invalid), "NaN material witness manufactured rollback authority");
        const auto nan = materialLeaseDifferences(invalid, invalid);
        require(nan.size() == 1 && nan.front().field == "propertyAlpha" && nan.front().expected.find("bits=0x") != std::string::npos,
            "Nonfinite initialized witness was misreported as no change or lost its exact bits");
        auto tiny = initialized; tiny.propertyAlpha = std::nextafter(1.F, 0.F);
        const auto delta = materialLeaseDifferences(initialized, tiny);
        require(delta.size() == 1 && delta.front().field == "propertyAlpha" && delta.front().expected != delta.front().observed,
            "Sub-micro alpha change disappeared in diagnostic float formatting");
        auto high = initialized; high.flags = 1ULL << 63;
        const auto flags = materialLeaseDifferences(initialized, high);
        require(flags.size() == 1 && flags.front().field == "flags" && flags.front().observed == "9223372036854775808",
            "Diagnostic flags lost uint64 precision");
        require(mayRestoreMaterial(initialized, tiny) && !mayRestoreMaterial(initialized, high) &&
            mayRestoreMaterial(initialized, initialized), "Fade separation relaxed a foreign content guard");

        // Exercise the production rollback algorithm, including engine setup
        // changing alpha, without substituting a second implementation.
        int ownMaterial{}, donorMaterial{}, cloneMaterial{}, foreignMaterial{};
        using Ptr = std::shared_ptr<Property>;
        const auto own = std::make_shared<Property>(Property{{1.F}, &ownMaterial});
        const auto donor = std::make_shared<Property>(Property{{0.25F}, &donorMaterial});
        const auto foreign = std::make_shared<Property>(Property{{0.65F}, &foreignMaterial});
        int donorFade{}, otherFade{};
        donor->fadeNode = &donorFade;
        Ptr current = own; unsigned clones{}, setups{};
        require(initializePrivateMaterial(current, own, donor, .25F, [&](const Ptr& copy) {
            require(copy->fadeNode == &donorFade, "Engine initializer did not receive the donor fade association");
            copy->fadeNode = nullptr; copy->alpha = .5F; return true;
        }) && current == own && own->fadeNode == &donorFade && own->alpha == .25F &&
            donor->fadeNode == &donorFade && donor->alpha == .25F,
            "Engine setup reset the private fade association/alpha or changed the shared donor");
        own->alpha = 1.F;
        current = own;
        require(!initializePrivateMaterial(current, own, donor, .25F, [&](const Ptr&) {
            current = foreign; return true;
        }) && current == foreign && foreign->alpha == .65F && foreign->fadeNode == nullptr,
            "Private setup overwrote a later geometry-property writer");
        current = own;
        require(!initializePrivateMaterial(current, own, donor, .25F, [&](const Ptr& copy) {
            copy->material = &foreignMaterial; copy->fadeNode = &otherFade; copy->alpha = .5F; return true;
        }) && current == own && own->material == &foreignMaterial && own->fadeNode == &otherFade && own->alpha == .5F,
            "Private setup overwrote a later material writer");
        own->material = &ownMaterial; own->alpha = 1.F; own->fadeNode = &donorFade;
        current = own;
        const auto clone = [&](const Ptr& source) {
            ++clones; auto copy = std::make_shared<Property>(*source); copy->material = &cloneMaterial; return copy;
        };
        require(restoreMaterialWithAlpha(current, own, donor, clone, [&](const Ptr& copy) {
            ++setups; require(current == copy, "Setup ran before the donor clone was bound");
            copy->fadeNode = nullptr; copy->alpha = 0.5F; return true;
        }), "Isolated donor rollback failed");
        require(current != donor && current != own && current->material == &cloneMaterial && current->alpha == 1.F && current->fadeNode == &donorFade &&
            donor->alpha == 0.25F && donor->material == &donorMaterial && own->alpha == 1.F && clones == 1 && setups == 1,
            "Rollback lost live alpha, mutated a shared donor, or skipped private material isolation");
        current = own;
        require(!restoreMaterialWithAlpha(current, own, donor, [](const Ptr&) { return Ptr{}; }, [](const Ptr&) { return true; }) &&
            current == own, "Clone failure discarded the prior private binding");
        for (const auto& alias : {donor, own}) {
            current = own;
            require(!restoreMaterialWithAlpha(current, own, donor, [&](const Ptr&) { return alias; }, [](const Ptr&) { return true; }) &&
                current == own && donor->alpha == 0.25F, "Aliased rollback clone changed a retained donor/owner");
        }
        current = own;
        require(!restoreMaterialWithAlpha(current, own, donor,
            [](const Ptr& source) { return std::make_shared<Property>(*source); }, [](const Ptr&) { return true; }) && current == own,
            "Shared donor material was admitted to geometry setup");
        current = own;
        require(!restoreMaterialWithAlpha(current, own, donor, clone, [](const Ptr&) { return false; }) && current == own,
            "Setup failure discarded the prior private binding");
        for (const bool initialized : {false, true}) {
            for (const auto* changedMaterial : std::array<const int*, 4>{nullptr, &donorMaterial, &ownMaterial, &foreignMaterial}) {
                current = own; Ptr changed;
                require(!restoreMaterialWithAlpha(current, own, donor, clone, [&](const Ptr& copy) {
                    changed = copy; copy->material = changedMaterial; copy->alpha = 0.5F; return initialized;
                }) && current == changed && current->material == changedMaterial && current->alpha == 0.5F &&
                    donor->material == &donorMaterial && donor->alpha == 0.25F,
                    "Setup replaced rollback material but its later binding/alpha was overwritten or reported restored");
            }
        }
        current = own;
        require(!restoreMaterialWithAlpha(current, own, donor, clone, [](const Ptr& copy) {
            copy->alpha = 0.5F; copy->alpha.refuseWrite = true; return true;
        }) && current == own && donor->alpha == 0.25F, "Alpha readback failure was reported as restored");
        for (const bool initialized : {false, true}) {
            current = own;
            require(!restoreMaterialWithAlpha(current, own, donor, clone, [&](const Ptr&) { current = foreign; return initialized; }) &&
                current == foreign && current->alpha == 0.65F, "Setup overwrote a later property writer");
        }
        clones = setups = 0; current = foreign;
        require(!restoreMaterialWithAlpha(current, own, donor, clone, [&](const Ptr&) { ++setups; return true; }) &&
            current == foreign && clones == 0 && setups == 0, "Foreign geometry property was replaced during rollback");
        const auto equalDonor = std::make_shared<Property>(Property{{1.F}, &donorMaterial}); current = own;
        require(restoreMaterialWithAlpha(current, own, equalDonor, clone, [&](const Ptr&) { ++setups; return true; }) &&
            current == equalDonor && clones == 0 && setups == 0, "Already-current donor alpha changed existing pointer rollback");
        current = own; own->alpha = std::numeric_limits<float>::infinity();
        require(!restoreMaterialWithAlpha(current, own, donor, clone, [](const Ptr&) { return true; }) && current == own && clones == 0,
            "Nonfinite live alpha reached donor restoration");
        own->alpha = 1.F;
        std::cout << "Coat content guards remain strict; finite property fade and rollback alpha are preserved without shared-donor writes\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
