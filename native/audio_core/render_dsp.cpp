#include "render_dsp.h"
#include <cmath>
#include <cstdint>
#include <limits>
namespace {
bool shape(size_t frames,unsigned channels) noexcept {
 return frames>0 && frames<=4096 && channels>0 && channels<=64;
}
bool finite_float(double x) noexcept {
 return std::isfinite(x) && std::fabs(x)<=std::numeric_limits<float>::max();
}
double envelope(unsigned long long frame,unsigned long long total,float gain,
                unsigned long long in,unsigned long long out) noexcept {
 double v=gain;
 if(in && frame<in)v*=double(frame)/double(in);
 if(out && total-frame<out)v*=double(total-frame)/double(out);
 return v;
}
}
unsigned mta_render_dsp_abi(void) noexcept {return 1;}
int mta_render_gain(float* pcm,size_t frames,unsigned channels,float gain) noexcept {
 if(!pcm || !shape(frames,channels) || !std::isfinite(gain) || gain<0 || gain>128)return -1;
 for(size_t i=0;i<frames*channels;++i)if(!finite_float(double(pcm[i])*gain))return -2;
 for(size_t i=0;i<frames*channels;++i)pcm[i]*=gain;
 return 0;
}
int mta_render_mix(const float* const* inputs,const float* gains,const float* pans,
 const unsigned char* enabled,size_t routes,float* output,size_t frames) noexcept {
 if(!inputs || !gains || !pans || !enabled || !output || !shape(frames,2) || routes<1 || routes>64)return -1;
 const auto dest=reinterpret_cast<std::uintptr_t>(output);
 const size_t bytes=frames*2*sizeof(float);
 for(size_t r=0;r<routes;++r){
  if(!enabled[r])continue;
  if(!inputs[r] || !std::isfinite(gains[r]) || gains[r]<0 || gains[r]>128 ||
     !std::isfinite(pans[r]) || pans[r]<-1 || pans[r]>1)return -1;
  const auto src=reinterpret_cast<std::uintptr_t>(inputs[r]);
  if(src>std::numeric_limits<std::uintptr_t>::max()-bytes || dest>std::numeric_limits<std::uintptr_t>::max()-bytes ||
     (src<dest+bytes && dest<src+bytes))return -1;
 }
 // Full preflight, including sum overflow, before writing a single sample.
 for(size_t i=0;i<frames*2;++i){
  double sum=0;
  for(size_t r=0;r<routes;++r){
   if(!enabled[r])continue;
   const double balance=(i%2==0)?(pans[r]>0?1.0-pans[r]:1.0):(pans[r]<0?1.0+pans[r]:1.0);
   if(!std::isfinite(inputs[r][i]))return -2;
   sum+=double(inputs[r][i])*gains[r]*balance;
  }
  if(!finite_float(sum))return -2;
 }
 for(size_t i=0;i<frames*2;++i){
  double sum=0;
  for(size_t r=0;r<routes;++r){
   if(!enabled[r])continue;
   const double balance=(i%2==0)?(pans[r]>0?1.0-pans[r]:1.0):(pans[r]<0?1.0+pans[r]:1.0);
   sum+=double(inputs[r][i])*gains[r]*balance;
  }
  output[i]=static_cast<float>(sum);
 }
 return 0;
}
int mta_render_envelope(float* pcm,size_t frames,unsigned channels,unsigned long long offset,
 unsigned long long total,float gain,unsigned long long in,unsigned long long out) noexcept {
 if(!pcm || !shape(frames,channels) || !total || offset>total || frames>total-offset ||
    !std::isfinite(gain) || gain<0 || gain>128)return -1;
 for(size_t f=0;f<frames;++f){
  const double g=envelope(offset+f,total,gain,in,out);
  for(unsigned c=0;c<channels;++c)if(!finite_float(double(pcm[f*channels+c])*g))return -2;
 }
 for(size_t f=0;f<frames;++f){
  const double g=envelope(offset+f,total,gain,in,out);
  for(unsigned c=0;c<channels;++c)pcm[f*channels+c]=static_cast<float>(pcm[f*channels+c]*g);
 }
 return 0;
}
