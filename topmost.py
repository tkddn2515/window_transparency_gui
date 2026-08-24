"""Always-on-top (z-order) operations on foreign windows."""

from typing import Sequence

import winapi
from pin_order import PinnedWindow
from window_query import exists, is_topmost


class WindowOperationError(RuntimeError):
    """A Win32 call refused the requested change. Message is user-facing."""


def _set_zorder(hwnd: int, insert_after: int, action: str) -> None:
    if not exists(hwnd):
        raise WindowOperationError("That window no longer exists. Refresh the list.")
    ok = winapi.SetWindowPos(
        hwnd, insert_after, 0, 0, 0, 0, winapi.SWP_ZORDER_ONLY
    )
    if not ok:
        raise WindowOperationError(
            winapi.last_error_message(action)
            + " Windows blocks this for apps running as administrator unless"
            " this controller is elevated too."
        )


def bring_to_topmost_front(hwnd: int) -> None:
    """Make ``hwnd`` always-on-top and put it in front of every other such window."""
    _set_zorder(hwnd, winapi.HWND_TOPMOST, "Pinning the window to the top")


def clear_topmost(hwnd: int) -> None:
    """Return ``hwnd`` to the normal (non always-on-top) band."""
    _set_zorder(hwnd, winapi.HWND_NOTOPMOST, "Unpinning the window")


def apply_order(pins: Sequence[PinnedWindow]) -> tuple[str, ...]:
    """Re-assert the pinned stacking order, front-most entry first in ``pins``.

    Each call to :func:`bring_to_topmost_front` moves a window to the front of
    the always-on-top band, so walking the list back-to-front leaves index 0 on
    top.  Failures are collected as user-facing messages instead of aborting, so
    one protected window cannot stop the rest from being restored.
    """
    failures = []
    for pin in reversed(tuple(pins)):
        try:
            bring_to_topmost_front(pin.hwnd)
        except WindowOperationError as error:
            failures.append(f'"{pin.title}": {error}')
    return tuple(failures)


def all_topmost(pins: Sequence[PinnedWindow]) -> bool:
    """True when every pinned window still carries the always-on-top style."""
    return all(is_topmost(pin.hwnd) for pin in pins)
