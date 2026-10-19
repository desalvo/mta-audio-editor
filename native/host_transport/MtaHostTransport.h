// MTA extension to the pinned Pedalboard/JUCE host; used only in DSP workers.
#pragma once
#include <cmath>
#include <mutex>
#include <stdexcept>

class MtaHostTransport final : public juce::AudioPlayHead {
 public:
  void set(double bpm, int numerator, int denominator, long long sample,
           double sampleRate, bool playing, bool looping, double loopStart,
           double loopEnd) {
    if (!std::isfinite(bpm) || bpm <= 0 || bpm > 2000 || numerator < 1 ||
        numerator > 64 || denominator < 1 || denominator > 64 ||
        (denominator & (denominator - 1)) || sample < 0 ||
        !std::isfinite(sampleRate) || sampleRate < 8000 || sampleRate > 384000 ||
        !std::isfinite(loopStart) || !std::isfinite(loopEnd) || loopStart < 0 ||
        loopEnd < loopStart || (looping && loopEnd == loopStart))
      throw std::invalid_argument("Invalid MTA VST transport context");
    std::lock_guard<std::mutex> guard(mutex);
    rate = sampleRate;ppqOffset=0;barOrigin=0;
    current.bpm = bpm;
    current.timeSigNumerator = numerator;
    current.timeSigDenominator = denominator;
    current.timeInSamples = sample;
    current.isPlaying = playing;
    current.isRecording = false;
    current.isLooping = looping;
    current.ppqLoopStart = loopStart;
    current.ppqLoopEnd = loopEnd;
    refresh();
  }
  void musical(double ppq,double bar) {
    if(!std::isfinite(ppq)||!std::isfinite(bar)||std::abs(ppq)>1e9||bar>ppq)
      throw std::invalid_argument("Invalid musical position");
    std::lock_guard<std::mutex> guard(mutex);
    ppqOffset=ppq-current.timeInSamples/rate*current.bpm/60.;barOrigin=bar;refresh();
  }
  bool getCurrentPosition(CurrentPositionInfo& result) override {
    std::lock_guard<std::mutex> guard(mutex);
    result = current;
    return true;
  }
  void advance(int frames) {
    std::lock_guard<std::mutex> guard(mutex);
    if (current.isPlaying) current.timeInSamples += frames;
    refresh();
  }
  CurrentPositionInfo snapshot() {
    CurrentPositionInfo result;
    getCurrentPosition(result);
    return result;
  }
 private:
  void refresh() {
    current.timeInSeconds = current.timeInSamples / rate;
    current.ppqPosition = current.timeInSeconds * current.bpm / 60. + ppqOffset;
    const double bar = current.timeSigNumerator * 4. / current.timeSigDenominator;
    current.ppqPositionOfLastBarStart = barOrigin+std::floor((current.ppqPosition-barOrigin) / bar+1e-10) * bar;
  }
  std::mutex mutex;
  CurrentPositionInfo current;
  double rate = 44100,ppqOffset=0,barOrigin=0;
};
