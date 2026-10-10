cmake_minimum_required(VERSION 3.18)
project(mta_audio_core LANGUAGES CXX)
add_library(mta_audio_core SHARED audio_core.cpp vst3_runtime_api.cpp)
target_compile_features(mta_audio_core PRIVATE cxx_std_20)
set_target_properties(mta_audio_core PROPERTIES CXX_VISIBILITY_PRESET hidden VISIBILITY_INLINES_HIDDEN YES)
target_compile_definitions(mta_audio_core PRIVATE MTA_AUDIO_CORE_EXPORTS)
if(MSVC)
  target_compile_options(mta_audio_core PRIVATE /W4 /EHsc)
else()
  target_compile_options(mta_audio_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Export the stable experimental C interface for integration consumers.
# VST3 readiness remains gated separately from successful library compilation.
target_include_directories(mta_audio_core PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}>
  $<INSTALL_INTERFACE:include/mta_audio_core>)
install(TARGETS mta_audio_core EXPORT MtaAudioCoreTargets
  RUNTIME DESTINATION bin LIBRARY DESTINATION lib ARCHIVE DESTINATION lib)
install(FILES vst3_runtime_api.h DESTINATION include/mta_audio_core)
