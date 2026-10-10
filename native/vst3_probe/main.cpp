// Isolated VST3 factory probe. This executable MUST NOT run on the audio thread.
// Loading a plugin executes third-party code; launch in a bounded subprocess.
#include <iostream>
#include <filesystem>
#include <string>
#include <iomanip>
#include <sstream>
#include <algorithm>
#include <cctype>
#ifdef MTA_HAS_VST3_SDK
#include "pluginterfaces/base/ipluginbase.h"
#include "pluginterfaces/vst/ivstcomponent.h"
#include <cstring>
#endif
#if defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#else
#include <dlfcn.h>
#endif
// Escape untrusted plugin metadata before emitting a JSON diagnostic record.
static std::string json_quote(const std::string& value) {
  std::ostringstream out; out << '"';
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') { out << '\\' << char(c); }
    else if (c < 0x20) { out << "\\u" << std::hex << std::setfill('0') << std::setw(4) << unsigned(c) << std::dec; }
    else out << char(c);
  }
  out << '"'; return out.str();
}
#ifdef MTA_HAS_VST3_SDK
static std::string class_cid(const Steinberg::TUID& id) {
  std::ostringstream out;
  out << std::hex << std::setfill('0');
  for (const auto byte : id) out << std::setw(2) << unsigned(static_cast<unsigned char>(byte));
  return out.str();
}
#endif
int main(int argc, char** argv) {
  const bool lifecycle = argc == 4 && std::string(argv[2]) == "--lifecycle";
  const bool instantiate = argc == 4 && (std::string(argv[2]) == "--instantiate" || lifecycle);
  if ((argc != 2 && !instantiate) || !std::filesystem::exists(argv[1]) || !std::filesystem::is_regular_file(argv[1])) {
    std::cerr << "usage: mta_vst3_probe <VST3 module binary> [--instantiate|--lifecycle <32-hex-CID>]\n";return 2;
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
  std::ostringstream classes;
  classes << "[";
  for (Steinberg::int32 i=0; i<classCount; ++i) {
    Steinberg::PClassInfo info{};
    if (pluginFactory->getClassInfo(i, &info) != Steinberg::kResultOk) continue;
    if (classes.tellp() > std::streampos(1)) classes << ",";
    classes << "{\"cid\":" << json_quote(class_cid(info.cid))
            << ",\"name\":" << json_quote(info.name)
            << ",\"category\":" << json_quote(info.category) << "}";
  }
  classes << "]";
  // Both modes are opt-in diagnostics. Never call setupProcessing(), setActive() or process().
  bool created = false;
  bool found = false;
  bool initialized = false;
  bool terminated = false;
  std::ostringstream busDetails;
  busDetails << "[";
  int reportedBuses = 0;
  if (instantiate) {
    const std::string wanted = argv[3];
    if (wanted.size() != 32 || !std::all_of(wanted.begin(), wanted.end(), [](unsigned char c) {
          return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F');
        })) {
      pluginFactory->release(); std::cerr << "Invalid class CID (expected 32 hexadecimal digits)\n"; return 7;
    }
    for (Steinberg::int32 i = 0; i < classCount; ++i) {
      Steinberg::PClassInfo info{};
      if (pluginFactory->getClassInfo(i, &info) != Steinberg::kResultOk) continue;
      auto hex = class_cid(info.cid);
      std::transform(hex.begin(), hex.end(), hex.begin(), [](unsigned char c) { return char(std::tolower(c)); });
      std::string target = wanted;
      std::transform(target.begin(), target.end(), target.begin(), [](unsigned char c) { return char(std::tolower(c)); });
      if (hex != target) continue;
      found = true;
      // Explicitly require an audio component class; controller-only entries are excluded.
      if (std::string(info.category) != "Audio Module Class") break;
      Steinberg::Vst::IComponent* component = nullptr;
      const auto result = pluginFactory->createInstance(info.cid, Steinberg::Vst::IComponent::iid,
                                                         reinterpret_cast<void**>(&component));
      if (result == Steinberg::kResultOk && component != nullptr) {
        created = true;
        if (lifecycle) {
          // Null host context intentionally does not claim a production host contract.
          // Some plugins require a real IHostApplication and will correctly refuse.
          const auto initResult = component->initialize(nullptr);
          initialized = (initResult == Steinberg::kResultOk);
          if (initialized) {
            // Read-only bus inspection in the isolated probe, before terminate().
            for (const auto media : {Steinberg::Vst::kAudio, Steinberg::Vst::kEvent}) {
              for (const auto direction : {Steinberg::Vst::kInput, Steinberg::Vst::kOutput}) {
                const auto count = component->getBusCount(media, direction);
                if (count < 0 || count > 256) continue;  // Do not trust third-party metadata.
                for (Steinberg::int32 index = 0; index < count && reportedBuses < 1024; ++index) {
                  Steinberg::Vst::BusInfo info{};
                  if (component->getBusInfo(media, direction, index, info) != Steinberg::kResultOk) continue;
                  if (reportedBuses++) busDetails << ",";
                  // Avoid logging untrusted UTF-16 bus names until a bounded conversion is available.
                  busDetails << "{\"media\":\"" << (media == Steinberg::Vst::kAudio ? "audio" : "event")
                             << "\",\"direction\":\"" << (direction == Steinberg::Vst::kInput ? "input" : "output")
                             << "\",\"index\":" << index << ",\"channels\":" << info.channelCount
                             << ",\"bus_type\":" << info.busType << "}";
                }
              }
            }
            terminated = (component->terminate() == Steinberg::kResultOk);
          }
        }
      }
      if (component) component->release();
      break;
    }
  }
  busDetails << "]";
  pluginFactory->release();
  std::cout << "{\"factory_export\":true,\"factory_classes\":" << classCount
            << ",\"classes\":" << classes.str()
            << ",\"instance_requested\":" << (instantiate ? "true" : "false")
            << ",\"instance_found\":" << (found ? "true" : "false")
            << ",\"instance_created\":" << (created ? "true" : "false")
            << ",\"lifecycle_requested\":" << (lifecycle ? "true" : "false")
            << ",\"instance_initialized\":" << (initialized ? "true" : "false")
            << ",\"instance_terminated\":" << (terminated ? "true" : "false")
            << ",\"buses\":" << busDetails.str() << ",\"native_host_ready\":false}\n";
#else
  if (instantiate) { std::cerr << "Instance creation requires MTA_VST3_SDK_ROOT\n"; return 8; }
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
