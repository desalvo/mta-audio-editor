// Deterministic in-repository test fixture. No vendor plugin binary is shipped.
#include <juce_audio_utils/juce_audio_utils.h>
class Probe : public juce::AudioProcessor {
public:
 Probe():AudioProcessor(BusesProperties().withInput("Main",juce::AudioChannelSet::stereo(),true).withInput("Key",juce::AudioChannelSet::stereo(),false).withOutput("Output",juce::AudioChannelSet::stereo(),true)){}
 const juce::String getName() const override{return "MTA Sidechain Probe";}
 void prepareToPlay(double,int)override{}void releaseResources()override{}
 bool isBusesLayoutSupported(const BusesLayout& l)const override{return l.getMainInputChannelSet()==juce::AudioChannelSet::stereo()&&l.getMainOutputChannelSet()==juce::AudioChannelSet::stereo();}
 void processBlock(juce::AudioBuffer<float>& b,juce::MidiBuffer&)override {
  auto main=getBusBuffer(b,true,0);
  if(getBus(true,1)->isEnabled()) {
   auto key=getBusBuffer(b,true,1);
   for(int c=0;c<2;c++)for(int i=0;i<b.getNumSamples();i++)main.setSample(c,i,main.getSample(c,i)*(1.f-key.getSample(c%key.getNumChannels(),i)));
  }
 }
 bool hasEditor()const override{return true;}juce::AudioProcessorEditor* createEditor()override{return new juce::GenericAudioProcessorEditor(*this);}
 bool acceptsMidi()const override{return false;}bool producesMidi()const override{return false;}bool isMidiEffect()const override{return false;}
 double getTailLengthSeconds()const override{return 0;}int getNumPrograms()override{return 1;}int getCurrentProgram()override{return 0;}void setCurrentProgram(int)override{}const juce::String getProgramName(int)override{return "Default";}void changeProgramName(int,const juce::String&)override{}
 void getStateInformation(juce::MemoryBlock& b)override{const char v=1;b.replaceWith(&v,1);}void setStateInformation(const void*,int)override{}
};
juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter(){return new Probe;}
