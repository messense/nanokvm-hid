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
from .keyboard import Keyboard, parse_combo
from .mouse import Mouse
from .screen import Screen
from .transport import (
    DEFAULT_KEYBOARD_DEVICE,
    DEFAULT_MOUSE_DEVICE,
    DEFAULT_TOUCHPAD_DEVICE,
    HIDTransport,
)

__all__ = [
    # High-level API
    "Keyboard",
    "Mouse",
    "Screen",
    # Lower-level
    "HIDTransport",
    "parse_combo",
    # Constants
    "MouseButton",
    "KEYCODES",
    "MODIFIER_MASKS",
    "CONSUMER_CODES",
    # Device defaults
    "DEFAULT_KEYBOARD_DEVICE",
    "DEFAULT_MOUSE_DEVICE",
    "DEFAULT_TOUCHPAD_DEVICE",
]

__version__ = "0.1.1"
