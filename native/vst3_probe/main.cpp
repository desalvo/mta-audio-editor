// Isolated VST3 factory probe. This executable MUST NOT run on the audio thread.
// Loading a plugin executes third-party code; launch in a bounded subprocess.
#include <iostream>
#include <filesystem>
#include <string>
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
  // Do not call the factory in this stage: module initialization and factory
  // ownership require the SDK host lifecycle, implemented in a later phase.
  std::cout << "{\"factory_export\":true,\"native_host_ready\":false}\n";
#if defined(_WIN32)
  FreeLibrary(module);
#else
  dlclose(module);
#endif
  return 0;
}
