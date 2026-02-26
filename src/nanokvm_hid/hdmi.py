"""HDMI capture chip control and EDID management.

The NanoKVM Pro uses a Lontium LT6911 HDMI capture chip.  This module
provides control over HDMI capture, passthrough (loopout), and EDID
profile switching.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# LT6911 procfs interface
_LT6911_POWER = "/proc/lt6911_info/power"
_LT6911_HDMI_POWER = "/proc/lt6911_info/hdmi_power"
_LT6911_LOOPOUT_POWER = "/proc/lt6911_info/loopout_power"
_LT6911_EDID = "/proc/lt6911_info/edid"
_LT6911_EDID_SNAPSHOT = "/proc/lt6911_info/edid_snapshot"

# EDID directories
_EDID_DIR = "/kvmcomm/edid"
_CUSTOM_EDID_DIR = "/etc/kvm/edid"
_CUSTOM_EDID_FLAG = "/etc/kvm/edid/edid_flag"

# Known EDID profiles (byte at offset 12 → name)
_EDID_MAP: dict[int, str] = {
    0x12: "E18-4K30FPS",
    0x30: "E48-4K39FPS",
    0x36: "E54-1080P60FPS",
    0x38: "E56-2K60FPS",
    0x3A: "E58-4K16-10",
    0x3F: "E63-Ultrawide",
}


class HDMI:
    """Control the HDMI capture chip and EDID profiles.

    Parameters
    ----------
    power_path:
        Procfs path for HDMI capture power control.
    hdmi_power_path:
        Procfs path for HDMI input power control.
    loopout_power_path:
        Procfs path for HDMI passthrough/loopout power control.

    Examples::

        hdmi = HDMI()

        # Capture control
        hdmi.capture_enabled          # True/False
        hdmi.set_capture(False)       # disable capture
        hdmi.set_capture(True)        # enable capture

        # Passthrough / loopout
        hdmi.passthrough_enabled      # True/False
        hdmi.set_passthrough(True)    # enable HDMI passthrough

        # EDID
        hdmi.current_edid             # e.g. "E54-1080P60FPS"
        hdmi.switch_edid("E56-2K60FPS")
    """

    def __init__(
        self,
        power_path: str = _LT6911_POWER,
        hdmi_power_path: str = _LT6911_HDMI_POWER,
        loopout_power_path: str = _LT6911_LOOPOUT_POWER,
    ) -> None:
        self._power_path = power_path
        self._hdmi_power_path = hdmi_power_path
        self._loopout_power_path = loopout_power_path

    # ------------------------------------------------------------------
    # HDMI capture
    # ------------------------------------------------------------------

    @property
    def capture_enabled(self) -> bool:
        """Whether HDMI capture is currently enabled."""
        return self._read_power(self._power_path)

    def set_capture(self, enabled: bool) -> None:
        """Enable or disable HDMI capture.

        Parameters
        ----------
        enabled:
            ``True`` to enable, ``False`` to disable.
        """
        status = "on" if enabled else "off"
        Path(self._power_path).write_text(status)
        logger.info("HDMI capture %s", status)

    # ------------------------------------------------------------------
    # HDMI passthrough / loopout
    # ------------------------------------------------------------------

    @property
    def passthrough_enabled(self) -> bool:
        """Whether HDMI passthrough (loopout) is currently enabled."""
        return self._read_power(self._loopout_power_path)

    def set_passthrough(self, enabled: bool) -> None:
        """Enable or disable HDMI passthrough (loopout).

        The passthrough feature routes the HDMI input signal to a
        second HDMI output, allowing a monitor to be connected
        alongside the KVM capture.

        Parameters
        ----------
        enabled:
            ``True`` to enable, ``False`` to disable.
        """
        if enabled:
            Path(self._hdmi_power_path).write_text("0")
            time.sleep(0.01)
            Path(self._loopout_power_path).write_text("1")
            Path(self._hdmi_power_path).write_text("1")
        else:
            Path(self._loopout_power_path).write_text("0")
            Path(self._hdmi_power_path).write_text("0")
            time.sleep(0.01)
            Path(self._hdmi_power_path).write_text("1")

        logger.info("HDMI passthrough %s", "enabled" if enabled else "disabled")

    # ------------------------------------------------------------------
    # EDID
    # ------------------------------------------------------------------

    @property
    def current_edid(self) -> str:
        """The name of the currently active EDID profile.

        Returns a known profile name (e.g. ``"E54-1080P60FPS"``) or
        a custom EDID filename, or ``"unknown"`` if not recognised.
        """
        snapshot_path = Path(_LT6911_EDID_SNAPSHOT)
        if not snapshot_path.exists():
            return "unknown"

        content = snapshot_path.read_bytes()
        if len(content) > 12:
            name = _EDID_MAP.get(content[12])
            if name:
                return name

        # Check for custom EDID flag
        flag_path = Path(_CUSTOM_EDID_FLAG)
        if flag_path.exists():
            return flag_path.read_text().strip()

        return "unknown"

    def list_edids(self) -> list[str]:
        """List all available EDID profiles (built-in + custom).

        Returns
        -------
        list of str
            Profile names.  Built-in profiles are listed first.
        """
        edids: list[str] = []

        # Built-in profiles
        edid_dir = Path(_EDID_DIR)
        if edid_dir.exists():
            for f in sorted(edid_dir.glob("*.bin")):
                edids.append(f.stem)

        # Custom EDID profiles
        custom_dir = Path(_CUSTOM_EDID_DIR)
        if custom_dir.exists():
            for f in sorted(custom_dir.iterdir()):
                if f.is_file() and f.suffix.lower() == ".bin":
                    edids.append(f.name)

        return edids

    def switch_edid(self, edid: str) -> None:
        """Switch to a different EDID profile.

        Parameters
        ----------
        edid:
            Profile name, e.g. ``"E54-1080P60FPS"`` for a built-in
            profile, or a filename in the custom EDID directory.

        Raises
        ------
        FileNotFoundError
            If the EDID profile does not exist.
        """
        # Try built-in first
        src = Path(_EDID_DIR) / f"{edid}.bin"
        if not src.exists():
            # Try custom
            src = Path(_CUSTOM_EDID_DIR) / edid
            if not src.exists():
                raise FileNotFoundError(f"EDID profile not found: {edid}")
            # Record custom EDID flag
            Path(_CUSTOM_EDID_FLAG).write_text(edid)

        # Apply by copying to the LT6911 procfs interface
        data = src.read_bytes()
        Path(_LT6911_EDID).write_bytes(data)
        logger.info("switched EDID to %s", edid)

    def upload_edid(self, src_path: str, name: str | None = None) -> str:
        """Upload a custom EDID binary file.

        Parameters
        ----------
        src_path:
            Path to the EDID ``.bin`` file to upload.
        name:
            Filename to save as.  Defaults to the source filename.

        Returns
        -------
        str
            The saved filename.

        Raises
        ------
        FileNotFoundError
            If the source file does not exist.
        """
        src = Path(src_path)
        if not src.exists():
            raise FileNotFoundError(f"EDID file not found: {src_path}")

        filename = name or src.name
        dst_dir = Path(_CUSTOM_EDID_DIR)
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / filename
        shutil.copy2(src, dst)
        logger.info("uploaded EDID: %s", filename)
        return filename

    def delete_edid(self, name: str) -> None:
        """Delete a custom EDID profile.

        Parameters
        ----------
        name:
            Filename of the custom EDID to delete.

        Raises
        ------
        FileNotFoundError
            If the EDID profile does not exist.
        """
        path = Path(_CUSTOM_EDID_DIR) / name
        if not path.exists():
            raise FileNotFoundError(f"Custom EDID not found: {name}")
        os.remove(path)
        logger.info("deleted EDID: %s", name)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_power(path: str) -> bool:
        """Read an on/off status from a procfs file."""
        try:
            content = Path(path).read_text().strip()
            return content == "on"
        except (FileNotFoundError, OSError) as exc:
            logger.warning("Cannot read %s: %s", path, exc)
            return False

    def __repr__(self) -> str:
        return (
            f"HDMI(capture={'on' if self.capture_enabled else 'off'}, "
            f"passthrough={'on' if self.passthrough_enabled else 'off'})"
        )
