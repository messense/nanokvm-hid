"""USB gadget mass-storage control for mounting ISO/IMG files.

The NanoKVM exposes a USB mass-storage gadget to the target machine.
This module controls which image file is mounted, and supports
CD-ROM emulation and read-only modes.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# USB gadget sysfs paths
_GADGET_LUN0 = "/sys/kernel/config/usb_gadget/g0/configs/c.1/mass_storage.disk0/lun.0"
_MOUNT_DEVICE = f"{_GADGET_LUN0}/file"
_CDROM_FLAG = f"{_GADGET_LUN0}/cdrom"
_RO_FLAG = f"{_GADGET_LUN0}/ro"
_USB_DISK_FLAG = "/boot/usb.disk0"
_USBDEV_SCRIPT = "/kvmapp/scripts/usbdev.sh"

# Directories to scan for images
_IMAGE_DIRS = ["/data", "/sdcard"]
_IMAGE_EXTENSIONS = {".iso", ".img"}


def _restart_usb(enable: bool) -> None:
    """Restart the USB gadget with mass-storage enabled or disabled."""
    if enable:
        Path(_USB_DISK_FLAG).touch()
    else:
        with contextlib.suppress(FileNotFoundError):
            os.remove(_USB_DISK_FLAG)

    # Use the NanoKVM's USB device script to re-enumerate
    script = Path(_USBDEV_SCRIPT)
    if script.exists():
        os.system(f"bash {_USBDEV_SCRIPT} restart")  # noqa: S605
    else:
        logger.warning("USB device script not found: %s", _USBDEV_SCRIPT)


class Storage:
    """Manage USB mass-storage gadget for virtual media.

    Mount ISO or IMG files to present them as a USB drive or CD-ROM
    to the target machine — useful for OS installation, BIOS updates,
    and diagnostics.

    Examples::

        storage = Storage()

        # List available images
        for img in storage.list_images():
            print(img)

        # Mount an ISO as CD-ROM
        storage.mount("/data/ubuntu-24.04.iso", cdrom=True)

        # Check what's mounted
        info = storage.mounted()
        print(info)  # {'file': '...', 'cdrom': True, ...}

        # Unmount
        storage.unmount()
    """

    def __init__(
        self,
        mount_device: str = _MOUNT_DEVICE,
        cdrom_flag: str = _CDROM_FLAG,
        ro_flag: str = _RO_FLAG,
        image_dirs: list[str] | None = None,
    ) -> None:
        self._mount_device = mount_device
        self._cdrom_flag = cdrom_flag
        self._ro_flag = ro_flag
        self._image_dirs = image_dirs or list(_IMAGE_DIRS)

    def list_images(self) -> list[str]:
        """List all ISO/IMG files available for mounting.

        Scans ``/data/`` and ``/sdcard/`` by default.

        Returns
        -------
        list of str
            Full paths to discovered image files.
        """
        images: list[str] = []
        for directory in self._image_dirs:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            for path in dir_path.rglob("*"):
                if path.is_file() and path.suffix.lower() in _IMAGE_EXTENSIONS:
                    images.append(str(path))
        logger.info("found %d images", len(images))
        return images

    def mount(
        self,
        file: str,
        *,
        cdrom: bool = False,
        read_only: bool = False,
    ) -> None:
        """Mount an ISO/IMG file as a USB mass-storage device.

        Parameters
        ----------
        file:
            Full path to the image file (e.g. ``"/data/ubuntu.iso"``).
        cdrom:
            If ``True``, emulate a CD-ROM drive.  Implies read-only.
        read_only:
            If ``True``, mount as read-only (forced on when ``cdrom=True``).

        Raises
        ------
        FileNotFoundError
            If the image file does not exist.
        """
        if not Path(file).exists():
            raise FileNotFoundError(f"Image not found: {file}")

        _restart_usb(enable=True)

        # Set cdrom flag
        cdrom_val = "1" if cdrom else "0"
        Path(self._cdrom_flag).write_text(cdrom_val)

        # Set read-only flag (cdrom implies read-only)
        ro_val = "1" if (cdrom or read_only) else "0"
        Path(self._ro_flag).write_text(ro_val)

        # Mount the image
        Path(self._mount_device).write_text(file)

        logger.info(
            "mounted %s (cdrom=%s, read_only=%s)", file, cdrom, cdrom or read_only
        )

    def unmount(self) -> None:
        """Unmount the currently mounted image."""
        Path(self._mount_device).write_text("\n")
        _restart_usb(enable=False)
        logger.info("unmounted image")

    def mounted(self) -> dict[str, object] | None:
        """Get information about the currently mounted image.

        Returns
        -------
        dict or None
            A dict with keys ``file``, ``cdrom``, ``read_only`` if an
            image is mounted, or ``None`` if nothing is mounted.
        """
        mount_path = Path(self._mount_device)
        if not mount_path.exists():
            return None

        try:
            file = mount_path.read_text().strip()
        except OSError:
            return None

        if not file:
            return None

        cdrom = False
        read_only = False

        cdrom_path = Path(self._cdrom_flag)
        if cdrom_path.exists():
            cdrom = cdrom_path.read_text().strip() == "1"

        ro_path = Path(self._ro_flag)
        if ro_path.exists():
            read_only = ro_path.read_text().strip() == "1"

        return {"file": file, "cdrom": cdrom, "read_only": read_only}

    def __repr__(self) -> str:
        mounted = self.mounted()
        if mounted:
            return f"Storage(mounted={mounted['file']!r})"
        return "Storage(unmounted)"
