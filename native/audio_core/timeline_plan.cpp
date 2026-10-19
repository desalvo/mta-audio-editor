#include "timeline_plan.h"
#include <algorithm>
#include <array>
#include <limits>
#include <vector>
struct Indexed {mta_timeline_clip clip;uint32_t index;};
struct mta_timeline_plan {std::array<std::vector<Indexed>,64> routes;};
namespace {
constexpr uint64_t max_frame=static_cast<uint64_t>(std::numeric_limits<int64_t>::max());
template<class F> size_t visit(const mta_timeline_plan* p,uint64_t pos,uint32_t frames,F emit) noexcept {
    size_t n=0;const uint64_t end=pos+frames;
    for(const auto& route:p->routes){
        // Non-overlap makes clip end monotonic; skip every completed clip in log N.
        auto it=std::lower_bound(route.begin(),route.end(),pos,[](const Indexed& c,uint64_t v){return c.clip.start+c.clip.frames<=v;});
        for(;it!=route.end()&&it->clip.start<end;++it){
            const auto& c=it->clip;const uint64_t a=std::max(pos,c.start),b=std::min(end,c.start+c.frames);
            if(a<b){emit(n,mta_timeline_slice{c.source+a-c.start,it->index,c.route,static_cast<uint32_t>(a-pos),static_cast<uint32_t>(b-a)});++n;}
        }
    }
    return n;
}
}
unsigned mta_timeline_abi(void) noexcept {return 1;}
mta_timeline_plan* mta_timeline_create(const mta_timeline_clip* clips,size_t n) noexcept {
    if(n>100000||(!clips&&n))return nullptr;
    try{
        auto* p=new mta_timeline_plan;
        try{
            for(size_t i=0;i<n;++i){const auto& c=clips[i];
                if(c.route>=64||!c.frames||c.start>max_frame||c.source>max_frame||c.frames>max_frame-c.start||c.frames>max_frame-c.source){delete p;return nullptr;}
                p->routes[c.route].push_back({c,static_cast<uint32_t>(i)});
            }
            for(auto& r:p->routes){std::sort(r.begin(),r.end(),[](const Indexed& a,const Indexed& b){return a.clip.start<b.clip.start;});
                for(size_t i=1;i<r.size();++i)if(r[i-1].clip.start+r[i-1].clip.frames>r[i].clip.start){delete p;return nullptr;}
            }
        }catch(...){delete p;throw;}
        return p;
    }catch(...){return nullptr;}
}
void mta_timeline_destroy(mta_timeline_plan* p) noexcept {delete p;}
int mta_timeline_query(const mta_timeline_plan* p,uint64_t pos,uint32_t frames,mta_timeline_slice* out,size_t cap) noexcept {
    if(!p||!frames||frames>4096||pos>max_frame||frames>max_frame-pos)return -1;
    const size_t count=visit(p,pos,frames,[](size_t,const mta_timeline_slice&){});
    if(count>cap)return -2;
    if(count&&!out)return -1;
    visit(p,pos,frames,[out](size_t i,const mta_timeline_slice& s){out[i]=s;});
    return static_cast<int>(count);
}
