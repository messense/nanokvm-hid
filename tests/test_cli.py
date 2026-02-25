"""Tests for the CLI argument parsing and dispatch."""

from __future__ import annotations

import io
import textwrap
from unittest.mock import patch

import pytest

from nanokvm_hid.cli import build_parser, main

# ── simple subcommand parsing ────────────────────────────────────────


@pytest.mark.parametrize(
    "cmd",
    [
        "info",
        "enter",
        "tab",
        "escape",
        "delete",
        "space",
        "volume-up",
        "volume-down",
        "mute",
        "play-pause",
        "next-track",
        "prev-track",
    ],
)
def test_parse_simple_command(cmd):
    args = build_parser().parse_args([cmd])
    assert args.command == cmd


def test_parse_key_single():
    args = build_parser().parse_args(["key", "CTRL+C"])
    assert args.combo == ["CTRL+C"]


def test_parse_key_multiple():
    args = build_parser().parse_args(["key", "CTRL+A", "BACKSPACE", "ENTER"])
    assert args.combo == ["CTRL+A", "BACKSPACE", "ENTER"]


def test_parse_type():
    args = build_parser().parse_args(["type", "hello world"])
    assert args.text == "hello world"


def test_parse_backspace():
    args = build_parser().parse_args(["backspace", "5"])
    assert args.count == 5


def test_parse_sleep():
    args = build_parser().parse_args(["sleep", "1.5"])
    assert args.seconds == 1.5


def test_parse_script_with_file():
    args = build_parser().parse_args(["script", "commands.txt"])
    assert args.file == "commands.txt"


def test_parse_script_no_file():
    args = build_parser().parse_args(["script"])
    assert args.file is None


def test_parse_global_delay():
    args = build_parser().parse_args(["--delay", "0.05", "key", "A"])
    assert args.delay == 0.05


def test_parse_no_command_exits():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


# ── mouse parsing ───────────────────────────────────────────────────


def test_parse_mouse_move():
    args = build_parser().parse_args(["mouse", "move", "0.5", "0.3"])
    assert args.mouse_command == "move"
    assert (args.x, args.y) == (0.5, 0.3)


def test_parse_mouse_click_defaults():
    args = build_parser().parse_args(["mouse", "click"])
    assert (args.x, args.y) == (0.0, 0.0)
    assert not args.right and not args.double


def test_parse_mouse_click_position():
    args = build_parser().parse_args(["mouse", "click", "0.8", "0.2"])
    assert (args.x, args.y) == (0.8, 0.2)


def test_parse_mouse_click_flags():
    args = build_parser().parse_args(["mouse", "click", "-r", "-d", "0.5", "0.5"])
    assert args.right and args.double


def test_parse_mouse_scroll_down_default():
    args = build_parser().parse_args(["mouse", "scroll-down"])
    assert args.steps == 1


def test_parse_mouse_scroll_up_steps():
    args = build_parser().parse_args(["mouse", "scroll-up", "5"])
    assert args.steps == 5


def test_parse_mouse_drag():
    args = build_parser().parse_args(["mouse", "drag", "0.1", "0.2", "0.8", "0.9"])
    assert (args.x0, args.y0, args.x1, args.y1) == (0.1, 0.2, 0.8, 0.9)


# ── capture parsing ─────────────────────────────────────────────────


def test_parse_capture_defaults():
    args = build_parser().parse_args(["capture"])
    assert args.output is None
    assert not args.base64
    assert not args.pikvm


def test_parse_capture_output():
    args = build_parser().parse_args(["capture", "-o", "shot.jpg"])
    assert args.output == "shot.jpg"


def test_parse_capture_base64():
    assert build_parser().parse_args(["capture", "--base64"]).base64


def test_parse_capture_url():
    args = build_parser().parse_args(["capture", "--url", "https://host/stream"])
    assert args.url == "https://host/stream"


def test_parse_capture_pikvm():
    assert build_parser().parse_args(["capture", "--pikvm"]).pikvm


