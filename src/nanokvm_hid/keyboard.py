"""HID keyboard and typing operations."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .constants import (
    CONSUMER_CODES,
    KEYBOARD_REPORT_SIZE,
    KEYCODES,
    MODIFIER_MASKS,
    char_to_key_descriptor,
)
from .transport import DEFAULT_KEYBOARD_DEVICE, HIDTransport

logger = logging.getLogger(__name__)


def parse_combo(key_combo: str) -> tuple[int, int | None, bool]:
    """Parse a key combination string into HID components.

    Parameters
    ----------
    key_combo:
        A string such as ``"a"``, ``"CTRL+SHIFT+A"``, ``"F11"``,
        ``"VOLUME_UP"``.

    Returns
    -------
    tuple of (modifier_mask, keycode | None, is_consumer_key)

    Raises
    ------
    ValueError
        If any component of the combo is unrecognised.
    """
    parts = [p.strip().upper() for p in key_combo.split("+")]
    modifier_mask = 0
    main_key: int | None = None
    is_consumer = False

    for part in parts:
        if part in MODIFIER_MASKS:
            modifier_mask |= MODIFIER_MASKS[part]
        elif part in KEYCODES:
            if main_key is not None:
                raise ValueError(f"Multiple non-modifier keys in combo {key_combo!r}")
            main_key = KEYCODES[part]
        elif part in CONSUMER_CODES:
            if main_key is not None:
                raise ValueError(f"Multiple non-modifier keys in combo {key_combo!r}")
            main_key = CONSUMER_CODES[part]
            is_consumer = True
        else:
            raise ValueError(f"Unknown key {part!r} in combo {key_combo!r}")

    return modifier_mask, main_key, is_consumer


def _build_keyboard_reports(modifier_mask: int, keycode: int | None) -> list[bytes]:
    """Build the press-then-release sequence for a standard keyboard key."""
    if keycode is None:
        # Modifier-only press (e.g. just "SHIFT")
        return [
            bytes([modifier_mask, 0, 0, 0, 0, 0, 0, 0]),
            bytes(KEYBOARD_REPORT_SIZE),
        ]
    if modifier_mask == 0:
        # Single key, no modifiers
        return [
            bytes([0, 0, keycode, 0, 0, 0, 0, 0]),
            bytes(KEYBOARD_REPORT_SIZE),
        ]
    # Combo: press modifier → press modifier+key → release key → release all
    return [
        bytes([modifier_mask, 0, 0, 0, 0, 0, 0, 0]),
        bytes([modifier_mask, 0, keycode, 0, 0, 0, 0, 0]),
        bytes([modifier_mask, 0, 0, 0, 0, 0, 0, 0]),
        bytes(KEYBOARD_REPORT_SIZE),
    ]


def _build_consumer_reports(keycode: int) -> list[bytes]:
    """Build the press-then-release for a consumer-control (media) key."""
    return [
        bytes([keycode & 0xFF, (keycode >> 8) & 0xFF]),
        bytes(2),
    ]


class Keyboard:
    """High-level HID keyboard controller.

    Parameters
    ----------
    device:
        Path to the HID keyboard gadget device.
    inter_report_delay:
        Seconds to wait between individual HID reports within a single
        key press sequence.  Increase if the target machine drops
        keystrokes.
    """

    def __init__(
        self,
        device: str | Path = DEFAULT_KEYBOARD_DEVICE,
        inter_report_delay: float = 0.02,
    ) -> None:
        self._transport = HIDTransport(device)
        self.inter_report_delay = inter_report_delay

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def press(self, key_combo: str) -> None:
        """Send a key combination.

        Examples::

            kb.press("a")
            kb.press("CTRL+C")
            kb.press("ALT+F4")
            kb.press("VOLUME_UP")
        """
        modifier_mask, keycode, is_consumer = parse_combo(key_combo)

        if is_consumer:
            if keycode is None:
                raise ValueError("Consumer key combo resolved to no keycode")
            reports = _build_consumer_reports(keycode)
        else:
            reports = _build_keyboard_reports(modifier_mask, keycode)

        for report in reports:
            self._transport.send(report)
            time.sleep(self.inter_report_delay)

        logger.info("key  %s", key_combo)

    # ------------------------------------------------------------------
    # Typing helpers
    # ------------------------------------------------------------------

    def type(self, text: str, *, inter_key_delay: float = 0.0) -> None:
        """Type a string of printable ASCII characters.

        Non-printable characters are silently skipped.  Use :meth:`press`
        for control keys like ``ENTER`` or ``TAB``.

        Parameters
        ----------
        text:
            The string to type.
        inter_key_delay:
            Additional delay between characters (on top of
            ``inter_report_delay``).

        Raises
        ------
        ValueError
            If *text* contains a character that cannot be mapped to a
            HID keycode.
        """
        for char in text:
            descriptor = char_to_key_descriptor(char)
            if descriptor is None:
                raise ValueError(
                    f"Character {char!r} (U+{ord(char):04X}) cannot be typed "
                    "via HID. Use Keyboard.press() for control keys."
                )
            self.press(descriptor)
            if inter_key_delay > 0:
                time.sleep(inter_key_delay)

    def backspace(self, count: int = 1) -> None:
        """Press the Backspace key *count* times."""
        for _ in range(count):
            self.press("BACKSPACE")

    # ------------------------------------------------------------------
    # Convenience shortcuts
    # ------------------------------------------------------------------

    def enter(self) -> None:
        """Press Enter."""
        self.press("ENTER")

    def tab(self) -> None:
        """Press Tab."""
        self.press("TAB")

    def escape(self) -> None:
        """Press Escape."""
        self.press("ESCAPE")

    def hotkey(self, *keys: str) -> None:
        """Press a key combination specified as separate arguments.

        Example::

            kb.hotkey("CTRL", "SHIFT", "A")
            # equivalent to kb.press("CTRL+SHIFT+A")
        """
        self.press("+".join(keys))

    def __repr__(self) -> str:
        return f"Keyboard({self._transport.device_path!r})"
