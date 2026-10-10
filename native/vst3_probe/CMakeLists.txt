cmake_minimum_required(VERSION 3.18)
project(mta_vst3_probe LANGUAGES CXX)
add_executable(mta_vst3_probe main.cpp)
target_compile_features(mta_vst3_probe PRIVATE cxx_std_20)
# Optional official Steinberg SDK. No SDK source or bundled commercial plugin is vendored.
# Only use an independently obtained copy covered by the SDK's applicable license.
set(MTA_VST3_SDK_ROOT "" CACHE PATH "Path to an independently obtained Steinberg VST3 SDK checkout")
if(MTA_VST3_SDK_ROOT)
  # GitHub "Download ZIP" does not populate Git submodules. Fail at configure
  # time rather than silently building the no-SDK diagnostic executable.
  foreach(required_header IN ITEMS
      "pluginterfaces/base/ipluginbase.h"
      "pluginterfaces/vst/ivstcomponent.h"
      "pluginterfaces/vst/ivstaudioprocessor.h"
      "base/source/fobject.h"
      "public.sdk/source/vst/vstcomponent.h"
      "pluginterfaces/base/coreiids.cpp"
      "public.sdk/source/vst/vstinitiids.cpp")
    if(NOT EXISTS "${MTA_VST3_SDK_ROOT}/${required_header}")
      message(FATAL_ERROR
        "Incomplete Steinberg VST3 SDK: missing ${required_header}. "
        "Download with git clone --recursive and run git submodule update --init --recursive.")
    endif()
  endforeach()
  target_include_directories(mta_vst3_probe PRIVATE "${MTA_VST3_SDK_ROOT}")
  target_compile_definitions(mta_vst3_probe PRIVATE MTA_HAS_VST3_SDK=1)
  target_sources(mta_vst3_probe PRIVATE
    "${MTA_VST3_SDK_ROOT}/pluginterfaces/base/coreiids.cpp"
    "${MTA_VST3_SDK_ROOT}/public.sdk/source/vst/vstinitiids.cpp"
  )
endif()
if(UNIX AND NOT APPLE)
  target_link_libraries(mta_vst3_probe PRIVATE ${CMAKE_DL_LIBS})
endif()
