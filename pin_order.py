"""Immutable ordering model for pinned ("always on top") windows.

Index 0 is the highest layer: it stays above every other pinned window.  All
functions here are pure — they return a brand new tuple and never touch the one
they were given — which keeps the Win32 side effects in :mod:`pin_keeper`
separate from the ordering rules, and makes those rules testable anywhere.
"""

from typing import Callable, Iterable, NamedTuple, Sequence

MAX_PINNED_WINDOWS = 32


class PinnedWindow(NamedTuple):
    """A window the user asked to keep on top, at a fixed layer."""

    hwnd: int
    title: str


class PinError(ValueError):
    """Raised when a pin request cannot be honoured. Message is user-facing."""


def validate_handle(hwnd: object) -> int:
    """Return ``hwnd`` as an int, rejecting anything that is not a usable handle."""
    if not isinstance(hwnd, int) or isinstance(hwnd, bool):
        raise PinError("The selected window has an invalid handle.")
    if hwnd <= 0:
        raise PinError("The selected window has an invalid handle.")
    return hwnd


def index_of(pins: Sequence[PinnedWindow], hwnd: int) -> int:
    """Return the position of ``hwnd`` in ``pins``, or -1 when it is not pinned."""
    for index, pin in enumerate(pins):
        if pin.hwnd == hwnd:
            return index
    return -1


def is_pinned(pins: Sequence[PinnedWindow], hwnd: int) -> bool:
    return index_of(pins, hwnd) >= 0


def handles(pins: Sequence[PinnedWindow]) -> tuple[int, ...]:
    """Return just the handles, front-most first."""
    return tuple(pin.hwnd for pin in pins)


def with_pin(
    pins: Sequence[PinnedWindow], hwnd: int, title: str
) -> tuple[PinnedWindow, ...]:
    """Return ``pins`` plus ``hwnd`` appended as the lowest pinned layer.

    Re-pinning an already pinned window keeps its layer and only refreshes the
    title, so a stale caption never reshuffles the user's chosen order.
    """
    validate_handle(hwnd)
    existing = index_of(pins, hwnd)
    if existing >= 0:
        return with_title(pins, hwnd, title)
    if len(pins) >= MAX_PINNED_WINDOWS:
        raise PinError(
            f"You can pin at most {MAX_PINNED_WINDOWS} windows. "
            "Unpin one before adding another."
        )
    return tuple(pins) + (PinnedWindow(hwnd=hwnd, title=title),)


def without_pin(pins: Sequence[PinnedWindow], hwnd: int) -> tuple[PinnedWindow, ...]:
    """Return ``pins`` with ``hwnd`` removed; unknown handles are a no-op."""
    return tuple(pin for pin in pins if pin.hwnd != hwnd)


def with_title(
    pins: Sequence[PinnedWindow], hwnd: int, title: str
) -> tuple[PinnedWindow, ...]:
    """Return ``pins`` with the caption of ``hwnd`` replaced, order untouched."""
    return tuple(
        pin._replace(title=title) if pin.hwnd == hwnd else pin for pin in pins
    )


def moved(
    pins: Sequence[PinnedWindow], index: int, offset: int
) -> tuple[PinnedWindow, ...]:
    """Return ``pins`` with the entry at ``index`` shifted by ``offset`` layers.

    Out-of-range requests (moving the top entry up, for instance) return the
    original ordering unchanged rather than raising, so the UI can bind the
    buttons unconditionally.
    """
    if index < 0 or index >= len(pins):
        return tuple(pins)
    target = index + offset
    if target < 0 or target >= len(pins):
        return tuple(pins)
    remaining = list(pins)
    moving = remaining.pop(index)
    remaining.insert(target, moving)
    return tuple(remaining)


def moved_up(pins: Sequence[PinnedWindow], index: int) -> tuple[PinnedWindow, ...]:
    """Raise the entry one layer (closer to the front)."""
    return moved(pins, index, -1)


def moved_down(pins: Sequence[PinnedWindow], index: int) -> tuple[PinnedWindow, ...]:
    """Lower the entry one layer (closer to the back)."""
    return moved(pins, index, 1)


def retained(
    pins: Sequence[PinnedWindow], keep: Callable[[int], bool]
) -> tuple[PinnedWindow, ...]:
    """Return only the pins for which ``keep(hwnd)`` is true (drops dead windows)."""
    return tuple(pin for pin in pins if keep(pin.hwnd))


def matches_zorder(
    pins: Sequence[PinnedWindow], actual_front_first: Iterable[int]
) -> bool:
    """True when the live stacking order already agrees with the pinned order.

    ``actual_front_first`` may contain unrelated windows; only pinned handles
    are compared, and any pinned window missing from it counts as a mismatch.
    """
    expected = handles(pins)
    actual = tuple(hwnd for hwnd in actual_front_first if hwnd in set(expected))
    return expected == actual