def test_parse_capture_pikvm_credentials():
    args = build_parser().parse_args(
        ["capture", "--pikvm", "--pikvm-username", "user", "--pikvm-password", "pw"]
    )
    assert args.pikvm_username == "user"
    assert args.pikvm_password == "pw"


# ── dispatch: keyboard commands ──────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "method"),
    [
        (["key", "CTRL+C"], "press"),
        (["enter"], "enter"),
        (["tab"], "tab"),
        (["escape"], "escape"),
        (["delete"], "delete"),
        (["space"], "space"),
        (["volume-up"], "volume_up"),
        (["volume-down"], "volume_down"),
        (["mute"], "mute"),
        (["play-pause"], "play_pause"),
        (["next-track"], "next_track"),
        (["prev-track"], "prev_track"),
    ],
)
@patch("nanokvm_hid.cli.Keyboard")
def test_keyboard_dispatch(MockKB, argv, method):
    main(argv)
    getattr(MockKB.return_value, method).assert_called_once()


@patch("nanokvm_hid.cli.Keyboard")
def test_type_dispatch(MockKB):
    main(["type", "hello"])
    MockKB.return_value.type.assert_called_once_with("hello")


@patch("nanokvm_hid.cli.Keyboard")
def test_backspace_dispatch(MockKB):
    main(["backspace", "3"])
    MockKB.return_value.backspace.assert_called_once_with(3)


@patch("nanokvm_hid.cli.time")
def test_sleep_dispatch(mock_time):
    main(["sleep", "0.5"])
    mock_time.sleep.assert_called_once_with(0.5)


# ── dispatch: mouse commands ────────────────────────────────────────


@patch("nanokvm_hid.cli.Mouse")
def test_mouse_move_dispatch(MockMouse):
    main(["mouse", "move", "0.5", "0.5"])
    MockMouse.return_value.move.assert_called_once_with(0.5, 0.5)


@patch("nanokvm_hid.cli.Mouse")
def test_mouse_click_dispatch(MockMouse):
    main(["mouse", "click", "0.3", "0.7"])
    MockMouse.return_value.left_click.assert_called_once_with(0.3, 0.7)


@patch("nanokvm_hid.cli.Mouse")
def test_mouse_right_click_dispatch(MockMouse):
    main(["mouse", "click", "-r", "0.3", "0.7"])
    MockMouse.return_value.right_click.assert_called_once_with(0.3, 0.7)


@pytest.mark.parametrize(
    ("argv", "method", "arg"),
    [
        (["mouse", "scroll-down", "3"], "scroll_down", 3),
        (["mouse", "scroll-up"], "scroll_up", 1),
    ],
)
@patch("nanokvm_hid.cli.Mouse")
def test_mouse_scroll_dispatch(MockMouse, argv, method, arg):
    main(argv)
    getattr(MockMouse.return_value, method).assert_called_once_with(arg)


@patch("nanokvm_hid.cli.Mouse")
def test_mouse_drag_dispatch(MockMouse):
    main(["mouse", "drag", "0.1", "0.2", "0.8", "0.9"])
    MockMouse.return_value.drag.assert_called_once_with(0.1, 0.2, 0.8, 0.9)


# ── script ───────────────────────────────────────────────────────────


@patch("nanokvm_hid.cli.Keyboard")
@patch("nanokvm_hid.cli.Mouse")
@patch("nanokvm_hid.cli.time")
def test_script_from_file(mock_time, MockMouse, MockKB, tmp_path):
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
def test_script_skips_blanks_and_comments(MockKB, tmp_path):
    script = tmp_path / "test.script"
    script.write_text("# comment\n\nkey A\n\n# another\n")
    main(["script", str(script)])
    MockKB.return_value.press.assert_called_once_with("A")


@patch("nanokvm_hid.cli.Keyboard")
@patch("nanokvm_hid.cli.Mouse")
@patch("nanokvm_hid.cli.time")
def test_script_from_stdin(mock_time, MockMouse, MockKB, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("key CTRL+C\nsleep 0.5\n"))
    main(["script"])
    MockKB.return_value.press.assert_called_once_with("CTRL+C")
    mock_time.sleep.assert_any_call(0.5)
