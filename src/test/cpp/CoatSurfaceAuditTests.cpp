#include "claw/CoatSurfaceAudit.h"
#include <iostream>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
}
int main() {
    using namespace claw::appearance;
    try {
        CoatSurfaceObservation row;
        row.name = "body"; row.managed = true; row.materialType = 2; row.feature = 5;
        row.diffusePath = "textures\\actual\\body.dds";
        row.diffuseResource = "textures\\bound\\different.dds";
        row.tint = RGB{0.125F, 1.5F, -0.25F}; // Actual values are never clamped to desired RGB.
        row.materialAlpha = .75F; row.propertyAlpha = .5F;
        row.shaderFlags = std::numeric_limits<std::uint64_t>::max(); row.noTint = 2;
        row.tracked = row.ownProperty = row.ownMaterial = true;
        const std::vector rows{row};
        CoatSurfaceAuditCache cache;
        require(cache.read(100).empty() && !cache.begin(0), "Missing audit fabricated data");
        require(cache.begin(1) && !cache.begin(2) && cache.read(100).empty(), "Pending admission reused old data");
        require(!cache.publish(2, 1, 100, true, rows) && cache.pending(1), "Stale completion changed current request");
        require(cache.publish(1, 7, 100, true, rows), "Valid observed snapshot rejected");
        const auto first = cache.read(100);
        require(first.find("\"sample\":\"1\"") != first.npos && first.find("\"modelGeneration\":\"7\"") != first.npos &&
            first.find("\"ageMs\":0") != first.npos, "Sample/generation/freshness metadata missing");
        require(first.find("textures\\\\actual\\\\body.dds") != first.npos && first.find("textures\\\\bound\\\\different.dds") != first.npos,
            "Texture-set path and bound resource observation were conflated");
        require(first.find("\"tint\":[0.125,1.5,-0.25]") != first.npos && first.find("18446744073709551615") != first.npos,
            "Actual tint or 64-bit flags lost precision or were clamped");
        require(!cache.read(2100).empty() && cache.read(2101).empty() && cache.read(99).empty(), "Stale or backward-clock audit remained available");
        require(cache.begin(3) && cache.read(101).empty(), "New sampling request exposed previous sample");
        cache.cancel(1); require(cache.pending(3), "Old cancellation erased a newer request");
        cache.invalidate(); require(!cache.publish(3, 7, 102, true, rows) && cache.read(102).empty(), "Invalidated sample was resurrected");
        require(cache.begin(4) && !cache.publish(4, 0, 102, true, rows) && cache.begin(5), "Invalid model generation blocked future requests");
        row.managed = false; row.tracked = row.ownProperty = row.ownMaterial = false;
        row.feature.reset(); row.tint.reset(); row.diffusePath.reset(); row.noTint = 0;
        require(cache.publish(5, 8, 103, false, {row}), "Excluded/unavailable field observation rejected");
        const auto excluded = cache.read(103);
        require(excluded.find("\"managed\":false") != excluded.npos && excluded.find("\"tint\":null") != excluded.npos &&
            excluded.find("\"diffusePath\":null") != excluded.npos && excluded.find("\"leaseRootCurrent\":false") != excluded.npos,
            "Missing fields or excluded surfaces acquired invented material state");
        require(coatAuditQuote(std::string{"\"\\\n"} + char(255)) == "\"\\\"\\\\\\u000a\\u00ff\"", "Observed bytes broke JSON escaping");
        require(coatAuditNumber(std::numeric_limits<float>::quiet_NaN()) == "null" &&
            coatAuditNumber(std::numeric_limits<float>::infinity()) == "null", "Nonfinite shader observation became invalid JSON");
        require(coatAuditRows({}).empty() && coatAuditRows(std::vector<CoatSurfaceObservation>(coatAuditMaxSurfaces + 1)).empty(),
            "Empty/excessive surface inventory was published as complete");
        row.name.assign(coatAuditMaxName + 1, 'x'); require(coatAuditRows({row}).empty(), "Excessive geometry name accepted");
        row.name = "eyes"; row.diffusePath = std::string(coatAuditMaxPath + 1, 'x');
        require(coatAuditRows({row}).empty(), "Excessive observed texture path accepted");
        row.diffusePath = std::string(coatAuditMaxPath, char(255)); row.diffuseResource = row.diffusePath;
        require(coatAuditRows(std::vector<CoatSurfaceObservation>(coatAuditMaxSurfaces, row)).empty(), "Excessive encoded snapshot accepted");
        std::cout << "Coat surface audit: observed fields, JSON bounds, request ownership, invalidation and freshness passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
