"""Tests for HID gadget management (reset / mode switching)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.hid_manager import (
    _run_usbdev,
    get_hid_mode,
    reset_hid,
    set_hid_mode,
)

# ── get_hid_mode ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("flag_exists", "expected"),
    [
        (False, "normal"),
        (True, "hid-only"),
    ],
)
@patch("nanokvm_hid.hid_manager.Path")
def test_get_hid_mode(mock_path, flag_exists, expected):
    mock_path.return_value.exists.return_value = flag_exists
    assert get_hid_mode() == expected


# ── set_hid_mode ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "target", "expected_arg"),
    [
        ("normal", "hid-only", "hid-only"),
        ("hid-only", "normal", "restart"),
    ],
)
@patch("nanokvm_hid.hid_manager.time")
@patch("nanokvm_hid.hid_manager._run_usbdev")
@patch("nanokvm_hid.hid_manager.get_hid_mode")
def test_set_hid_mode(
    mock_get,
    mock_run,
    mock_time,
    current,
    target,
    expected_arg,
):
    mock_get.return_value = current
    set_hid_mode(target)
    mock_run.assert_called_once_with(expected_arg)


@patch("nanokvm_hid.hid_manager._run_usbdev")
@patch("nanokvm_hid.hid_manager.get_hid_mode", return_value="normal")
def test_set_hid_mode_noop_when_same(mock_get, mock_run):
    set_hid_mode("normal")
    mock_run.assert_not_called()


def test_set_hid_mode_invalid():
    with pytest.raises(ValueError, match="Invalid HID mode"):
        set_hid_mode("turbo")


# ── reset_hid ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("current", "expected_arg"),
    [
        ("normal", "restart"),
        ("hid-only", "hid-only"),
    ],
)
@patch("nanokvm_hid.hid_manager.time")
@patch("nanokvm_hid.hid_manager._run_usbdev")
@patch("nanokvm_hid.hid_manager.get_hid_mode")
def test_reset_hid(
    mock_get,
    mock_run,
    mock_time,
    current,
    expected_arg,
):
    mock_get.return_value = current
    reset_hid()
    mock_run.assert_called_once_with(expected_arg)
    mock_time.sleep.assert_called_once_with(3)


# ── _run_usbdev ──────────────────────────────────────────────────────


@patch("nanokvm_hid.hid_manager.Path")
def test_run_usbdev_script_not_found(mock_path):
    mock_path.return_value.exists.return_value = False
    with pytest.raises(RuntimeError, match="not found"):
        _run_usbdev("restart")
