#include "claw/PhysicsFit.h"
#include "claw/PosedContactSupport.h"
#include <cassert>
#include <chrono>
#include <iostream>
#ifdef CLAW_PHYSICS_MODEL_HEADER
#include CLAW_PHYSICS_MODEL_HEADER
#endif
#ifdef CLAW_PHYSICS_FIXTURE_HEADER
#include CLAW_PHYSICS_FIXTURE_HEADER
#endif

int main() {
    using namespace claw::physics;
    std::array<std::size_t, vrHeadPoseSlots + vrEarTailPoseSlots> poseSlots;
    for (std::size_t i = 0; i < vrHeadPoseSlots; ++i) poseSlots[i] = 20 + i;
    for (std::size_t i = 0; i < vrEarTailPoseSlots; ++i) poseSlots[i + vrHeadPoseSlots] = 88 + i;
    assert(VRPoseSlotsMatch(poseSlots) && VRPoseSlotsMatch(std::span(poseSlots).subspan(vrHeadPoseSlots)));
    assert(!VRPoseSlotsMatch(std::span(poseSlots).subspan(1)));
    poseSlots[1] = poseSlots[0];
    assert(!VRPoseSlotsMatch(poseSlots));
    const auto captured = std::chrono::steady_clock::time_point{} + vrPosePeriod;
    assert(VRPoseCaptureCurrent(captured, captured + vrPoseMaxAge));
    assert(!VRPoseCaptureCurrent(captured, captured + vrPoseMaxAge + std::chrono::milliseconds(1)));
    assert(!VRPoseCaptureCurrent(captured, captured - std::chrono::milliseconds(1)));
    const auto deadline = captured + vrPoseMaxAge;
    const auto late = deadline + std::chrono::milliseconds(1);
    VRPoseOffer unused;
    assert(unused.readable() && !unused.expired(late));
    VRPoseOffer delayed{captured};
    assert(!delayed.readable() && !delayed.claim(late) && delayed.expired(late));
    VRPoseOffer inFlight{captured};
    assert(!inFlight.claim(captured - std::chrono::milliseconds(1)));
    assert(inFlight.claim(deadline) && !inFlight.claim(deadline));
    assert(inFlight.readable() && !inFlight.expired(late));
    inFlight.claimed = false; // Busy helper returned before mutation.
    assert(!inFlight.readable() && inFlight.expired(late));

    const Capsule accepted{{0., 0., 0.}, {0., 0., 2.}, 1.};
    const Capsule shifted{{.02, 0., 0.}, {.02, 0., 2.}, 1.};
    const std::array<Vec3, 1> inward{Vec3{.99, 0., 1.}};
    const std::array<Vec3, 1> protruding{Vec3{1.01, 0., 1.}};
    assert(!PoseCapsuleChanged(accepted, shifted, poseCapsuleTolerance));
    assert(CapsuleDistance(protruding[0], shifted) < 0.);
    assert(CanKeepPoseCapsule(accepted, shifted, inward));
    assert(!CanKeepPoseCapsule(accepted, shifted, protruding));
    const Capsule precisionEdge{accepted.p1, accepted.p2, 1.00000004};
    const std::array<Vec3, 1> floatRounding{Vec3{1.00000002, 0., 1.}};
    assert(CapsuleDistance(floatRounding[0], precisionEdge) < 0.);
    assert(!CanKeepPoseCapsule(precisionEdge, accepted, floatRounding));
    const auto radiusCorrected = EnclosingProviderPoseCapsule(precisionEdge, floatRounding);
    assert(radiusCorrected.radius == std::nextafter(1.0F, 2.0F));
    assert(CapsuleDistance(floatRounding[0], radiusCorrected) <= 0.);
    assert(CanKeepPoseCapsule(radiusCorrected, precisionEdge, floatRounding));
    const Capsule endpointEdge{{16777217., 0., 0.}, {16777217., 0., 2.}, 1.};
    const std::array<Vec3, 1> endpointSupport{Vec3{16777217., 1., 1.}};
    const auto endpointCorrected = EnclosingProviderPoseCapsule(endpointEdge, endpointSupport);
    assert(endpointCorrected.p1[0] == 16777216. && endpointCorrected.p2[0] == 16777216.);
    assert(CapsuleDistance(endpointSupport[0], endpointCorrected) <= 0.);
    const Capsule oneStepSmaller{endpointCorrected.p1, endpointCorrected.p2,
        std::nextafter(static_cast<float>(endpointCorrected.radius), 0.0F)};
    assert(CapsuleDistance(endpointSupport[0], oneStepSmaller) > 0.);
    assert(EnclosingProviderPoseCapsule(accepted, inward) == accepted);
    const auto rejectsProviderRange = [](const Capsule& capsule, std::span<const Vec3> points) {
        try { (void)EnclosingProviderPoseCapsule(capsule, points); }
        catch (const std::invalid_argument&) { return true; }
        return false;
    };
    const double tooWide = 2. * std::numeric_limits<float>::max();
    const std::array<Vec3, 1> remoteSupport{Vec3{tooWide, 0., 0.}};
    assert(rejectsProviderRange({{tooWide, 0., 0.}, accepted.p2, accepted.radius}, inward));
    assert(rejectsProviderRange({accepted.p1, accepted.p2, tooWide}, inward));
    assert(rejectsProviderRange({accepted.p1, accepted.p2, std::numeric_limits<double>::min()}, inward));
    assert(rejectsProviderRange(accepted, remoteSupport));
    Model simple{"fixture",{"grow","shrink"},{{"TailBone01",
        {{-1,-1,-4},{1,1,-4},{-1,1,4},{1,-1,4}},
        {{0,{{-.5,-.5,-2},{.5,.5,-2},{-.5,.5,2},{.5,-.5,2}}},
         {1,{{.25,.25,1},{-.25,-.25,1},{.25,-.25,-1},{-.25,.25,-1}}}}}}};
    const auto base=Evaluate(simple,{0,0}),grown=Evaluate(simple,{1,0}),shrunk=Evaluate(simple,{0,1});
    assert(grown[0].radius>base[0].radius && shrunk[0].radius<base[0].radius);
    assert(Evaluate(simple,{0,0})[0].p1==base[0].p1);
    for (const auto bad: {-0.1,1.1,std::numeric_limits<double>::infinity()}) {
        bool rejected=false;try { (void)Evaluate(simple,{bad,0}); } catch (const std::runtime_error&) { rejected=true; }
        assert(rejected);
    }
    auto malformed=simple;malformed.slots[0].fields[0].deltas.pop_back();
    bool rejected=false;try {(void)Evaluate(malformed,{0,0});}catch(const std::runtime_error&){rejected=true;}assert(rejected);
    auto weighted=simple;weighted.weightDependent=true;
    weighted.slots[0].weightDeltas={{2,0,0},{2,0,0},{2,0,0},{2,0,0}};
    const auto low=Evaluate(weighted,{1,0},0),high=Evaluate(weighted,{1,0},1);
    assert(std::abs(high[0].p1[0]-low[0].p1[0]-2)<1e-10);
    assert(std::abs(high[0].radius-low[0].radius)<1e-10);
    weighted.slots.push_back({});weighted.slots.back().node="NPC L Breast P1";weighted.slots.back().active=false;
    const auto gated=Evaluate(weighted,{0,0},.5);assert(gated.size()==2 && gated[1].radius==0.);
    const auto sphereSurface=ObjectiveSurface({{0,0,0},{0,0,0},2}),nearSphereSurface=ObjectiveSurface({{0,0,0},{1e-14,-1e-14,0},2});
    for(std::size_t i=0;i<sphereSurface.size();++i)for(std::size_t j=0;j<3;++j)assert(std::abs(sphereSurface[i][j]-nearSphereSurface[i][j])<1e-12);
    const auto tiedSurface=ObjectiveSurface({{0,0,0},{1,-1,1},2}),nearTiedSurface=ObjectiveSurface({{0,0,0},{1-2e-15,-1,1+1e-15},2});
    for(std::size_t i=0;i<tiedSurface.size();++i)for(std::size_t j=0;j<3;++j)assert(std::abs(tiedSurface[i][j]-nearTiedSurface[i][j])<1e-12);
    auto unsupported=simple;unsupported.contactPasses=1;unsupported.slots[0].prescribedAxis=true;unsupported.slots[0].axis={1,0,0};
    rejected=false;try{(void)Evaluate(unsupported,{0,0});}catch(const std::runtime_error&){rejected=true;}assert(rejected);
#if defined(CLAW_PHYSICS_MODEL_HEADER) && defined(CLAW_PHYSICS_FIXTURE_HEADER)
    const auto modelForFixture = [](bool female, std::string_view identity) -> const Model& {
#if defined(CLAW_PHYSICS_RUNTIME_PROFILES)
        const auto& flat = CompiledModel(female, ContactRuntimeEdition::flat);
        return flat.identity == identity ? flat : CompiledModel(female, ContactRuntimeEdition::vr);
#else
        (void)identity;
        return CompiledModel(female);
#endif
    };
    const auto& fixtures = CompiledFixtures();
    assert(!fixtures.empty());
    double maximumError=0.;std::size_t capsules=0,activeCapsules=0;
    std::size_t fixtureIndex=0;
    for (const auto& fixture:fixtures) {
        const auto& model=modelForFixture(fixture.female, fixture.identity);
        assert(model.identity==fixture.identity);
        const auto actual=Evaluate(model,fixture.values,fixture.weight);
        assert(actual.size()==fixture.capsules.size());
        for (std::size_t i=0;i<actual.size();++i) {
            if(actual[i].radius>0)++activeCapsules;
            double slotError=std::abs(actual[i].radius-fixture.capsules[i].radius);
            for(std::size_t j=0;j<3;++j)slotError=std::max({slotError,std::abs(actual[i].p1[j]-fixture.capsules[i].p1[j]),std::abs(actual[i].p2[j]-fixture.capsules[i].p2[j])});
            if(slotError>1e-8)std::cerr<<"fixture="<<fixtureIndex<<" slot="<<i<<" node="<<model.slots[i].node<<" error="<<slotError<<"\n";
            maximumError=std::max(maximumError,std::abs(actual[i].radius-fixture.capsules[i].radius));
            for (std::size_t j=0;j<3;++j) {
                maximumError=std::max(maximumError,std::abs(actual[i].p1[j]-fixture.capsules[i].p1[j]));
                maximumError=std::max(maximumError,std::abs(actual[i].p2[j]-fixture.capsules[i].p2[j]));
            }
        }
        capsules+=actual.size();
        ++fixtureIndex;
    }
    std::cout<<"maximum_error_before_assert="<<maximumError<<"\n";
    assert(maximumError<1e-8);
    std::cout<<"fixtures="<<fixtures.size()<<" capsule_slot_outputs="<<capsules<<" active_capsule_outputs="<<activeCapsules<<" maximum_coordinate_or_radius_error="<<maximumError
             <<"\n";
    constexpr unsigned repetitions=40;
    for(const auto female:{false,true}) {
        const auto& model=modelForFixture(female, fixtures.front().identity);
        std::vector<double> mixed(model.morphs.size(),.35);
        for(const auto weight:std::vector<double>(model.weightDependent?std::vector<double>{0.,.5,1.}:std::vector<double>{0.})) {
            const auto start=std::chrono::steady_clock::now();
            for (unsigned i=0;i<repetitions;++i) {(void)Evaluate(model,mixed,weight);}
            const auto elapsed=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
            std::cout<<"female="<<female<<" weight="<<weight<<" evaluation_ms_mean="<<elapsed/repetitions<<" repetitions="<<repetitions<<"\n";
        }
    }
#endif
    std::cout<<"current-vector numeric fixtures passed; no game/provider execution\n";
}
