"""Keeps the desktop's always-on-top stack matching the user's pinned order.

:class:`PinKeeper` owns an immutable tuple of :class:`~pin_order.PinnedWindow`
entries and replaces it wholesale on every change.  All Win32 access goes
through an injected backend so the coordination logic can be tested with a fake
desktop.
"""

from typing import Callable, Iterable, NamedTuple, Optional, Sequence

import pin_order
from pin_order import PinError, PinnedWindow

OWNER_LABEL = "(this controller)"


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

    def __init__(
        self, backend: Optional[object] = None, owner_hwnd: int = 0
    ) -> None:
        self._backend = backend if backend is not None else Win32PinBackend()
        self._pins = ()
        self._owner_hwnd = owner_hwnd

    @property
    def owner_hwnd(self) -> int:
        """The controller's own window, kept in front of the pinned ones."""
        return self._owner_hwnd

    def set_owner(self, hwnd: int) -> tuple[str, ...]:
        """Adopt ``hwnd`` as the controller window and put it in front."""
        self._owner_hwnd = hwnd
        return self._enforce_order()

    def raise_owner(self) -> tuple[str, ...]:
        """Bring the controller back in front, if it is not already there."""
        if not self._owner_front_active() or self._owner_is_in_front():
            return ()
        return self._collect_failure(self._owner_hwnd, self._backend.pin)

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

    def restore(self, pins: Sequence[PinnedWindow]) -> tuple[PinnedWindow, ...]:
        """Adopt windows a previous run left pinned, keeping their saved order.

        A window is taken back only while it still exists and is still
        always-on-top, so a handle that has been recycled by an ordinary window
        is never grabbed.  The title is refreshed rather than required to match:
        browsers, editors and terminals rename themselves constantly, and the
        window would otherwise stay stranded on top with nothing to undo it.
        """
        adopted = tuple(
            pin._replace(title=self._backend.title_of(pin.hwnd) or pin.title)
            for pin in pins[:pin_order.MAX_PINNED_WINDOWS]
            if pin.hwnd > 0
            and self._backend.exists(pin.hwnd)
            and self._backend.is_topmost(pin.hwnd)
        )
        if not adopted:
            return ()

        self._pins = adopted
        self._enforce_order()
        return adopted

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
        return failures + self._release_owner_if_idle()

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
        if self._order_holds():
            return SyncReport(dropped=dropped)
        return SyncReport(dropped=dropped, reordered=True, failures=self._enforce_order())

    def _front_sequence(self) -> tuple[PinnedWindow, ...]:
        """The stacking order to enforce, controller first when it is held up."""
        if not self._owner_front_active():
            return self._pins
        others = pin_order.without_pin(self._pins, self._owner_hwnd)
        owner = PinnedWindow(hwnd=self._owner_hwnd, title=OWNER_LABEL)
        return (owner,) + others

    def _owner_front_active(self) -> bool:
        """True while the controller has to stay above the pinned windows.

        Pinned windows are always-on-top, so a controller left in the normal
        band would be buried under them and could not be clicked at all.
        """
        return bool(
            self._pins
            and self._owner_hwnd
            and self._backend.exists(self._owner_hwnd)
        )

    def _release_owner_if_idle(self) -> tuple[str, ...]:
        """Drop the controller back to the normal band when it need not float.

        A window the user pinned explicitly is left alone, even when it is the
        controller itself.
        """
        if self._owner_front_active() or not self._owner_hwnd:
            return ()
        if pin_order.is_pinned(self._pins, self._owner_hwnd):
            return ()
        if not self._backend.exists(self._owner_hwnd):
            return ()
        if not self._backend.is_topmost(self._owner_hwnd):
            return ()
        return self._collect_failure(self._owner_hwnd, self._backend.unpin)

    def _owner_is_in_front(self) -> bool:
        if not self._backend.is_topmost(self._owner_hwnd):
            return False
        live = self._backend.zorder(pin_order.handles(self._front_sequence()))
        return bool(live) and live[0] == self._owner_hwnd

    def _order_holds(self) -> bool:
        sequence = self._front_sequence()
        if not sequence:
            return True
        if not all(self._backend.is_topmost(pin.hwnd) for pin in sequence):
            return False
        live_order = self._backend.zorder(pin_order.handles(sequence))
        return pin_order.matches_zorder(sequence, live_order)

    def _enforce_order(self) -> tuple[str, ...]:
        failures = self._release_owner_if_idle()
        sequence = self._front_sequence()
        if not sequence:
            return failures
        return failures + tuple(self._backend.apply_order(sequence))

    @staticmethod
    def _collect_failure(hwnd: int, action: Callable[[int], None]) -> tuple[str, ...]:
        """Run ``action`` and turn any failure into a user-facing message."""
        try:
            action(hwnd)
        except Exception as error:  # surfaced to the user, never swallowed
            return (str(error),)
        return ()
