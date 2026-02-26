"""nanokvm-hid — Python library for HID control via NanoKVM Pro.

Quick start::

    from nanokvm_hid import Keyboard, Mouse

    kb = Keyboard()
    mouse = Mouse()

    mouse.left_click(0.5, 0.5)     # click center of screen
    kb.type("hello world")         # type a string
    kb.press("ENTER")              # press Enter
    kb.hotkey("CTRL", "S")         # Ctrl+S
    mouse.scroll_down(3)           # scroll down
"""

from __future__ import annotations

from .constants import CONSUMER_CODES, KEYCODES, MODIFIER_MASKS, MouseButton
from .gpio import GPIO
from .hdmi import HDMI
from .hid_manager import get_hid_mode, reset_hid, set_hid_mode
from .jiggler import Jiggler
from .keyboard import Keyboard, parse_combo
from .mouse import Mouse
from .screen import Screen
from .storage import Storage
from .stream import (
    RATE_CONTROL_CBR,
    RATE_CONTROL_VBR,
    STREAM_MODE_H264_DIRECT,
    STREAM_MODE_H264_WEBRTC,
    STREAM_MODE_H265_DIRECT,
    STREAM_MODE_H265_WEBRTC,
    STREAM_MODE_MJPEG,
    Stream,
    VideoFrame,
)
from .transport import (
    DEFAULT_KEYBOARD_DEVICE,
    DEFAULT_MOUSE_DEVICE,
    DEFAULT_TOUCHPAD_DEVICE,
    HIDTransport,
)
from .virtual_devices import VirtualDevices
from .wol import wake_on_lan

__all__ = [
    # High-level API
    "Keyboard",
    "Mouse",
    "Screen",
    # KVM device control
    "GPIO",
    "HDMI",
    "Jiggler",
    "Storage",
    "Stream",
    "VideoFrame",
    "VirtualDevices",
    # HID management
    "get_hid_mode",
    "reset_hid",
    "set_hid_mode",
    # Network
    "wake_on_lan",
    # Lower-level
    "HIDTransport",
    "parse_combo",
    # Constants
    "MouseButton",
    "KEYCODES",
    "MODIFIER_MASKS",
    "CONSUMER_CODES",
    "RATE_CONTROL_CBR",
    "RATE_CONTROL_VBR",
    "STREAM_MODE_MJPEG",
    "STREAM_MODE_H264_WEBRTC",
    "STREAM_MODE_H264_DIRECT",
    "STREAM_MODE_H265_WEBRTC",
    "STREAM_MODE_H265_DIRECT",
    # Device defaults
    "DEFAULT_KEYBOARD_DEVICE",
    "DEFAULT_MOUSE_DEVICE",
    "DEFAULT_TOUCHPAD_DEVICE",
]

__version__ = "0.2.0"
