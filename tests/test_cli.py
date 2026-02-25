"""Tests for the CLI argument parsing and dispatch."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nanokvm_hid.cli import build_parser, main


class TestParser:
    def test_info(self) -> None:
        args = build_parser().parse_args(["info"])
        assert args.command == "info"

    def test_key_single(self) -> None:
        args = build_parser().parse_args(["key", "CTRL+C"])
        assert args.combo == ["CTRL+C"]

    def test_key_multiple(self) -> None:
        args = build_parser().parse_args(["key", "CTRL+A", "BACKSPACE", "ENTER"])
        assert args.combo == ["CTRL+A", "BACKSPACE", "ENTER"]

    def test_type(self) -> None:
        args = build_parser().parse_args(["type", "hello world"])
        assert args.text == "hello world"

    def test_backspace(self) -> None:
        args = build_parser().parse_args(["backspace", "5"])
        assert args.count == 5

    def test_mouse_move(self) -> None:
        args = build_parser().parse_args(["mouse", "move", "0.5", "0.3"])
        assert args.mouse_command == "move"
        assert args.x == 0.5
        assert args.y == 0.3

    def test_mouse_click_defaults(self) -> None:
        args = build_parser().parse_args(["mouse", "click"])
        assert args.x == 0.0
        assert args.y == 0.0
        assert not args.right
        assert not args.double

    def test_mouse_click_with_position(self) -> None:
        args = build_parser().parse_args(["mouse", "click", "0.8", "0.2"])
        assert args.x == 0.8
        assert args.y == 0.2

    def test_mouse_click_right_double(self) -> None:
        args = build_parser().parse_args(["mouse", "click", "-r", "-d", "0.5", "0.5"])
        assert args.right
        assert args.double

    def test_mouse_scroll_down_default(self) -> None:
        args = build_parser().parse_args(["mouse", "scroll-down"])
        assert args.steps == 1

    def test_mouse_scroll_up_with_steps(self) -> None:
        args = build_parser().parse_args(["mouse", "scroll-up", "5"])
        assert args.steps == 5

    def test_mouse_drag(self) -> None:
        args = build_parser().parse_args(["mouse", "drag", "0.1", "0.2", "0.8", "0.9"])
        assert (args.x0, args.y0, args.x1, args.y1) == (0.1, 0.2, 0.8, 0.9)

    def test_global_delay(self) -> None:
        args = build_parser().parse_args(["--delay", "0.05", "key", "A"])
        assert args.delay == 0.05

    def test_no_command_exits(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args([])


class TestDispatch:
    @patch("nanokvm_hid.cli.Keyboard")
    def test_key_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["key", "CTRL+C"])
        kb_instance.press.assert_called_once_with("CTRL+C")

    @patch("nanokvm_hid.cli.Keyboard")
    def test_type_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["type", "hello"])
        kb_instance.type.assert_called_once_with("hello")

    @patch("nanokvm_hid.cli.Keyboard")
    def test_backspace_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["backspace", "3"])
        kb_instance.backspace.assert_called_once_with(3)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_move_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "move", "0.5", "0.5"])
        m.move.assert_called_once_with(0.5, 0.5)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_click_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "click", "0.3", "0.7"])
        m.left_click.assert_called_once_with(0.3, 0.7)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_right_click_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "click", "-r", "0.3", "0.7"])
        m.right_click.assert_called_once_with(0.3, 0.7)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_scroll_down_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "scroll-down", "3"])
        m.scroll_down.assert_called_once_with(3)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_scroll_up_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "scroll-up"])
        m.scroll_up.assert_called_once_with(1)

    @patch("nanokvm_hid.cli.Mouse")
    def test_mouse_drag_dispatches(self, MockMouse: MagicMock) -> None:
        m = MockMouse.return_value
        main(["mouse", "drag", "0.1", "0.2", "0.8", "0.9"])
        m.drag.assert_called_once_with(0.1, 0.2, 0.8, 0.9)
