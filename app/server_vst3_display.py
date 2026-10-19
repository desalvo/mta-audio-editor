"""Worker-private X11 desktop for original VST editors; never a public VNC service.

Every worker owns an authenticated Xvfb. Only the owning HTTP session can receive
JPEG frames or inject bounded input. No shell, clipboard or filesystem channel.
"""
import ctypes as C
import ctypes.util
import os
from pathlib import Path
import secrets
import shutil
import struct
import subprocess
import threading
import time


def executable():
    private=Path(__file__).resolve().parents[1]/'bin/Xvfb'
    return str(private) if private.is_file() and os.access(private,os.X_OK) else shutil.which('Xvfb')

def unavailable_reason():
    try:C.CDLL('libX11.so.6');C.CDLL('libXtst.so.6')
    except OSError:return 'Original server editors require Xvfb and libXtst. Install the updated server package.'
    from .vst3_sandbox import available as confinement_available
    if not executable():return 'Original server editors require Xvfb. Install the updated server package.'
    if not confinement_available() and os.getenv('MTA_VST3_DISPLAY_TEST_TCP')!='1':return 'Original server editors require Linux Landlock ABI 3 or newer, permitted by the host/container policy.'
    return ''

def available():return not unavailable_reason()


class Image(C.Structure):
    _fields_=[('width',C.c_int),('height',C.c_int),('xoffset',C.c_int),('format',C.c_int),('data',C.c_void_p),('byte_order',C.c_int),('bitmap_unit',C.c_int),('bitmap_bit_order',C.c_int),('bitmap_pad',C.c_int),('depth',C.c_int),('bytes_per_line',C.c_int),('bits_per_pixel',C.c_int),('red_mask',C.c_ulong),('green_mask',C.c_ulong),('blue_mask',C.c_ulong)]


