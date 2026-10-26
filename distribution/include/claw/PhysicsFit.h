#pragma once
// Pure current-vector numeric fitter. This does not mutate an actor or provider.
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <limits>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace claw::physics {
using Vec3 = std::array<double, 3>;
struct Capsule { Vec3 p1{}, p2{}; double radius{}; };
struct Field { std::size_t morph{}; std::vector<Vec3> deltas; };
struct Slot {
    std::string node;
    std::vector<Vec3> points;
    std::vector<Field> fields;
    bool prescribedAxis{false};
    Vec3 axis{};
    std::vector<Field> axisFields;
    std::vector<std::array<std::size_t,3>> triangles;
    std::vector<Vec3> weightDeltas;
    bool active{true};
};
struct Model {
    std::string identity;
    std::vector<std::string> morphs;
    std::vector<Slot> slots;
    double padding{0.0001};
    unsigned contactPasses{};
    bool weightDependent{false};
};
inline Vec3 add(Vec3 a, const Vec3& b, double factor = 1.) {
    for (std::size_t i=0;i<3;++i) a[i] += b[i]*factor;
    return a;
}
inline double dot(const Vec3& a, const Vec3& b) {
    return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];
}
inline bool finite(const Vec3& a) {
    return std::isfinite(a[0]) && std::isfinite(a[1]) && std::isfinite(a[2]);
}
inline Capsule Fit(const std::vector<Vec3>& points, double padding=0.0001, const Vec3* direction=nullptr) {
    if (points.size()<2 || !std::isfinite(padding) || padding<=0 || padding>0.01)
        throw std::runtime_error("Invalid current-vector capsule support");
    Vec3 centre{};
    for (const auto& p:points) {
        if (!finite(p)) throw std::runtime_error("Nonfinite current-vector point");
        centre=add(centre,p,1./static_cast<double>(points.size()));
    }
    std::array<Vec3,3> covariance{};
    for (const auto& p:points) {
        const auto q=add(p,centre,-1.);
        for (std::size_t i=0;i<3;++i)
            for (std::size_t j=0;j<3;++j) covariance[i][j]+=q[i]*q[j];
    }
    std::size_t largest=0;
    for (std::size_t i=1;i<3;++i)
        if (covariance[i][i]>covariance[largest][largest]) largest=i;
    const auto varianceTolerance=1e-12*std::max(1.,std::abs(covariance[largest][largest]));
    for(std::size_t i=0;i<3;++i)if(std::abs(covariance[i][i]-covariance[largest][largest])<=varianceTolerance){largest=i;break;}
    Vec3 axis{}; axis[largest]=1.;
    for (unsigned iteration=0;!direction && iteration<48;++iteration) {
        Vec3 moved{dot(covariance[0],axis),dot(covariance[1],axis),dot(covariance[2],axis)};
        const auto length=std::sqrt(dot(moved,moved));
        if (length<1e-20) break;
        for (auto& v:moved) v/=length;
        axis=moved;
    }
    if (direction) {
        const auto length=std::sqrt(dot(*direction,*direction));
        if (!finite(*direction) || length<1e-12) throw std::runtime_error("Invalid current-vector direction");
        axis=*direction;for (auto& v:axis) v/=length;
    }
    largest=0;
    for (std::size_t i=1;i<3;++i) if (std::abs(axis[i])>std::abs(axis[largest])) largest=i;
    const auto maximumComponent=std::abs(axis[largest]);
    for(std::size_t i=0;i<3;++i)if(std::abs(std::abs(axis[i])-maximumComponent)<=1e-10){largest=i;break;}
    if (axis[largest]<0) for (auto& v:axis) v=-v;
    std::vector<double> along,radial;
    double radius=0.;
    for (const auto& p:points) {
        const auto relative=add(p,centre,-1.);
        const auto projection=dot(relative,axis);
        const auto perpendicular=add(relative,axis,-projection);
        const auto distance=std::sqrt(std::max(0.,dot(perpendicular,perpendicular)));
        along.push_back(projection);radial.push_back(distance);
        radius=std::max(radius,distance);
    }
    radius+=padding;
    double lower=std::numeric_limits<double>::infinity(),upper=-lower;
    for (std::size_t i=0;i<along.size();++i) {
        const auto slack=std::sqrt(std::max(0.,radius*radius-radial[i]*radial[i]));
        lower=std::min(lower,along[i]+slack); upper=std::max(upper,along[i]-slack);
    }
    if (upper<lower) lower=upper=(lower+upper)*0.5;
    return {add(centre,axis,lower),add(centre,axis,upper),radius};
}
inline Vec3 cross(const Vec3& a,const Vec3& b) {
    return {a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]};
}
inline double CapsuleDistance(const Vec3& p,const Capsule& cap) {
    const auto direction=add(cap.p2,cap.p1,-1.),relative=add(p,cap.p1,-1.);
    const auto square=dot(direction,direction);
    const auto fraction=square>1e-20?std::clamp(dot(relative,direction)/square,0.,1.):0.;
    const auto remainder=add(relative,direction,-fraction);
    return std::sqrt(dot(remainder,remainder))-cap.radius;
}
inline double TriangleDistanceSquared(const Vec3& p,const Vec3& a,const Vec3& b,const Vec3& c) {
    const auto u=add(b,a,-1.),v=add(c,a,-1.),w=add(p,a,-1.);
    const auto uu=dot(u,u),uv=dot(u,v),vv=dot(v,v),wu=dot(w,u),wv=dot(w,v),denominator=uu*vv-uv*uv;
    double result=std::numeric_limits<double>::infinity();
    if (std::abs(denominator)>1e-24) {
        const auto beta=(wu*vv-wv*uv)/denominator,gamma=(wv*uu-wu*uv)/denominator;
        if (beta>=0 && gamma>=0 && beta+gamma<=1) {
            const auto residual=add(add(w,u,-beta),v,-gamma);result=dot(residual,residual);
        }
    }
    for (const auto& edge:std::array<std::array<Vec3,2>,3>{{{a,b},{b,c},{c,a}}}) {
        const auto start=edge[0],direction=add(edge[1],start,-1.),relative=add(p,start,-1.);
        const auto square=dot(direction,direction);
        const auto fraction=std::clamp(dot(relative,direction)/(square>1e-24?square:1.),0.,1.);
        const auto residual=add(relative,direction,-fraction);result=std::min(result,dot(residual,residual));
    }
    return std::max(0.,result);
}
inline std::vector<Vec3> ObjectiveSurface(const Capsule& cap) {
    auto axis=add(cap.p2,cap.p1,-1.);const auto length=std::sqrt(dot(axis,axis));
    if (length>1e-10) for (auto& v:axis) v/=length;else axis={0.,0.,1.};
    const auto minimumComponent=std::min({std::abs(axis[0]),std::abs(axis[1]),std::abs(axis[2])});
    std::size_t smallest=0;while(std::abs(axis[smallest])-minimumComponent>1e-10)++smallest;
    Vec3 helper{};helper[smallest]=1.;auto u=cross(axis,helper);const auto unorm=std::sqrt(dot(u,u));for(auto& v:u)v/=unorm;
    const auto v=cross(axis,u);std::vector<Vec3> ring,result;ring.reserve(8);result.reserve(42);
    for(unsigned i=0;i<8;++i)ring.push_back(add(add(Vec3{},u,std::cos(i*3.141592653589793/4.)),v,std::sin(i*3.141592653589793/4.)));
    for(const auto f:{0.,.5,1.})for(const auto& r:ring)result.push_back(add(add(cap.p1,add(cap.p2,cap.p1,-1.),f),r,cap.radius));
    const auto root2=std::sqrt(2.);
    for(unsigned end=0;end<2;++end) {
        const auto origin=end?cap.p2:cap.p1;const auto sign=end?1.:-1.;
        for(const auto& r:ring)result.push_back(add(origin,add(add(Vec3{},r,1./root2),axis,sign/root2),cap.radius));
        result.push_back(add(origin,axis,sign*cap.radius));
    }
    return result;
}
inline Capsule ContactFit(const std::vector<Vec3>& points,const std::vector<std::array<std::size_t,3>>& faces,double padding,unsigned passes) {
    if(faces.empty() || passes>8)throw std::runtime_error("Invalid contact-fit surface or iteration budget");
    std::vector<std::array<Vec3,3>> triangles;
    for(const auto& face:faces) {
        if(face[0]>=points.size() || face[1]>=points.size() || face[2]>=points.size())throw std::runtime_error("Invalid contact-fit triangle index");
        triangles.push_back({points[face[0]],points[face[1]],points[face[2]]});
    }
    std::vector<Vec3> skin;
    for(const auto& weights:std::array<Vec3,7>{{{1.,0.,0.},{0.,1.,0.},{0.,0.,1.},{.5,.5,0.},{.5,0.,.5},{0.,.5,.5},{1./3,1./3,1./3}}})
        for(const auto& triangle:triangles)skin.push_back(add(add(add(Vec3{},triangle[0],weights[0]),triangle[1],weights[1]),triangle[2],weights[2]));
    const auto initial=Fit(points,padding);const auto scale=std::max(initial.radius,padding*10.);
    using Parameters=std::array<double,7>;
    const auto fromParameters=[](const Parameters& x){return Capsule{{x[0],x[1],x[2]},{x[3],x[4],x[5]},x[6]};};
    const auto objective=[&](const Parameters& x) {
        if(x[6]<padding)return std::numeric_limits<double>::infinity();
        const auto cap=fromParameters(x);double maximum=0.,sum=0.;std::size_t count=0;
        for(const auto& point:skin) {const auto d=std::abs(CapsuleDistance(point,cap));maximum=std::max(maximum,d);sum+=d*d;++count;}
        for(const auto& point:ObjectiveSurface(cap)) {
            double square=std::numeric_limits<double>::infinity();
            for(const auto& triangle:triangles)square=std::min(square,TriangleDistanceSquared(point,triangle[0],triangle[1],triangle[2]));
            const auto d=std::sqrt(square);maximum=std::max(maximum,d);sum+=square;++count;
        }
        return maximum+.2*std::sqrt(sum/static_cast<double>(count));
    };
    Parameters x{initial.p1[0],initial.p1[1],initial.p1[2],initial.p2[0],initial.p2[1],initial.p2[2],initial.radius};
    auto score=objective(x),minimum=std::numeric_limits<double>::infinity(),maximum=-minimum;
    auto axisCapsule=initial;axisCapsule.radius=0.;
    for(const auto& p:skin){const auto radial=CapsuleDistance(p,axisCapsule);minimum=std::min(minimum,radial);maximum=std::max(maximum,radial);}
    auto candidate=x;candidate[6]=std::max(padding,(minimum+maximum)*.5);auto trial=objective(candidate);
    if(trial<score-1e-7){x=candidate;score=trial;}
    for(unsigned iteration=0;iteration<passes;++iteration) {
        const auto step=scale*.3*std::pow(.5,static_cast<double>(iteration));
        for(std::size_t dimension=0;dimension<7;++dimension) {
            auto chosen=x;auto best=score;
            for(const auto sign:{-1.,1.}) {
                candidate=x;candidate[dimension]+=step*sign;trial=objective(candidate);
                if(trial<best-1e-7){chosen=candidate;best=trial;}
            }
            x=chosen;score=best;
        }
    }
    return fromParameters(x);
}
inline std::vector<Capsule> Evaluate(const Model& model, const std::vector<double>& values, double weight=0.) {
    if (model.identity.empty() || model.morphs.empty() || model.morphs.size()>32 ||
        model.slots.empty() || model.slots.size()>128 || values.size()!=model.morphs.size())
        throw std::runtime_error("Invalid current-vector model contract");
    if (!std::isfinite(weight) || weight<0 || weight>1)
        throw std::runtime_error("Actor weight outside finite [0,1]");
    for (std::size_t i=0;i<model.morphs.size();++i) {
        if (model.morphs[i].empty() || std::find(model.morphs.begin(),model.morphs.begin()+i,model.morphs[i])!=model.morphs.begin()+i)
            throw std::runtime_error("Invalid or repeated current-vector morph name");
        if (!std::isfinite(values[i]) || values[i]<0 || values[i]>1)
            throw std::runtime_error("Current-vector morph outside finite [0,1]");
    }
    std::vector<Capsule> result;result.reserve(model.slots.size());
    for (const auto& slot:model.slots) {
        if (slot.node.empty()) throw std::runtime_error("Missing current-vector slot node");
        if (!slot.active) {result.push_back({});continue;}
        if(model.contactPasses && slot.prescribedAxis)throw std::runtime_error("Prescribed-axis contact optimization is not supported");
        auto points=slot.points;
        if (!slot.weightDeltas.empty() && slot.weightDeltas.size()!=points.size())
            throw std::runtime_error("Invalid weight endpoint topology");
        if (model.weightDependent && slot.weightDeltas.size()!=points.size())
            throw std::runtime_error("Missing independent weight endpoint field");
        for (std::size_t i=0;i<slot.weightDeltas.size();++i) {
            if (!finite(slot.weightDeltas[i])) throw std::runtime_error("Nonfinite independent weight delta");
            points[i]=add(points[i],slot.weightDeltas[i],weight);
        }
        std::vector<bool> seen(model.morphs.size(),false);
        for (const auto& field:slot.fields) {
            if (field.morph>=values.size() || seen[field.morph] || field.deltas.size()!=points.size())
                throw std::runtime_error("Invalid current-vector field topology");
            seen[field.morph]=true;
            for (std::size_t i=0;i<points.size();++i) {
                if (!finite(field.deltas[i])) throw std::runtime_error("Nonfinite current-vector delta");
                points[i]=add(points[i],field.deltas[i],values[field.morph]);
            }
        }
        auto axis=slot.axis;
        std::fill(seen.begin(),seen.end(),false);
        for (const auto& field:slot.axisFields) {
            if (field.morph>=values.size() || seen[field.morph] || field.deltas.size()!=1 || !finite(field.deltas[0]))
                throw std::runtime_error("Invalid current-vector direction field");
            seen[field.morph]=true;axis=add(axis,field.deltas[0],values[field.morph]);
        }
        result.push_back(model.contactPasses?ContactFit(points,slot.triangles,model.padding,model.contactPasses):Fit(points,model.padding,slot.prescribedAxis?&axis:nullptr));
    }
    return result;
}
} // namespace claw::physics
