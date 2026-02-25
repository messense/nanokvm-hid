"""HID mouse and absolute-positioning (touchpad) operations."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from .constants import ABS_COORD_MAX, MouseButton
from .transport import (
    DEFAULT_MOUSE_DEVICE,
    DEFAULT_TOUCHPAD_DEVICE,
    HIDTransport,
)

logger = logging.getLogger(__name__)

# Screen resolution source on NanoKVM (LT6911 HDMI capture chip)
_SCREEN_WIDTH_PATH = "/proc/lt6911_info/width"
_SCREEN_HEIGHT_PATH = "/proc/lt6911_info/height"


def _read_screen_size() -> tuple[int, int]:
    """Read the captured screen resolution from the kernel.

    Returns ``(width, height)`` or ``(1920, 1080)`` as fallback.
    """
    try:
        w = int(Path(_SCREEN_WIDTH_PATH).read_text().strip())
        h = int(Path(_SCREEN_HEIGHT_PATH).read_text().strip())
        return w, h
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.warning("Cannot read screen size (%s), using 1920×1080", exc)
        return 1920, 1080


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class Mouse:
    """High-level HID mouse & touchpad controller.

    The NanoKVM exposes two HID gadgets for pointer control:

    * **Touchpad** (``/dev/hidg2``) – absolute positioning using
      normalised coordinates in the range ``[0.0, 1.0]``.
    * **Mouse** (``/dev/hidg1``) – relative movements, button clicks,
      and scroll wheel.

    Parameters
    ----------
    mouse_device:
        Path to the relative-mouse HID gadget.
    touchpad_device:
        Path to the absolute-positioning HID gadget.
    screen_size:
        ``(width, height)`` of the controlled display, used only for
        debug logging.  If *None*, the size is auto-detected from the
        NanoKVM's HDMI capture chip.
    """

    def __init__(
        self,
        mouse_device: str | Path = DEFAULT_MOUSE_DEVICE,
        touchpad_device: str | Path = DEFAULT_TOUCHPAD_DEVICE,
        screen_size: tuple[int, int] | None = None,
    ) -> None:
        self._mouse = HIDTransport(mouse_device)
        self._touchpad = HIDTransport(touchpad_device)
        if screen_size is not None:
            self._screen_w, self._screen_h = screen_size
        else:
            self._screen_w, self._screen_h = _read_screen_size()

    # ------------------------------------------------------------------
    # Low-level report helpers
    # ------------------------------------------------------------------

    def _send_touchpad(self, x_norm: float, y_norm: float) -> None:
        """Send an absolute-position report.

        *x_norm* and *y_norm* are normalised to ``[0.0, 1.0]``.
        """
        x = int(_clamp(x_norm, 0.0, 1.0) * ABS_COORD_MAX)
        y = int(_clamp(y_norm, 0.0, 1.0) * ABS_COORD_MAX)
        report = bytes([0x00, x & 0xFF, x >> 8, y & 0xFF, y >> 8, 0x00])
        self._touchpad.send(report)
        logger.debug(
            "touchpad  (%.3f, %.3f) → pixel (%d, %d)",
            x_norm, y_norm,
            int(x_norm * self._screen_w),
            int(y_norm * self._screen_h),
        )

    def _send_mouse(
        self,
        buttons: int = 0,
        dx: int = 0,
        dy: int = 0,
        wheel: int = 0,
    ) -> None:
        """Send a 4-byte relative mouse report ``[buttons, dx, dy, wheel]``."""
        report = bytes([buttons, dx & 0xFF, dy & 0xFF, wheel & 0xFF])
        self._mouse.send(report)

    # ------------------------------------------------------------------
    # Movement
    # ------------------------------------------------------------------

    def move(self, x: float, y: float) -> None:
        """Move the cursor to an absolute position.

        Parameters
        ----------
        x, y:
            Normalised screen coordinates in ``[0.0, 1.0]``.
        """
        self._send_touchpad(x, y)
        logger.info(
            "move  (%.3f, %.3f) → pixel (%d, %d)",
            x, y,
            int(x * self._screen_w),
            int(y * self._screen_h),
        )

    # ------------------------------------------------------------------
    # Clicks
    # ------------------------------------------------------------------

    def click(
        self,
        x: float = 0.0,
        y: float = 0.0,
        *,
        button: int = MouseButton.LEFT,
    ) -> None:
        """Move to *(x, y)* and perform a single click.

        Parameters
        ----------
        x, y:
            Normalised coordinates.  ``(0, 0)`` means *don't move*.
        button:
            :data:`MouseButton.LEFT` (1) or :data:`MouseButton.RIGHT` (2).
        """
        if x != 0.0 or y != 0.0:
            self._send_touchpad(x, y)
            time.sleep(0.1)
        self._send_mouse(buttons=button)
        time.sleep(0.05)
        self._send_mouse()  # release
        logger.info("click  btn=%d @ (%.3f, %.3f)", button, x, y)

    def left_click(self, x: float = 0.0, y: float = 0.0) -> None:
        """Left-click at *(x, y)*."""
        self.click(x, y, button=MouseButton.LEFT)

    def right_click(self, x: float = 0.0, y: float = 0.0) -> None:
        """Right-click at *(x, y)*."""
        self.click(x, y, button=MouseButton.RIGHT)

    def double_click(
        self,
        x: float = 0.0,
        y: float = 0.0,
        *,
        button: int = MouseButton.LEFT,
    ) -> None:
        """Double-click at *(x, y)*."""
        if x != 0.0 or y != 0.0:
            self._send_touchpad(x, y)
            time.sleep(0.1)
        # First click
        self._send_mouse(buttons=button)
        time.sleep(0.05)
        self._send_mouse()
        time.sleep(0.1)
        # Second click
        self._send_mouse(buttons=button)
        time.sleep(0.05)
        self._send_mouse()
        logger.info("double_click  btn=%d @ (%.3f, %.3f)", button, x, y)

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------

    def scroll_down(self, steps: int = 1) -> None:
        """Scroll down by *steps* notches."""
        for _ in range(steps):
            # 0xFE = -2 in signed byte → scroll down
            for _ in range(4):
                self._send_mouse(wheel=0xFE)
            time.sleep(0.1)
            self._send_mouse()  # release
        logger.info("scroll_down  steps=%d", steps)

    def scroll_up(self, steps: int = 1) -> None:
        """Scroll up by *steps* notches."""
        for _ in range(steps):
            for _ in range(4):
                self._send_mouse(wheel=0x02)
            time.sleep(0.1)
            self._send_mouse()  # release
        logger.info("scroll_up  steps=%d", steps)

    # ------------------------------------------------------------------
    # Drag
    # ------------------------------------------------------------------

    def drag(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        *,
        step_size: int = 16,
    ) -> None:
        """Drag from *(x0, y0)* to *(x1, y1)* with the left button held.

        The start position uses absolute positioning; the motion path
        uses relative mouse reports so the button state is maintained.

        Parameters
        ----------
        x0, y0:
            Normalised start coordinates.
        x1, y1:
            Normalised end coordinates.
        step_size:
            Maximum pixel displacement per relative report.
        """
        # Move to start
        self._send_touchpad(x0, y0)
        time.sleep(0.1)

        # Press left button
        self._send_mouse(buttons=MouseButton.LEFT)
        time.sleep(0.1)

        # Compute remaining pixel displacement
        dx_remaining = int((x1 - x0) * self._screen_w)
        dy_remaining = int((y1 - y0) * self._screen_h)

        while dx_remaining != 0 or dy_remaining != 0:
            dx = max(-step_size, min(step_size, dx_remaining))
            dy = max(-step_size, min(step_size, dy_remaining))
            self._send_mouse(buttons=MouseButton.LEFT, dx=dx, dy=dy)
            time.sleep(0.01)
            dx_remaining -= dx
            dy_remaining -= dy

        # Release
        self._send_mouse()
        logger.info(
            "drag  (%.3f,%.3f) → (%.3f,%.3f)", x0, y0, x1, y1
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @property
    def screen_size(self) -> tuple[int, int]:
        """The screen dimensions ``(width, height)`` in pixels."""
        return self._screen_w, self._screen_h

    def __repr__(self) -> str:
        return (
            f"Mouse(mouse={self._mouse.device_path!r}, "
            f"touchpad={self._touchpad.device_path!r}, "
            f"screen={self._screen_w}×{self._screen_h})"
        )
