"""Control-thread lifetime for prepared C++ timeline plans, with absolute seeks.

The borrowed plan must not be closed while queries are in flight. The native
query is bounded and allocation-free; this Python adapter is for offline/control
use, never an audio device callback.
"""
import ctypes as ct
from .cpp_audio import runtime,BLOCK


class Clip(ct.Structure):
    _fields_=[('start',ct.c_uint64),('source',ct.c_uint64),('frames',ct.c_uint64),('route',ct.c_uint32)]


class Slice(ct.Structure):
    _fields_=[('source',ct.c_uint64),('clip',ct.c_uint32),('route',ct.c_uint32),('offset',ct.c_uint32),('frames',ct.c_uint32)]


class Timeline:
    def __init__(self,clips):
        self._handle=None
        lib=runtime().lib
        lib.mta_timeline_abi.restype=ct.c_uint
        if lib.mta_timeline_abi()!=1:raise RuntimeError('Unsupported C++ timeline ABI')
        lib.mta_timeline_create.argtypes=[ct.POINTER(Clip),ct.c_size_t];lib.mta_timeline_create.restype=ct.c_void_p
        lib.mta_timeline_destroy.argtypes=[ct.c_void_p];lib.mta_timeline_destroy.restype=None
        lib.mta_timeline_query.argtypes=[ct.c_void_p,ct.c_uint64,ct.c_uint32,ct.POINTER(Slice),ct.c_size_t];lib.mta_timeline_query.restype=ct.c_int
        rows=list(clips)
        if len(rows)>100000:raise ValueError('Too many timeline clips')
        for row in rows:
            if len(row)!=4 or any(type(v) is not int or not 0<=v<2**63 for v in row) or row[3]>=64:raise ValueError('Invalid timeline clip')
        data=(Clip*len(rows))(*(Clip(*row) for row in rows));self._lib=lib
        self._slices=(Slice*len(rows))();self._handle=lib.mta_timeline_create(data,len(rows))
        if not self._handle:raise ValueError('Invalid or overlapping timeline clips')

    def query(self,position,frames):
        if self._handle is None:raise RuntimeError('Timeline closed')
        if type(position) is not int or not 0<=position<2**63 or type(frames) is not int or not 1<=frames<=BLOCK:raise ValueError('Invalid timeline block')
        count=self._lib.mta_timeline_query(self._handle,position,frames,self._slices,len(self._slices))
        if count<0:raise ValueError('Timeline query rejected')
        return [Slice.from_buffer_copy(self._slices[i]) for i in range(count)]

    def close(self):
        if self._handle is not None:self._lib.mta_timeline_destroy(self._handle);self._handle=None

    def __enter__(self):return self

    def __exit__(self,*exc):self.close()

    def __del__(self):self.close()
