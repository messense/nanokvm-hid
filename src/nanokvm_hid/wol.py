"""Wake-on-LAN support.

Send WoL magic packets to power on machines on the local network.
"""

from __future__ import annotations

import logging
import re
import subprocess

logger = logging.getLogger(__name__)


def _normalise_mac(mac: str) -> str:
    """Parse and normalise a MAC address to ``AA:BB:CC:DD:EE:FF`` format.

    Accepts formats: ``AA:BB:CC:DD:EE:FF``, ``AA-BB-CC-DD-EE-FF``,
    ``AABB.CCDD.EEFF``, ``AABBCCDDEEFF``.

    Raises
    ------
    ValueError
        If the MAC address is invalid.
    """
    cleaned = mac.upper().replace("-", "").replace(":", "").replace(".", "")
    if not re.fullmatch(r"[0-9A-F]{12}", cleaned):
        raise ValueError(f"Invalid MAC address: {mac}")
    return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))


def wake_on_lan(mac: str) -> None:
    """Send a Wake-on-LAN magic packet.

    Uses ``ether-wake`` which is available on the NanoKVM's BusyBox
    Linux.  The packet is broadcast on all interfaces.

    Parameters
    ----------
    mac:
        MAC address of the target machine.  Accepts common formats
        (colon-separated, dash-separated, or raw hex).

    Raises
    ------
    ValueError
        If the MAC address is invalid.
    RuntimeError
        If ``ether-wake`` fails.

    Examples::

        from nanokvm_hid import wake_on_lan

        wake_on_lan("AA:BB:CC:DD:EE:FF")
        wake_on_lan("aabb.ccdd.eeff")
    """
    normalised = _normalise_mac(mac)

    result = subprocess.run(
        ["ether-wake", "-b", normalised],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        error_msg = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"ether-wake failed: {error_msg}")

    logger.info("WoL magic packet sent to %s", normalised)
