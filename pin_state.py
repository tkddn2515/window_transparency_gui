"""Remember pinned windows between runs.

A normal exit releases every pin, so this file only matters when the
controller dies without running its shutdown path - killed from Task Manager,
a closed console, a crash.  Without it those windows stay stuck on top with no
way to see or undo them in the app.
"""

import json
import os
import tempfile
from typing import Sequence

from pin_order import MAX_PINNED_WINDOWS, PinnedWindow

APP_DIR_NAME = "WindowTransparencyGUI"
STATE_FILE_NAME = "pins.json"


def state_path() -> str:
    """Where the pin list is remembered between runs."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, APP_DIR_NAME, STATE_FILE_NAME)


def save(pins: Sequence[PinnedWindow]) -> None:
    """Write the pin list. Best effort: a failure here must not break pinning."""
    if not pins:
        clear()
        return

    payload = [{"hwnd": pin.hwnd, "title": pin.title} for pin in pins]
    path = state_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        handle, temp_path = tempfile.mkstemp(dir=os.path.dirname(path))
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False)
        os.replace(temp_path, path)
    except OSError:
        pass


def load() -> tuple[PinnedWindow, ...]:
    """Read the remembered pin list, ignoring anything malformed."""
    try:
        with open(state_path(), encoding="utf-8") as stream:
            payload = json.load(stream)
    except (OSError, ValueError):
        return ()

    if not isinstance(payload, list):
        return ()

    restored = []
    for entry in payload[:MAX_PINNED_WINDOWS]:
        pin = _as_pin(entry)
        if pin is not None:
            restored.append(pin)
    return tuple(restored)


def clear() -> None:
    """Forget the remembered pin list."""
    try:
        os.remove(state_path())
    except OSError:
        pass


def _as_pin(entry: object) -> PinnedWindow | None:
    """Validate one stored entry; return None when it cannot be trusted."""
    if not isinstance(entry, dict):
        return None
    hwnd = entry.get("hwnd")
    title = entry.get("title")
    if not isinstance(hwnd, int) or isinstance(hwnd, bool) or hwnd <= 0:
        return None
    if not isinstance(title, str):
        return None
    return PinnedWindow(hwnd=hwnd, title=title)
