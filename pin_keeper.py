"""Keeps the desktop's always-on-top stack matching the user's pinned order.

:class:`PinKeeper` owns an immutable tuple of :class:`~pin_order.PinnedWindow`
entries and replaces it wholesale on every change.  All Win32 access goes
through an injected backend so the coordination logic can be tested with a fake
desktop.
"""

from typing import Callable, Iterable, NamedTuple, Optional, Sequence

import pin_order
from pin_order import PinError, PinnedWindow


class SyncReport(NamedTuple):
    """What a single :meth:`PinKeeper.sync` pass had to do."""

    dropped: tuple[PinnedWindow, ...] = ()
    reordered: bool = False
    failures: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.dropped) or self.reordered or bool(self.failures)


class Win32PinBackend:
    """The real desktop. Thin adapter over :mod:`topmost` and :mod:`window_query`."""

    def __init__(self) -> None:
        import topmost
        import window_query

        self._topmost = topmost
        self._query = window_query

    def exists(self, hwnd: int) -> bool:
        return self._query.exists(hwnd)

    def is_topmost(self, hwnd: int) -> bool:
        return self._query.is_topmost(hwnd)

    def title_of(self, hwnd: int) -> str:
        return self._query.get_title(hwnd)

    def zorder(self, hwnds: Iterable[int]) -> tuple[int, ...]:
        return self._query.zorder_of(hwnds)

    def pin(self, hwnd: int) -> None:
        self._topmost.bring_to_topmost_front(hwnd)

    def unpin(self, hwnd: int) -> None:
        self._topmost.clear_topmost(hwnd)

    def apply_order(self, pins: Sequence[PinnedWindow]) -> tuple[str, ...]:
        return self._topmost.apply_order(pins)


class PinKeeper:
    """Pin windows on top and hold them in a fixed order relative to each other."""

    def __init__(self, backend: Optional[object] = None) -> None:
        self._backend = backend if backend is not None else Win32PinBackend()
        self._pins = ()

    @property
    def pins(self) -> tuple[PinnedWindow, ...]:
        """The current pinned windows, front-most first (immutable)."""
        return self._pins

    def index_of(self, hwnd: int) -> int:
        return pin_order.index_of(self._pins, hwnd)

    def is_pinned(self, hwnd: int) -> bool:
        return pin_order.is_pinned(self._pins, hwnd)

    def pin(self, hwnd: int, title: str) -> tuple[str, ...]:
        """Pin ``hwnd`` at the back of the pinned stack and enforce the order."""
        pin_order.validate_handle(hwnd)
        if not self._backend.exists(hwnd):
            raise PinError("That window no longer exists. Refresh the list.")

        candidate = pin_order.with_pin(self._pins, hwnd, title)
        try:
            self._backend.pin(hwnd)
        except Exception as error:  # leave the pin list untouched on refusal
            raise PinError(str(error)) from error

        self._pins = candidate
        return self._enforce_order()

    def unpin(self, hwnd: int) -> tuple[str, ...]:
        """Release ``hwnd`` back to the normal window band."""
        if not pin_order.is_pinned(self._pins, hwnd):
            return ()
        self._pins = pin_order.without_pin(self._pins, hwnd)
        failures = ()
        if self._backend.exists(hwnd):
            failures = self._collect_failure(hwnd, self._backend.unpin)
        return failures + self._enforce_order()

    def unpin_all(self) -> tuple[str, ...]:
        """Release every pinned window."""
        failures = ()
        for pin in self._pins:
            if self._backend.exists(pin.hwnd):
                failures += self._collect_failure(pin.hwnd, self._backend.unpin)
        self._pins = ()
        return failures

    def move(self, index: int, offset: int) -> tuple[int, tuple[str, ...]]:
        """Shift the pin at ``index`` by ``offset`` layers and re-apply the order.

        Returns the pin's new index, or -1 when the move was out of range.
        """
        reordered = pin_order.moved(self._pins, index, offset)
        if reordered == self._pins:
            return -1, ()
        self._pins = reordered
        return index + offset, self._enforce_order()

    def sync(self) -> SyncReport:
        """Drop dead windows, refresh titles, and restore the order if it slipped.

        Called on a timer: anything that stole the top spot (another app going
        always-on-top, a window being re-shown) is corrected here.
        """
        alive = pin_order.retained(self._pins, self._backend.exists)
        dropped = tuple(pin for pin in self._pins if pin not in alive)

        for pin in alive:
            title = self._backend.title_of(pin.hwnd)
            if title and title != pin.title:
                alive = pin_order.with_title(alive, pin.hwnd, title)

        self._pins = alive
        if not alive or self._order_holds():
            return SyncReport(dropped=dropped)
        return SyncReport(dropped=dropped, reordered=True, failures=self._enforce_order())

    def _order_holds(self) -> bool:
        if not all(self._backend.is_topmost(pin.hwnd) for pin in self._pins):
            return False
        live_order = self._backend.zorder(pin_order.handles(self._pins))
        return pin_order.matches_zorder(self._pins, live_order)

    def _enforce_order(self) -> tuple[str, ...]:
        if not self._pins:
            return ()
        return tuple(self._backend.apply_order(self._pins))

    @staticmethod
    def _collect_failure(hwnd: int, action: Callable[[int], None]) -> tuple[str, ...]:
        """Run ``action`` and turn any failure into a user-facing message."""
        try:
            action(hwnd)
        except Exception as error:  # surfaced to the user, never swallowed
            return (str(error),)
        return ()
