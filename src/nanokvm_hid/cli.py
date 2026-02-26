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
    elif cmd == "power":
        _cmd_power(args)
    elif cmd == "reset-button":
        _cmd_reset_button(args)
    elif cmd == "power-led":
        _cmd_power_led()
    elif cmd == "hdd-led":
        _cmd_hdd_led()
    elif cmd == "storage":
        _dispatch_storage(args)
    elif cmd == "jiggler":
        _dispatch_jiggler(args)
    elif cmd == "hdmi":
        _dispatch_hdmi(args)
    elif cmd == "hid-reset":
        _cmd_hid_reset()
    elif cmd == "hid-mode":
        _cmd_hid_mode(args)
    elif cmd == "wol":
        _cmd_wol(args)
    elif cmd == "virtual-device":
        _dispatch_virtual_device(args)
    elif cmd == "stream":
        _dispatch_stream(args)


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


# ── Device info ──────────────────────────────────────────────────────


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


# ── Capture ──────────────────────────────────────────────────────────


def _cmd_capture(args: argparse.Namespace) -> None:
    """Capture a screenshot."""
    screen = Screen(
        url=args.url,
        pikvm=args.pikvm,
        pikvm_username=args.pikvm_username,
        pikvm_password=args.pikvm_password,
    )
    if args.output:
        path = screen.capture_to_file(args.output)
        print(f"Saved to {path}")
    elif args.base64:
        print(screen.capture_base64())
    else:
        sys.stdout.buffer.write(screen.capture())


# ── Script ───────────────────────────────────────────────────────────


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


# ── GPIO: power / reset / LEDs ──────────────────────────────────────


def _cmd_power(args: argparse.Namespace) -> None:
    """Press the power button on the target machine."""
    from .gpio import GPIO

    gpio = GPIO()
    gpio.power(duration_ms=args.duration)
    print(f"Power button pressed ({args.duration} ms)")


def _cmd_reset_button(args: argparse.Namespace) -> None:
    """Press the reset button on the target machine."""
    from .gpio import GPIO

    gpio = GPIO()
    gpio.reset(duration_ms=args.duration)
    print(f"Reset button pressed ({args.duration} ms)")


def _cmd_power_led() -> None:
    """Read the power LED status."""
    from .gpio import GPIO

    gpio = GPIO()
    state = gpio.power_led()
    print(f"Power LED: {'on' if state else 'off'}")
    if not state:
        sys.exit(1)


def _cmd_hdd_led() -> None:
    """Read the HDD LED status."""
    from .gpio import GPIO

    gpio = GPIO()
    state = gpio.hdd_led()
    print(f"HDD LED: {'on' if state else 'off'}")


# ── Storage ──────────────────────────────────────────────────────────


def _dispatch_storage(args: argparse.Namespace) -> None:
    """Dispatch storage subcommands."""
    from .storage import Storage

    storage = Storage()
    sub = args.storage_command

    if sub == "list":
        images = storage.list_images()
        if not images:
            print("No images found")
        else:
            for img in images:
                print(img)
    elif sub == "mount":
        storage.mount(args.file, cdrom=args.cdrom, read_only=args.read_only)
        cdrom_str = " (cdrom)" if args.cdrom else ""
        ro_str = " (read-only)" if args.read_only else ""
        print(f"Mounted: {args.file}{cdrom_str}{ro_str}")
    elif sub == "unmount":
        storage.unmount()
        print("Unmounted")
    elif sub == "status":
        info = storage.mounted()
        if info is None:
            print("No image mounted")
        else:
            flags = []
            if info["cdrom"]:
                flags.append("cdrom")
            if info["read_only"]:
                flags.append("read-only")
            flag_str = f" ({', '.join(flags)})" if flags else ""
            print(f"Mounted: {info['file']}{flag_str}")


# ── Jiggler ──────────────────────────────────────────────────────────


def _dispatch_jiggler(args: argparse.Namespace) -> None:
    """Dispatch jiggler subcommands."""
    from .jiggler import Jiggler

    sub = args.jiggler_command

    if sub == "on":
        jiggler = Jiggler()
        jiggler.start(mode=args.mode)
        print(f"Mouse jiggler started (mode={args.mode})")
        # Keep running in foreground
        try:
            while jiggler.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            jiggler.stop()
            print("\nMouse jiggler stopped")
    elif sub == "off":
        jiggler = Jiggler()
        jiggler.stop()
        print("Mouse jiggler stopped")
    elif sub == "status":
        jiggler = Jiggler()
        status = "running" if jiggler.enabled else "stopped"
        print(f"Mouse jiggler: {status} (mode={jiggler.mode})")


