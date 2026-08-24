"""Low-level Windows API bindings used by the transparency controller.

This module holds nothing but constants and ``ctypes`` prototypes so that the
rest of the application can stay free of raw Win32 details.  Every prototype
declares ``argtypes``/``restype`` explicitly: without them ``ctypes`` narrows
Python integers to a 32-bit C ``int``, which silently truncates 64-bit window
handles.
"""

import ctypes
from ctypes import wintypes

# --- Window style constants ---
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TOPMOST = 0x00000008

# --- Layered window (transparency) constants ---
LWA_ALPHA = 0x00000002
OPAQUE_ALPHA = 255

# --- RedrawWindow constants ---
RDW_INVALIDATE = 0x0001
RDW_ERASE = 0x0004
RDW_ALLCHILDREN = 0x0080
RDW_FRAME = 0x0400
RDW_FULL_REFRESH = RDW_ERASE | RDW_INVALIDATE | RDW_FRAME | RDW_ALLCHILDREN

# --- GetAncestor constants ---
GA_ROOT = 2

# --- SetWindowPos constants ---
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_NOOWNERZORDER = 0x0200
SWP_ZORDER_ONLY = SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_NOOWNERZORDER

user32 = ctypes.WinDLL("user32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

EnumWindows = user32.EnumWindows
EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
EnumWindows.restype = wintypes.BOOL

IsWindow = user32.IsWindow
IsWindow.argtypes = [wintypes.HWND]
IsWindow.restype = wintypes.BOOL

IsWindowVisible = user32.IsWindowVisible
IsWindowVisible.argtypes = [wintypes.HWND]
IsWindowVisible.restype = wintypes.BOOL

GetWindowTextW = user32.GetWindowTextW
GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
GetWindowTextW.restype = ctypes.c_int

GetWindowTextLengthW = user32.GetWindowTextLengthW
GetWindowTextLengthW.argtypes = [wintypes.HWND]
GetWindowTextLengthW.restype = ctypes.c_int

# GetWindowLongPtrW only exists in 64-bit user32; the 32-bit build exports the
# non-Ptr variant, which is equivalent there.
_get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
_set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)

GetWindowLong = _get_long
GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
GetWindowLong.restype = ctypes.c_ssize_t

SetWindowLong = _set_long
SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
SetWindowLong.restype = ctypes.c_ssize_t

SetLayeredWindowAttributes = user32.SetLayeredWindowAttributes
SetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    wintypes.COLORREF,
    ctypes.c_ubyte,
    wintypes.DWORD,
]
SetLayeredWindowAttributes.restype = wintypes.BOOL

GetAncestor = user32.GetAncestor
GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
GetAncestor.restype = wintypes.HWND

GetLayeredWindowAttributes = user32.GetLayeredWindowAttributes
GetLayeredWindowAttributes.argtypes = [
    wintypes.HWND,
    ctypes.POINTER(wintypes.COLORREF),
    ctypes.POINTER(ctypes.c_ubyte),
    ctypes.POINTER(wintypes.DWORD),
]
GetLayeredWindowAttributes.restype = wintypes.BOOL

SetWindowPos = user32.SetWindowPos
SetWindowPos.argtypes = [
    wintypes.HWND,
    wintypes.HWND,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.UINT,
]
SetWindowPos.restype = wintypes.BOOL

RedrawWindow = user32.RedrawWindow
RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.HANDLE, wintypes.UINT]
RedrawWindow.restype = wintypes.BOOL


def last_error_message(action: str) -> str:
    """Build a user-facing message for the calling thread's last Win32 error."""
    code = ctypes.get_last_error()
    if code == 0:
        return f"{action} failed for an unknown reason."
    detail = ctypes.FormatError(code).strip()
    return f"{action} failed (Windows error {code}: {detail})."
