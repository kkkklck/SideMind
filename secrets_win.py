"""Windows DPAPI: store only encrypted API keys for the current Windows user."""
import base64
import ctypes as C
from ctypes import wintypes as W

class Blob(C.Structure):
    _fields_=[("cbData",W.DWORD),("pbData",C.POINTER(C.c_ubyte))]

def transform(data, decrypt=False):
    src=C.create_string_buffer(data)
    incoming=Blob(len(data),C.cast(src,C.POINTER(C.c_ubyte)))
    out=Blob()
    crypt=C.windll.crypt32
    func=crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    func.argtypes=[C.POINTER(Blob),C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,W.DWORD,C.POINTER(Blob)]
    func.restype=W.BOOL
    if not func(C.byref(incoming),None,None,None,None,1,C.byref(out)):
        raise OSError("Windows API Key 加密/解密失败")
    try:
        return C.string_at(out.pbData,out.cbData)
    finally:
        free=C.windll.kernel32.LocalFree
        free.argtypes=[C.c_void_p]
        free.restype=C.c_void_p
        free(C.cast(out.pbData,C.c_void_p))

def protect(key):
    return base64.b64encode(transform(key.encode("utf-8"))).decode("ascii") if key else ""

def unprotect(value):
    return transform(base64.b64decode(value),True).decode("utf-8") if value else ""
