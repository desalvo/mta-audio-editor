// Isolated VST3 factory probe. This executable MUST NOT run on the audio thread.
// Loading a plugin executes third-party code; launch in a bounded subprocess.
#include <iostream>
#include <filesystem>
#include <string>
#ifdef MTA_HAS_VST3_SDK
#include "pluginterfaces/base/ipluginbase.h"
#endif
#if defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#endif
int main(int argc, char** argv) {
  if (argc != 2 || !std::filesystem::exists(argv[1]) || !std::filesystem::is_regular_file(argv[1])) {
    std::cerr << "usage: mta_vst3_probe <VST3 module binary>\n";return 2;
  }
#if defined(_WIN32)
  HMODULE module = LoadLibraryA(argv[1]);
  if (!module) {std::cerr << "LoadLibrary failed\n";return 3;}
  auto factory = reinterpret_cast<void*(*)()>(GetProcAddress(module, "GetPluginFactory"));
  if (!factory) { FreeLibrary(module);std::cerr << "GetPluginFactory missing\n";return 4; }
#else
  void* module = dlopen(argv[1], RTLD_NOW | RTLD_LOCAL);
  if (!module) {std::cerr << "dlopen failed: " << dlerror() << "\n";return 3;}
  auto factory = reinterpret_cast<void*(*)()>(dlsym(module, "GetPluginFactory"));
  if (!factory) {dlclose(module);std::cerr << "GetPluginFactory missing\n";return 4;}
#endif
#ifdef MTA_HAS_VST3_SDK
  // Factory enumeration is diagnostic only. An actual host must initialize the
  // module, negotiate interfaces and buses, then activate and process instances.
  // This path runs exclusively in the isolated subprocess, never audio callback.
  auto* pluginFactory = reinterpret_cast<Steinberg::IPluginFactory*(*)()>(factory)();
  if (!pluginFactory) {std::cerr << "Factory returned null\n";return 5;}
  const Steinberg::int32 classCount = pluginFactory->countClasses();
  if (classCount < 0 || classCount > 10000) {
    pluginFactory->release();std::cerr << "Invalid class count\n";return 6;
  }
  pluginFactory->release();
  std::cout << "{\"factory_export\":true,\"factory_classes\":" << classCount
            << ",\"native_host_ready\":false}\n";
#else
  // Without the SDK the export can be checked but no Steinberg interfaces are invoked.
  std::cout << "{\"factory_export\":true,\"native_host_ready\":false}\n";
#endif
#if defined(_WIN32)
  FreeLibrary(module);
#else
  dlclose(module);
#endif
  return 0;
}
