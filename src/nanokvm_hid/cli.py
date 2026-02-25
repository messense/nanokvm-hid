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


class _Session:
    """Lazily-initialised device handles, created once and reused."""

    def __init__(self, delay: float = 0.02) -> None:
        self.delay = delay
        self._keyboard: Keyboard | None = None
        self._mouse: Mouse | None = None

    @property
    def keyboard(self) -> Keyboard:
        if self._keyboard is None:
            self._keyboard = Keyboard(inter_report_delay=self.delay)
        return self._keyboard

    @property
    def mouse(self) -> Mouse:
        if self._mouse is None:
            self._mouse = Mouse()
        return self._mouse


def _dispatch(args: argparse.Namespace, session: _Session) -> None:
    """Dispatch a parsed command using shared device handles."""
    cmd = args.command

    if cmd == "info":
        _cmd_info()
    elif cmd == "key":
        for combo in args.combo:
            session.keyboard.press(combo)
            if len(args.combo) > 1:
                time.sleep(session.delay)
    elif cmd == "type":
        session.keyboard.type(args.text)
    elif cmd == "backspace":
        session.keyboard.backspace(args.count)
    elif cmd == "enter":
        session.keyboard.enter()
    elif cmd == "tab":
        session.keyboard.tab()
    elif cmd == "escape":
        session.keyboard.escape()
    elif cmd == "delete":
        session.keyboard.delete()
    elif cmd == "space":
        session.keyboard.space()
    elif cmd == "volume-up":
        session.keyboard.volume_up()
    elif cmd == "volume-down":
        session.keyboard.volume_down()
    elif cmd == "mute":
        session.keyboard.mute()
    elif cmd == "play-pause":
        session.keyboard.play_pause()
    elif cmd == "next-track":
        session.keyboard.next_track()
    elif cmd == "prev-track":
        session.keyboard.prev_track()
    elif cmd == "sleep":
        time.sleep(args.seconds)
    elif cmd == "capture":
        _cmd_capture(args)
    elif cmd == "script":
        _cmd_script(args, session)
    elif cmd == "mouse":
        _dispatch_mouse(args, session)


def _dispatch_mouse(args: argparse.Namespace, session: _Session) -> None:
    """Dispatch mouse subcommands."""
    from .constants import MouseButton

    mouse = session.mouse
    sub = args.mouse_command

    if sub == "move":
        mouse.move(args.x, args.y)
    elif sub == "click":
        if args.double:
            button = MouseButton.RIGHT if args.right else MouseButton.LEFT
            mouse.double_click(args.x, args.y, button=button)
        elif args.right:
            mouse.right_click(args.x, args.y)
        else:
            mouse.left_click(args.x, args.y)
    elif sub == "scroll-down":
        mouse.scroll_down(args.steps)
    elif sub == "scroll-up":
        mouse.scroll_up(args.steps)
    elif sub == "drag":
        mouse.drag(args.x0, args.y0, args.x1, args.y1)


def _cmd_info() -> None:
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


def _cmd_capture(args: argparse.Namespace) -> None:
    """Capture a screenshot from the MJPEG stream."""
    screen = Screen(url=args.url)
    if args.output:
        path = screen.capture_to_file(args.output)
        print(f"Saved to {path}")
    elif args.base64:
        print(screen.capture_base64())
    else:
        sys.stdout.buffer.write(screen.capture())


def _cmd_script(args: argparse.Namespace, session: _Session) -> None:
    """Run a sequence of nanokvm-hid commands from a file or stdin."""
    if args.file:
        with open(args.file) as f:
            lines = f.readlines()
    else:
        lines = sys.stdin.readlines()

    parser = build_parser()

    for lineno, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
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

        _dispatch(script_args, session)


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


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    session = _Session(delay=args.delay)

    try:
        _dispatch(args, session)
    except (FileNotFoundError, PermissionError, ConnectionError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
