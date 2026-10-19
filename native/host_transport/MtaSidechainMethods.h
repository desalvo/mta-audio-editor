// Included inside the pinned ExternalPlugin class, outside the device callback.
 public:
  py::list mtaSidechainBuses() {
    py::list result;
    for (int i=1; i<pluginInstance->getBusCount(true); ++i) {
      auto* bus=pluginInstance->getBus(true,i);
      py::dict item;item["index"]=i;item["name"]=bus->getName().toStdString();
      item["channels"]=bus->getDefaultLayout().size();result.append(item);
    }
    return result;
  }
  py::array_t<float> mtaProcessSidechain(
      py::array_t<float,py::array::c_style|py::array::forcecast> main,
      py::array_t<float,py::array::c_style|py::array::forcecast> side,
      double rate,int busIndex=1) {
    if (main.ndim()!=2 || side.ndim()!=2 || main.shape(0)!=2 ||
        side.shape(0)!=2 || main.shape(1)!=side.shape(1) || main.shape(1)<1 ||
        main.shape(1)>32768 || !std::isfinite(rate) || rate<8000 || rate>192000)
      throw std::invalid_argument("Invalid stereo sidechain buffer");
    if (busIndex<1 || busIndex>=pluginInstance->getBusCount(true))
      throw std::invalid_argument("VST3 has no selected external sidechain bus");
    const int count=static_cast<int>(main.shape(1));
    if (lastSpec.sampleRate!=rate || lastSpec.maximumBlockSize<count ||
        lastSpec.numChannels!=2 || !pluginInstance->getBus(true,busIndex)->isEnabled()) {
      pluginInstance->releaseResources();setNumChannels(2);
      auto* bus=pluginInstance->getBus(true,busIndex);
      const int channels=bus->isNumberOfChannelsSupported(2)?2:1;
      if (!bus->setNumberOfChannels(channels) || !bus->enable(true))
        throw std::invalid_argument("VST3 rejected external sidechain layout");
      pluginInstance->setNonRealtime(false);pluginInstance->prepareToPlay(rate,std::max(512,count));
      lastSpec={rate,static_cast<juce::uint32>(std::max(512,count)),2};
    }
    juce::AudioBuffer<float> audio(std::max(pluginInstance->getTotalNumInputChannels(),
        pluginInstance->getTotalNumOutputChannels()),count);audio.clear();
    for(int c=0;c<2;c++)audio.copyFrom(c,0,main.data(c),count);
    auto aux=pluginInstance->getBusBuffer(audio,true,busIndex);
    for(int c=0;c<aux.getNumChannels();c++) {
      if(aux.getNumChannels()==1)for(int i=0;i<count;i++)aux.setSample(c,i,(side.at(0,i)+side.at(1,i))*.5f);
      else aux.copyFrom(c,0,side.data(c%2),count);
    }
    juce::MidiBuffer midi;
    {py::gil_scoped_release release;pluginInstance->processBlock(audio,midi);}
    mtaTransport.advance(count);samplesProvided+=count;
    int usable=static_cast<int>(std::min<long>(count,std::max<long>(0,samplesProvided-pluginInstance->getLatencySamples())));
    py::array_t<float> output({2,usable});
    for(int c=0;c<2;c++)std::copy(audio.getReadPointer(c)+count-usable,audio.getReadPointer(c)+count,output.mutable_data(c));
    return output;
  }
