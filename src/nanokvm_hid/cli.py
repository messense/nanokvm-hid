"""Command-line interface for nanokvm-hid."""

from __future__ import annotations

import argparse
import shlex
import sys
import time

from .keyboard import Keyboard
from .mouse import Mouse
from .screen import Screen
from .transport import (
    DEFAULT_KEYBOARD_DEVICE,
    DEFAULT_MOUSE_DEVICE,
    DEFAULT_TOUCHPAD_DEVICE,
    HIDTransport,
)


def cmd_info(args: argparse.Namespace) -> None:
    """Show device status and screen resolution."""
    devices = [
        ("Keyboard", DEFAULT_KEYBOARD_DEVICE),
        ("Mouse", DEFAULT_MOUSE_DEVICE),
        ("Touchpad", DEFAULT_TOUCHPAD_DEVICE),
    ]
    for name, path in devices:
        t = HIDTransport(path)
        status = "✅ available" if t.available else "❌ not found"
        print(f"  {name:10s}  {path}  {status}")

    mouse = Mouse()
    w, h = mouse.screen_size
    print(f"  {'Screen':10s}  {w}×{h}")


def cmd_mouse_move(args: argparse.Namespace) -> None:
    mouse = Mouse()
    mouse.move(args.x, args.y)


def cmd_mouse_click(args: argparse.Namespace) -> None:
    from .constants import MouseButton

    mouse = Mouse()
    if args.double:
        button = MouseButton.RIGHT if args.right else MouseButton.LEFT
        mouse.double_click(args.x, args.y, button=button)
    elif args.right:
        mouse.right_click(args.x, args.y)
    else:
        mouse.left_click(args.x, args.y)


def cmd_mouse_scroll(args: argparse.Namespace) -> None:
    mouse = Mouse()
    if args.direction == "down":
        mouse.scroll_down(args.steps)
    else:
        mouse.scroll_up(args.steps)


def cmd_mouse_drag(args: argparse.Namespace) -> None:
    mouse = Mouse()
    mouse.drag(args.x0, args.y0, args.x1, args.y1)


