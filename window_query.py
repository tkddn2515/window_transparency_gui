"""Read-only queries about the windows currently open on the desktop."""

import ctypes
from typing import Iterable, NamedTuple

import winapi


class WindowInfo(NamedTuple):
    """A visible top-level window. Immutable snapshot taken at enumeration time."""

    hwnd: int
    title: str


def get_title(hwnd: int) -> str:
    """Return the caption of ``hwnd``, or an empty string when unavailable."""
    if not exists(hwnd):
        return ""
    length = winapi.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buffer = ctypes.create_unicode_buffer(length + 1)
    winapi.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def exists(hwnd: int) -> bool:
    """True when ``hwnd`` still refers to a live window."""
    return bool(hwnd) and bool(winapi.IsWindow(hwnd))


def is_topmost(hwnd: int) -> bool:
    """True when the window carries the WS_EX_TOPMOST extended style."""
    if not exists(hwnd):
        return False
    ex_style = winapi.GetWindowLong(hwnd, winapi.GWL_EXSTYLE)
    return bool(ex_style & winapi.WS_EX_TOPMOST)


def enumerate_visible_windows() -> tuple[WindowInfo, ...]:
    """Return every titled, visible top-level window, front-most first.

    ``EnumWindows`` walks the desktop in z-order, so the resulting order is also
    the current stacking order — which is what the pin keeper compares against.
    """
    found = []

    def _collect(hwnd: int, _lparam: int) -> bool:
        if winapi.IsWindowVisible(hwnd):
            title = get_title(hwnd)
            if title:
                found.append(WindowInfo(hwnd=hwnd, title=title))
        return True

    winapi.EnumWindows(winapi.EnumWindowsProc(_collect), 0)
    return tuple(found)


def zorder_of(hwnds: Iterable[int]) -> tuple[int, ...]:
    """Return the given handles ordered front-most first, dropping dead ones.

    Handles that are alive but no longer enumerable (hidden, for example) are
    appended at the end so callers never silently lose track of them.
    """
    wanted = tuple(hwnds)
    if not wanted:
        return ()
    ranked = [info.hwnd for info in enumerate_visible_windows() if info.hwnd in wanted]
    missing = [hwnd for hwnd in wanted if hwnd not in ranked and exists(hwnd)]
    return tuple(ranked + missing)