class Desktop:
    width=1600;height=1000
    def __init__(self,root):
        if not available():raise RuntimeError(unavailable_reason())
        self.proc=None;self.display=None;self.lock=threading.RLock();self.buttons=set();self.keys=set();self.last=0
        self.lib=C.CDLL('libX11.so.6');self.test=C.CDLL('libXtst.so.6')
        self.lib.XInitThreads()
        def bind(lib,name,restype,*args):
            f=getattr(lib,name);f.restype=restype;f.argtypes=list(args);return f
        bind(self.lib,'XOpenDisplay',C.c_void_p,C.c_char_p)
        bind(self.lib,'XDefaultRootWindow',C.c_ulong,C.c_void_p)
        bind(self.lib,'XGetImage',C.POINTER(Image),C.c_void_p,C.c_ulong,C.c_int,C.c_int,C.c_uint,C.c_uint,C.c_ulong,C.c_int)
        bind(self.lib,'XDestroyImage',C.c_int,C.POINTER(Image))
        bind(self.lib,'XFlush',C.c_int,C.c_void_p)
        bind(self.lib,'XCloseDisplay',C.c_int,C.c_void_p)
        bind(self.lib,'XStringToKeysym',C.c_ulong,C.c_char_p)
        bind(self.lib,'XKeysymToKeycode',C.c_uint,C.c_void_p,C.c_ulong)
        bind(self.test,'XTestFakeMotionEvent',C.c_int,C.c_void_p,C.c_int,C.c_int,C.c_int,C.c_ulong)
        bind(self.test,'XTestFakeButtonEvent',C.c_int,C.c_void_p,C.c_uint,C.c_int,C.c_ulong)
        bind(self.test,'XTestFakeKeyEvent',C.c_int,C.c_void_p,C.c_uint,C.c_int,C.c_ulong)
        self.authority=Path(root)/'display.auth';self.log=(Path(root)/'display.log').open('wb')
        # FamilyWild avoids hostname/container alias differences. File is private,
        # cookie is random per worker and never returned in HTTP responses.
        cookie=secrets.token_bytes(16)
        def field(value):return struct.pack('>H',len(value))+value
        tcp=os.getenv('MTA_VST3_DISPLAY_TEST_TCP')=='1'
        for _ in range(3):
            number=secrets.randbelow(4000)+100
            self.authority.write_bytes(struct.pack('>H',65535)+field(b'')+field(str(number).encode())+field(b'MIT-MAGIC-COOKIE-1')+field(cookie));self.authority.chmod(0o600)
            name=f'127.0.0.1:{number}' if tcp else f':{number}'
            env={**os.environ,'XAUTHORITY':str(self.authority),'DISPLAY':name}
            args=[executable(),f':{number}','-screen','0',f'{self.width}x{self.height}x24','-auth',str(self.authority),'-nolisten','unix' if tcp else 'tcp','-noreset','-extension','MIT-SHM']
            if tcp:args+=['-listen','tcp']
            self.proc=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log,env=env)
            os.environ['XAUTHORITY']=str(self.authority);os.environ['DISPLAY']=name
            until=time.monotonic()+3
            while time.monotonic()<until and self.proc.poll() is None:
                self.display=self.lib.XOpenDisplay(name.encode())
                if self.display:break
                time.sleep(.03)
            if self.display:break
            if self.proc.poll() is None:self.proc.terminate();self.proc.wait(timeout=2)
        if not self.display:
            self.close();raise RuntimeError('The private plugin display could not start')
        self.root=self.lib.XDefaultRootWindow(self.display)
        bind(self.lib,'XInternAtom',C.c_ulong,C.c_void_p,C.c_char_p,C.c_int)
        # No window manager is needed for the single editor, but JUCE and other
        # toolkits look up these standard WM atoms with only_if_exists=True.
        for atom in ('WM_PROTOCOLS','WM_TAKE_FOCUS','WM_DELETE_WINDOW','WM_CHANGE_STATE','WM_STATE','_NET_WM_PING','_NET_WM_WINDOW_TYPE','_NET_WM_WINDOW_TYPE_NORMAL','_NET_WM_WINDOW_TYPE_COMBO','_NET_WM_STATE','_NET_WM_STATE_HIDDEN','_NET_WM_STATE_FULLSCREEN','_NET_FRAME_EXTENTS','_NET_WM_ALLOWED_ACTIONS','_MOTIF_WM_HINTS'):
            self.lib.XInternAtom(self.display,atom.encode(),0)
        self.lib.XFlush(self.display)

    def frame(self):
        from PIL import Image as PILImage
        import io
        with self.lock:
            if time.monotonic()-self.last<.06:raise ValueError('Editor frame rate exceeded')
            self.last=time.monotonic()
            pointer=self.lib.XGetImage(self.display,self.root,0,0,self.width,self.height,C.c_ulong(-1).value,2)
            if not pointer:raise RuntimeError('Cannot capture plugin editor')
            try:
                img=pointer.contents
                if img.bits_per_pixel!=32 or (img.red_mask,img.green_mask,img.blue_mask)!=(0xff0000,0xff00,0xff) or img.byte_order!=0:raise RuntimeError('Unsupported private display pixel format')
                pixels=C.string_at(img.data,img.bytes_per_line*img.height)
                frame=PILImage.frombytes('RGB',(img.width,img.height),pixels,'raw','BGRX',img.bytes_per_line,1)
                bounds=frame.getbbox()
                if bounds:frame=frame.crop((0,0,min(self.width,bounds[2]+8),min(self.height,bounds[3]+8)))
                buffer=io.BytesIO();frame.save(buffer,format='JPEG',quality=82);return buffer.getvalue()
            finally:self.lib.XDestroyImage(pointer)

    def input(self,events):
        if not isinstance(events,list) or len(events)>64:raise ValueError('Invalid editor input batch')
        with self.lock:
            for e in events:
                if not isinstance(e,dict):raise ValueError('Invalid editor input')
                kind=e.get('type')
                if kind=='move':
                    x,y=e.get('x'),e.get('y')
                    if type(x) is not int or type(y) is not int or not 0<=x<self.width or not 0<=y<self.height:raise ValueError('Invalid editor coordinates')
                    self.test.XTestFakeMotionEvent(self.display,-1,x,y,0)
                elif kind=='button':
                    button=e.get('button');down=e.get('down')
                    if type(button) is not int or not 1<=button<=7 or type(down) is not bool:raise ValueError('Invalid editor button')
                    self.test.XTestFakeButtonEvent(self.display,button,int(down),0)
                    (self.buttons.add if down else self.buttons.discard)(button)
                elif kind=='key':
                    key=e.get('key');down=e.get('down')
                    names={'Enter':'Return','Escape':'Escape','Backspace':'BackSpace','Delete':'Delete','Tab':'Tab','ArrowLeft':'Left','ArrowRight':'Right','ArrowUp':'Up','ArrowDown':'Down','Home':'Home','End':'End','Shift':'Shift_L','Control':'Control_L','Alt':'Alt_L',' ':'space','.' :'period',',':'comma','-':'minus','+':'plus','=':'equal','/':'slash','\\':'backslash',';':'semicolon',':':'colon','[':'bracketleft',']':'bracketright','(':'parenleft',')':'parenright','_':'underscore','@':'at','#':'numbersign','%':'percent','&':'ampersand','!':'exclam','?':'question'}
                    if not isinstance(key,str) or not (key in names or (len(key)==1 and key.isascii() and key.isprintable())) or type(down) is not bool:raise ValueError('Unsupported editor key')
                    code=self.lib.XKeysymToKeycode(self.display,self.lib.XStringToKeysym(names.get(key,key).encode()))
                    if not code:continue
                    self.test.XTestFakeKeyEvent(self.display,code,int(down),0);(self.keys.add if down else self.keys.discard)(code)
                elif kind=='release':self.release()
                else:raise ValueError('Unsupported editor input')
            self.lib.XFlush(self.display)

    def release(self):
        for b in self.buttons:self.test.XTestFakeButtonEvent(self.display,b,0,0)
        for k in self.keys:self.test.XTestFakeKeyEvent(self.display,k,0,0)
        self.buttons.clear();self.keys.clear();self.lib.XFlush(self.display)

    def close(self):
        if self.display:
            self.release();self.lib.XCloseDisplay(self.display);self.display=None
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:self.proc.kill();self.proc.wait(timeout=2)
        if hasattr(self,'log'):self.log.close()
