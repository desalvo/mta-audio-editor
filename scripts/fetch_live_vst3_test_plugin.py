"""Fetch a hash-pinned, upstream-owned Linux test effect; never ship it in MTA."""
from pathlib import Path
import hashlib
import urllib.request

COMMIT='05e8f0b3c4851e77485d7e842dc0355b44106471'
SHA256='7f875a6922ca9e49c7a742a27f26152c685bed2991460781640cc23cfb16d319'
RELATIVE='tests/plugins/effect/Linux/CHOWTapeModel.vst3/Contents/x86_64-linux/CHOWTapeModel.so'


def fetch(destination):
    target=Path(destination)/'CHOWTapeModel.vst3/Contents/x86_64-linux/CHOWTapeModel.so'
    with urllib.request.urlopen('https://raw.githubusercontent.com/spotify/pedalboard/'+COMMIT+'/'+RELATIVE,timeout=60) as response:  # noqa: S310 -- fixed HTTPS upstream and required SHA-256
        data=response.read(7*1024*1024)
    if hashlib.sha256(data).hexdigest()!=SHA256:raise RuntimeError('VST3 test plugin checksum mismatch')
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    return target.parents[2]


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('destination');args=parser.parse_args();print(fetch(args.destination))
