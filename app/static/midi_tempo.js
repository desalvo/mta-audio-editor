/* Hardware MIDI uses the same origin and quarter-note grid as the transport. */
(function(root){'use strict';
 const Clock=root.MtaMusicalClock?.Clock||(typeof require!=='undefined'?require('./musical_clock.js').Clock:null);
 class TempoMap{
  constructor(p){this.clock=new Clock(p);this.points=this.clock.sections.map(v=>({at:v.at,ppq:v.q,bpm:v.quarterBpm}))}
  ppq(ms){return this.clock.quarterAt(ms)}
  time(ppq){return this.clock.timeAtQuarter(ppq)}
 }
 root.MtaTempoMap=TempoMap;if(typeof module!=='undefined')module.exports=TempoMap;
})(typeof globalThis!=='undefined'?globalThis:this);