# ── HDMI ─────────────────────────────────────────────────────────────


def _dispatch_hdmi(args: argparse.Namespace) -> None:
    """Dispatch HDMI subcommands."""
    from .hdmi import HDMI

    hdmi = HDMI()
    sub = args.hdmi_command

    if sub == "status":
        capture = "on" if hdmi.capture_enabled else "off"
        passthrough = "on" if hdmi.passthrough_enabled else "off"
        edid = hdmi.current_edid
        print(f"  Capture:     {capture}")
        print(f"  Passthrough: {passthrough}")
        print(f"  EDID:        {edid}")
    elif sub == "capture":
        hdmi.set_capture(args.state == "on")
        print(f"HDMI capture {args.state}")
    elif sub == "passthrough":
        hdmi.set_passthrough(args.state == "on")
        print(f"HDMI passthrough {args.state}")
    elif sub == "edid":
        if args.edid_command == "list":
            edids = hdmi.list_edids()
            current = hdmi.current_edid
            for e in edids:
                marker = " ← active" if e == current else ""
                print(f"  {e}{marker}")
        elif args.edid_command == "switch":
            hdmi.switch_edid(args.profile)
            print(f"Switched EDID to {args.profile}")
        elif args.edid_command == "current":
            print(hdmi.current_edid)


# ── HID management ──────────────────────────────────────────────────


def _cmd_hid_reset() -> None:
    """Reset HID devices."""
    from .hid_manager import reset_hid

    print("Resetting HID devices...")
    reset_hid()
    print("HID devices reset")


def _cmd_hid_mode(args: argparse.Namespace) -> None:
    """Get or set HID mode."""
    from .hid_manager import get_hid_mode, set_hid_mode

    if args.mode:
        print(f"Switching HID mode to {args.mode}...")
        set_hid_mode(args.mode)
        print(f"HID mode: {args.mode}")
    else:
        print(f"HID mode: {get_hid_mode()}")


# ── Wake on LAN ─────────────────────────────────────────────────────


def _cmd_wol(args: argparse.Namespace) -> None:
    """Send a Wake-on-LAN magic packet."""
    from .wol import wake_on_lan

    wake_on_lan(args.mac)
    print(f"WoL packet sent to {args.mac}")


# ── Virtual devices ─────────────────────────────────────────────────


def _dispatch_virtual_device(args: argparse.Namespace) -> None:
    """Dispatch virtual-device subcommands."""
    from .virtual_devices import VirtualDevices

    vdev = VirtualDevices()
    sub = args.vdev_command

    if sub == "status":
        status = vdev.status()
        print(f"  Network:    {'enabled' if status['network'] else 'disabled'}")
        print(f"  Microphone: {'enabled' if status['mic'] else 'disabled'}")
        disk = status["disk"] or "disabled"
        print(f"  Disk:       {disk}")
        print(f"  SD card:    {'present' if status['sd_card_present'] else 'absent'}")
        print(f"  eMMC:       {'present' if status['emmc_present'] else 'absent'}")
    elif sub == "network":
        enabled = vdev.toggle_network()
        print(f"Virtual network {'enabled' if enabled else 'disabled'}")
    elif sub == "mic":
        enabled = vdev.toggle_mic()
        print(f"Virtual microphone {'enabled' if enabled else 'disabled'}")
    elif sub == "disk":
        vdev.set_disk(args.type)
        print(f"Virtual disk: {args.type or 'disabled'}")


