"""Per-window transparency (layered window alpha) operations."""

import winapi
from topmost import WindowOperationError
from window_query import exists

MIN_PERCENT = 0
MAX_PERCENT = 100


def validate_percent(percent: object) -> int:
    """Return ``percent`` as an int in 0..100, rejecting anything else."""
    try:
        value = int(percent)
    except (TypeError, ValueError):
        raise WindowOperationError("Transparency must be a number between 0 and 100.")
    if value < MIN_PERCENT or value > MAX_PERCENT:
        raise WindowOperationError("Transparency must be between 0% and 100%.")
    return value


def percent_to_alpha(percent: object) -> int:
    """Map 0..100 (100 = opaque) onto the 0..255 alpha channel."""
    return int(round(winapi.OPAQUE_ALPHA * validate_percent(percent) / MAX_PERCENT))


def apply(hwnd: int, percent: object) -> None:
    """Make ``hwnd`` layered and set its opacity to ``percent``."""
    alpha = percent_to_alpha(percent)
    if not exists(hwnd):
        raise WindowOperationError("That window no longer exists. Refresh the list.")

    ex_style = winapi.GetWindowLong(hwnd, winapi.GWL_EXSTYLE)
    winapi.SetWindowLong(hwnd, winapi.GWL_EXSTYLE, ex_style | winapi.WS_EX_LAYERED)
    if not winapi.SetLayeredWindowAttributes(hwnd, 0, alpha, winapi.LWA_ALPHA):
        raise WindowOperationError(winapi.last_error_message("Applying transparency"))


def reset(hwnd: int) -> None:
    """Drop the layered style so ``hwnd`` becomes fully opaque again."""
    if not exists(hwnd):
        raise WindowOperationError("That window no longer exists. Refresh the list.")

    ex_style = winapi.GetWindowLong(hwnd, winapi.GWL_EXSTYLE)
    winapi.SetWindowLong(hwnd, winapi.GWL_EXSTYLE, ex_style & ~winapi.WS_EX_LAYERED)
    winapi.RedrawWindow(hwnd, None, None, winapi.RDW_FULL_REFRESH)
