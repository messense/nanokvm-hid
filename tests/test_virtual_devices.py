"""Tests for virtual USB device management."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.virtual_devices import VirtualDevices

# ── status ───────────────────────────────────────────────────────────


@patch("nanokvm_hid.virtual_devices._file_exists", return_value=False)
def test_status_all_disabled(mock_exists):
    vdev = VirtualDevices()
    with patch.object(VirtualDevices, "_get_mounted_disk", return_value=None):
        status = vdev.status()

    assert status["network"] is False
    assert status["mic"] is False
    assert status["disk"] is None
    assert status["sd_card_present"] is False
    assert status["emmc_present"] is False


# ── toggle ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "return_val"),
    [
        ("toggle_network", True),
        ("toggle_network", False),
        ("toggle_mic", True),
        ("toggle_mic", False),
    ],
)
@patch("nanokvm_hid.virtual_devices._toggle_device")
def test_toggle(mock_toggle, method, return_val):
    mock_toggle.return_value = return_val
    vdev = VirtualDevices()
    assert getattr(vdev, method)() is return_val


# ── set_disk ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("disk_type", ["sdcard", "emmc", None])
@patch("nanokvm_hid.virtual_devices._restart_usb")
@patch("nanokvm_hid.virtual_devices.os.remove")
@patch("nanokvm_hid.virtual_devices._file_exists", return_value=True)
def test_set_disk(mock_exists, mock_remove, mock_restart, disk_type):
    vdev = VirtualDevices()
    with patch("nanokvm_hid.virtual_devices.Path"):
        vdev.set_disk(disk_type)
    mock_restart.assert_called_once()


def test_set_disk_invalid():
    with pytest.raises(ValueError, match="Invalid disk type"):
        VirtualDevices().set_disk("floppy")


# ── _get_mounted_disk ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("/dev/mmcblk1", "sdcard"),
        ("/dev/mmcblk1p1", "sdcard"),
        ("/exfat.img", "emmc"),
    ],
)
def test_get_mounted_disk(tmp_path, content, expected):
    indicator = tmp_path / "disk_file"
    indicator.write_text(content)

    with (
        patch(
            "nanokvm_hid.virtual_devices._VIRTUAL_DISK_INDICATOR",
            str(indicator),
        ),
        patch(
            "nanokvm_hid.virtual_devices._file_exists",
            return_value=True,
        ),
    ):
        assert VirtualDevices._get_mounted_disk() == expected


@patch("nanokvm_hid.virtual_devices._file_exists", return_value=False)
def test_get_mounted_disk_none(mock_exists):
    assert VirtualDevices._get_mounted_disk() is None
