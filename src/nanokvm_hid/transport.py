"""Low-level transport for writing HID reports to Linux gadget device files."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default NanoKVM HID gadget device paths
DEFAULT_KEYBOARD_DEVICE = "/dev/hidg0"
DEFAULT_MOUSE_DEVICE = "/dev/hidg1"
DEFAULT_TOUCHPAD_DEVICE = "/dev/hidg2"


class HIDTransport:
    """Write raw HID reports to a ``/dev/hidgN`` device file.

    Parameters
    ----------
    device_path:
        Path to the HID gadget character device (e.g. ``/dev/hidg0``).
    """

    def __init__(self, device_path: str | Path) -> None:
        self.device_path = Path(device_path)

    def send(self, report: bytes | bytearray) -> None:
        """Write a single HID report to the device.

        Raises
        ------
        FileNotFoundError
            If the device file does not exist.
        PermissionError
            If the process lacks write permission on the device.
        OSError
            On any other I/O failure.
        """
        logger.debug("HID %s <- %s", self.device_path, report.hex())
        with open(self.device_path, "wb") as f:
            f.write(bytes(report))

    @property
    def available(self) -> bool:
        """Return ``True`` if the device file exists."""
        return self.device_path.exists()

    def __repr__(self) -> str:
        return f"HIDTransport({str(self.device_path)!r})"
