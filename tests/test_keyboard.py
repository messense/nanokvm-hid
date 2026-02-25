"""Tests for keyboard combo parsing and report generation."""

from __future__ import annotations

import pytest

from nanokvm_hid.keyboard import (
    Keyboard,
    _build_consumer_reports,
    _build_keyboard_reports,
    parse_combo,
)

from .conftest import FakeTransport


class TestParseCombo:
    def test_single_letter(self) -> None:
        mod, key, consumer = parse_combo("A")
        assert mod == 0
        assert key == 0x04
        assert consumer is False

    def test_ctrl_c(self) -> None:
        mod, key, consumer = parse_combo("CTRL+C")
        assert mod == 0x01
        assert key == 0x06
        assert consumer is False

    def test_triple_combo(self) -> None:
        mod, key, consumer = parse_combo("CTRL+SHIFT+A")
        assert mod == 0x03  # CTRL(0x01) | SHIFT(0x02)
        assert key == 0x04

    def test_consumer_key(self) -> None:
        mod, key, consumer = parse_combo("VOLUME_UP")
        assert consumer is True
        assert key == 0xE9

    def test_case_insensitive(self) -> None:
        mod1, key1, _ = parse_combo("ctrl+c")
        mod2, key2, _ = parse_combo("CTRL+C")
        assert (mod1, key1) == (mod2, key2)

    def test_unknown_key_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown key"):
            parse_combo("CTRL+BANANA")

    def test_multiple_main_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="Multiple non-modifier"):
            parse_combo("A+B")

    def test_modifier_only(self) -> None:
        mod, key, consumer = parse_combo("SHIFT")
        assert mod == 0x02
        assert key is None

    def test_gui_aliases(self) -> None:
        for alias in ("GUI", "WIN", "SUPER", "META", "COMMAND", "CMD"):
            mod, _, _ = parse_combo(f"{alias}+L")
            assert mod == 0x08, f"Alias {alias} did not resolve to GUI mask"


class TestBuildReports:
    def test_single_key_has_2_reports(self) -> None:
        reports = _build_keyboard_reports(0, 0x04)
        assert len(reports) == 2
        assert reports[0] == bytes([0, 0, 0x04, 0, 0, 0, 0, 0])
        assert reports[1] == bytes(8)

    def test_combo_has_4_reports(self) -> None:
        reports = _build_keyboard_reports(0x01, 0x06)
        assert len(reports) == 4

    def test_modifier_only_has_2_reports(self) -> None:
        reports = _build_keyboard_reports(0x02, None)
        assert len(reports) == 2

    def test_consumer_has_2_reports(self) -> None:
        reports = _build_consumer_reports(0xE9)
        assert len(reports) == 2
        assert reports[0] == bytes([0xE9, 0x00])
        assert reports[1] == bytes(2)


class TestKeyboardIntegration:
    def test_press_sends_reports(self) -> None:
        transport = FakeTransport()
        kb = Keyboard(inter_report_delay=0)
        kb._transport = transport

        kb.press("A")
        assert len(transport.reports) == 2

    def test_type_string(self) -> None:
        transport = FakeTransport()
        kb = Keyboard(inter_report_delay=0)
        kb._transport = transport

        kb.type("hi")
        # "h" → 2 reports, "i" → 2 reports
        assert len(transport.reports) == 4

    def test_type_invalid_char_raises(self) -> None:
        transport = FakeTransport()
        kb = Keyboard(inter_report_delay=0)
        kb._transport = transport

        with pytest.raises(ValueError, match="cannot be typed"):
            kb.type("hello\nworld")

    def test_backspace(self) -> None:
        transport = FakeTransport()
        kb = Keyboard(inter_report_delay=0)
        kb._transport = transport

        kb.backspace(3)
        # 3 backspaces × 2 reports each
        assert len(transport.reports) == 6

    def test_hotkey(self) -> None:
        transport = FakeTransport()
        kb = Keyboard(inter_report_delay=0)
        kb._transport = transport

        kb.hotkey("CTRL", "SHIFT", "A")
        # combo → 4 reports
        assert len(transport.reports) == 4
