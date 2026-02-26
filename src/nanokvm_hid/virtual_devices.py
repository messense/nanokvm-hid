"""Virtual USB device management (network, microphone, disk).

The NanoKVM can expose additional USB gadgets to the target machine
beyond HID and mass-storage:

* **Virtual Network** (USB NCM) — presents a USB network adapter.
* **Virtual Microphone** (USB UAC2) — presents a USB audio device.
* **Virtual Disk** — exposes an SD card or eMMC as a USB drive.

These are controlled via flag files in ``/boot/`` and the
``usbdev.sh`` script.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Flag files that enable virtual devices
_VIRTUAL_NETWORK_FLAG = "/boot/usb.ncm"
_VIRTUAL_MIC_FLAG = "/boot/usb.uac2"
_VIRTUAL_DISK_SD_FLAG = "/boot/usb.disk1.sd"
_VIRTUAL_DISK_EMMC_FLAG = "/boot/usb.disk1.emmc"

# Sysfs indicators that devices are actually mounted
_VIRTUAL_NETWORK_INDICATOR = "/sys/kernel/config/usb_gadget/g0/configs/c.1/ncm.usb0"
_VIRTUAL_MIC_INDICATOR = "/sys/kernel/config/usb_gadget/g0/configs/c.1/uac2.usb0"
_VIRTUAL_DISK_INDICATOR = (
    "/sys/kernel/config/usb_gadget/g0/functions/mass_storage.disk1/lun.0/file"
)

# Scripts
_USBDEV_SCRIPT = "/kvmapp/scripts/usbdev.sh"
_MOUNT_EMMC_SCRIPT = "/kvmcomm/scripts/mount_emmc.py"

# Disk sources
_SD_CARD_DEVICE = "/dev/mmcblk1"
_EMMC_IMAGE = "/exfat.img"


def _file_exists(path: str) -> bool:
    return Path(path).exists()


def _restart_usb() -> None:
    """Restart USB gadgets via the NanoKVM script."""
    if _file_exists(_USBDEV_SCRIPT):
        os.system(f"bash {_USBDEV_SCRIPT} restart")  # noqa: S605
    else:
        logger.warning("USB device script not found: %s", _USBDEV_SCRIPT)


def _toggle_device(flag_file: str, stop_first: bool = True) -> bool:
    """Toggle a virtual device by adding/removing its flag file.

    Returns the new state (True = enabled).
    """
    if stop_first and _file_exists(_USBDEV_SCRIPT):
        os.system(f"bash {_USBDEV_SCRIPT} stop")  # noqa: S605

    if _file_exists(flag_file):
        os.remove(flag_file)
        enabled = False
    else:
        Path(flag_file).touch()
        enabled = True

    if _file_exists(_USBDEV_SCRIPT):
        os.system(f"bash {_USBDEV_SCRIPT} start")  # noqa: S605

    return enabled


class VirtualDevices:
    """Manage virtual USB devices exposed to the target machine.

    Examples::

        vdev = VirtualDevices()

        # Check status
        status = vdev.status()
        # {'network': False, 'mic': False, 'disk': None,
        #  'sd_card_present': True, 'emmc_present': False}

        # Toggle virtual network adapter
        vdev.toggle_network()

        # Toggle virtual microphone
        vdev.toggle_mic()

        # Mount SD card as USB disk
        vdev.set_disk("sdcard")

        # Unmount virtual disk
        vdev.set_disk(None)
    """

    def status(self) -> dict[str, object]:
        """Get the current state of all virtual devices.

        Returns
        -------
        dict
            Keys: ``network`` (bool), ``mic`` (bool),
            ``disk`` (``"sdcard"``, ``"emmc"``, or ``None``),
            ``sd_card_present`` (bool), ``emmc_present`` (bool).
        """
        return {
            "network": _file_exists(_VIRTUAL_NETWORK_INDICATOR),
            "mic": _file_exists(_VIRTUAL_MIC_INDICATOR),
            "disk": self._get_mounted_disk(),
            "sd_card_present": _file_exists(_SD_CARD_DEVICE),
            "emmc_present": _file_exists(_EMMC_IMAGE),
        }

    def toggle_network(self) -> bool:
        """Toggle the virtual network adapter (USB NCM).

        Returns
        -------
        bool
            ``True`` if the adapter is now enabled.
        """
        enabled = _toggle_device(_VIRTUAL_NETWORK_FLAG)
        logger.info("virtual network %s", "enabled" if enabled else "disabled")
        return enabled

    def toggle_mic(self) -> bool:
        """Toggle the virtual microphone (USB UAC2).

        Returns
        -------
        bool
            ``True`` if the microphone is now enabled.
        """
        enabled = _toggle_device(_VIRTUAL_MIC_FLAG)
        logger.info("virtual mic %s", "enabled" if enabled else "disabled")
        return enabled

    def set_disk(self, disk_type: str | None) -> None:
        """Set the virtual disk source.

        Parameters
        ----------
        disk_type:
            ``"sdcard"`` to expose the SD card, ``"emmc"`` to expose
            the eMMC image, or ``None`` to disable the virtual disk.

        Raises
        ------
        ValueError
            If *disk_type* is not valid.
        FileNotFoundError
            If the eMMC image doesn't exist and can't be created.
        """
        if disk_type is not None and disk_type not in ("sdcard", "emmc"):
            raise ValueError(
                f"Invalid disk type: {disk_type!r} (use 'sdcard', 'emmc', or None)"
            )

        # Ensure eMMC image exists if needed
        if disk_type == "emmc" and not _file_exists(_EMMC_IMAGE):
            if _file_exists(_MOUNT_EMMC_SCRIPT):
                os.system(f"python {_MOUNT_EMMC_SCRIPT} start")  # noqa: S605
            if not _file_exists(_EMMC_IMAGE):
                raise FileNotFoundError("eMMC image not found and could not be created")

        # Clear existing flags
        for flag in (_VIRTUAL_DISK_SD_FLAG, _VIRTUAL_DISK_EMMC_FLAG):
            with contextlib.suppress(FileNotFoundError):
                os.remove(flag)

        # Set new flag if enabling
        if disk_type == "sdcard":
            Path(_VIRTUAL_DISK_SD_FLAG).touch()
        elif disk_type == "emmc":
            Path(_VIRTUAL_DISK_EMMC_FLAG).touch()

        _restart_usb()
        logger.info("virtual disk set to %s", disk_type or "disabled")

    @staticmethod
    def _get_mounted_disk() -> str | None:
        """Check which disk type is currently mounted."""
        if not _file_exists(_VIRTUAL_DISK_INDICATOR):
            return None
        try:
            content = Path(_VIRTUAL_DISK_INDICATOR).read_text().strip()
        except OSError:
            return None

        if content in (_SD_CARD_DEVICE, "/dev/mmcblk1p1"):
            return "sdcard"
        elif content == _EMMC_IMAGE:
            return "emmc"
        return None

    def __repr__(self) -> str:
        return f"VirtualDevices({self.status()!r})"
