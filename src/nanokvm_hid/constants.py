"""HID keycodes, modifier masks, and character mapping tables."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Standard HID keyboard usage codes (USB HID Usage Tables §10)
# ---------------------------------------------------------------------------
# fmt: off
KEYCODES: dict[str, int] = {
    # Letters
    "A": 0x04, "B": 0x05, "C": 0x06, "D": 0x07, "E": 0x08,
    "F": 0x09, "G": 0x0A, "H": 0x0B, "I": 0x0C, "J": 0x0D,
    "K": 0x0E, "L": 0x0F, "M": 0x10, "N": 0x11, "O": 0x12,
    "P": 0x13, "Q": 0x14, "R": 0x15, "S": 0x16, "T": 0x17,
    "U": 0x18, "V": 0x19, "W": 0x1A, "X": 0x1B, "Y": 0x1C,
    "Z": 0x1D,
    # Digits
    "1": 0x1E, "2": 0x1F, "3": 0x20, "4": 0x21, "5": 0x22,
    "6": 0x23, "7": 0x24, "8": 0x25, "9": 0x26, "0": 0x27,
    # Symbols (unshifted)
    "`": 0x35, "-": 0x2D, "=": 0x2E, "[": 0x2F, "]": 0x30,
    "\\": 0x31, ";": 0x33, "'": 0x34, ",": 0x36, ".": 0x37,
    "/": 0x38,
    # Control keys
    "ENTER": 0x28, "ESCAPE": 0x29, "BACKSPACE": 0x2A, "TAB": 0x2B,
    "SPACE": 0x2C, "CAPS_LOCK": 0x39, "DELETE": 0x4C, "INSERT": 0x49,
    # Function keys
    "F1": 0x3A, "F2": 0x3B, "F3": 0x3C, "F4": 0x3D,
    "F5": 0x3E, "F6": 0x3F, "F7": 0x40, "F8": 0x41,
    "F9": 0x42, "F10": 0x43, "F11": 0x44, "F12": 0x45,
    # Navigation
    "PRINT_SCREEN": 0x46, "SCROLL_LOCK": 0x47, "PAUSE": 0x48,
    "HOME": 0x4A, "PAGE_UP": 0x4B, "END": 0x4D, "PAGE_DOWN": 0x4E,
    "RIGHT_ARROW": 0x4F, "LEFT_ARROW": 0x50,
    "DOWN_ARROW": 0x51, "UP_ARROW": 0x52,
    # Modifier keys (also have keycodes for standalone press)
    "LEFT_CONTROL": 0xE0, "LEFT_SHIFT": 0xE1, "LEFT_ALT": 0xE2,
    "LEFT_GUI": 0xE3, "RIGHT_CONTROL": 0xE4, "RIGHT_SHIFT": 0xE5,
    "RIGHT_ALT": 0xE6, "RIGHT_GUI": 0xE7,
}

MODIFIER_MASKS: dict[str, int] = {
    # Generic aliases
    "CTRL": 0x01, "SHIFT": 0x02, "ALT": 0x04, "GUI": 0x08,
    "CONTROL": 0x01, "WIN": 0x08, "SUPER": 0x08, "META": 0x08,
    "COMMAND": 0x08, "CMD": 0x08,
    # Explicit side
    "LEFT_CTRL": 0x01, "LEFT_CONTROL": 0x01, "LEFT_SHIFT": 0x02,
    "LEFT_ALT": 0x04, "LEFT_GUI": 0x08,
    "RIGHT_CTRL": 0x10, "RIGHT_CONTROL": 0x10, "RIGHT_SHIFT": 0x20,
    "RIGHT_ALT": 0x40, "RIGHT_GUI": 0x80,
}

CONSUMER_CODES: dict[str, int] = {
    # Media
    "PLAY_PAUSE": 0xCD, "SCAN_NEXT_TRACK": 0xB5,
    "SCAN_PREVIOUS_TRACK": 0xB6, "STOP": 0xB7,
    "FAST_FORWARD": 0xB3, "REWIND": 0xB4, "RECORD": 0xB2,
    # Volume
    "VOLUME_UP": 0xE9, "VOLUME_DOWN": 0xEA, "MUTE": 0xE2,
    # Power
    "POWER": 0x30, "SYSTEM_SLEEP": 0x32, "WAKE": 0x33,
    # Browser / applications
    "BROWSER_HOME": 0x223, "BROWSER_BACK": 0x224,
    "BROWSER_FORWARD": 0x225, "BROWSER_REFRESH": 0x227,
    "BROWSER_BOOKMARKS": 0x22A,
    # System shortcuts
    "CALCULATOR": 0x192, "EMAIL": 0x18A,
    "BROWSER": 0x196, "FILE_EXPLORER": 0x194,
}
# fmt: on

# ---------------------------------------------------------------------------
# Character‑to‑key descriptor mapping (for typestr)
# ---------------------------------------------------------------------------
# Characters that can be typed *without* Shift
_UNSHIFTED_CHARS = "`1234567890-=qwertyuiop[]\\asdfghjkl;'zxcvbnm,./"
# Characters that require Shift (parallel to _UNSHIFTED_CHARS base keys)
_SHIFTED_CHARS = '~!@#$%^&*()_+QWERTYUIOP{}|ASDFGHJKL:"ZXCVBNM<>?'
# The key descriptor (upper‑case letter of the *unshifted* key)
_KEY_DESCRIPTORS = "`1234567890-=QWERTYUIOP[]\\ASDFGHJKL;'ZXCVBNM,./"


def char_to_key_descriptor(char: str) -> str | None:
    """Map a single printable ASCII character to a HID key descriptor.

    Returns a string like ``"A"`` or ``"SHIFT+A"`` that can be passed to
    :func:`keyboard.parse_combo`, or ``None`` if the character is not
    representable.
    """
    if char == " ":
        return "SPACE"
    idx = _UNSHIFTED_CHARS.find(char)
    if idx != -1:
        return _KEY_DESCRIPTORS[idx]
    idx = _SHIFTED_CHARS.find(char)
    if idx != -1:
        return f"SHIFT+{_KEY_DESCRIPTORS[idx]}"
    return None


# ---------------------------------------------------------------------------
# Mouse button values
# ---------------------------------------------------------------------------


class MouseButton:
    """Mouse button constants for the HID report."""

    NONE = 0
    LEFT = 1
    RIGHT = 2


# ---------------------------------------------------------------------------
# HID report sizes
# ---------------------------------------------------------------------------
KEYBOARD_REPORT_SIZE = 8  # 8-byte boot keyboard report
CONSUMER_REPORT_SIZE = 2  # 2-byte consumer control report
MOUSE_REPORT_SIZE = 4  # [buttons, dx, dy, wheel]
TOUCHPAD_REPORT_SIZE = 6  # [0x00, x_lo, x_hi, y_lo, y_hi, 0x00]

# Absolute coordinate range for the touchpad HID descriptor (0–0x7FFF)
ABS_COORD_MAX = 0x7FFF
