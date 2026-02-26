"""Mouse jiggler to prevent the target machine from sleeping.

Periodically sends small mouse movements via HID to keep the target
machine awake, without affecting user interaction.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

from .transport import DEFAULT_MOUSE_DEVICE, DEFAULT_TOUCHPAD_DEVICE, HIDTransport

logger = logging.getLogger(__name__)

_CONFIG_FILE = "/etc/kvm/mouse-jiggler"
_DEFAULT_INTERVAL = 15.0  # seconds, matches the Go server


class Jiggler:
    """Mouse jiggler — prevents the target machine from sleeping.

    Sends periodic small mouse movements via HID.  Supports two modes:

    * **relative** (default) — sends tiny relative movements that
      are barely perceptible (±10 px each way).
    * **absolute** — moves to two fixed points alternately using the
      touchpad device.

    The jiggler runs in a background thread and can be started/stopped
    at any time.  State is persisted to ``/etc/kvm/mouse-jiggler``
    so it survives reboots.

    Parameters
    ----------
    mouse_device:
        Path to the relative-mouse HID gadget.
    touchpad_device:
        Path to the absolute-positioning HID gadget.
    interval:
        Seconds between jiggle movements.

    Examples::

        jiggler = Jiggler()
        jiggler.start()                  # default relative mode
        jiggler.start(mode="absolute")   # absolute mode
        jiggler.is_running                # True
        jiggler.stop()
    """

    def __init__(
        self,
        mouse_device: str = DEFAULT_MOUSE_DEVICE,
        touchpad_device: str = DEFAULT_TOUCHPAD_DEVICE,
        interval: float = _DEFAULT_INTERVAL,
    ) -> None:
        self._mouse = HIDTransport(mouse_device)
        self._touchpad = HIDTransport(touchpad_device)
        self._interval = interval
        self._mode = "relative"
        self._enabled = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Restore state from config file
        self._load_config()

    def _load_config(self) -> None:
        """Load persisted jiggler state."""
        try:
            content = Path(_CONFIG_FILE).read_text().strip()
            if content:
                self._mode = content
                self._enabled = True
        except (FileNotFoundError, OSError):
            pass

    def _save_config(self) -> None:
        """Persist jiggler state to disk."""
        try:
            Path(_CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
            Path(_CONFIG_FILE).write_text(self._mode)
        except OSError as exc:
            logger.warning("Cannot save jiggler config: %s", exc)

    def _remove_config(self) -> None:
        """Remove persisted config."""
        try:
            os.remove(_CONFIG_FILE)
        except FileNotFoundError:
            pass
        except OSError as exc:
            logger.warning("Cannot remove jiggler config: %s", exc)

    def _jiggle(self) -> None:
        """Perform one jiggle movement."""
        if self._mode == "absolute":
            # Move to two different absolute positions
            self._touchpad.send(bytes([0x00, 0x00, 0x3F, 0x00, 0x3F, 0x00]))
            time.sleep(0.1)
            self._touchpad.send(bytes([0x00, 0xFF, 0x3F, 0xFF, 0x3F, 0x00]))
        else:
            # Small relative movement: +10, +10 then -10, -10
            self._mouse.send(bytes([0x00, 0x0A, 0x0A, 0x00]))
            time.sleep(0.1)
            self._mouse.send(bytes([0x00, 0xF6, 0xF6, 0x00]))

    def _run(self) -> None:
        """Background thread loop."""
        logger.info(
            "jiggler started (mode=%s, interval=%.1fs)",
            self._mode,
            self._interval,
        )
        while not self._stop_event.wait(self._interval):
            if not self._enabled:
                break
            try:
                self._jiggle()
            except OSError as exc:
                logger.error("jiggle failed: %s", exc)

    def start(self, mode: str = "relative") -> None:
        """Start the mouse jiggler.

        Parameters
        ----------
        mode:
            ``"relative"`` (default) or ``"absolute"``.
        """
        if mode not in ("relative", "absolute"):
            raise ValueError(
                f"Invalid jiggler mode: {mode!r} (use 'relative' or 'absolute')"
            )

        self._mode = mode
        self._enabled = True
        self._save_config()

        if self._thread is not None and self._thread.is_alive():
            logger.info("jiggler already running, updating mode to %s", mode)
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the mouse jiggler."""
        self._enabled = False
        self._stop_event.set()
        self._remove_config()

        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

        logger.info("jiggler stopped")

    @property
    def is_running(self) -> bool:
        """Return ``True`` if the jiggler thread is active."""
        return self._thread is not None and self._thread.is_alive()

    @property
    def mode(self) -> str:
        """The current jiggler mode (``"relative"`` or ``"absolute"``)."""
        return self._mode

    @property
    def enabled(self) -> bool:
        """Whether the jiggler is enabled (may be persisted but not yet started)."""
        return self._enabled

    def __repr__(self) -> str:
        status = "running" if self.is_running else "stopped"
        return f"Jiggler(mode={self._mode!r}, {status})"
