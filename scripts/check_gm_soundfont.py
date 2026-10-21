#!/usr/bin/env python3
"""Offline smoke-test for all 128 GM programs and percussion on installed SF2.

Requires reviewed FluidR3 GM and FluidSynth or TinySoundFont runtime. Not a listening test.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.gm_instruments import Synth,status


def audit(rate=48000,bank_id='fluidr3-gm'):
    import numpy as np
    report={'schema':'mta-gm-audit-1','status':status() if bank_id=='fluidr3-gm' else status(bank_id),'programs':[],'drums':{},'certified':False}
    if not report['status']['available']:
        report['blocked']='Reviewed bank and audio runtime must be installed'
        return report
    synth=None
    try:
        synth=Synth({'bank_id':bank_id,'program':0,'reverb_level':0},rate)
        for program in range(128):
            entry={'program':program,'tested_pitches':[],'ok':False}
            try:
                synth.configure({'program':program})
                # SF2 presets need not cover every MIDI key. A contrabass bank
                # may legitimately have no C4 sample. Probe its actual range.
                for pitch in (60,48,36,72):
                    synth.reset()
                    wave=synth.process([(bytes((0x90,pitch,110)),.01),(bytes((0x80,pitch,0)),.12)],duration=.22,sample_rate=rate)
                    finite=bool(np.isfinite(wave).all());peak=float(np.max(np.abs(wave)))
                    entry['tested_pitches'].append(pitch)
                    entry.update(finite=finite,peak=peak,frames=wave.shape[1],ok=finite and peak>1e-6)
                    if entry['ok']:break
            except Exception as exc:
                entry.update(ok=False,error=f'{type(exc).__name__}: {exc}')
            report['programs'].append(entry)
        for pitch in range(35,82):
            try:
                synth.reset()
                wave=synth.process([(bytes((0x99,pitch,120)),.01),(bytes((0x89,pitch,0)),.12)],duration=.22,sample_rate=rate)
                report['drums'][str(pitch)]={'ok':bool(np.isfinite(wave).all() and np.max(np.abs(wave))>1e-6),'peak':float(np.max(np.abs(wave)))}
            except Exception as exc:
                report['drums'][str(pitch)]={'ok':False,'error':str(exc)}
    finally:
        if synth is not None:synth.close()
    report['software_smoke_pass']=all(item['ok'] for item in report['programs']) and all(item['ok'] for item in report['drums'].values())
    return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',help='Write JSON audit file')
    parser.add_argument('--bank-id',default='fluidr3-gm')
    args=parser.parse_args()
    result=audit(bank_id=args.bank_id);encoded=json.dumps(result,indent=2)
    if args.output:Path(args.output).write_text(encoded+'\n')
    else:print(encoded)
    sys.exit(0 if result.get('software_smoke_pass') else 2)
