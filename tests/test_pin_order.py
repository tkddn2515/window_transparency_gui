"""Unit tests for the pure pinned-window ordering model."""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pin_order
from pin_order import PinError, PinnedWindow


def make_pins(*specs):
    return tuple(PinnedWindow(hwnd=hwnd, title=title) for hwnd, title in specs)


BASE = make_pins((10, "Editor"), (20, "Terminal"), (30, "Browser"))


class ValidateHandleTests(unittest.TestCase):
    def test_accepts_positive_handle(self):
        self.assertEqual(pin_order.validate_handle(42), 42)

    def test_rejects_zero_and_negative(self):
        for bad in (0, -1):
            with self.assertRaises(PinError):
                pin_order.validate_handle(bad)

    def test_rejects_non_integer(self):
        for bad in ("10", None, 1.5, True):
            with self.assertRaises(PinError):
                pin_order.validate_handle(bad)


class LookupTests(unittest.TestCase):
    def test_index_of_known_and_unknown(self):
        self.assertEqual(pin_order.index_of(BASE, 20), 1)
        self.assertEqual(pin_order.index_of(BASE, 99), -1)

    def test_is_pinned(self):
        self.assertTrue(pin_order.is_pinned(BASE, 30))
        self.assertFalse(pin_order.is_pinned(BASE, 99))

    def test_handles_preserves_order(self):
        self.assertEqual(pin_order.handles(BASE), (10, 20, 30))


class WithPinTests(unittest.TestCase):
    def test_appends_new_pin_at_the_back(self):
        result = pin_order.with_pin(BASE, 40, "Notes")
        self.assertEqual(pin_order.handles(result), (10, 20, 30, 40))

    def test_does_not_mutate_the_original(self):
        pin_order.with_pin(BASE, 40, "Notes")
        self.assertEqual(pin_order.handles(BASE), (10, 20, 30))

    def test_repinning_keeps_layer_and_refreshes_title(self):
        result = pin_order.with_pin(BASE, 10, "Editor - file.py")
        self.assertEqual(pin_order.handles(result), (10, 20, 30))
        self.assertEqual(result[0].title, "Editor - file.py")

    def test_rejects_pin_beyond_the_limit(self):
        full = make_pins(*((i + 1, f"W{i}") for i in range(pin_order.MAX_PINNED_WINDOWS)))
        with self.assertRaises(PinError):
            pin_order.with_pin(full, 9999, "One too many")

    def test_rejects_invalid_handle(self):
        with self.assertRaises(PinError):
            pin_order.with_pin(BASE, 0, "Bad")


class WithoutPinTests(unittest.TestCase):
    def test_removes_only_the_requested_window(self):
        result = pin_order.without_pin(BASE, 20)
        self.assertEqual(pin_order.handles(result), (10, 30))

    def test_unknown_handle_is_a_no_op(self):
        self.assertEqual(pin_order.without_pin(BASE, 99), BASE)


class WithTitleTests(unittest.TestCase):
    def test_replaces_title_in_place(self):
        result = pin_order.with_title(BASE, 20, "Terminal - build")
        self.assertEqual(result[1].title, "Terminal - build")
        self.assertEqual(pin_order.handles(result), (10, 20, 30))
        self.assertEqual(BASE[1].title, "Terminal")


class MoveTests(unittest.TestCase):
    def test_moved_up_swaps_with_the_layer_above(self):
        result = pin_order.moved_up(BASE, 2)
        self.assertEqual(pin_order.handles(result), (10, 30, 20))

    def test_moved_down_swaps_with_the_layer_below(self):
        result = pin_order.moved_down(BASE, 0)
        self.assertEqual(pin_order.handles(result), (20, 10, 30))

    def test_move_past_the_front_is_ignored(self):
        self.assertEqual(pin_order.moved_up(BASE, 0), BASE)

    def test_move_past_the_back_is_ignored(self):
        self.assertEqual(pin_order.moved_down(BASE, 2), BASE)

    def test_invalid_index_is_ignored(self):
        self.assertEqual(pin_order.moved(BASE, -1, 1), BASE)
        self.assertEqual(pin_order.moved(BASE, 7, -1), BASE)

    def test_larger_offset_relocates_across_layers(self):
        result = pin_order.moved(BASE, 0, 2)
        self.assertEqual(pin_order.handles(result), (20, 30, 10))

    def test_does_not_mutate_the_original(self):
        pin_order.moved(BASE, 0, 2)
        self.assertEqual(pin_order.handles(BASE), (10, 20, 30))


class RetainedTests(unittest.TestCase):
    def test_drops_windows_that_failed_the_predicate(self):
        result = pin_order.retained(BASE, lambda hwnd: hwnd != 20)
        self.assertEqual(pin_order.handles(result), (10, 30))

    def test_keeps_everything_when_all_alive(self):
        self.assertEqual(pin_order.retained(BASE, lambda hwnd: True), BASE)


class MatchesZorderTests(unittest.TestCase):
    def test_matches_when_relative_order_agrees(self):
        self.assertTrue(pin_order.matches_zorder(BASE, (10, 20, 30)))

    def test_ignores_unrelated_windows_in_between(self):
        self.assertTrue(pin_order.matches_zorder(BASE, (10, 77, 20, 88, 30)))

    def test_detects_a_swapped_pair(self):
        self.assertFalse(pin_order.matches_zorder(BASE, (20, 10, 30)))

    def test_detects_a_missing_pinned_window(self):
        self.assertFalse(pin_order.matches_zorder(BASE, (10, 20)))

    def test_empty_pins_always_match(self):
        self.assertTrue(pin_order.matches_zorder((), (1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
