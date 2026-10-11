# r172 native PDC status

The C++20 route planner calculates the alignment delay of each active path using cumulative plugin and inter-process transport latency. It refuses excessive counts and delays, supports up to 64 routes and is tested by compiling and running a native C++ program. No actual realtime routing is enabled. The next phase must wire block-accurate delay lines to the native playback/mixer with timeline changes, device renegotiation, MIDI and automation alignment, dry/wet bypass and plugin crash handling, then validate on every supported platform. `native_host_ready=false`.
