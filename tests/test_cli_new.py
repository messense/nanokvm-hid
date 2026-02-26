"""Tests for new CLI commands (gpio, storage, hdmi, jiggler, wol, etc.)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.cli import build_parser, main

# ── power / reset / LED ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "expected_cmd", "expected_dur"),
    [
        (["power"], "power", 800),
        (["power", "--duration", "5000"], "power", 5000),
        (["reset-button"], "reset-button", 800),
        (["reset-button", "--duration", "200"], "reset-button", 200),
    ],
)
def test_parse_power_reset(argv, expected_cmd, expected_dur):
    args = build_parser().parse_args(argv)
    assert args.command == expected_cmd
    assert args.duration == expected_dur


@pytest.mark.parametrize(
    ("argv", "mock_target", "method", "kwargs"),
    [
        (
            ["power"],
            "nanokvm_hid.gpio.GPIO.power",
            None,
            {"duration_ms": 800},
        ),
        (
            ["power", "--duration", "5000"],
            "nanokvm_hid.gpio.GPIO.power",
            None,
            {"duration_ms": 5000},
        ),
        (
            ["reset-button"],
            "nanokvm_hid.gpio.GPIO.reset",
            None,
            {"duration_ms": 800},
        ),
    ],
)
def test_power_reset_dispatch(argv, mock_target, method, kwargs):
    with patch(mock_target) as mock_fn:
        main(argv)
        mock_fn.assert_called_once_with(**kwargs)


@pytest.mark.parametrize(
    ("argv", "mock_target", "return_val", "exit_code"),
    [
        (["power-led"], "nanokvm_hid.gpio.GPIO.power_led", True, None),
        (["power-led"], "nanokvm_hid.gpio.GPIO.power_led", False, 1),
        (["hdd-led"], "nanokvm_hid.gpio.GPIO.hdd_led", False, None),
    ],
)
def test_led_dispatch(argv, mock_target, return_val, exit_code):
    with patch(mock_target, return_value=return_val):
        if exit_code is not None:
            with pytest.raises(SystemExit) as exc_info:
                main(argv)
            assert exc_info.value.code == exit_code
        else:
            main(argv)


# ── storage ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "expected_sub"),
    [
        (["storage", "list"], "list"),
        (["storage", "unmount"], "unmount"),
        (["storage", "status"], "status"),
    ],
)
def test_parse_storage_simple(argv, expected_sub):
    args = build_parser().parse_args(argv)
    assert args.storage_command == expected_sub


def test_parse_storage_mount():
    args = build_parser().parse_args(["storage", "mount", "/data/test.iso", "--cdrom"])
    assert args.file == "/data/test.iso"
    assert args.cdrom is True


@patch(
    "nanokvm_hid.storage.Storage.list_images",
    return_value=["/data/test.iso"],
)
def test_storage_list_dispatch(mock_list):
    main(["storage", "list"])
    mock_list.assert_called_once()


@patch("nanokvm_hid.storage.Storage.mount")
def test_storage_mount_dispatch(mock_mount):
    main(["storage", "mount", "/data/a.iso", "--cdrom", "--read-only"])
    mock_mount.assert_called_once_with(
        "/data/a.iso",
        cdrom=True,
        read_only=True,
    )


@patch("nanokvm_hid.storage.Storage.unmount")
def test_storage_unmount_dispatch(mock_unmount):
    main(["storage", "unmount"])
    mock_unmount.assert_called_once()


@patch(
    "nanokvm_hid.storage.Storage.mounted",
    return_value={
        "file": "/data/test.iso",
        "cdrom": True,
        "read_only": True,
    },
)
def test_storage_status_dispatch(mock_mounted):
    main(["storage", "status"])
    mock_mounted.assert_called_once()


# ── jiggler ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "expected_sub", "expected_mode"),
    [
        (["jiggler", "on"], "on", "relative"),
        (["jiggler", "on", "--mode", "absolute"], "on", "absolute"),
        (["jiggler", "off"], "off", None),
        (["jiggler", "status"], "status", None),
    ],
)
def test_parse_jiggler(argv, expected_sub, expected_mode):
    args = build_parser().parse_args(argv)
    assert args.jiggler_command == expected_sub
    if expected_mode is not None:
        assert args.mode == expected_mode


# ── HDMI ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "expected_sub"),
    [
        (["hdmi", "status"], "status"),
        (["hdmi", "capture", "on"], "capture"),
        (["hdmi", "passthrough", "off"], "passthrough"),
    ],
)
def test_parse_hdmi(argv, expected_sub):
    args = build_parser().parse_args(argv)
    assert args.hdmi_command == expected_sub


def test_parse_hdmi_edid_switch():
    args = build_parser().parse_args(
        ["hdmi", "edid", "switch", "E54-1080P60FPS"],
    )
    assert args.edid_command == "switch"
    assert args.profile == "E54-1080P60FPS"


@pytest.mark.parametrize(
    ("argv", "mock_target", "call_args"),
    [
        (
            ["hdmi", "capture", "on"],
            "nanokvm_hid.hdmi.HDMI.set_capture",
            (True,),
        ),
        (
            ["hdmi", "capture", "off"],
            "nanokvm_hid.hdmi.HDMI.set_capture",
            (False,),
        ),
        (
            ["hdmi", "passthrough", "on"],
            "nanokvm_hid.hdmi.HDMI.set_passthrough",
            (True,),
        ),
        (
            ["hdmi", "passthrough", "off"],
            "nanokvm_hid.hdmi.HDMI.set_passthrough",
            (False,),
        ),
    ],
)
def test_hdmi_dispatch(argv, mock_target, call_args):
    with patch(mock_target) as mock_fn:
        main(argv)
        mock_fn.assert_called_once_with(*call_args)


# ── HID management ──────────────────────────────────────────────────


def test_parse_hid_reset():
    assert build_parser().parse_args(["hid-reset"]).command == "hid-reset"


@pytest.mark.parametrize(
    ("argv", "expected_mode"),
    [
        (["hid-mode"], None),
        (["hid-mode", "hid-only"], "hid-only"),
        (["hid-mode", "normal"], "normal"),
    ],
)
def test_parse_hid_mode(argv, expected_mode):
    assert build_parser().parse_args(argv).mode == expected_mode


@patch("nanokvm_hid.hid_manager.reset_hid")
def test_hid_reset_dispatch(mock_reset):
    main(["hid-reset"])
    mock_reset.assert_called_once()


@patch("nanokvm_hid.hid_manager.get_hid_mode", return_value="normal")
def test_hid_mode_get_dispatch(mock_get):
    main(["hid-mode"])
    mock_get.assert_called_once()


@patch("nanokvm_hid.hid_manager.set_hid_mode")
def test_hid_mode_set_dispatch(mock_set):
    main(["hid-mode", "hid-only"])
    mock_set.assert_called_once_with("hid-only")


# ── WoL ──────────────────────────────────────────────────────────────


def test_parse_wol():
    args = build_parser().parse_args(["wol", "AA:BB:CC:DD:EE:FF"])
    assert args.command == "wol"
    assert args.mac == "AA:BB:CC:DD:EE:FF"


@patch("nanokvm_hid.wol.wake_on_lan")
def test_wol_dispatch(mock_wol):
    main(["wol", "AA:BB:CC:DD:EE:FF"])
    mock_wol.assert_called_once_with("AA:BB:CC:DD:EE:FF")


# ── virtual-device ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("argv", "expected_sub"),
    [
        (["virtual-device", "status"], "status"),
        (["virtual-device", "network"], "network"),
        (["virtual-device", "mic"], "mic"),
    ],
)
def test_parse_vdev(argv, expected_sub):
    assert build_parser().parse_args(argv).vdev_command == expected_sub


@pytest.mark.parametrize(
    ("argv_tail", "expected_type"),
    [
        (["disk", "sdcard"], "sdcard"),
        (["disk", "emmc"], "emmc"),
        (["disk"], None),
    ],
)
def test_parse_vdev_disk(argv_tail, expected_type):
    args = build_parser().parse_args(["virtual-device", *argv_tail])
    assert args.type == expected_type


@patch(
    "nanokvm_hid.virtual_devices.VirtualDevices.status",
    return_value={
        "network": False,
        "mic": False,
        "disk": None,
        "sd_card_present": True,
        "emmc_present": False,
    },
)
def test_vdev_status_dispatch(mock_status):
    main(["virtual-device", "status"])
    mock_status.assert_called_once()


@patch(
    "nanokvm_hid.virtual_devices.VirtualDevices.toggle_network",
    return_value=True,
)
def test_vdev_network_dispatch(mock_toggle):
    main(["virtual-device", "network"])
    mock_toggle.assert_called_once()


@patch("nanokvm_hid.virtual_devices.VirtualDevices.set_disk")
def test_vdev_disk_dispatch(mock_set):
    main(["virtual-device", "disk", "sdcard"])
    mock_set.assert_called_once_with("sdcard")
