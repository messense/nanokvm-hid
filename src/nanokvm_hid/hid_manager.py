"""HID gadget management — reset devices and switch USB modes.

Controls the USB HID gadget configuration on the NanoKVM, including
resetting stuck devices and switching between normal and HID-only mode.
"""

from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_USBDEV_SCRIPT = "/kvmapp/scripts/usbdev.sh"
_HID_ONLY_FLAG = "/dev/shm/tmp/hid_only"

# Valid HID modes and their usbdev.sh arguments
_MODE_ARGS = {
    "normal": "restart",
    "hid-only": "hid-only",
}


def reset_hid() -> None:
    """Reset all HID gadget devices.

    This restarts the USB gadget subsystem, which can fix issues like
    stuck keys, unresponsive mouse, or the target machine not
    recognising the HID devices.

    The operation takes about 3 seconds while USB re-enumerates.

    Raises
    ------
    RuntimeError
        If the USB device script fails.
    """
    mode = get_hid_mode()
    arg = _MODE_ARGS.get(mode, "restart")

    _run_usbdev(arg)
    time.sleep(3)
    logger.info("HID devices reset (mode=%s)", mode)


def get_hid_mode() -> str:
    """Get the current HID mode.

    Returns
    -------
    str
        ``"normal"`` or ``"hid-only"``.

    In **normal** mode, the NanoKVM exposes HID + mass-storage + other
    USB gadgets.  In **hid-only** mode, only HID keyboard/mouse/touchpad
    are exposed, which can improve compatibility with some BIOS/UEFI.
    """
    if Path(_HID_ONLY_FLAG).exists():
        return "hid-only"
    return "normal"


def set_hid_mode(mode: str) -> None:
    """Switch the HID USB mode.

    Parameters
    ----------
    mode:
        ``"normal"`` — HID + mass-storage + other gadgets.
        ``"hid-only"`` — HID devices only (better BIOS compatibility).

    The mode change takes about 3 seconds while USB re-enumerates.

    Raises
    ------
    ValueError
        If *mode* is not ``"normal"`` or ``"hid-only"``.
    RuntimeError
        If the USB device script fails.
    """
    if mode not in _MODE_ARGS:
        raise ValueError(f"Invalid HID mode: {mode!r} (use 'normal' or 'hid-only')")

    current = get_hid_mode()
    if mode == current:
        logger.info("HID mode already %s", mode)
        return

    _run_usbdev(_MODE_ARGS[mode])
    time.sleep(3)
    logger.info("HID mode switched to %s", mode)


def _run_usbdev(arg: str) -> None:
    """Run the USB device management script.

    Raises
    ------
    RuntimeError
        If the script doesn't exist or fails.
    """
    if not Path(_USBDEV_SCRIPT).exists():
        raise RuntimeError(f"USB device script not found: {_USBDEV_SCRIPT}")

    result = subprocess.run(
        ["bash", _USBDEV_SCRIPT, arg],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"usbdev.sh {arg} failed: {error_msg}")
