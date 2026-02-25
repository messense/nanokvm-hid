"""Tests for mouse operations."""

from __future__ import annotations

from nanokvm_hid.constants import ABS_COORD_MAX, MouseButton

# ── move ─────────────────────────────────────────────────────────────


def test_move_sends_touchpad_report(fake_mouse):
    m, _, tp = fake_mouse
    m.move(0.5, 0.5)
    assert len(tp.reports) == 1
    report = tp.reports[0]
    assert len(report) == 6
    mid = ABS_COORD_MAX // 2
    assert report[1] == mid & 0xFF
    assert report[2] == mid >> 8


def test_move_to_origin(fake_mouse):
    m, _, tp = fake_mouse
    m.move(0.0, 0.0)
    report = tp.reports[0]
    assert report[1] == 0 and report[2] == 0
    assert report[3] == 0 and report[4] == 0


def test_move_clamps(fake_mouse):
    m, _, tp = fake_mouse
    m.move(2.0, -1.0)  # should clamp to (1.0, 0.0)
    report = tp.reports[0]
    x = report[1] | (report[2] << 8)
    y = report[3] | (report[4] << 8)
    assert x == ABS_COORD_MAX
    assert y == 0


# ── click ────────────────────────────────────────────────────────────


def test_left_click_at_position(fake_mouse):
    m, mouse_t, tp = fake_mouse
    m.left_click(0.5, 0.5)
    assert len(tp.reports) == 1
    assert len(mouse_t.reports) == 2
    assert mouse_t.reports[0][0] == MouseButton.LEFT
    assert mouse_t.reports[1] == bytes(4)


def test_right_click(fake_mouse):
    m, mouse_t, _ = fake_mouse
    m.right_click(0.5, 0.5)
    assert mouse_t.reports[0][0] == MouseButton.RIGHT


def test_click_no_move(fake_mouse):
    m, mouse_t, tp = fake_mouse
    m.left_click()  # x=0, y=0 → no move
    assert len(tp.reports) == 0
    assert len(mouse_t.reports) == 2


def test_double_click(fake_mouse):
    m, mouse_t, _ = fake_mouse
    m.double_click(0.5, 0.5)
    assert len(mouse_t.reports) == 4  # 2 clicks × 2 reports


# ── scroll ───────────────────────────────────────────────────────────


def test_scroll_down(fake_mouse):
    m, mouse_t, _ = fake_mouse
    m.scroll_down(1)
    assert len(mouse_t.reports) == 5  # 4 scroll + 1 release
    assert mouse_t.reports[0][3] == 0xFE


def test_scroll_up(fake_mouse):
    m, mouse_t, _ = fake_mouse
    m.scroll_up(1)
    assert len(mouse_t.reports) == 5
    assert mouse_t.reports[0][3] == 0x02


# ── drag ─────────────────────────────────────────────────────────────


def test_drag(fake_mouse):
    m, mouse_t, tp = fake_mouse
    m.drag(0.1, 0.1, 0.2, 0.2)
    assert len(tp.reports) == 1
    assert len(mouse_t.reports) >= 3  # press + moves + release
    assert mouse_t.reports[0][0] == MouseButton.LEFT
    assert mouse_t.reports[-1] == bytes(4)


# ── screen size ──────────────────────────────────────────────────────


def test_explicit_screen_size():
    from nanokvm_hid.mouse import Mouse

    m = Mouse(screen_size=(3840, 2160))
    assert m.screen_size == (3840, 2160)
