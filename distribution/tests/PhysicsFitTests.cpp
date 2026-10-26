#include "claw/PhysicsFit.h"
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
    double maximumError=0.;std::size_t capsules=0,activeCapsules=0;
    std::size_t fixtureIndex=0;
    for (const auto& fixture:CompiledFixtures()) {
        const auto& model=CompiledModel(fixture.female);
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
    std::cout<<"fixtures="<<CompiledFixtures().size()<<" capsule_slot_outputs="<<capsules<<" active_capsule_outputs="<<activeCapsules<<" maximum_coordinate_or_radius_error="<<maximumError
             <<"\n";
    constexpr unsigned repetitions=40;
    for(const auto female:{false,true}) {
        const auto& model=CompiledModel(female);std::vector<double> mixed(model.morphs.size(),.35);
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
