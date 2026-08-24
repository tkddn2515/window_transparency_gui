"""Tests for PinKeeper against a fake desktop (no Win32 calls involved)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pin_keeper import PinKeeper
from pin_order import PinError, handles


class FakeDesktop:
    """A minimal stand-in for Windows' z-order.

    ``order`` is front-most first.  Always-on-top windows always sit ahead of
    normal ones, matching how Windows keeps the two bands separated.
    """

    def __init__(self, titles, blocked=()):
        self.titles = dict(titles)
        self.order = list(self.titles)
        self.topmost = set()
        self.blocked = set(blocked)
        self.pin_calls = []

    # --- backend protocol ---

    def exists(self, hwnd):
        return hwnd in self.titles

    def is_topmost(self, hwnd):
        return hwnd in self.topmost

    def title_of(self, hwnd):
        return self.titles.get(hwnd, "")

    def zorder(self, hwnds):
        wanted = set(hwnds)
        return tuple(hwnd for hwnd in self.order if hwnd in wanted)

    def pin(self, hwnd):
        self.pin_calls.append(hwnd)
        if hwnd in self.blocked:
            raise RuntimeError("Access is denied.")
        self.topmost.add(hwnd)
        self.order.remove(hwnd)
        self.order.insert(0, hwnd)

    def unpin(self, hwnd):
        if hwnd in self.blocked:
            raise RuntimeError("Access is denied.")
        self.topmost.discard(hwnd)
        self.order.remove(hwnd)
        self.order.insert(len(self.topmost), hwnd)

    def apply_order(self, pins):
        failures = []
        for pin in reversed(tuple(pins)):
            try:
                self.pin(pin.hwnd)
            except RuntimeError as error:
                failures.append(f'"{pin.title}": {error}')
        return tuple(failures)

    # --- test helpers ---

    def close(self, hwnd):
        self.titles.pop(hwnd, None)
        self.order.remove(hwnd)
        self.topmost.discard(hwnd)

    def steal_top(self, hwnd):
        """Simulate another app jumping to the front of the stack."""
        self.order.remove(hwnd)
        self.order.insert(0, hwnd)


def make_desktop(**kwargs):
    return FakeDesktop({10: "Editor", 20: "Terminal", 30: "Browser"}, **kwargs)


class PinTests(unittest.TestCase):
    def setUp(self):
        self.desktop = make_desktop()
        self.keeper = PinKeeper(backend=self.desktop)

    def test_pin_puts_the_window_on_top(self):
        self.keeper.pin(10, "Editor")
        self.assertEqual(self.desktop.order[0], 10)
        self.assertIn(10, self.desktop.topmost)
        self.assertEqual(handles(self.keeper.pins), (10,))

    def test_second_pin_stacks_below_the_first(self):
        self.keeper.pin(10, "Editor")
        self.keeper.pin(20, "Terminal")
        self.assertEqual(handles(self.keeper.pins), (10, 20))
        self.assertEqual(self.desktop.order[:2], [10, 20])

    def test_pin_rejects_a_closed_window(self):
        with self.assertRaises(PinError):
            self.keeper.pin(99, "Ghost")
        self.assertEqual(self.keeper.pins, ())

    def test_pin_rejects_an_invalid_handle(self):
        with self.assertRaises(PinError):
            self.keeper.pin(0, "Bad")

    def test_a_refused_pin_leaves_the_list_untouched(self):
        desktop = make_desktop(blocked={20})
        keeper = PinKeeper(backend=desktop)
        keeper.pin(10, "Editor")
        with self.assertRaises(PinError):
            keeper.pin(20, "Terminal")
        self.assertEqual(handles(keeper.pins), (10,))

    def test_repinning_does_not_duplicate(self):
        self.keeper.pin(10, "Editor")
        self.keeper.pin(10, "Editor")
        self.assertEqual(handles(self.keeper.pins), (10,))


class UnpinTests(unittest.TestCase):
    def setUp(self):
        self.desktop = make_desktop()
        self.keeper = PinKeeper(backend=self.desktop)
        self.keeper.pin(10, "Editor")
        self.keeper.pin(20, "Terminal")

    def test_unpin_clears_topmost_and_keeps_the_rest_ordered(self):
        self.keeper.unpin(10)
        self.assertEqual(handles(self.keeper.pins), (20,))
        self.assertNotIn(10, self.desktop.topmost)
        self.assertEqual(self.desktop.order[0], 20)

    def test_unpin_of_an_unpinned_window_is_a_no_op(self):
        self.assertEqual(self.keeper.unpin(30), ())
        self.assertEqual(handles(self.keeper.pins), (10, 20))

    def test_unpin_all_releases_everything(self):
        self.keeper.unpin_all()
        self.assertEqual(self.keeper.pins, ())
        self.assertEqual(self.desktop.topmost, set())

    def test_unpin_reports_a_refusal_without_keeping_the_pin(self):
        desktop = make_desktop()
        keeper = PinKeeper(backend=desktop)
        keeper.pin(10, "Editor")
        desktop.blocked.add(10)
        failures = keeper.unpin(10)
        self.assertTrue(failures)
        self.assertEqual(keeper.pins, ())


class ReorderTests(unittest.TestCase):
    def setUp(self):
        self.desktop = make_desktop()
        self.keeper = PinKeeper(backend=self.desktop)
        self.keeper.pin(10, "Editor")
        self.keeper.pin(20, "Terminal")
        self.keeper.pin(30, "Browser")

    def test_move_up_restacks_the_desktop(self):
        new_index, failures = self.keeper.move(2, -1)
        self.assertEqual(new_index, 1)
        self.assertEqual(failures, ())
        self.assertEqual(handles(self.keeper.pins), (10, 30, 20))
        self.assertEqual(self.desktop.order[:3], [10, 30, 20])

    def test_move_down_restacks_the_desktop(self):
        new_index, _ = self.keeper.move(0, 1)
        self.assertEqual(new_index, 1)
        self.assertEqual(self.desktop.order[:3], [20, 10, 30])

    def test_move_out_of_range_reports_minus_one(self):
        new_index, failures = self.keeper.move(0, -1)
        self.assertEqual(new_index, -1)
        self.assertEqual(failures, ())
        self.assertEqual(handles(self.keeper.pins), (10, 20, 30))


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.desktop = make_desktop()
        self.keeper = PinKeeper(backend=self.desktop)
        self.keeper.pin(10, "Editor")
        self.keeper.pin(20, "Terminal")

    def test_sync_is_quiet_when_the_order_already_holds(self):
        self.desktop.pin_calls.clear()
        report = self.keeper.sync()
        self.assertFalse(report.changed)
        self.assertEqual(self.desktop.pin_calls, [])

    def test_sync_restores_the_order_after_an_intruder_jumps_ahead(self):
        self.desktop.steal_top(20)
        self.assertEqual(self.desktop.order[:2], [20, 10])

        report = self.keeper.sync()
        self.assertTrue(report.reordered)
        self.assertEqual(self.desktop.order[:2], [10, 20])

    def test_sync_restores_a_window_that_lost_its_topmost_style(self):
        self.desktop.topmost.discard(10)
        report = self.keeper.sync()
        self.assertTrue(report.reordered)
        self.assertIn(10, self.desktop.topmost)

    def test_sync_drops_closed_windows(self):
        self.desktop.close(10)
        report = self.keeper.sync()
        self.assertEqual(handles(report.dropped), (10,))
        self.assertEqual(handles(self.keeper.pins), (20,))

    def test_sync_refreshes_a_changed_title_without_reordering(self):
        self.desktop.titles[20] = "Terminal - build"
        report = self.keeper.sync()
        self.assertEqual(self.keeper.pins[1].title, "Terminal - build")
        self.assertEqual(handles(self.keeper.pins), (10, 20))
        self.assertFalse(report.reordered)

    def test_sync_reports_a_window_it_cannot_restore(self):
        self.desktop.blocked.add(20)
        self.desktop.steal_top(30)
        self.desktop.topmost.discard(20)
        report = self.keeper.sync()
        self.assertTrue(report.failures)
        self.assertIn("Terminal", report.failures[0])


if __name__ == "__main__":
    unittest.main()
