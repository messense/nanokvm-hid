"""Tests for the CLI argument parsing and dispatch."""

from __future__ import annotations

import textwrap
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

    def test_enter(self) -> None:
        args = build_parser().parse_args(["enter"])
        assert args.command == "enter"

    def test_tab(self) -> None:
        args = build_parser().parse_args(["tab"])
        assert args.command == "tab"

    def test_escape(self) -> None:
        args = build_parser().parse_args(["escape"])
        assert args.command == "escape"

    def test_delete(self) -> None:
        args = build_parser().parse_args(["delete"])
        assert args.command == "delete"

    def test_space(self) -> None:
        args = build_parser().parse_args(["space"])
        assert args.command == "space"

    def test_volume_up(self) -> None:
        args = build_parser().parse_args(["volume-up"])
        assert args.command == "volume-up"

    def test_volume_down(self) -> None:
        args = build_parser().parse_args(["volume-down"])
        assert args.command == "volume-down"

    def test_mute(self) -> None:
        args = build_parser().parse_args(["mute"])
        assert args.command == "mute"

    def test_play_pause(self) -> None:
        args = build_parser().parse_args(["play-pause"])
        assert args.command == "play-pause"

    def test_next_track(self) -> None:
        args = build_parser().parse_args(["next-track"])
        assert args.command == "next-track"

    def test_prev_track(self) -> None:
        args = build_parser().parse_args(["prev-track"])
        assert args.command == "prev-track"

    def test_sleep(self) -> None:
        args = build_parser().parse_args(["sleep", "1.5"])
        assert args.seconds == 1.5

    def test_script_with_file(self) -> None:
        args = build_parser().parse_args(["script", "commands.txt"])
        assert args.file == "commands.txt"

    def test_script_no_file(self) -> None:
        args = build_parser().parse_args(["script"])
        assert args.file is None

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

    @patch("nanokvm_hid.cli.Keyboard")
    def test_enter_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["enter"])
        kb_instance.enter.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_tab_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["tab"])
        kb_instance.tab.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_escape_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["escape"])
        kb_instance.escape.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_delete_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["delete"])
        kb_instance.delete.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_space_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["space"])
        kb_instance.space.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_volume_up_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["volume-up"])
        kb_instance.volume_up.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_volume_down_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["volume-down"])
        kb_instance.volume_down.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_mute_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["mute"])
        kb_instance.mute.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_play_pause_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["play-pause"])
        kb_instance.play_pause.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_next_track_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["next-track"])
        kb_instance.next_track.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_prev_track_dispatches(self, MockKB: MagicMock) -> None:
        kb_instance = MockKB.return_value
        main(["prev-track"])
        kb_instance.prev_track.assert_called_once()

    @patch("nanokvm_hid.cli.time")
    def test_sleep_dispatches(self, mock_time: MagicMock) -> None:
        main(["sleep", "0.5"])
        mock_time.sleep.assert_called_once_with(0.5)

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


class TestParserCapture:
    def test_capture_defaults(self) -> None:
        args = build_parser().parse_args(["capture"])
        assert args.command == "capture"
        assert args.output is None
        assert not args.base64

    def test_capture_output(self) -> None:
        args = build_parser().parse_args(["capture", "-o", "shot.jpg"])
        assert args.output == "shot.jpg"

    def test_capture_base64(self) -> None:
        args = build_parser().parse_args(["capture", "--base64"])
        assert args.base64

    def test_capture_custom_url(self) -> None:
        args = build_parser().parse_args(["capture", "--url", "https://host/stream"])
        assert args.url == "https://host/stream"


class TestScript:
    @patch("nanokvm_hid.cli.Keyboard")
    @patch("nanokvm_hid.cli.Mouse")
    @patch("nanokvm_hid.cli.time")
    def test_script_from_file(
        self,
        mock_time: MagicMock,
        MockMouse: MagicMock,
        MockKB: MagicMock,
        tmp_path: MagicMock,
    ) -> None:
        script = tmp_path / "test.script"
        script.write_text(
            textwrap.dedent("""\
            # Move to center and click
            mouse move 0.5 0.5
            mouse click 0.5 0.5
            sleep 1
            type "hello world"
            enter
        """)
        )

        main(["script", str(script)])

        m = MockMouse.return_value
        kb = MockKB.return_value
        m.move.assert_called_once_with(0.5, 0.5)
        m.left_click.assert_called_once_with(0.5, 0.5)
        mock_time.sleep.assert_any_call(1.0)
        kb.type.assert_called_once_with("hello world")
        kb.enter.assert_called_once()

    @patch("nanokvm_hid.cli.Keyboard")
    def test_script_skips_blanks_and_comments(
        self, MockKB: MagicMock, tmp_path: MagicMock
    ) -> None:
        script = tmp_path / "test.script"
        script.write_text(
            textwrap.dedent("""\
            # this is a comment

            key A

            # another comment
        """)
        )

        main(["script", str(script)])
        MockKB.return_value.press.assert_called_once_with("A")

    @patch("nanokvm_hid.cli.Keyboard")
    @patch("nanokvm_hid.cli.Mouse")
    @patch("nanokvm_hid.cli.time")
    def test_script_from_stdin(
        self,
        mock_time: MagicMock,
        MockMouse: MagicMock,
        MockKB: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO("key CTRL+C\nsleep 0.5\n"))
        main(["script"])

        MockKB.return_value.press.assert_called_once_with("CTRL+C")
        mock_time.sleep.assert_any_call(0.5)
