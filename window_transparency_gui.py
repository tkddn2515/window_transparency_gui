"""Tkinter front end: control per-window transparency and always-on-top order."""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Sequence

import pin_order
import transparency
import window_query
from pin_drag import ListboxDragReorder
from pin_keeper import PinKeeper
from pin_order import PinError, PinnedWindow
from topmost import WindowOperationError

DEFAULT_ALPHA_PERCENT = 85
SYNC_INTERVAL_MS = 1000
OWN_WINDOW_RETRY_MS = 100
OWN_WINDOW_MAX_TRIES = 30
WINDOW_GEOMETRY = "520x680"


class WindowTransparencyApp:
    """Wires the widgets to :mod:`transparency` and :class:`PinKeeper`."""

    def __init__(self, root: tk.Tk, keeper: Optional[PinKeeper] = None) -> None:
        self.root = root
        self.root.title("Window Transparency & Always-on-Top Controller")
        self.root.geometry(WINDOW_GEOMETRY)
        self.root.minsize(420, 560)

        self.open_windows = ()
        self.keeper = keeper if keeper is not None else PinKeeper()
        self._sync_job = None

        main_frame = ttk.Frame(root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self._build_window_list(main_frame)
        self._build_transparency_controls(main_frame)
        self._build_pin_controls(main_frame)

        self.status_var = tk.StringVar(value="Ready. Please refresh the list.")
        self.status_bar = ttk.Label(
            root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W, padding=5
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.refresh_pin_list()
        self.refresh_window_list()
        self.root.after_idle(self._adopt_own_window)
        self._schedule_sync()

    # --- Layout -----------------------------------------------------------

    def _build_window_list(self, parent: ttk.Frame) -> None:
        list_frame = ttk.LabelFrame(parent, text="Open Windows")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, height=8)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(
            list_frame, orient=tk.VERTICAL, command=self.listbox.yview
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.config(yscrollcommand=scrollbar.set)

        controls_frame = ttk.Frame(parent)
        controls_frame.pack(fill=tk.X, pady=5)
        ttk.Button(
            controls_frame, text="Refresh List", command=self.refresh_window_list
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _build_transparency_controls(self, parent: ttk.Frame) -> None:
        slider_frame = ttk.LabelFrame(
            parent, text="Transparency Level (0% = Invisible, 100% = Opaque)"
        )
        slider_frame.pack(fill=tk.X, pady=5)

        self.alpha_var = tk.IntVar(value=DEFAULT_ALPHA_PERCENT)
        self.slider = ttk.Scale(
            slider_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.alpha_var,
            command=self.update_slider_label,
        )
        self.slider.pack(fill=tk.X, expand=True, padx=5, pady=(5, 0))

        self.slider_label = ttk.Label(slider_frame, text=f"{DEFAULT_ALPHA_PERCENT}%")
        self.slider_label.pack()

        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, pady=5)
        ttk.Button(
            action_frame, text="Apply Transparency", command=self.apply_transparency
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(
            action_frame, text="Reset Transparency", command=self.reset_transparency
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)

    def _build_pin_controls(self, parent: ttk.Frame) -> None:
        pin_frame = ttk.LabelFrame(
            parent,
            text="Always on Top (drag to reorder — the top row stays in front)",
        )
        pin_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        pin_body = ttk.Frame(pin_frame)
        pin_body.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.pin_listbox = tk.Listbox(pin_body, selectmode=tk.SINGLE, height=6)
        self.pin_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        pin_scroll = ttk.Scrollbar(
            pin_body, orient=tk.VERTICAL, command=self.pin_listbox.yview
        )
        pin_scroll.pack(side=tk.LEFT, fill=tk.Y)
        self.pin_listbox.config(yscrollcommand=pin_scroll.set)

        self.pin_drag = ListboxDragReorder(
            self.pin_listbox,
            row_count=lambda: len(self.keeper.pins),
            on_preview=self.preview_pin_order,
            on_drop=self.drop_pin,
        )

        order_frame = ttk.Frame(pin_body)
        order_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        ttk.Button(order_frame, text="▲ Up", width=8, command=self.move_pin_up).pack(
            pady=(0, 3)
        )
        ttk.Button(order_frame, text="▼ Down", width=8, command=self.move_pin_down).pack()

        pin_actions = ttk.Frame(pin_frame)
        pin_actions.pack(fill=tk.X, padx=5, pady=(0, 5))
        ttk.Button(
            pin_actions, text="Pin Selected", command=self.pin_selected
        ).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(pin_actions, text="Unpin", command=self.unpin_selected).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5)
        )
        ttk.Button(pin_actions, text="Unpin All", command=self.unpin_all).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        self.lock_order_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            pin_frame,
            text="Keep this order locked (re-apply automatically every second)",
            variable=self.lock_order_var,
        ).pack(anchor=tk.W, padx=5, pady=(0, 2))

        self.stay_in_front_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            pin_frame,
            text="Keep this controller in front of pinned windows",
            variable=self.stay_in_front_var,
            command=self.toggle_stay_in_front,
        ).pack(anchor=tk.W, padx=5, pady=(0, 5))

    # --- Window list ------------------------------------------------------

    def update_slider_label(self, value: str) -> None:
        self.slider_label.config(text=f"{int(float(value))}%")

    def refresh_window_list(self) -> None:
        self.status_var.set("Refreshing window list...")
        self.listbox.delete(0, tk.END)
        self.open_windows = window_query.enumerate_visible_windows()

        if not self.open_windows:
            self.listbox.insert(tk.END, "No windows found.")
            self.status_var.set("No windows found.")
            return

        for info in self.open_windows:
            marker = "📌 " if self.keeper.is_pinned(info.hwnd) else ""
            self.listbox.insert(tk.END, f"{marker}{info.title}")
        self.status_var.set(f"Found {len(self.open_windows)} window(s). Select one.")

    def get_selected_window(self) -> Optional[window_query.WindowInfo]:
        """Return the highlighted :class:`WindowInfo`, or None after warning."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a window from the list."
            )
            return None

        index = selection[0]
        if index >= len(self.open_windows):
            messagebox.showerror("Error", "Invalid selection. Please refresh the list.")
            return None
        return self.open_windows[index]

    def get_selected_hwnd(self) -> Optional[int]:
        info = self.get_selected_window()
        return info.hwnd if info else None

    # --- Transparency -----------------------------------------------------

    def apply_transparency(self) -> None:
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return

        percent = self.alpha_var.get()
        try:
            transparency.apply(hwnd, percent)
            self.status_var.set(f"Applied {percent}% transparency to the window.")
        except WindowOperationError as error:
            self._report_error("Could not apply transparency.", error)

    def reset_transparency(self) -> None:
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return

        try:
            transparency.reset(hwnd)
            self.status_var.set("Transparency has been reset for the window.")
        except WindowOperationError as error:
            self._report_error("Could not reset transparency.", error)

    # --- Pinning ----------------------------------------------------------

    def pin_selected(self) -> None:
        info = self.get_selected_window()
        if not info:
            return
        if self.keeper.is_pinned(info.hwnd):
            self.status_var.set(f'"{info.title}" is already pinned.')
            return
        if info.hwnd == self.keeper.owner_hwnd and self.keeper.keep_owner_front:
            self.status_var.set(
                "This controller is already kept in front of pinned windows."
            )
            return

        try:
            failures = self.keeper.pin(info.hwnd, info.title)
        except PinError as error:
            self._report_error("Could not pin the window.", error)
            return

        self.refresh_pin_list()
        self.refresh_window_list()
        self._report_failures(
            failures, f'Pinned "{info.title}" at layer {len(self.keeper.pins)}.'
        )

    def unpin_selected(self) -> None:
        pin = self._selected_pin()
        if not pin:
            return

        failures = self.keeper.unpin(pin.hwnd)
        self.refresh_pin_list()
        self.refresh_window_list()
        self._report_failures(failures, f'Unpinned "{pin.title}".')

    def unpin_all(self) -> None:
        if not self.keeper.pins:
            self.status_var.set("Nothing is pinned.")
            return

        failures = self.keeper.unpin_all()
        self.refresh_pin_list()
        self.refresh_window_list()
        self._report_failures(failures, "All windows have been unpinned.")

    def move_pin_up(self) -> None:
        self._move_pin(-1)

    def move_pin_down(self) -> None:
        self._move_pin(1)

    def _move_pin(self, offset: int) -> None:
        selection = self.pin_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a pinned window to reorder."
            )
            return

        new_index, failures = self.keeper.move(selection[0], offset)
        if new_index < 0:
            self.status_var.set("That window is already at the end of the order.")
            return

        self.refresh_pin_list(select_index=new_index)
        self.pin_listbox.see(new_index)
        self._report_failures(failures, f"Moved to layer {new_index + 1}.")

    def _selected_pin(self) -> Optional[PinnedWindow]:
        selection = self.pin_listbox.curselection()
        if not selection:
            messagebox.showwarning(
                "No Selection", "Please select a window from the pinned list."
            )
            return None

        index = selection[0]
        pins = self.keeper.pins
        if index >= len(pins):
            self.refresh_pin_list()
            return None
        return pins[index]

    def _adopt_own_window(self, attempt: int = 1) -> None:
        """Hand our own window to the keeper so it can be held in front.

        Pinned windows are always-on-top; without this the controller sits in
        the normal band and every pinned window covers it for good.  Tk hands
        out a child handle until the frame Windows actually stacks exists, so
        this retries until the two differ.
        """
        widget_id = self.root.winfo_id()
        hwnd = window_query.root_window_of(widget_id)
        if hwnd == widget_id:
            if attempt < OWN_WINDOW_MAX_TRIES:
                self.root.after(
                    OWN_WINDOW_RETRY_MS,
                    lambda: self._adopt_own_window(attempt + 1),
                )
                return
            self.status_var.set(
                "Could not identify this window; pinned windows may cover it."
            )
            return

        failures = self.keeper.set_owner(hwnd)
        if failures:
            self.status_var.set(failures[0])

    def toggle_stay_in_front(self) -> None:
        """Apply the \"keep this controller in front\" checkbox."""
        enabled = self.stay_in_front_var.get()
        failures = self.keeper.set_keep_owner_front(enabled)
        message = (
            "This window will stay in front of pinned windows."
            if enabled
            else "This window no longer stays in front; pinned windows may cover it."
        )
        self._report_failures(failures, message)

    def preview_pin_order(self, start: int, current: int) -> None:
        """Show how the list would look mid-drag, without touching any window."""
        previewed = pin_order.moved(self.keeper.pins, start, current - start)
        self._render_pin_rows(previewed, select_index=current)

    def drop_pin(self, start: int, end: int) -> None:
        """Commit a finished drag: restack the windows once, then redraw."""
        new_index, failures = self.keeper.move(start, end - start)
        if new_index < 0:
            self.refresh_pin_list(select_index=start)
            return

        self.refresh_pin_list(select_index=new_index)
        self.pin_listbox.see(new_index)
        self._report_failures(failures, f"Moved to layer {new_index + 1}.")

    def refresh_pin_list(self, select_index: Optional[int] = None) -> None:
        """Redraw the pinned list from the keeper, front-most layer first."""
        self._render_pin_rows(self.keeper.pins, select_index=select_index)

    def _render_pin_rows(
        self, pins: Sequence[PinnedWindow], select_index: Optional[int] = None
    ) -> None:
        """Draw ``pins`` as numbered rows.

        Passing ``select_index`` highlights that row; otherwise the previous
        selection is restored when it still exists.
        """
        previous = self.pin_listbox.curselection()
        wanted = select_index if select_index is not None else (
            previous[0] if previous else None
        )
        self.pin_listbox.delete(0, tk.END)

        if not pins:
            self.pin_listbox.insert(tk.END, "Nothing pinned yet.")
            return

        for layer, pin in enumerate(pins, start=1):
            self.pin_listbox.insert(tk.END, f"{layer}. {pin.title}")
        if wanted is not None and 0 <= wanted < len(pins):
            self.pin_listbox.selection_clear(0, tk.END)
            self.pin_listbox.selection_set(wanted)

    # --- Order enforcement ------------------------------------------------

    def _schedule_sync(self) -> None:
        self._sync_job = self.root.after(SYNC_INTERVAL_MS, self._sync_tick)

    def _sync_tick(self) -> None:
        """Re-assert the pinned order on a timer, then reschedule."""
        try:
            if self.pin_drag.is_dragging:
                return  # never rebuild the list while the user is dragging
            if self.keeper.pins and self.lock_order_var.get():
                report = self.keeper.sync()
                if report.dropped:
                    self.refresh_pin_list()
                    closed = ", ".join(f'"{pin.title}"' for pin in report.dropped)
                    self.status_var.set(f"Removed closed window(s) from pins: {closed}.")
                elif report.failures:
                    self.status_var.set(report.failures[0])
            else:
                self.keeper.raise_owner()
        except Exception as error:  # a timer must never kill the event loop
            self.status_var.set(f"Order lock paused: {error}")
        finally:
            self._schedule_sync()

    # --- Shutdown / messaging --------------------------------------------

    def on_close(self) -> None:
        """Release every pinned window so nothing is left stuck on top."""
        if self._sync_job is not None:
            self.root.after_cancel(self._sync_job)
            self._sync_job = None
        try:
            self.keeper.unpin_all()
        except Exception:
            pass  # closing must not be blocked by a protected window
        self.root.destroy()

    def _report_error(self, headline: str, error: Exception) -> None:
        self.status_var.set(f"{headline} {error}")
        messagebox.showerror("Error", f"{headline}\n\n{error}")

    def _report_failures(self, failures: Sequence[str], success_message: str) -> None:
        if not failures:
            self.status_var.set(success_message)
            return
        detail = "\n".join(failures)
        self.status_var.set(failures[0])
        messagebox.showwarning("Some windows could not be changed", detail)


def main() -> None:
    root = tk.Tk()
    WindowTransparencyApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
