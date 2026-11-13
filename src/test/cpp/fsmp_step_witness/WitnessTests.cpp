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
 objectTests();
}
