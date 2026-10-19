// Private host envelope, stripped here before the plugin sees an event list.
// Native UMP hardware output never receives this MIDI 1 SysEx envelope.
if (msg.isSysEx() && msg.getSysExDataSize()==15) {
    const auto* bytes=msg.getSysExData();
    if(bytes[0]==0x7d && bytes[1]=='M' && bytes[2]=='T' && bytes[3]=='A' && bytes[4]==2) {
        uint32_t word[2]={0,0};
        for(int w=0;w<2;w++)for(int b=0;b<5;b++)word[w]|=uint32_t(bytes[5+w*5+b])<<(b*7);
        if((word[0]>>28)!=4)continue;
        const int status=(word[0]>>20)&15,ch=(word[0]>>16)&15,pitch=(word[0]>>8)&127;
        const int noteId=((word[0]>>24)&15)*2048+ch*128+pitch;
        Steinberg::Vst::Event e{};e.busIndex=0;e.sampleOffset=metadata.samplePosition;
        if(status==8 || status==9) {
            const float velocity=float(word[1]>>16)/65535.f;
            if(status==9) {e.type=Steinberg::Vst::Event::kNoteOnEvent;e.noteOn.channel=ch;e.noteOn.pitch=pitch;e.noteOn.velocity=velocity;e.noteOn.noteId=noteId;
                if((word[0]&255)==3)e.noteOn.tuning=float((word[1]&65535)/512.0-pitch)*100.f;
            }else {e.type=Steinberg::Vst::Event::kNoteOffEvent;e.noteOff.channel=ch;e.noteOff.pitch=pitch;e.noteOff.velocity=velocity;e.noteOff.noteId=noteId;}
            result.addEvent(e);
        }else if(status==10) {
            e.type=Steinberg::Vst::Event::kPolyPressureEvent;e.polyPressure.channel=ch;e.polyPressure.pitch=pitch;e.polyPressure.pressure=float(double(word[1])/4294967295.0);e.polyPressure.noteId=noteId;result.addEvent(e);
        }else if(status==6 || status==0 || status==1) {
            e.type=Steinberg::Vst::Event::kNoteExpressionValueEvent;e.noteExpressionValue.noteId=noteId;
            e.noteExpressionValue.value=double(word[1])/4294967295.0;
            if(status==6) {
                e.noteExpressionValue.typeId=Steinberg::Vst::kTuningTypeID;
                // UMP per-note pitch bend is +/- 48 semitones by default.
                e.noteExpressionValue.value=0.5+(double(word[1])-2147483648.0)/2147483648.0*48.0/240.0;
            }else {
                // VST3 3.8 MIDI 2 note-expression namespace. Numeric IDs
                // preserve wire compatibility with our pinned older SDK.
                e.noteExpressionValue.typeId=(status==1?201000u:202000u)+(word[0]&255u);
            }
            result.addEvent(e);
        }else if((status==11 || status==13 || status==14) && midiMapping!=nullptr && parameterChanges!=nullptr) {
            const auto cc=status==11?Steinberg::Vst::CtrlNumber(pitch):status==13?Steinberg::Vst::kAfterTouch:Steinberg::Vst::kPitchBend;
            const auto id=midiMapping->getMapping(ch,cc);
            if(id!=Steinberg::Vst::kNoParamId) {Steinberg::int32 ignore;if(auto* q=parameterChanges->addParameterData(id,ignore))q->addPoint(metadata.samplePosition,double(word[1])/4294967295.0,ignore);}
        }
        continue;
    }
}
