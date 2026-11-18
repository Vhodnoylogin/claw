#include "Geometry.h"
#include "../../../main/cpp/include/claw/WorldStartPolicy.h"
#include <cassert>
#include <iostream>
#include <limits>
using namespace claw::geometry;
template<class F> void refused(F f){bool failed=false;try{f();}catch(const std::runtime_error&){failed=true;}assert(failed);}
int main(){
    struct PartitionRow {int value;};std::array<PartitionRow,2> partitionRows{{{7},{9}}};
    auto admitted=partitionStorage(partitionRows.data(),2);assert(admitted.size()==2&&admitted[1].value==9);
    unsigned elementReads=0;
    refused([&]{auto missing=partitionStorage(static_cast<PartitionRow*>(nullptr),1);++elementReads;(void)missing[0].value;});
    assert(elementReads==0); // Valid metadata cannot dereference a missing backing array.
    refused([&]{partitionStorage(partitionRows.data(),0);});refused([&]{partitionStorage(partitionRows.data(),maxPartitions+1);});
    assert(claw::mayActivateWorld(claw::WorldStart::postLoadGame,1,1));assert(!claw::mayActivateWorld(claw::WorldStart::postLoadGame,1,0));assert(!claw::mayActivateWorld(claw::WorldStart::postLoadGame,0,1));
    assert(half(0)==0&&half(0x3C00)==1&&half(1)==std::ldexp(1.0f,-24)&&half(0xBC00)==-1);
    refused([]{half(0x7C00);});refused([]{half(0x7E01);});
    Layout l{32,0,16,0x41};std::array<std::uint8_t,32> data{};float xyz[3]{1,2,3};std::memcpy(data.data(),xyz,12);std::uint16_t weights[4]{0x3800,0x3800,0,0};std::memcpy(data.data()+16,weights,8);data[24]=0;data[25]=1;
    auto p=decode(data,l,1,0);assert(p.position[2]==3&&p.weights[0]==.5f);std::array<std::uint16_t,2> expected{0x3800,0x3800};assert(support(p,expected));
    refused([&]{decode(data,l,1,1);});refused([&]{decode(std::span(data).first(31),l,1,0);});
    refused([&]{auto bad=l;bad.flags=1;decode(data,bad,1,0);});
    refused([&]{auto bad=data;float v=std::numeric_limits<float>::infinity();std::memcpy(bad.data(),&v,4);decode(bad,l,1,0);});
    refused([&]{auto bad=data;std::uint16_t v=0xB800;std::memcpy(bad.data()+16,&v,2);decode(bad,l,1,0);});
    refused([&]{auto bad=l;bad.skinning=26;decode(data,bad,1,0);});refused([&]{auto bad=l;bad.position=16;decode(data,bad,1,0);});
    refused([&]{auto bad=p;bad.indices[1]=0;support(bad,expected);});refused([&]{auto bad=p;bad.indices[1]=2;support(bad,expected);});
    auto wrong=expected;wrong[1]=0x3400;assert(!support(p,wrong));
    std::array<Triangle,2> tris{{{1,2,3},{3,4,1}}};auto other=tris;std::swap(other[0],other[1]);other[0]={4,1,3};assert(topology(tris)==topology(other));other=tris;std::swap(other[0][1],other[0][2]);assert(topology(tris)!=topology(other));
    refused([]{std::array<Triangle,1> bad{{{1,1,2}}};topology(bad);});
    Slot slot;assert(!slot.request(0x14,fixtureBase,1,1,10,5));assert(!slot.request(0xFF000800,7,1,1,10,5));
    assert(!slot.request(0xFF000800,fixtureBase,1,1,0,5));assert(sameBoundEpoch(0,1)&&sameBoundEpoch(1,1)&&!sameBoundEpoch(1,2));
    assert(slot.request(0xFF000800,fixtureBase,1,1,10,5));assert(!slot.request(0xFF000800,fixtureBase,2,1,10,5)); // one pending / busy
    assert(slot.begin(1,1,14,false));assert(!slot.begin(1,2,14,false));assert(!slot.begin(1,1,15,false));assert(!slot.begin(1,1,14,true));
    assert(!slot.finish(1,2,14,true));assert(!slot.request(0xFF000800,fixtureBase,1,2,20,5)); // stale nonce cannot replay
    assert(slot.request(0xFF000800,fixtureBase,2,2,20,5));assert(slot.finish(2,2,21,true));assert(slot.ready);
    assert(!slot.request(0xFF000801,fixtureBase,3,2,22,5));assert(slot.ready); // immutable old result on refused request
    for(unsigned n=3;n<=32;++n){assert(slot.request(0xFF000800,fixtureBase,n,2,30,5));assert(slot.finish(n,2,31,true));}
    assert(!slot.request(0xFF000800,fixtureBase,33,2,30,5));
    Slot unknown;assert(unknown.request(0xFF000800,fixtureBase,1,1,10,5));unknown.poisoned=true;
    assert(!unknown.request(0xFF000800,fixtureBase,2,1,11,5)&&!unknown.begin(1,1,11,false));
    assert(!unknown.finish(1,1,11,true)&&!unknown.request(0xFF000800,fixtureBase,2,1,12,5));
    Lease lease{0xFF000800,fixtureBase,beastRace,9,1,10};assert(sameLease(lease,lease));
    auto changed=lease;changed.root++;assert(!sameLease(lease,changed));changed=lease;changed.handle++;assert(!sameLease(lease,changed));changed=lease;changed.epoch++;assert(!sameLease(lease,changed));
    std::cout<<"geometry bounds/layout/half/support/topology/slot controls passed\n";
}
