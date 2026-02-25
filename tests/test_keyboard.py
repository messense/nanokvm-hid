"""Tests for keyboard combo parsing and report generation."""

from __future__ import annotations

import pytest

from nanokvm_hid.keyboard import (
    _build_consumer_reports,
    _build_keyboard_reports,
    parse_combo,
)

# ── parse_combo ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("combo", "mod", "key", "consumer"),
    [
        ("A", 0x00, 0x04, False),
        ("CTRL+C", 0x01, 0x06, False),
        ("CTRL+SHIFT+A", 0x03, 0x04, False),
        ("VOLUME_UP", 0x00, 0xE9, True),
        ("SHIFT", 0x02, None, False),
        ("F11", 0x00, 0x44, False),
        ("ALT+F4", 0x04, 0x3D, False),
    ],
)
def test_parse_combo(combo, mod, key, consumer):
    m, k, c = parse_combo(combo)
    assert m == mod
    assert k == key
    assert c == consumer


def test_parse_combo_case_insensitive():
    assert parse_combo("ctrl+c") == parse_combo("CTRL+C")


@pytest.mark.parametrize("alias", ["GUI", "WIN", "SUPER", "META", "COMMAND", "CMD"])
def test_gui_aliases(alias):
    mod, _, _ = parse_combo(f"{alias}+L")
    assert mod == 0x08


def test_unknown_key_raises():
    with pytest.raises(ValueError, match="Unknown key"):
        parse_combo("CTRL+BANANA")


def test_multiple_main_keys_raises():
    with pytest.raises(ValueError, match="Multiple non-modifier"):
        parse_combo("A+B")


# ── report building ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("mod", "key", "expected_len"),
    [
        (0, 0x04, 2),  # single key
        (0x01, 0x06, 4),  # combo
        (0x02, None, 2),  # modifier only
    ],
)
def test_keyboard_report_count(mod, key, expected_len):
    assert len(_build_keyboard_reports(mod, key)) == expected_len


def test_single_key_report_content():
    reports = _build_keyboard_reports(0, 0x04)
    assert reports[0] == bytes([0, 0, 0x04, 0, 0, 0, 0, 0])
    assert reports[1] == bytes(8)


def test_consumer_reports():
    reports = _build_consumer_reports(0xE9)
    assert len(reports) == 2
    assert reports[0] == bytes([0xE9, 0x00])
    assert reports[1] == bytes(2)


# ── Keyboard integration ────────────────────────────────────────────


def test_press_sends_reports(kb, fake_transport):
    kb.press("A")
    assert len(fake_transport.reports) == 2


def test_type_string(kb, fake_transport):
    kb.type("hi")
    assert len(fake_transport.reports) == 4  # 2 chars × 2 reports


def test_type_invalid_char_raises(kb):
    with pytest.raises(ValueError, match="cannot be typed"):
        kb.type("hello\nworld")


def test_backspace(kb, fake_transport):
    kb.backspace(3)
    assert len(fake_transport.reports) == 6  # 3 × 2 reports


def test_hotkey(kb, fake_transport):
    kb.hotkey("CTRL", "SHIFT", "A")
    assert len(fake_transport.reports) == 4  # combo → 4 reports