def _dispatch_stream(args: argparse.Namespace) -> None:
    """Dispatch stream subcommands."""
    from .stream import Stream

    stream = Stream()
    sub = args.stream_command

    if sub == "status":
        info = stream.status()
        res = info["resolution"]
        print(f"  FPS:          {info['fps']} (0 = auto)")
        print(f"  GOP:          {info['gop']}")
        print(f"  Bitrate:      {info['bitrate']} kbps")
        print(f"  Resolution:   {res['width']}×{res['height']}")
        print(f"  Captured FPS: {info['captured_fps']}")

    elif sub == "fps":
        stream.set_fps(args.value)
        print(f"FPS set to {args.value}")

    elif sub == "gop":
        stream.set_gop(args.value)
        print(f"GOP set to {args.value}")

    elif sub == "quality":
        stream.set_quality(args.value)
        print(f"Quality set to {args.value}")

    elif sub == "bitrate":
        stream.set_bitrate(args.value)
        print(f"Bitrate set to {args.value} kbps")

    elif sub == "rate-control":
        stream.set_rate_control(args.mode)
        print(f"Rate control set to {args.mode.upper()}")

    elif sub == "record":
        desc = args.codec.upper()
        if args.duration:
            desc += f", {args.duration}s"
        elif args.frames:
            desc += f", {args.frames} frames"
        else:
            desc += ", press Ctrl+C to stop"
        print(f"Recording {desc} → {args.output}")

        try:
            result = stream.record(
                args.output,
                codec=args.codec,
                max_frames=args.frames,
                duration=args.duration,
                timeout=args.timeout,
            )
            mb = result["bytes"] / (1024 * 1024)
            print(f"  {result['frames']} frames, {mb:.1f} MB, {result['duration']}s")
        except KeyboardInterrupt:
            import os

            print()
            if os.path.exists(args.output):
                size = os.path.getsize(args.output)
                mb = size / (1024 * 1024)
                print(f"  Stopped — {mb:.1f} MB saved to {args.output}")

    elif sub == "mode":
        stream.set_mode(args.mode)
        print(f"Stream mode set to {args.mode}")


