#include "Witness.h"
#include "ObjectWindow.h"
#include <cassert>
#include <limits>
#include <thread>
#include <vector>
#include <iostream>
#include <memory>
using namespace claw::witness;
ObjectFrame frame(std::uint64_t when=100) {
 ObjectFrame f;f.count=3;f.qpc=when;f.epoch=2;f.thread=7;f.dt=.016f;
 for(std::uint32_t i=0;i<f.count;++i){auto& o=f.objects[i];o.key=100+i;o.rigidBody=true;o.flags=i?0:1;o.inverseMass=i?20.f:0.f;o.world[0]=o.world[4]=o.world[8]=1;o.world[9]=float(i);}
 return f;
}
struct FakeBody;
struct FakeEdge {
 FakeBody *a{},*b{};int type{12};
 const FakeBody& getRigidBodyA() const {return *a;}
 const FakeBody& getRigidBodyB() const {return *b;}
};
struct FakeBody {
 std::array<FakeEdge*,65> refs{};int count{},countCalls{},refCalls{};bool change{};
 int getNumConstraintRefs(){return count+(change&&countCalls++?1:0);}
 FakeEdge* getConstraintRef(int i){++refCalls;return refs[i];}
};
void constraintTests() {
 auto f=std::make_unique<ObjectFrame>();auto bodies=std::make_unique<std::array<FakeBody,128>>();
 auto setup=[&](unsigned count=3){*f=frame();f->count=count;*bodies={};
  for(unsigned i=0;i<count;++i){f->objects[i].key=reinterpret_cast<std::uintptr_t>(&(*bodies)[i]);f->objects[i].rigidBody=true;}
 };
 int reads=0;auto capture=[&]{incidentConstraints(*f,[&](unsigned i){return &(*bodies)[i];},[&](FakeEdge* e,ConstraintPose& row){
  ++reads;row.type=e->type;row.enabled=true;row.damping[0]=.4f;return true;
 });};
 setup();FakeEdge edge{&(*bodies)[0],&(*bodies)[1]};(*bodies)[0].count=(*bodies)[1].count=1;
 (*bodies)[0].refs[0]=(*bodies)[1].refs[0]=&edge;capture();
 assert(f->constraintFailure==ConstraintFailure::none&&f->constraintCount==1&&reads==1);
 assert(f->constraints[0].bodyA==1&&f->constraints[0].bodyB==2&&f->constraints[0].damping[0]==.4f);
 auto w=std::make_unique<ObjectWindow>();auto s=std::make_unique<WindowSnapshot>();assert(w->request(77,2));w->pre(*f);
 f->qpc=101;w->post(*f);assert(w->copy(*s)&&s->constraintCount==1&&s->constraints[0].damping[0]==.4f&&s->pairedSteps==1);
 f->qpc=103;f->constraints[0].damping[0]=0;w->pre(*f);assert(w->copy(*s)&&s->failure==WindowFailure::constraintChanged);
 setup();(*bodies)[0].count=65;capture();assert(f->constraintFailure==ConstraintFailure::referenceOverflow&&(*bodies)[0].refCalls==0);
 setup();(*bodies)[0].count=-1;capture();assert(f->constraintFailure==ConstraintFailure::referenceOverflow);
 setup();(*bodies)[0].count=1;capture();assert(f->constraintFailure==ConstraintFailure::nullReference);
 setup();edge={&(*bodies)[1],&(*bodies)[2]};(*bodies)[0].count=1;(*bodies)[0].refs[0]=&edge;
 int before=reads;capture();assert(f->constraintFailure==ConstraintFailure::notIncident&&reads==before);
 setup();FakeBody outside;edge={&(*bodies)[0],&outside};(*bodies)[0].count=1;(*bodies)[0].refs[0]=&edge;
 before=reads;capture();assert(f->constraintFailure==ConstraintFailure::invalidEndpoint&&reads==before);
 setup();edge={&(*bodies)[0],&(*bodies)[1]};(*bodies)[0].count=1;(*bodies)[0].refs[0]=&edge;(*bodies)[0].change=true;
 capture();assert(f->constraintFailure==ConstraintFailure::referencesChanged);
 setup();edge={&(*bodies)[0],&(*bodies)[1],11};(*bodies)[0].count=1;(*bodies)[0].refs[0]=&edge;capture();
 assert(f->constraintCount==1&&f->constraints[0].type==11&&f->constraintFailure==ConstraintFailure::none);
 setup(6);auto edges=std::make_unique<std::array<FakeEdge,257>>();
 for(unsigned i=0;i<edges->size();++i){const auto b=i/64;(*edges)[i]={&(*bodies)[b],&(*bodies)[b+1]};auto& body=(*bodies)[b];body.refs[body.count++]=&(*edges)[i];}
 before=reads;capture();assert(f->constraintFailure==ConstraintFailure::uniqueOverflow&&f->constraintCount==256&&reads-before==256);
 auto bad=std::make_unique<ObjectWindow>();assert(bad->request(78,2));bad->pre(*f);
 assert(bad->copy(*s)&&s->failure==WindowFailure::constraintRefused&&s->constraintFailure==ConstraintFailure::uniqueOverflow);
 std::cout<<"v4 incident traversal: endpoint membership/incidence, dedup, per-body/unique bounds, changed references/config and unsupported type passed\n";
}
void dynamicsTests() {
 auto w=std::make_unique<ObjectWindow>();auto s=std::make_unique<WindowSnapshot>();assert(w->request(5,2));
 auto pre=frame(100),post=frame(101);pre.dt=post.dt=.02f;
 pre.objects[1].inverseLocalInertia={10.f,0.f,10.f};post.objects[1].inverseLocalInertia=pre.objects[1].inverseLocalInertia;
 post.objects[1].linearVelocity={-3.5f,0.f,2.f};post.objects[1].angularVelocity={0.f,-.25f,0.f};
 w->pre(pre);assert(w->copy(*s)&&s->pairedSteps==0&&s->minimumPairedHostTimeStep==0&&s->summedPairedHostTimeStep==0);
 w->post(post);assert(w->copy(*s)&&s->pairedSteps==1&&s->minimumPairedHostTimeStep==.02f&&s->summedPairedHostTimeStep==double(.02f));
 assert(s->objects[1].initialPre.linearVelocity[0]==0&&s->objects[1].lastPost.linearVelocity[0]==-3.5f);
 assert(s->objects[1].firstNonzeroStep==0); // Selection remains WORLD-only, not velocity-only.
 pre=post;pre.qpc=103;pre.dt=.01f;post=pre;post.qpc=104;post.objects[1].world[9]+=.01f;
 post.objects[1].angularVelocity[1]=.5f;post.objects[1].inverseLocalInertia[2]=8.f;
 w->pre(pre);assert(w->copy(*s)&&s->pairedSteps==1&&s->minimumPairedHostTimeStep==.02f); // Pending pre not counted.
 w->post(post);assert(w->copy(*s)&&s->pairedSteps==2&&s->minimumPairedHostTimeStep==.01f);
 assert(s->summedPairedHostTimeStep==double(.02f)+double(.01f));
 const auto& r=s->objects[1];assert(r.firstNonzeroStep==2&&r.firstNonzeroPre.linearVelocity[0]==-3.5f);
 assert(r.firstNonzeroPre.angularVelocity[1]==-.25f&&r.firstNonzeroPost.angularVelocity[1]==.5f);
 assert(r.initialPre.inverseLocalInertia[2]==10.f&&r.firstNonzeroPost.inverseLocalInertia[2]==8.f);
 for(int channel=0;channel<3;++channel) {
  auto bad=std::make_unique<ObjectWindow>();assert(bad->request(7,2));auto f=frame();
  if(channel==0)f.objects[1].linearVelocity[1]=std::numeric_limits<float>::infinity();
  if(channel==1)f.objects[1].angularVelocity[0]=std::numeric_limits<float>::quiet_NaN();
  if(channel==2)f.objects[1].inverseLocalInertia[2]=-1.f;
  bad->pre(f);assert(bad->copy(*s)&&s->failure==WindowFailure::invalid&&s->pairedSteps==0&&s->summedPairedHostTimeStep==0);
 }
 auto unavailable=std::make_unique<ObjectWindow>();assert(unavailable->request(9,2));pre=frame();post=frame(101);
 pre.objects[0].rigidBody=post.objects[0].rigidBody=false;unavailable->pre(pre);unavailable->post(post);
 assert(unavailable->copy(*s)&&s->failure==WindowFailure::none&&!s->objects[0].lastPost.rigidBody);
 std::cout<<"v3 co-temporal dynamics, zero inertia, WORLD-only first pair and completed-host-pair dt statistics passed\n";
}
void objectTests() {
 auto w=std::make_unique<ObjectWindow>();auto s=std::make_unique<WindowSnapshot>();
 assert(!w->request(0,2)&&!w->request(41,0));assert(w->request(41,2));
 assert(w->request(41,2)&&!w->request(42,2)&&!w->request(41,3));
 w->post(frame(99));assert(w->copy(*s)&&!s->started); // Arm between callbacks waits for a full pair.
 for(std::uint32_t i=0;i<pairedStepLimit;++i) {
  auto pre=frame(100+3*i);auto post=frame(101+3*i);
  post.objects[1].world[9]+=float(i)*.001f;
  w->pre(pre);w->post(post);
 }
 assert(w->copy(*s)&&s->complete&&s->pairedSteps==900&&s->count==3&&s->coherent&&!s->dropped&&s->failure==WindowFailure::none);
 assert(s->objects[1].firstNonzeroStep==2&&s->objects[1].initialPre.world[9]==1);
 assert(s->objects[1].firstNonzeroPreQpc==103&&s->objects[1].firstNonzeroPostQpc==104);
 assert(s->objects[1].firstNonzeroPre.world[9]==1&&s->objects[1].firstNonzeroPost.world[9]>1);
 assert(s->objects[1].minimumPost[9]==1&&s->objects[1].maximumPost[9]==1.899f);
 assert(s->objects[0].maximumPairedDifference==0&&s->objects[0].firstNonzeroStep==0);
 assert(s->minimumPairedHostTimeStep==.016f&&s->summedPairedHostTimeStep==double(.016f)*900);
 const auto last=s->lastPostQpc;w->pre(frame(10000));w->post(frame(10001));
 assert(w->copy(*s)&&s->lastPostQpc==last&&s->pairedSteps==900&&!w->requested());
 auto failure=[&](ObjectFrame pre,ObjectFrame post,WindowFailure expected){
  auto bad=std::make_unique<ObjectWindow>();assert(bad->request(4,2));bad->pre(pre);bad->post(post);
  assert(bad->copy(*s)&&s->complete&&s->failure==expected);
 };
 auto pre=frame();auto post=frame(101);
 auto changed=pre;changed.count=objectCapacity+1;failure(changed,post,WindowFailure::overflow);
 changed=pre;changed.count=0;failure(changed,post,WindowFailure::empty);
 changed=pre;changed.objects[0].world[3]=std::numeric_limits<float>::quiet_NaN();failure(changed,post,WindowFailure::invalid);
 changed=pre;changed.objects[0].inverseMass=-1;failure(changed,post,WindowFailure::invalid);
 changed=post;changed.epoch=3;failure(pre,changed,WindowFailure::epochChanged);
 changed=post;changed.objects[1].key=500;failure(pre,changed,WindowFailure::invalid); // Unsorted/duplicate catalogs refuse.
 changed=post;changed.objects[2].key=500;failure(pre,changed,WindowFailure::identityChanged);
 changed=post;changed.count=2;failure(pre,changed,WindowFailure::identityChanged);
 changed=post;changed.objects[1].flags=2;failure(pre,changed,WindowFailure::metadataChanged);
 changed=post;changed.objects[1].inverseMass=21;failure(pre,changed,WindowFailure::metadataChanged);
 changed=pre;changed.objects[1].world[9]=-std::numeric_limits<float>::max();
 auto huge=post;huge.objects[1].world[9]=std::numeric_limits<float>::max();failure(changed,huge,WindowFailure::invalid);
 changed=post;changed.thread=8;failure(pre,changed,WindowFailure::timing);
 changed=post;changed.dt=.02f;failure(pre,changed,WindowFailure::timing);
 failure(pre,pre,WindowFailure::timing);
 auto duplicate=std::make_unique<ObjectWindow>();assert(duplicate->request(8,2));duplicate->pre(pre);duplicate->pre(post);
 assert(duplicate->copy(*s)&&s->failure==WindowFailure::unpaired);
 // A main-thread POD copy may cause a callback try-gate refusal, never a wait or
 // silent accepted partial window. The writer uses actual production methods.
 auto concurrent=std::make_unique<ObjectWindow>();assert(concurrent->request(9,2));std::atomic<bool> done{};
 std::thread producer([&]{for(unsigned i=0;i<900;++i){concurrent->pre(frame(100+3*i));concurrent->post(frame(101+3*i));}done=true;});
 while(!done.load())concurrent->copy(*s);producer.join();assert(concurrent->copy(*s));
 assert((s->failure==WindowFailure::none&&s->pairedSteps==900)||s->failure==WindowFailure::callbackDropped||s->failure==WindowFailure::unpaired);
 std::cout<<"object window: 900-step cap, idempotent nonce, extrema/first delta, malformed inputs, membership/epoch/metadata/timing and contention passed\n";
}
void frameBufferTests() {
 using namespace claw::witness;
 auto buffer=std::make_unique<ObjectFrameBuffer>();
 auto window=std::make_unique<ObjectWindow>();assert(window->request(33,2));
 bool consumed=false,nestedConsumed=false;
 assert(buffer->capture([](ObjectFrame& frame) noexcept {
     frame.objects.back().key=123;frame.constraints.back().key=456;
     frame.constraintCount=7;frame.constraintFailure=ConstraintFailure::nullReference;frame.qpc=99;
 },[&](const ObjectFrame& frame) noexcept {
     consumed=true;assert(frame.qpc==99);
     const bool entered=buffer->capture([](ObjectFrame&) noexcept {},[&](const ObjectFrame&) noexcept {nestedConsumed=true;});
     assert(!entered);window->captureDropped();
 }));
 assert(consumed&&!nestedConsumed);
 assert(buffer->capture([](ObjectFrame&) noexcept {},[](const ObjectFrame& frame) noexcept {
     assert(!frame.objects.back().key&&!frame.constraints.back().key&&!frame.constraintCount&&!frame.qpc);
     assert(frame.constraintFailure==ConstraintFailure::none);
 }));
 auto snapshot=std::make_unique<WindowSnapshot>();assert(window->copy(*snapshot));
 assert(snapshot->dropped==1&&snapshot->failure==WindowFailure::callbackDropped);
 std::cout<<"scratch frame: reset, nested contention refusal and visible window drop passed\n";
}
int main() {
 using namespace claw::witness;
 assert(compatible({2,0,0},{3,24,0}));
 assert(!compatible({1,0,0},{3,24,0}));assert(!compatible({2,0,1},{3,24,0}));assert(!compatible({2,0,0},{3,25,0}));
 const int fake{};assert(startupEnvelope(0,&fake,0));assert(!startupEnvelope(1,&fake,0));assert(!startupEnvelope(0,nullptr,0));assert(!startupEnvelope(0,&fake,sizeof(void*)));
 EventCounter c;auto a=c.read();assert(a.coherent&&a.count==0&&a.lastQpc==0);
 c.record(.01f,100,7);a=c.read();assert(a.coherent&&a.count==1&&a.lastQpc==100&&a.lastThreadId==7&&a.lastTimeStep==.01f&&a.invalidEvents==0);
 c.record(std::numeric_limits<float>::quiet_NaN(),0,0);a=c.read();assert(a.count==2&&a.invalidEvents==1);
 EventCounter parallel;std::vector<std::thread> threads;
 for(int i=0;i<4;i++)threads.emplace_back([&]{for(int j=0;j<10000;j++)parallel.record(.02f,j+1,3);});
 for(auto& t:threads)t.join();a=parallel.read();assert(a.coherent&&a.count+a.droppedEvents==40000&&a.invalidEvents==0&&a.lastThreadId==3);
 std::cout<<"witness ABI, finite values, coherent publication and bounded contention checks passed\n";
 objectTests();dynamicsTests();constraintTests();frameBufferTests();
}
