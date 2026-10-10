"""Five separately exercised native VST3 prerequisites, still experimental."""
import shutil
import subprocess
from pathlib import Path
import pytest

def test_five_native_cycles(tmp_path):
    cc=shutil.which("g++") or shutil.which("clang++")
    if not cc: pytest.skip("C++20 compiler unavailable")
    inc=Path(__file__).resolve().parents[1]/"native"/"audio_core"
    source=tmp_path/"five.cpp"
    source.write_text(r"""
#include "vst3_playout_bridge.hpp"
#include "vst3_parallel_mix.hpp"
#include "vst3_latency_policy.hpp"
#include "vst3_event_packet.hpp"
#include "vst3_recovery_policy.hpp"
#include <cassert>
#include <cmath>
int main(){
 // 131: strict negotiated quantum; invalid frame count silences output.
 mta::Vst3PlayoutBridge bridge(16,2,64,2);
 assert(bridge.valid()); float x[128]{}; float out[128]{};
 x[0]=1; assert(bridge.callback(x,out,64,2));
 out[0]=10; assert(!bridge.callback(x,out,32,2)); assert(out[0]==0);
 // 132: aligned dry fallback has no fake wet signal.
 mta::Vst3ParallelMix mix(1,1); float in[3]{1,2,3}, o[3]{};
 assert(mix.valid()); assert(mix.process(in,nullptr,o,3,1,1));
 assert(o[0]==0 && o[1]==1 && o[2]==2);
 // 133: composed lookahead plus plugin delay and relative alignment.
 mta::Vst3LatencyPolicy a{13,64,2},b{26,64,2};
 assert(a.valid() && a.dry_delay_frames()==141 && a.relative_delay_to(b)==13);
 assert((!mta::Vst3LatencyPolicy{1048576,512,32}.fits_delay_line()));
 // 134: bounded sorted events tied to epoch and transport sequence.
 mta::Vst3EventPacket packet; assert(packet.initialize(4,123,64));
 assert(packet.note(3,0x90,60,100)); assert(!packet.note(2,0x90,60,100));
 assert(packet.parameter(5,3,0.25f)); assert(!packet.parameter(5,64,0.5f));
 assert(packet.matches(4,123,64) && !packet.matches(5,123,64));
 // 135: retry policy circuitbreaker never spins without cap.
 mta::Vst3RecoveryPolicy recovery(3);
 assert(recovery.next_backoff_ms()==250);
 assert(recovery.next_backoff_ms()==500);
 assert(recovery.next_backoff_ms()==1000);
 assert(!recovery.may_restart() && recovery.next_backoff_ms()==0);
 recovery.stable_session(); assert(recovery.may_restart());
 // Long dry-only callback stress with no worker; every call returns safely.
 for(int n=0;n<10000;++n) assert(bridge.callback(x,out,64,2));
 return 0;
}
""")
    binary=tmp_path/"five"
    subprocess.run([cc,"-std=c++20","-O2","-pthread","-Wall","-Wextra","-Werror","-pedantic","-I",str(inc),str(source),"-o",str(binary)],check=True,timeout=30)
    subprocess.run([str(binary)],check=True,timeout=10)