# ── Parser ───────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nanokvm-hid",
        description="Control keyboard, mouse, and KVM features on NanoKVM Pro.",
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
    p.add_argument(
        "--pikvm",
        action="store_true",
        help="Use PiKVM snapshot API instead of MJPEG stream",
    )
    p.add_argument(
        "--pikvm-username",
        default="admin",
        help="PiKVM Basic Auth username (default: admin)",
    )
    p.add_argument(
        "--pikvm-password",
        default="admin",
        help="PiKVM Basic Auth password (default: admin)",
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

    # ── power ────────────────────────────────────────────────────
    p = sub.add_parser("power", help="Press the power button on the target machine")
    p.add_argument(
        "--duration",
        type=int,
        default=800,
        help="Button press duration in ms (default: 800, use 5000 for force-off)",
    )

    # ── reset-button ─────────────────────────────────────────────
    p = sub.add_parser(
        "reset-button",
        help="Press the reset button on the target machine",
    )
    p.add_argument(
        "--duration",
        type=int,
        default=800,
        help="Button press duration in ms (default: 800)",
    )

    # ── power-led / hdd-led ──────────────────────────────────────
    sub.add_parser("power-led", help="Read power LED state (exit code 1 if off)")
    sub.add_parser("hdd-led", help="Read HDD activity LED state")

    # ── storage ──────────────────────────────────────────────────
    storage_parser = sub.add_parser("storage", help="USB virtual media (ISO/IMG)")
    ssub = storage_parser.add_subparsers(dest="storage_command", required=True)

    ssub.add_parser("list", help="List available images")
    ssub.add_parser("status", help="Show currently mounted image")
    ssub.add_parser("unmount", help="Unmount the current image")

    p = ssub.add_parser("mount", help="Mount an ISO/IMG file")
    p.add_argument("file", help="Path to image file (e.g. /data/ubuntu.iso)")
    p.add_argument("--cdrom", action="store_true", help="Emulate CD-ROM drive")
    p.add_argument("--read-only", action="store_true", help="Mount as read-only")

    # ── jiggler ──────────────────────────────────────────────────
    jiggler_parser = sub.add_parser("jiggler", help="Mouse jiggler (prevent sleep)")
    jsub = jiggler_parser.add_subparsers(dest="jiggler_command", required=True)

    p = jsub.add_parser("on", help="Start the mouse jiggler")
    p.add_argument(
        "--mode",
        choices=["relative", "absolute"],
        default="relative",
        help="Jiggle mode (default: relative)",
    )
    jsub.add_parser("off", help="Stop the mouse jiggler")
    jsub.add_parser("status", help="Show jiggler status")

    # ── hdmi ─────────────────────────────────────────────────────
    hdmi_parser = sub.add_parser("hdmi", help="HDMI capture and passthrough control")
    hsub = hdmi_parser.add_subparsers(dest="hdmi_command", required=True)

    hsub.add_parser("status", help="Show HDMI status")

    p = hsub.add_parser("capture", help="Enable/disable HDMI capture")
    p.add_argument("state", choices=["on", "off"], help="on or off")

    p = hsub.add_parser("passthrough", help="Enable/disable HDMI passthrough")
    p.add_argument("state", choices=["on", "off"], help="on or off")

    edid_parser = hsub.add_parser("edid", help="EDID profile management")
    esub = edid_parser.add_subparsers(dest="edid_command", required=True)
    esub.add_parser("list", help="List available EDID profiles")
    esub.add_parser("current", help="Show current EDID profile")
    p = esub.add_parser("switch", help="Switch EDID profile")
    p.add_argument("profile", help="EDID profile name")

    # ── hid-reset ────────────────────────────────────────────────
    sub.add_parser("hid-reset", help="Reset HID USB gadget devices")

    # ── hid-mode ─────────────────────────────────────────────────
    p = sub.add_parser("hid-mode", help="Get or set HID USB mode")
    p.add_argument(
        "mode",
        nargs="?",
        choices=["normal", "hid-only"],
        default=None,
        help="Set mode (omit to show current mode)",
    )

    # ── wol ──────────────────────────────────────────────────────
    p = sub.add_parser("wol", help="Send Wake-on-LAN magic packet")
    p.add_argument("mac", help="MAC address (e.g. AA:BB:CC:DD:EE:FF)")

    # ── virtual-device ───────────────────────────────────────────
    vdev_parser = sub.add_parser(
        "virtual-device",
        help="Virtual USB device management",
    )
    vsub = vdev_parser.add_subparsers(
        dest="vdev_command",
        required=True,
    )

    vsub.add_parser("status", help="Show virtual device status")
    vsub.add_parser(
        "network",
        help="Toggle virtual network adapter (USB NCM)",
    )
    vsub.add_parser(
        "mic",
        help="Toggle virtual microphone (USB UAC2)",
    )
    p = vsub.add_parser("disk", help="Set virtual disk source")
    p.add_argument(
        "type",
        nargs="?",
        choices=["sdcard", "emmc"],
        default=None,
        help="Disk source (omit to disable)",
    )

    # ── stream ───────────────────────────────────────────────────
    stream_parser = sub.add_parser(
        "stream",
        help="Video stream encoder control",
    )
    strsub = stream_parser.add_subparsers(
        dest="stream_command",
        required=True,
    )

    strsub.add_parser("status", help="Show current stream encoder status")

    p = strsub.add_parser("fps", help="Set encoder FPS")
    p.add_argument(
        "value",
        type=int,
        help="FPS (0=auto, 1–120)",
    )

    p = strsub.add_parser("gop", help="Set encoder GOP length")
    p.add_argument("value", type=int, help="GOP length (1–200)")

    p = strsub.add_parser("quality", help="Set MJPEG quality")
    p.add_argument("value", type=int, help="Quality (1–100)")

    p = strsub.add_parser("bitrate", help="Set H264/H265 bitrate")
    p.add_argument("value", type=int, help="Bitrate in kbps (1000–20000)")

    p = strsub.add_parser(
        "rate-control",
        help="Set rate-control mode",
    )
    p.add_argument(
        "mode",
        choices=["cbr", "vbr"],
        help="cbr or vbr",
    )

    p = strsub.add_parser("mode", help="Set stream mode")
    p.add_argument(
        "mode",
        choices=[
            "mjpeg",
            "h264-webrtc",
            "h264-direct",
            "h265-webrtc",
            "h265-direct",
        ],
        help="Stream mode",
    )

    p = strsub.add_parser("record", help="Record raw video stream to file")
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file path (e.g. recording.h264)",
    )
    p.add_argument(
        "--codec",
        choices=["h264", "h265"],
        default="h264",
        help="Video codec (default: h264)",
    )
    p.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Record for N seconds",
    )
    p.add_argument(
        "--frames",
        type=int,
        default=None,
        help="Record N frames",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Per-frame timeout in seconds (default: 10)",
    )

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
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
