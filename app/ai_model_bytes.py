"""Read verified immutable bytes for supported in-process model loaders.

This binds loader input, not arbitrary Python adapters or external data files.
"""
import hashlib
import os
import stat


def verified_model_bytes(path,expected_sha256,*,max_bytes):
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        info=os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or not 0<info.st_size<=max_bytes:
            raise ValueError('Unsafe model byte source')
        data=stream.read(max_bytes+1)
        after=os.fstat(stream.fileno())
        if (len(data)!=info.st_size or len(data)>max_bytes
                or (info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns)
                or hashlib.sha256(data).hexdigest()!=expected_sha256):
            raise ValueError('Loaded model bytes failed integrity verification')
        return data

