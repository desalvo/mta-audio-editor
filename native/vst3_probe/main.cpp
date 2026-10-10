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
#include "pluginterfaces/vst/ivstaudioprocessor.h"
#include "pluginterfaces/vst/ivsteditcontroller.h"
#include "pluginterfaces/vst/ivsthostapplication.h"
#include <cstring>
#include <limits>
#include <atomic>
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
// Portable bounded read of fixed-size Steinberg metadata, including malformed
// non-NUL-terminated arrays (strnlen is not portable across MSVC toolchains).
template <size_t N> static std::string bounded_class_string(const char (&data)[N]) {
  return std::string(data, std::find(data, data + N, '\0'));
}
// Minimal diagnostic host context. It deliberately does not provide IMessage,
// attribute lists, GUI callbacks, transport or realtime services.
class DiagnosticHost final : public Steinberg::Vst::IHostApplication {
 public:
  Steinberg::tresult PLUGIN_API queryInterface(const Steinberg::TUID iid, void** obj) override {
    if (!obj) return Steinberg::kInvalidArgument;
    *obj = nullptr;
    if (Steinberg::FUnknownPrivate::iidEqual(iid, Steinberg::Vst::IHostApplication::iid) ||
        Steinberg::FUnknownPrivate::iidEqual(iid, Steinberg::FUnknown::iid)) {
      *obj = static_cast<Steinberg::Vst::IHostApplication*>(this);
      addRef();
      return Steinberg::kResultOk;
    }
    return Steinberg::kNoInterface;
  }
  Steinberg::uint32 PLUGIN_API addRef() override { return ++refs_; }
  Steinberg::uint32 PLUGIN_API release() override {
    // Stack-owned for the duration of initialize/terminate; never delete this.
    const auto count = refs_.load();
    return count > 1 ? --refs_ : count;
  }
  Steinberg::tresult PLUGIN_API getName(Steinberg::Vst::String128 name) override {
    if (!name) return Steinberg::kInvalidArgument;
    constexpr char16_t hostName[] = u"MTA Audio Editor VST3 Diagnostic";
    for (size_t i = 0; i < 128; ++i) name[i] = i < sizeof(hostName)/sizeof(hostName[0]) ? hostName[i] : 0;
    return Steinberg::kResultOk;
  }
  Steinberg::tresult PLUGIN_API createInstance(Steinberg::TUID, Steinberg::TUID, void** obj) override {
    if (obj) *obj = nullptr;
    return Steinberg::kNotImplemented;
  }
 private:
  std::atomic<Steinberg::uint32> refs_{1};
};
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
  // Validate user-controlled CID before loading any third-party binary.
  // This applies with and without the optional Steinberg SDK.
  if (instantiate) {
    const std::string cid = argv[3];
    if (cid.size() != 32 || !std::all_of(cid.begin(), cid.end(), [](unsigned char c) {
          return std::isxdigit(c) != 0 && c < 128;
        })) {
      std::cerr << "Invalid class CID (expected 32 hexadecimal digits)\n";
      return 7;
    }
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
    // Steinberg's PClassInfo carries fixed-size character arrays. Bound reads
    // even when a malformed third-party factory omits NUL termination.
    const std::string safeName = bounded_class_string(info.name);
    const std::string safeCategory = bounded_class_string(info.category);
    classes << "{\"cid\":" << json_quote(class_cid(info.cid))
            << ",\"name\":" << json_quote(safeName)
            << ",\"category\":" << json_quote(safeCategory) << "}";
  }
  classes << "]";
  // Both modes are opt-in diagnostics. Never call setupProcessing(), setActive() or process().
  bool created = false;
  bool found = false;
  bool initialized = false;
  bool hostContextProvided = false;
  bool terminated = false;
  bool audioProcessor = false;
  bool supports32Bit = false;
  bool supports64Bit = false;
  bool sampleSizeQueried = false;
  int latencySamples = -1;
  bool editController = false;
  bool audioProcessorQueried = false;
  bool editControllerQueried = false;
  std::ostringstream busDetails;
  busDetails << "[";
  int reportedBuses = 0;
  if (instantiate) {
    const std::string wanted = argv[3];
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
      if (bounded_class_string(info.category) != "Audio Module Class") break;
      Steinberg::Vst::IComponent* component = nullptr;
      const auto result = pluginFactory->createInstance(info.cid, Steinberg::Vst::IComponent::iid,
                                                         reinterpret_cast<void**>(&component));
      Steinberg::Vst::IAudioProcessor* processor = nullptr;
      if (result == Steinberg::kResultOk && component != nullptr) {
        created = true;
        // Discovery only: query interfaces without calling setupProcessing, setActive,
        // process or creating a GUI. A component need not implement IEditController.
        audioProcessorQueried = true;
        if (component->queryInterface(Steinberg::Vst::IAudioProcessor::iid,
                                      reinterpret_cast<void**>(&processor)) == Steinberg::kResultOk && processor) {
          audioProcessor = true;
        }
        // Query read-only processor capabilities after component initialization below.
        // Retain the processor interface until the diagnostic cycle is complete.
        Steinberg::Vst::IEditController* controller = nullptr;
        editControllerQueried = true;
        if (component->queryInterface(Steinberg::Vst::IEditController::iid,
                                      reinterpret_cast<void**>(&controller)) == Steinberg::kResultOk && controller) {
          editController = true;
        }
        if (controller) controller->release();
        if (lifecycle) {
          // A minimal IHostApplication may still be rejected by plugins requiring
          // IMessage, IAttributeList or other optional host capabilities.
          DiagnosticHost host;
          hostContextProvided = true;
          const auto initResult = component->initialize(&host);
          initialized = (initResult == Steinberg::kResultOk);
          if (initialized) {
            if (processor) {
              sampleSizeQueried = true;
              supports32Bit = processor->canProcessSampleSize(Steinberg::Vst::kSample32) == Steinberg::kResultOk;
              supports64Bit = processor->canProcessSampleSize(Steinberg::Vst::kSample64) == Steinberg::kResultOk;
              const auto reportedLatency = processor->getLatencySamples();
              if (reportedLatency <= 10000000U) latencySamples = static_cast<int>(reportedLatency);
            }
            // Read-only bus inspection in the isolated probe, before terminate().
            for (const auto media : {Steinberg::Vst::kAudio, Steinberg::Vst::kEvent}) {
              for (const auto direction : {Steinberg::Vst::kInput, Steinberg::Vst::kOutput}) {
                const auto count = component->getBusCount(media, direction);
                if (count < 0 || count > 256) continue;  // Do not trust third-party metadata.
                for (Steinberg::int32 index = 0; index < count && reportedBuses < 1024; ++index) {
                  Steinberg::Vst::BusInfo info{};
                  if (component->getBusInfo(media, direction, index, info) != Steinberg::kResultOk) continue;
                  if (info.channelCount < 0 || info.channelCount > 1024) continue;
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
      if (processor) processor->release();
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
            << ",\"host_context_provided\":" << (hostContextProvided ? "true" : "false")
            << ",\"instance_initialized\":" << (initialized ? "true" : "false")
            << ",\"instance_terminated\":" << (terminated ? "true" : "false")
            << ",\"audio_processor_queried\":" << (audioProcessorQueried ? "true" : "false")
            << ",\"audio_processor_available\":" << (audioProcessor ? "true" : "false")
            << ",\"edit_controller_queried\":" << (editControllerQueried ? "true" : "false")
            << ",\"edit_controller_available\":" << (editController ? "true" : "false")
            << ",\"sample_size_queried\":" << (sampleSizeQueried ? "true" : "false")
            << ",\"supports_32_bit\":" << (supports32Bit ? "true" : "false")
            << ",\"supports_64_bit\":" << (supports64Bit ? "true" : "false")
            << ",\"latency_samples\":" << latencySamples
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
