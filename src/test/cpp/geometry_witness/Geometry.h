#pragma once
// Transport/engine-free bounded decoder and immutable request policy.
#include <algorithm>
#include <array>
#include <bit>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <span>
#include <stdexcept>
#include <vector>

namespace claw::geometry {
inline constexpr std::uint32_t maxBones=128,maxPartitions=32,maxTriangles=32768,maxObjects=4096,maxSamples=32;
inline constexpr std::uint32_t fixtureBase=0x0D000801,beastRace=0x000CDD84;
inline void require(bool ok,const char* reason){if(!ok)throw std::runtime_error(reason);}
template<class T> inline std::span<T> partitionStorage(T* storage,std::uint32_t count) {
    // The attached engine allocation/count invariant remains required. SimpleArray
    // size() is not an independently qualified allocation-length oracle here.
    require(storage&&count&&count<=maxPartitions,"Missing/out-of-bounds attached partition storage");
    return {storage,count};
}
inline float half(std::uint16_t h) {
    const auto sign=std::uint32_t(h&0x8000)<<16;auto e=(h>>10)&31u;auto m=std::uint32_t(h&1023);
    if(e==31)throw std::runtime_error("Nonfinite FP16 influence");
    if(!e){if(!m)return std::bit_cast<float>(sign);int shift=0;while(!(m&1024)){m<<=1;++shift;}return std::bit_cast<float>(sign|std::uint32_t(113-shift)<<23|(m&1023)<<13);}
    return std::bit_cast<float>(sign|(e+112)<<23|m<<13);
}
struct Layout {std::uint32_t stride{},position{},skinning{};std::uint16_t flags{};};
inline void validate(Layout l,std::uint32_t count) {
    require(count&&count<=65535,"Vertex count outside bounded layout");
    require(l.stride>=28&&l.stride<=128&&l.stride%4==0,"Unsupported vertex stride");
    require((l.flags&0x41)==0x41,"Position/skinning attributes required");
    require(l.position%4==0&&l.position<=l.stride-12&&l.skinning%2==0&&l.skinning<=l.stride-12,"Attribute offset outside stride");
    require(l.position+12<=l.skinning||l.skinning+12<=l.position,"Overlapping position/skinning attributes");
}
struct Point {std::array<float,3> position{};std::array<std::uint16_t,4> halfWeights{};std::array<std::uint8_t,4> indices{};std::array<float,4> weights{};};
inline Point decode(std::span<const std::uint8_t> bytes,Layout l,std::uint32_t count,std::uint32_t index) {
    validate(l,count);require(index<count&&bytes.size()==std::size_t(count)*l.stride,"Vertex index/byte extent mismatch");
    Point p;const auto* row=bytes.data()+std::size_t(index)*l.stride;
    std::memcpy(p.position.data(),row+l.position,12);std::memcpy(p.halfWeights.data(),row+l.skinning,8);std::memcpy(p.indices.data(),row+l.skinning+8,4);
    for(float v:p.position)require(std::isfinite(v),"Nonfinite CPU position");
    float sum=0;for(unsigned i=0;i<4;++i){p.weights[i]=half(p.halfWeights[i]);require(p.weights[i]>=0,"Negative skin influence");sum+=p.weights[i];}
    require(sum>0&&std::isfinite(sum),"Empty skin influence");return p;
}
inline bool support(const Point& point,std::span<const std::uint16_t> expected) {
    std::array<std::uint16_t,maxBones> observed{};std::array<bool,maxBones> seen{};
    require(!expected.empty()&&expected.size()<=maxBones,"Bone count outside bounded palette");
    for(unsigned i=0;i<4;++i)if(point.weights[i]!=0){const auto b=point.indices[i];require(b<expected.size()&&!seen[b],"Invalid/duplicate nonzero packed bone index");seen[b]=true;observed[b]=point.halfWeights[i];}
    return std::equal(expected.begin(),expected.end(),observed.begin());
}
using Triangle=std::array<std::uint16_t,3>;
inline std::uint64_t topology(std::span<const Triangle> input) {
    require(!input.empty()&&input.size()<=maxTriangles,"Triangle count outside bounded topology");
    std::vector<Triangle> rows(input.begin(),input.end());
    for(auto& t:rows){require(t[0]!=t[1]&&t[1]!=t[2]&&t[2]!=t[0],"Degenerate topology index");if(t[1]<t[0]&&t[1]<t[2])t={t[1],t[2],t[0]};else if(t[2]<t[0]&&t[2]<t[1])t={t[2],t[0],t[1]};}
    std::sort(rows.begin(),rows.end());std::uint64_t h=14695981039346656037ull;
    for(auto t:rows)for(auto index:t)for(unsigned s:{0u,8u}){h^=(index>>s)&255;h*=1099511628211ull;}return h;
}
struct Slot {
    std::uint32_t form{},base{},serial{},nonce{},count{};std::uint64_t epoch{},deadline{};bool pending{},ready{},poisoned{};
    bool request(std::uint32_t f,std::uint32_t b,std::uint32_t n,std::uint64_t e,std::uint64_t now,std::uint64_t ttl) {
        if(poisoned||pending||count>=maxSamples||!n||n>0x7fffffff||n<=nonce||(f>>24)!=255||b!=fixtureBase||!e||!now||!ttl||now>UINT64_MAX-ttl||(form&&(form!=f||base!=b)))return false;
        form=f;base=b;nonce=n;epoch=e;deadline=now+ttl;serial=++count;pending=true;ready=false;return true;
    }
    bool begin(std::uint32_t s,std::uint64_t e,std::uint64_t now,bool loading)const {return !poisoned&&pending&&serial==s&&epoch==e&&!loading&&now&&now<deadline;}
    bool finish(std::uint32_t s,std::uint64_t e,std::uint64_t now,bool ok){if(serial!=s)return false;pending=false;ready=!poisoned&&ok&&epoch==e&&now&&now<deadline;return ready;}
};
struct Lease {
    std::uint32_t form{},base{},race{},handle{};std::uint64_t epoch{},root{};
    friend bool operator==(const Lease&,const Lease&)=default;
};
inline bool validLease(const Lease& l){return (l.form>>24)==255&&l.base==fixtureBase&&l.race==beastRace&&l.handle&&l.epoch&&l.root;}
inline bool sameLease(const Lease& a,const Lease& b){return validLease(a)&&a==b;}
inline bool sameBoundEpoch(std::uint64_t bound,std::uint64_t requested){return requested&&(!bound||bound==requested);}
}
