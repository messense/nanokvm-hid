"""Tests for mouse operations."""

from __future__ import annotations

from nanokvm_hid.constants import ABS_COORD_MAX, MouseButton
from nanokvm_hid.mouse import Mouse

from .conftest import FakeTransport


def _make_mouse() -> tuple[Mouse, FakeTransport, FakeTransport]:
    """Create a Mouse backed by fake transports."""
    mouse_transport = FakeTransport()
    touchpad_transport = FakeTransport()
    m = Mouse(screen_size=(1920, 1080))
    m._mouse = mouse_transport
    m._touchpad = touchpad_transport
    return m, mouse_transport, touchpad_transport


class TestMove:
    def test_move_sends_touchpad_report(self) -> None:
        m, _, tp = _make_mouse()
        m.move(0.5, 0.5)
        assert len(tp.reports) == 1
        report = tp.reports[0]
        assert len(report) == 6
        # Check midpoint encoding
        mid = ABS_COORD_MAX // 2
        assert report[1] == mid & 0xFF
        assert report[2] == mid >> 8

    def test_move_to_origin(self) -> None:
        m, _, tp = _make_mouse()
        m.move(0.0, 0.0)
        report = tp.reports[0]
        assert report[1] == 0 and report[2] == 0
        assert report[3] == 0 and report[4] == 0

    def test_move_clamps(self) -> None:
        m, _, tp = _make_mouse()
        m.move(2.0, -1.0)  # should clamp to (1.0, 0.0)
        report = tp.reports[0]
        x = report[1] | (report[2] << 8)
        y = report[3] | (report[4] << 8)
        assert x == ABS_COORD_MAX
        assert y == 0


class TestClick:
    def test_left_click_at_position(self) -> None:
        m, mouse_t, tp = _make_mouse()
        m.left_click(0.5, 0.5)
        # Should move first (touchpad), then click+release (mouse)
        assert len(tp.reports) == 1
        assert len(mouse_t.reports) == 2
        # First mouse report: left button pressed
        assert mouse_t.reports[0][0] == MouseButton.LEFT
        # Second mouse report: released (all zeros)
        assert mouse_t.reports[1] == bytes(4)

    def test_right_click(self) -> None:
        m, mouse_t, _ = _make_mouse()
        m.right_click(0.5, 0.5)
        assert mouse_t.reports[0][0] == MouseButton.RIGHT

    def test_click_no_move(self) -> None:
        m, mouse_t, tp = _make_mouse()
        m.left_click()  # x=0, y=0 → no move
        assert len(tp.reports) == 0
        assert len(mouse_t.reports) == 2


class TestDoubleClick:
    def test_double_click_sends_4_mouse_reports(self) -> None:
        m, mouse_t, _ = _make_mouse()
        m.double_click(0.5, 0.5)
        # 2 clicks × 2 reports each = 4 mouse reports
        assert len(mouse_t.reports) == 4


class TestScroll:
    def test_scroll_down(self) -> None:
        m, mouse_t, _ = _make_mouse()
        m.scroll_down(1)
        # 4 scroll reports + 1 release
        assert len(mouse_t.reports) == 5
        # Check scroll direction (0xFE = -2 signed)
        assert mouse_t.reports[0][3] == 0xFE

    def test_scroll_up(self) -> None:
        m, mouse_t, _ = _make_mouse()
        m.scroll_up(1)
        assert len(mouse_t.reports) == 5
        assert mouse_t.reports[0][3] == 0x02


class TestDrag:
    def test_drag_sends_touchpad_then_mouse(self) -> None:
        m, mouse_t, tp = _make_mouse()
        m.drag(0.1, 0.1, 0.2, 0.2)
        # Touchpad: 1 report for start position
        assert len(tp.reports) == 1
        # Mouse: 1 press + N relative moves + 1 release
        assert len(mouse_t.reports) >= 3
        # First mouse report: button held
        assert mouse_t.reports[0][0] == MouseButton.LEFT
        # Last mouse report: released
        assert mouse_t.reports[-1] == bytes(4)


class TestScreenSize:
    def test_explicit_screen_size(self) -> None:
        m = Mouse(screen_size=(3840, 2160))
        assert m.screen_size == (3840, 2160)
