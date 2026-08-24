"""Drag-to-reorder behaviour for a ``tk.Listbox``.

The widget only previews the new arrangement while the mouse is down; the move
is committed once on release through the injected ``on_drop`` callback, so an
expensive commit (re-stacking real windows) happens a single time per drag
instead of on every mouse motion.
"""

import tkinter as tk
from typing import Callable, Optional

AUTOSCROLL_UNITS = 1


class ListboxDragReorder:
    """Bind press/motion/release on ``listbox`` to a reorder gesture.

    ``row_count`` reports how many real rows exist (placeholder text counts as
    zero), ``on_preview(start, current)`` redraws the list as it would look if
    the row were dropped now, and ``on_drop(start, end)`` applies the move.
    """

    def __init__(
        self,
        listbox: tk.Listbox,
        row_count: Callable[[], int],
        on_preview: Callable[[int, int], None],
        on_drop: Callable[[int, int], None],
    ) -> None:
        self._listbox = listbox
        self._row_count = row_count
        self._on_preview = on_preview
        self._on_drop = on_drop
        self._start: Optional[int] = None
        self._current: Optional[int] = None

        listbox.bind("<Button-1>", self._on_press, add="+")
        listbox.bind("<B1-Motion>", self._on_motion, add="+")
        listbox.bind("<ButtonRelease-1>", self._on_release, add="+")

    @property
    def is_dragging(self) -> bool:
        """True between pressing a real row and releasing the button."""
        return self._start is not None

    def cancel(self) -> None:
        """Abandon the gesture, e.g. when the list is rebuilt underneath it."""
        self._start = None
        self._current = None
        self._listbox.config(cursor="")

    # --- internals --------------------------------------------------------

    def _row_at(self, y: int) -> int:
        """Return the row nearest to ``y``, clamped to the real rows, or -1."""
        count = self._row_count()
        if count <= 0:
            return -1
        return max(0, min(self._listbox.nearest(y), count - 1))

    def _autoscroll(self, y: int) -> None:
        """Scroll the list when the pointer is dragged past its edges."""
        if y < 0:
            self._listbox.yview_scroll(-AUTOSCROLL_UNITS, "units")
        elif y > self._listbox.winfo_height():
            self._listbox.yview_scroll(AUTOSCROLL_UNITS, "units")

    def _on_press(self, event: tk.Event) -> None:
        row = self._row_at(event.y)
        if row < 0:
            self.cancel()
            return
        self._start = row
        self._current = row
        self._listbox.config(cursor="fleur")

    def _on_motion(self, event: tk.Event) -> None:
        if self._start is None:
            return
        self._autoscroll(event.y)
        row = self._row_at(event.y)
        if row < 0 or row == self._current:
            return
        self._current = row
        self._on_preview(self._start, row)

    def _on_release(self, event: tk.Event) -> None:
        if self._start is None:
            return
        start, end = self._start, self._current
        self.cancel()
        if end is not None and end != start:
            self._on_drop(start, end)
