#include "claw/CoatSurfaceAudit.h"
#include "claw/CoatGeometry.h"
#include <iostream>
#include <memory>
#include <stdexcept>

namespace {
void require(bool value, const char* message) { if (!value) throw std::runtime_error(message); }
std::string joined(const std::vector<std::string>& chunks) {
    std::string result;
    for (const auto& chunk : chunks) result += chunk;
    return result;
}
void chunksPreserveBoundedBytes() {
    using namespace claw::appearance;
    require(coatAuditChunks({}).empty(), "Unavailable audit became a fabricated chunk");
    for (const auto size : {std::size_t{1}, coatAuditChunkBytes - 1, coatAuditChunkBytes,
             coatAuditChunkBytes + 1, coatAuditMaxPayloadBytes - 1, coatAuditMaxPayloadBytes}) {
        const std::string payload(size, 'x');
        const auto chunks = coatAuditChunks(payload);
        require(chunks.size() == (size + coatAuditChunkBytes - 1) / coatAuditChunkBytes,
            "Chunk count truncated the bounded payload");
        require(chunks.size() <= coatAuditMaxChunks && joined(chunks) == payload, "Chunk join changed observation bytes");
        for (const auto& chunk : chunks) require(!chunk.empty() && chunk.size() <= coatAuditChunkBytes,
            "Transport chunk exceeded its per-String bound");
    }
    require(coatAuditChunks(std::string(coatAuditMaxPayloadBytes + 1, 'x')).empty(),
        "Oversize audit was partially returned instead of rejected");
    require(coatAuditChunks(std::string{"ascii"} + char(255)).empty() &&
        coatAuditChunks(std::string{"a\0b", 3}).empty(), "Non-ASCII or embedded-NUL transport accepted");
    const auto escaped = coatAuditQuote(std::string(coatAuditChunkBytes - 2, 'a') + char(255) + "\\\"");
    const auto chunks = coatAuditChunks(escaped);
    require(chunks.size() == 2 && chunks[0].back() == '\\' && chunks[1].starts_with("u00ff") && joined(chunks) == escaped,
        "An escape crossing a fragment boundary was rewritten or truncated");
}
void maximumPublishedObservationUsesOneFreshPayload() {
    using namespace claw::appearance;
    CoatSurfaceObservation row;
    row.name = "x"; row.diffusePath = ""; row.diffuseResource = "";
    std::vector<CoatSurfaceObservation> rows(coatAuditMaxSurfaces, row);
    // ASCII padding changes serialized size by exactly one byte. Fill all legal
    // row fields to the maximum accepted encoded rows size, including ']'.
    const auto initial = coatAuditRows(rows);
    require(!initial.empty() && initial.size() < coatAuditMaxRowsBytes + 1, "Invalid max-payload fixture");
    auto remaining = coatAuditMaxRowsBytes + 1 - initial.size();
    const auto pad = [&remaining](std::string& field, std::size_t maximum) {
        const auto count = std::min(remaining, maximum - field.size());
        field.append(count, 'x'); remaining -= count;
    };
    for (auto& observed : rows) {
        pad(observed.name, coatAuditMaxName);
        pad(*observed.diffusePath, coatAuditMaxPath);
        pad(*observed.diffuseResource, coatAuditMaxPath);
    }
    require(!remaining && coatAuditRows(rows).size() == coatAuditMaxRowsBytes + 1,
        "Maximum accepted observation fixture did not reach the rows bound");
    CoatSurfaceAuditCache cache;
    constexpr auto largest = std::numeric_limits<std::uint64_t>::max();
    require(cache.begin(largest) && cache.publish(largest, largest, 100, true, rows, std::string(129, char(255)), .5733334F),
        "Maximum valid observed audit was rejected");
    const auto payload = cache.read(2100); // One time sample, even across 63 fragments.
    const auto chunks = coatAuditChunks(payload);
    require(payload.size() > coatAuditMaxRowsBytes && payload.size() <= coatAuditMaxPayloadBytes &&
        chunks.size() > 1 && chunks.size() <= coatAuditMaxChunks && joined(chunks) == payload,
        "Maximum actual cached JSON was truncated by chunk transport");
    const auto age = payload.find("\"ageMs\":2000");
    require(age != payload.npos && payload.find("\"ageMs\":", age + 1) == payload.npos,
        "Fragments gained inconsistent or repeated sample ages");
    require(payload.find("\"variation\":0.5733334") != payload.npos, "Bounded JSON lost selection variation");
    require(coatAuditChunks(cache.read(2101)).empty() && coatAuditChunks(cache.read(99)).empty(),
        "Stale or backward-clock audit escaped through fragments");
    require(cache.begin(7) && coatAuditChunks(cache.read(2100)).empty(), "Pending sample exposed old fragments");
    cache.invalidate();
    require(coatAuditChunks(cache.read(2100)).empty(), "Invalidated audit exposed old fragments");

    const std::vector sample{row};
    require(cache.begin(8) && cache.publish(8, 1, 3000, false, sample, "valley-brown", .57F) &&
        cache.read(3000).find("\"coatDecision\"") == std::string::npos,
        "A different model root acquired applied selection evidence");
    require(cache.begin(9) && cache.publish(9, 1, 3001, true, sample, "valley-brown") &&
        cache.read(3001).find("\"coatDecision\"") == std::string::npos,
        "No variation was sampled, but an automatic selection was reported");
}
void routineRefreshKeepsAnUnchangedHumanAudit() {
    using namespace claw::appearance;
    int humanRoot{}, replacementRoot{};
    CoatSurfaceAuditCache cache;
    const auto restore = [&](const void* current, const void* attempt, const void* sampled, bool bound = false) {
        if (coatRestorationNeedsUnbind(current, attempt, sampled, bound)) cache.invalidate();
    };
    CoatSurfaceObservation hair;
    hair.name = "hair";
    require(cache.begin(1), "Initial human observation could not queue");
    restore(&humanRoot, nullptr, nullptr);
    require(cache.pending(1) && cache.publish(1, 7, 100, false, {hair}),
        "The ordinary scan dropped the pending first human observation");
    restore(&humanRoot, nullptr, &humanRoot);
    require(cache.read(166).find("\"sample\":\"1\"") != std::string::npos &&
        !cache.read(100 + coatAuditMaxAgeMs).empty() && cache.read(101 + coatAuditMaxAgeMs).empty(),
        "The ordinary scan erased the original sample or altered its expiry");

    require(cache.begin(2), "Replacement observation could not queue");
    restore(&replacementRoot, nullptr, &humanRoot);
    require(!cache.pending(2) && cache.begin(3), "Root replacement did not fence the old request");
    cache.cancel(2);
    require(!cache.publish(2, 7, 2200, false, {hair}) && cache.pending(3),
        "Late observation of the old model disturbed a newer request");
    restore(nullptr, nullptr, nullptr);
    require(!cache.pending(3) && cache.begin(4), "Unload kept a pending request without a sampled root");
    restore(&humanRoot, &humanRoot, &humanRoot);
    require(!cache.pending(4) && cache.begin(5), "Returning to a model with a previous coat attempt retained its audit");
    restore(&humanRoot, nullptr, &humanRoot, true);
    require(!cache.pending(5), "Actual material restoration left its old audit pending");
}

void appliedDecisionRequiresCompletePrivateMaterialEvidence() {
    using namespace claw::appearance;
    CoatSurfaceObservation managed;
    managed.managed = managed.tracked = managed.healthyLease = managed.ownDiffuse = true;
    std::vector<CoatSurfaceObservation> rows{managed, managed, CoatSurfaceObservation{}};
    require(completeCoatLease(rows, 2), "Unmanaged geometry prevented a complete coat decision");
    require(!completeCoatLease(rows, 3) && !completeCoatLease({}, 0), "Incomplete managed inventory was accepted");
    rows[1].ownDiffuse = false;
    require(!completeCoatLease(rows, 2), "External diffuse replacement retained coat decision evidence");
    rows[1].ownDiffuse = true;
    rows[1].healthyLease = false;
    require(!completeCoatLease(rows, 2), "Unhealthy material lease retained coat decision evidence");
}

void optionalEarRequiresItsTrialRouteAndOwnLease() {
    using namespace claw::appearance;
    const std::string_view male = "Actors/WerewolfBeast/CLAW/FirstPerson/Male/EarWorldTrial.tri";
    const std::string_view female = R"(actors\werewolfbeast\claw\firstperson\female\earworldtrial.tri)";
    require(vrEarCoatBodyTriMatches(male, false) && vrEarCoatBodyTriMatches(female, true),
        "Valid sex-specific ear TRI was rejected");
    require(!vrEarCoatBodyTriMatches(male, true) && !vrEarCoatBodyTriMatches(female, false) &&
        !vrEarCoatBodyTriMatches({}, false) && !vrEarCoatBodyTriMatches("Meshes/" + std::string(male), false) &&
        !vrEarCoatBodyTriMatches(R"(actors\werewolfbeast\claw\firstperson\male\body.tri)", false),
        "An unrelated TRI acquired the optional ear lease");

    CoatSurfaceObservation own;
    own.managed = own.tracked = own.healthyLease = own.ownDiffuse = true;
    std::vector rows(12, own);
    require(completeCoatLease(rows, 12) && !completeCoatLease(rows, 12, 1),
        "Legacy inventory or missing optional lease was classified incorrectly");
    rows.push_back(own);
    require(completeCoatLease(rows, 12, 1), "A fully managed ear prevented valid readback");
    rows.back().ownDiffuse = false;
    require(!completeCoatLease(rows, 12, 1), "An unowned ear diffuse passed as fully applied");
    rows.back().ownDiffuse = true;
    rows.push_back(own);
    require(!completeCoatLease(rows, 12, 2), "An ambiguous ear inventory proved the automatic decision");
}

void sameRootReplacementRequiresNewUnambiguousGeometry() {
    using namespace claw::appearance;
    struct Node {
        std::optional<std::size_t> role;
        std::shared_ptr<int> geometry;
        std::vector<Node*> children;
    };
    Node body{0, std::make_shared<int>(1)}, head{1, std::make_shared<int>(2)};
    Node newBody{0, std::make_shared<int>(3)}, newHead{1, std::make_shared<int>(4)};
    Node root{std::nullopt, {}, {&body, &head}};
    const std::vector lost{body.geometry};
    const auto observe = [&] {
        return collectCoatGeometry<int, 2>(&root, [](auto* node) {
            return std::pair{node->geometry.get(), node->role};
        }, [](auto* node, auto&& push) {
            return std::ranges::all_of(node->children, push);
        });
    };
    *body.geometry = 9;
    require(!observe().clearOf(lost), "A material change passed as geometry turnover");
    root.children = {&body, &newHead};
    require(!observe().clearOf(lost), "Replacement of another surface released the conflict");
    root.children = {&newBody, &newHead, &body};
    body.role.reset();
    require(!observe().clearOf(lost), "Renaming the conflicted surface hid its retained identity");
    root.children.pop_back();
    const auto replaced = observe();
    require(replaced.clearOf(lost) && replaced.unique(0) == newBody.geometry.get() &&
        replaced.unique(1) == newHead.geometry.get(), "Unique full replacement under the same root was rejected");
    const std::vector bothLost{body.geometry, head.geometry};
    root.children = {&newBody, &head};
    require(!observe().clearOf(bothLost), "Replacement of one of two conflicts released both");
    root.children = {&newHead};
    require(!observe().unique(0), "An incomplete replacement obtained a surface");
    Node duplicateName{0, {}};
    root.children = {&newBody, &duplicateName, &newHead};
    require(!observe().unique(0), "An ambiguous replacement obtained a surface");
    root.children = {&newBody, &newHead, &root};
    require(!observe().clearOf(lost) && !observe().unique(0), "Incomplete traversal proved turnover");
}

void publicGeometryIdsTrackAdjacentObjectsWithoutExposingPointers() {
    using namespace claw::appearance;
    using Geometry = CoatAuditGeometry<std::shared_ptr<int>>;
    std::uint64_t next{1};
    const Geometry empty;
    Geometry first;
    auto body = std::make_shared<int>(1), head = std::make_shared<int>(2);
    const std::weak_ptr<int> retainedBody = body;
    auto replacement = std::make_shared<int>(1);
    require(first.observe(body, empty, next) == 1 && first.observe(head, empty, next) == 2,
        "Initial managed geometry IDs are not distinct");
    Geometry second;
    require(second.observe(head, first, next) == 2 && second.observe(replacement, first, next) == 3,
        "Geometry replacement or traversal order was confused with identity");
    require(second.observe(replacement, first, next) == 0 && next == 4, "An aliased geometry received two IDs");
    body.reset();
    require(!retainedBody.expired(), "Previous observation let an address recycle during comparison");
    first = std::move(second);
    require(retainedBody.expired(), "Old geometry outlived its observation bracket");

    std::uint64_t exhausted = std::numeric_limits<std::uint64_t>::max();
    Geometry refused;
    require(refused.observe(head, first, exhausted) == 2 &&
        refused.observe(std::make_shared<int>(3), first, exhausted) == 0, "ID exhaustion reused an old token");
    CoatSurfaceObservation managed;
    managed.managed = true; managed.geometryId = 3;
    const auto encoded = coatAuditRows({managed});
    require(encoded.find("\"geometryId\":\"3\"") != encoded.npos, "Managed geometry has no opaque ID on the wire");
    managed.managed = false;
    require(coatAuditRows({managed}).find("\"geometryId\":\"3\"") != encoded.npos,
        "Unmanaged geometry lost its identity after a rename");
    managed.geometryId = 0;
    require(coatAuditRows({managed}).find("geometryId") == std::string::npos, "An unobserved geometry acquired an ID");
}
}
int main() {
    using namespace claw::appearance;
    try {
        chunksPreserveBoundedBytes(); maximumPublishedObservationUsesOneFreshPayload();
        routineRefreshKeepsAnUnchangedHumanAudit();
        appliedDecisionRequiresCompletePrivateMaterialEvidence();
        optionalEarRequiresItsTrialRouteAndOwnLease();
        sameRootReplacementRequiresNewUnambiguousGeometry();
        publicGeometryIdsTrackAdjacentObjectsWithoutExposingPointers();
        CoatSurfaceObservation row;
        row.name = "body"; row.managed = true; row.materialType = 2; row.feature = 5;
        row.diffusePath = "textures\\actual\\body.dds";
        row.diffuseResource = "textures\\bound\\different.dds";
        row.tint = RGB{0.125F, 1.5F, -0.25F}; // Actual values are never clamped to desired RGB.
        row.materialAlpha = .75F; row.propertyAlpha = .5F;
        row.originalPropertyAlpha = .25F;
        row.originalShaderFlags = std::uint64_t{1} << 35;
        row.hasFadeNode = false; row.originalHasFadeNode = true; row.sameFadeNode = false;
        row.shaderFlags = std::numeric_limits<std::uint64_t>::max(); row.noTint = 2;
        row.tracked = row.ownProperty = row.ownMaterial = true;
        const std::vector rows{row};
        CoatSurfaceAuditCache cache;
        CoatSurfaceAuditCache diagnostic;
        require(cache.begin(91) && diagnostic.begin(92) && diagnostic.publish(92, 7, 100, true, rows),
            "Separate diagnostic observation could not be captured");
        require(cache.pending(91) && cache.read(100).empty() && !diagnostic.read(100).empty(),
            "Diagnostic sampling published/cancelled a public request");
        diagnostic.invalidate(); require(cache.pending(91), "Diagnostic cleanup cancelled a public request");
        cache.invalidate();
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
        require(first.find("\"originalPropertyAlpha\":0.25") != first.npos &&
            first.find("\"originalShaderFlags\":\"34359738368\"") != first.npos, "Retained donor alpha and flags were conflated");
        require(first.find("\"hasFadeNode\":false") != first.npos && first.find("\"originalHasFadeNode\":true") != first.npos &&
            first.find("\"sameFadeNode\":false") != first.npos, "Fade association diagnostics invented a shared node");
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
        std::cout << "Coat surface audit: observed fields, JSON/chunk bounds, exact joins, request ownership, invalidation and freshness passed\n";
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