def cmd_key(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    for combo in args.combo:
        kb.press(combo)
        if len(args.combo) > 1:
            time.sleep(args.delay)


def cmd_type(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.type(args.text)


def cmd_backspace(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.backspace(args.count)


def cmd_enter(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.enter()


def cmd_tab(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.tab()


def cmd_escape(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.escape()


def cmd_delete(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.delete()


def cmd_space(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.space()


def cmd_volume_up(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.volume_up()


def cmd_volume_down(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.volume_down()


def cmd_mute(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.mute()


def cmd_play_pause(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.play_pause()


def cmd_next_track(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.next_track()


def cmd_prev_track(args: argparse.Namespace) -> None:
    kb = Keyboard(inter_report_delay=args.delay)
    kb.prev_track()


def cmd_sleep(args: argparse.Namespace) -> None:
    time.sleep(args.seconds)


def cmd_capture(args: argparse.Namespace) -> None:
    """Capture a screenshot from the MJPEG stream."""
    screen = Screen(url=args.url)
    if args.output:
        path = screen.capture_to_file(args.output)
        print(f"Saved to {path}")
    elif args.base64:
        print(screen.capture_base64())
    else:
        # Write raw JPEG to stdout
        sys.stdout.buffer.write(screen.capture())


def cmd_script(args: argparse.Namespace) -> None:
    """Run a sequence of nanokvm-hid commands from a file or stdin."""
    if args.file:
        with open(args.file) as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    parser = build_parser()

    for lineno, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        # Skip blanks and comments
        if not line or line.startswith("#"):
            continue
        try:
            script_argv = shlex.split(line)
        except ValueError as exc:
            print(f"Error: line {lineno}: {exc}", file=sys.stderr)
            sys.exit(1)

        try:
            script_args = parser.parse_args(script_argv)
        except SystemExit:
            print(f"Error: line {lineno}: invalid command: {line}", file=sys.stderr)
            sys.exit(1)

        # Inherit global --delay from the outer invocation
        if not hasattr(script_args, "delay") or script_args.delay == 0.02:
            script_args.delay = args.delay

        _dispatch(script_args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nanokvm-hid",
        description="Control keyboard & mouse via NanoKVM Pro HID gadgets.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.02,
        help="inter-report delay in seconds (default: 0.02)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ── info ─────────────────────────────────────────────────────
    sub.add_parser("info", help="Show device status and screen size")

    # ── key ──────────────────────────────────────────────────────
    p = sub.add_parser("key", help="Press key combination(s)")
    p.add_argument(
        "combo",
        nargs="+",
        help="Key combo(s) to press, e.g. CTRL+C ENTER ALT+F4",
    )

    # ── type ─────────────────────────────────────────────────────
    p = sub.add_parser("type", help="Type a string of printable ASCII")
    p.add_argument("text", help="Text to type")

    # ── backspace ────────────────────────────────────────────────
    p = sub.add_parser("backspace", help="Press Backspace N times")
    p.add_argument("count", type=int, help="Number of backspaces")

    # ── enter / tab / escape / delete / space ───────────────────
    sub.add_parser("enter", help="Press Enter")
    sub.add_parser("tab", help="Press Tab")
    sub.add_parser("escape", help="Press Escape")
    sub.add_parser("delete", help="Press Delete")
    sub.add_parser("space", help="Press Space")

    # ── media / consumer control ─────────────────────────────────
    sub.add_parser("volume-up", help="Press Volume Up")
    sub.add_parser("volume-down", help="Press Volume Down")
    sub.add_parser("mute", help="Press Mute")
    sub.add_parser("play-pause", help="Press Play/Pause")
    sub.add_parser("next-track", help="Press Next Track")
    sub.add_parser("prev-track", help="Press Previous Track")

    # ── sleep ────────────────────────────────────────────────────
    p = sub.add_parser("sleep", help="Delay for N seconds")
    p.add_argument("seconds", type=float, help="Duration (supports decimals, e.g. 0.5)")

    # ── capture ──────────────────────────────────────────────────
    p = sub.add_parser("capture", help="Capture a screenshot from the HDMI stream")
    p.add_argument(
        "-o",
        "--output",
        default=None,
        help="Save to file (e.g. screenshot.jpg)",
    )
    p.add_argument(
        "--base64",
        action="store_true",
        help="Output as base64-encoded string",
    )
    p.add_argument(
        "--url",
        default="https://localhost/api/stream/mjpeg",
        help="MJPEG stream URL (default: https://localhost/api/stream/mjpeg)",
    )

    # ── script ───────────────────────────────────────────────────
    p = sub.add_parser(
        "script",
        help="Run commands from a file or stdin (one per line)",
    )
    p.add_argument(
        "file",
        nargs="?",
        default=None,
        help="Script file (default: read from stdin)",
    )

    # ── mouse ────────────────────────────────────────────────────
    mouse_parser = sub.add_parser("mouse", help="Mouse operations")
    msub = mouse_parser.add_subparsers(dest="mouse_command", required=True)

    # mouse move
    p = msub.add_parser("move", help="Move cursor to position")
    p.add_argument("x", type=float, help="Normalised X (0.0–1.0)")
    p.add_argument("y", type=float, help="Normalised Y (0.0–1.0)")

    # mouse click
    p = msub.add_parser("click", help="Click at position")
    p.add_argument(
        "x", type=float, nargs="?", default=0.0, help="X (default: 0 = don't move)"
    )
    p.add_argument(
        "y", type=float, nargs="?", default=0.0, help="Y (default: 0 = don't move)"
    )
    p.add_argument("-r", "--right", action="store_true", help="Right-click")
    p.add_argument("-d", "--double", action="store_true", help="Double-click")

    # mouse scroll
    for direction in ("scroll-up", "scroll-down"):
        p = msub.add_parser(direction, help=f"Scroll {direction.split('-')[1]}")
        p.add_argument(
            "steps",
            type=int,
            nargs="?",
            default=1,
            help="Number of steps (default: 1)",
        )

    # mouse drag
    p = msub.add_parser("drag", help="Drag from (x0,y0) to (x1,y1)")
    p.add_argument("x0", type=float, help="Start X")
    p.add_argument("y0", type=float, help="Start Y")
    p.add_argument("x1", type=float, help="End X")
    p.add_argument("y1", type=float, help="End Y")

    return parser


def _dispatch(args: argparse.Namespace) -> None:
    """Dispatch a parsed command."""
    if args.command == "info":
        cmd_info(args)
    elif args.command == "key":
        cmd_key(args)
    elif args.command == "type":
        cmd_type(args)
    elif args.command == "backspace":
        cmd_backspace(args)
    elif args.command == "enter":
        cmd_enter(args)
    elif args.command == "tab":
        cmd_tab(args)
    elif args.command == "escape":
        cmd_escape(args)
    elif args.command == "delete":
        cmd_delete(args)
    elif args.command == "space":
        cmd_space(args)
    elif args.command == "volume-up":
        cmd_volume_up(args)
    elif args.command == "volume-down":
        cmd_volume_down(args)
    elif args.command == "mute":
        cmd_mute(args)
    elif args.command == "play-pause":
        cmd_play_pause(args)
    elif args.command == "next-track":
        cmd_next_track(args)
    elif args.command == "prev-track":
        cmd_prev_track(args)
    elif args.command == "sleep":
        cmd_sleep(args)
    elif args.command == "capture":
        cmd_capture(args)
    elif args.command == "script":
        cmd_script(args)
    elif args.command == "mouse":
        if args.mouse_command == "move":
            cmd_mouse_move(args)
        elif args.mouse_command == "click":
            cmd_mouse_click(args)
        elif args.mouse_command == "scroll-down":
            args.direction = "down"
            cmd_mouse_scroll(args)
        elif args.mouse_command == "scroll-up":
            args.direction = "up"
            cmd_mouse_scroll(args)
        elif args.mouse_command == "drag":
            cmd_mouse_drag(args)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        _dispatch(args)
    except (FileNotFoundError, PermissionError, ConnectionError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
