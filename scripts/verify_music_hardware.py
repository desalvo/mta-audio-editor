#!/usr/bin/env python3
"""Read-only hardware inventory by default; physical tests require explicit flags.

No model download, driver installation, production service change or billing
configuration is performed. A passed inventory is not hardware certification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def drm_counters():
    result=[];folder=Path('/proc/self/fdinfo')
    if folder.is_dir():
        for path in folder.iterdir():
            try:lines=path.read_text().splitlines()
            except OSError:continue
            values={k.strip():v.strip() for line in lines if ':' in line for k,v in [line.split(':',1)]
                    if k.startswith(('drm-engine-','drm-client-id','drm-pdev'))}
            if values:result.append(values)
    return result


def inventory():
    result={'schema':'mta-hardware-acceptance-1','version':'0.3.0-r210',
        'system':platform.system(),'machine':platform.machine(),'kernel':platform.release(),
        'container':None,'checks':{},'certified':False,'physical_tests_run':False}
    marker=Path('/run/systemd/container')
    if marker.is_file():result['container']=marker.read_text().strip()[:100]
    result['checks']['drm_fdinfo']={'available':bool(drm_counters()),'verified':False,
        'note':'Empty fdinfo does not establish GPU inactivity or driver incompatibility.'}
    try:
        from app.native_device_io import devices
        # Inventory is an explicit standalone native operation, not a web alias.
        previous=os.environ.get('MTA_NATIVE_SINGLE_USER');os.environ['MTA_NATIVE_SINGLE_USER']='true'
        try:result['checks']['audio_inventory']={**devices(),'verified':False}
        finally:
            if previous is None:os.environ.pop('MTA_NATIVE_SINGLE_USER',None)
            else:os.environ['MTA_NATIVE_SINGLE_USER']=previous
    except Exception as exc:result['checks']['audio_inventory']={'available':False,'verified':False,'error':type(exc).__name__+': '+str(exc)[:500]}
    return result


def rocm_test():
    import torch
    if not torch.version.hip or not torch.cuda.is_available():raise RuntimeError('This interpreter has no available ROCm GPU; use the installed engine ROCm interpreter')
    before=drm_counters();device=torch.cuda.current_device()
    with torch.inference_mode():
        a=torch.randn((1024,1024),device=device);b=torch.randn_like(a)
        for _ in range(3):a@b
        torch.cuda.synchronize()
        begin=torch.cuda.Event(enable_timing=True);end=torch.cuda.Event(enable_timing=True)
        begin.record()
        for _ in range(32):value=a@b
        end.record();end.synchronize()
        duration=begin.elapsed_time(end)
        if not torch.isfinite(value).all().item() or duration<=0:raise RuntimeError('ROCm computation/timing self-test failed')
    return {'verified':True,'test':'32 matrix products on one stream','torch':torch.__version__,
        'hip':torch.version.hip,'device':torch.cuda.get_device_name(device),
        'stream_interval_ms':duration,'drm_before':before,'drm_after':drm_counters(),
        'note':'Validates this computation only; does not certify model compatibility, process attribution or billing.'}


def audio_test(settings,seconds,require_asio):
    import numpy as np
    from app.native_device_io import Settings,PortAudioDevice
    cfg=Settings.model_validate_json(Path(settings).read_bytes())
    if cfg.backend!='portaudio':raise ValueError('Select explicit PortAudio routing in the supplied settings')
    device=PortAudioDevice(48000,seconds*48000,cfg)
    try:
        if require_asio and 'ASIO' not in device.host_api.upper():raise ValueError('Selected host API is not ASIO')
        block=np.zeros((1024,2),dtype=np.float32);sent=0;total=seconds*48000
        while sent<min(total,8192):
            part=block[:min(len(block),total-sent)]
            if not device.push(part):raise RuntimeError('Cannot prime output ring')
            sent+=len(part)
        device.control('play');deadline=time.monotonic()+seconds+10
        finished=False
        while time.monotonic()<deadline:
            while sent<total and device.buffered()<8192:
                part=block[:min(len(block),total-sent)]
                if not device.push(part):break
                sent+=len(part)
            if sent==total and not finished:device.finish();finished=True
            state=device.status()
            if state['failed']:raise RuntimeError('Physical output failed')
            if state['ended']:break
            time.sleep(.003)
        else:raise RuntimeError('Physical transport did not finish within its deadline')
        if state['underruns']:raise RuntimeError('Physical output underruns: '+str(state['underruns']))
        return {'verified':True,'test':'silent physical output stream','frames_sent':sent,'state':state,
            'note':'Does not test electrical loopback, input channels, audible routing or MIDI hardware.'}
    finally:device.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--exercise-rocm',action='store_true')
    parser.add_argument('--exercise-audio',action='store_true',help='Open the selected physical output and stream silence')
    parser.add_argument('--audio-settings',type=Path)
    parser.add_argument('--require-asio',action='store_true')
    parser.add_argument('--seconds',type=int,choices=range(2,31),default=10)
    args=parser.parse_args()
    if args.exercise_audio and not args.audio_settings:parser.error('--exercise-audio requires --audio-settings JSON exported from Audio I/O')
    result=inventory();failed=False
    for name,enabled,operation in [('rocm_compute',args.exercise_rocm,rocm_test),
        ('physical_audio',args.exercise_audio,lambda:audio_test(args.audio_settings,args.seconds,args.require_asio))]:
        if not enabled:result['checks'][name]={'verified':False,'status':'not_run'};continue
        result['physical_tests_run']=True
        try:result['checks'][name]=operation()
        except Exception as exc:result['checks'][name]={'verified':False,'status':'failed','error':str(exc)[:1000]};failed=True
    data=json.dumps(result,indent=2,ensure_ascii=False).encode()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_bytes(data)
        args.output.with_suffix(args.output.suffix+'.sha256').write_text(hashlib.sha256(data).hexdigest()+'  '+args.output.name+'\n')
    else:print(data.decode())
    return int(failed)


if __name__=='__main__':raise SystemExit(main())
