#include "PairProvider.h"
#include "PairWindow.h"

#include "../ActorManager.h"
#include "../hdtSkinnedMesh/hdtSkinnedMeshShape.h"
#include "../hdtSkyrimPhysicsWorld.h"
#include "../hdtSkyrimSystem.h"

#include <algorithm>
#include <string>
#include <string_view>
#include <Windows.h>

namespace claw::contact::provider {
namespace {
constexpr std::string_view prefix = "SKSE/Plugins/hdtSkinnedMeshConfigs/CLAW/";
constexpr std::string_view surfaceTag = "CLAW.NeutralAnatomy.Surface.v1";
constexpr std::string_view probeTag = "CLAW.NeutralAnatomy.Peer.v1";
constexpr std::string_view controlTag = "CLAW.NeutralAnatomy.Control.v1";
constexpr std::array drivers{"WWD 2", "WWLB 1", "WWRB 1"};
constexpr std::string_view probeBoneName = "NPC Pelvis [Pelv]";

struct Bound {
    Key body{}, root{}, worldObject{};
    std::array<Key, 3> drivers{};
    Key probeBone{};
    bool control{};
};

Window window;
Bound surface{}, probe{};
std::uint32_t confirmedNonce{};

Tick qpc() noexcept {
    LARGE_INTEGER value{};
    return ::QueryPerformanceCounter(&value) && value.QuadPart > 0 ? static_cast<Tick>(value.QuadPart) : 0;
}

template <class T> Key key(const T* pointer) noexcept {
    return reinterpret_cast<Key>(pointer);
}

bool sameName(const RE::BSFixedString& actual, std::string_view original, std::string_view renamePrefix) {
    const std::string_view value = actual.c_str();
    return value == original || (!renamePrefix.empty() && value.starts_with(renamePrefix)
                                 && value.substr(renamePrefix.size()) == original);
}

Bound validate(const hdt::SkinnedMeshBody* candidate, Key root, bool isSurface, bool isControl,
               std::string_view renamePrefix) {
    const auto* body = static_cast<const hdt::SkyrimBody*>(candidate);
    const auto hasTag = [](const auto& tags, std::string_view value) {
        return std::ranges::any_of(tags, [value](const auto& tag) { return value == tag.c_str(); });
    };
    if (!body || !body->m_mesh || key(body->m_mesh->m_skeleton.get()) != root || body->m_disabled
        || body->m_shared != hdt::SkyrimBody::SharedType::SHARED_EXTERNAL || !body->m_shape
        || body->m_isKinematic == isSurface || bool(body->m_shape->asPerTriangleShape()) != isSurface
        || body->m_tags.size() != 1 || body->m_canCollideWithTags.size() != 1 || !body->m_noCollideWithTags.empty()
        || !hasTag(body->m_tags, isSurface ? surfaceTag : isControl ? controlTag : probeTag)
        || !hasTag(body->m_canCollideWithTags, isSurface ? probeTag : surfaceTag))
        return {};

    Bound result{key(candidate), root, key(static_cast<const btCollisionObject*>(candidate)), {}, 0, isControl};
    for (const auto& entry : body->m_skinnedBones) {
        const auto* bone = entry.ptr;
        if (!bone) return {};
        if (isSurface && !entry.isKinematic) {
            for (std::size_t i = 0; i < drivers.size(); ++i) {
                if (!sameName(bone->m_name, drivers[i], renamePrefix)) continue;
                if (result.drivers[i]) return {};
                result.drivers[i] = key(bone);
            }
        } else if (!isSurface && entry.isKinematic && sameName(bone->m_name, probeBoneName, renamePrefix)) {
            if (result.probeBone) return {};
            result.probeBone = key(bone);
        }
    }
    if (isSurface ? std::ranges::find(result.drivers, Key{}) != result.drivers.end()
                  : !result.probeBone || body->m_skinnedBones.size() != 1)
        return {};
    return result;
}

Bound resolve(std::uint32_t actor, std::uint32_t addon, bool isSurface) {
    Bound result;
    for (auto& skeleton : hdt::ActorManager::instance()->getSkeletons()) {
        if (!skeleton.skeleton || !skeleton.npc) continue;
        const auto* owner = skeleton.skeleton->GetUserData();
        if (!owner || owner->formID != actor) continue;
        for (auto& armor : skeleton.getArmors()) {
            if (!armor.armorWorn || !armor.m_physics || !armor.m_physics->m_world
                || !hasAddonId(armor.armorWorn->name.c_str(), addon))
                continue;
            auto path = armor.physicsFile.first;
            std::replace(path.begin(), path.end(), '\\', '/');
            if (!std::string_view(path).starts_with(prefix)) continue;
            const auto file = std::string_view(path).substr(prefix.size());
            const bool control = file == "CLAWAnatomyContactProbeNoContact.xml";
            const bool exact = isSurface ? file == "CLAWNeutralAnatomyContact.xml"
                                      || file == "CLAWMotionNeutralAnatomyContactMale.xml"
                                         : control || file == "CLAWAnatomyContactProbe.xml";
            if (!exact) continue;
            for (const auto& body : armor.meshes()) {
                if (!body || std::string_view(body->m_name.c_str()) != (isSurface ? "genitals" : "CLAWAnatomyContactProbe"))
                    continue;
                if (result.body) return {};
                result = validate(body.get(), key(skeleton.npc.get()), isSurface, control, armor.prefix);
                if (!result.body) return {};
            }
        }
    }
    return result;
}

bool ownedRef(std::uint32_t id) noexcept {
    return id >= 0xff000000u && id < 0xffffffffu;
}

bool arm(RE::StaticFunctionTag*, RE::Actor* surfaceActor, RE::TESObjectARMA* surfaceAddon,
         RE::Actor* probeActor, RE::TESObjectARMA* probeAddon, std::int32_t nonce, std::int32_t epoch, std::int32_t steps) {
    if (!surfaceActor || !probeActor || !surfaceAddon || !probeAddon || nonce <= 0 || epoch <= 0 || steps <= 0
        || !ownedRef(surfaceActor->formID) || !ownedRef(probeActor->formID))
        return false;
    auto actorGuard = hdt::ActorManager::instance()->lockGuard();
    auto simulationGuard = hdt::SkyrimPhysicsWorld::get()->lockSimulation();
    const auto left = resolve(surfaceActor->formID, surfaceAddon->formID, true);
    const auto right = resolve(probeActor->formID, probeAddon->formID, false);
    LARGE_INTEGER frequency{};
    if (!::QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0) return false;
    if (!window.arm({static_cast<std::uint32_t>(nonce), static_cast<std::uint32_t>(epoch),
                     static_cast<std::uint32_t>(steps), static_cast<Tick>(frequency.QuadPart)},
                    {surfaceActor->formID, surfaceAddon->formID, probeActor->formID, probeAddon->formID,
                     left.body, right.body, left.root, right.root, right.control}))
        return false;
    surface = left;
    probe = right;
    confirmedNonce = 0;
    return true;
}

bool cancel(RE::StaticFunctionTag*, std::int32_t nonce) {
    auto simulationGuard = hdt::SkyrimPhysicsWorld::get()->lockSimulation();
    if (nonce <= 0 || static_cast<std::uint32_t>(nonce) != window.trial().nonce || window.state() != State::armed)
        return false;
    window.refuse();
    return true;
}

std::string status() {
    if (window.state() == State::complete) return "complete";
    return window.state() == State::armed ? "armed" : "refused";
}

std::string describe(RE::StaticFunctionTag*, std::int32_t nonce) {
    auto actorGuard = hdt::ActorManager::instance()->lockGuard();
    auto simulationGuard = hdt::SkyrimPhysicsWorld::get()->lockSimulation();
    if (nonce <= 0 || static_cast<std::uint32_t>(nonce) != window.trial().nonce) return R"({"status":"unknown_nonce"})";
    const auto& pair = window.pair();
    const auto& trial = window.trial();
    if (window.state() == State::complete) {
        const auto left = resolve(pair.surfaceRef, pair.surfaceAddon, true);
        const auto right = resolve(pair.probeRef, pair.probeAddon, false);
        if (left.body != pair.surface || left.root != pair.surfaceSkeleton || left.drivers != surface.drivers
            || right.body != pair.probe || right.root != pair.probeSkeleton || right.probeBone != probe.probeBone
            || right.control != pair.control)
            window.refuse();
        else
            confirmedNonce = trial.nonce;
    }
    return fmt::format(
        R"({{"schema":"claw-fsmp-pair-contact/1","status":"{}","pid":{},"nonce":{},"callerEpoch":{},"mode":"{}",)"
        R"("surfaceRef":{},"surfaceAddon":{},"probeRef":{},"probeAddon":{},"frames":{},"requiredFrames":{},)"
        R"("qpcFrequency":{},"firstQpc":{},"lastQpc":{},"contactRows":{},"measure":"pre-solve accepted contact point"}})",
        status(), ::GetCurrentProcessId(), trial.nonce, trial.callerEpoch, pair.control ? "tag_control" : "reciprocal",
        pair.surfaceRef, pair.surfaceAddon, pair.probeRef, pair.probeAddon, window.steps(), trial.frames,
        trial.qpcFrequency, window.first(), window.last(), window.count());
}

std::string read(RE::StaticFunctionTag*, std::int32_t nonce, std::int32_t offset) {
    auto simulationGuard = hdt::SkyrimPhysicsWorld::get()->lockSimulation();
    if (nonce <= 0 || static_cast<std::uint32_t>(nonce) != confirmedNonce || offset < 0
        || window.state() != State::complete || static_cast<std::uint32_t>(offset) > window.count())
        return R"({"status":"unavailable"})";
    auto result = fmt::format(R"({{"status":"complete","nonce":{},"offset":{},"total":{},"rows":[)",
                              nonce, offset, window.count());
    auto start = static_cast<std::uint32_t>(offset);
    for (auto i = start; i < std::min(window.count(), start + 12); ++i) {
        const auto& row = *window.row(i);
        if (i != start) result += ',';
        result += fmt::format(
            R"({{"step":{},"qpc":{},"surfaceDriver":"{}","signedDepth":{},"normalToSurface":[{},{},{}],)"
            R"("surfaceLocal":[{},{},{}],"probeLocal":[{},{},{}]}})",
            row.step, row.qpc, drivers[row.driver - 1], row.depth, row.normalToSurface[0],
            row.normalToSurface[1], row.normalToSurface[2], row.surfaceLocal[0], row.surfaceLocal[1],
            row.surfaceLocal[2], row.probeLocal[0], row.probeLocal[1], row.probeLocal[2]);
    }
    return result + "]}";
}

Vec3 xyz(const btVector3& vector) noexcept {
    return {vector.x(), vector.y(), vector.z()};
}
}

void registerFunctions(RE::BSScript::IVirtualMachine* registry) {
    registry->RegisterFunction("Arm", "CLAWFSMPPairContact", arm);
    registry->RegisterFunction("Cancel", "CLAWFSMPPairContact", cancel);
    registry->RegisterFunction("Describe", "CLAWFSMPPairContact", describe);
    registry->RegisterFunction("Read", "CLAWFSMPPairContact", read);
}

void begin(const btAlignedObjectArray<btCollisionObject*>& objects) noexcept {
    if (window.state() != State::armed) return;
    unsigned seenSurface = 0, seenProbe = 0;
    for (int i = 0; i < objects.size(); ++i) {
        const auto* object = objects[i];
        const auto objectKey = key(object);
        if (objectKey != surface.worldObject && objectKey != probe.worldObject) continue;
        const auto* body = static_cast<const hdt::SkyrimBody*>(object);
        if (!body->m_mesh || body->m_disabled) continue;
        const auto root = key(body->m_mesh->m_skeleton.get());
        if (objectKey == surface.worldObject && root == surface.root) ++seenSurface;
        if (objectKey == probe.worldObject && root == probe.root) ++seenProbe;
    }
    window.begin(seenSurface == 1 && seenProbe == 1, qpc());
}

void end() noexcept {
    if (window.accepting()) window.end(qpc());
}

void note(const hdt::SkinnedMeshBody* bodyA, const hdt::SkinnedMeshBody* bodyB,
          const hdt::SkinnedMeshBone* boneA, const hdt::SkinnedMeshBone* boneB,
          const btManifoldPoint& point) noexcept {
    if (!window.accepting()) return;
    const bool forward = key(bodyA) == surface.body && key(bodyB) == probe.body;
    if (!forward && !(key(bodyA) == probe.body && key(bodyB) == surface.body)) return;
    const auto driver = key(forward ? boneA : boneB);
    const auto anchor = key(forward ? boneB : boneA);
    const auto found = std::ranges::find(surface.drivers, driver);
    unsigned role = 0;
    if (anchor == probe.probeBone && found != surface.drivers.end())
        role = static_cast<unsigned>(found - surface.drivers.begin()) + 1;
    window.note(key(bodyA), key(bodyB), role, qpc(), point.getDistance(), xyz(point.m_normalWorldOnB),
                xyz(point.m_localPointA), xyz(point.m_localPointB));
}
}
