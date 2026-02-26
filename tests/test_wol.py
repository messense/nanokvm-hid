"""Tests for Wake-on-LAN."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.wol import _normalise_mac, wake_on_lan

# ── MAC normalisation ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"),
        ("aa:bb:cc:dd:ee:ff", "AA:BB:CC:DD:EE:FF"),
        ("AA-BB-CC-DD-EE-FF", "AA:BB:CC:DD:EE:FF"),
        ("AABB.CCDD.EEFF", "AA:BB:CC:DD:EE:FF"),
        ("AABBCCDDEEFF", "AA:BB:CC:DD:EE:FF"),
        ("aabbccddeeff", "AA:BB:CC:DD:EE:FF"),
    ],
)
def test_normalise_mac_valid(raw, expected):
    assert _normalise_mac(raw) == expected


@pytest.mark.parametrize(
    "invalid",
    ["", "AA:BB:CC", "ZZZZZZZZZZZZ", "AA:BB:CC:DD:EE:GG"],
)
def test_normalise_mac_invalid(invalid):
    with pytest.raises(ValueError, match="Invalid MAC"):
        _normalise_mac(invalid)


# ── wake_on_lan ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("input_mac", "expected_mac"),
    [
        ("AA:BB:CC:DD:EE:FF", "AA:BB:CC:DD:EE:FF"),
        ("aabbccddeeff", "AA:BB:CC:DD:EE:FF"),
    ],
)
@patch("nanokvm_hid.wol.subprocess")
def test_wol_success(mock_sp, input_mac, expected_mac):
    mock_sp.run.return_value.returncode = 0
    wake_on_lan(input_mac)
    mock_sp.run.assert_called_once_with(
        ["ether-wake", "-b", expected_mac],
        capture_output=True,
        text=True,
        check=False,
    )


@patch("nanokvm_hid.wol.subprocess")
def test_wol_failure_raises(mock_sp):
    mock_sp.run.return_value.returncode = 1
    mock_sp.run.return_value.stderr = "no such device"
    mock_sp.run.return_value.stdout = ""

    with pytest.raises(RuntimeError, match="ether-wake failed"):
        wake_on_lan("AA:BB:CC:DD:EE:FF")


def test_wol_invalid_mac_raises():
    with pytest.raises(ValueError, match="Invalid MAC"):
        wake_on_lan("not-a-mac")
