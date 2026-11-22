#pragma once

class btManifoldPoint;
class btCollisionObject;
template <class T> class btAlignedObjectArray;

namespace hdt {
class SkinnedMeshBody;
struct SkinnedMeshBone;
}

namespace claw::contact::provider {
void registerFunctions(RE::BSScript::IVirtualMachine* registry);
void begin(const btAlignedObjectArray<btCollisionObject*>& objects) noexcept;
void end() noexcept;
void note(const hdt::SkinnedMeshBody* bodyA, const hdt::SkinnedMeshBody* bodyB,
          const hdt::SkinnedMeshBone* boneA, const hdt::SkinnedMeshBone* boneB,
          const btManifoldPoint& point) noexcept;
}
