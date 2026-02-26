"""Tests for HDMI capture/passthrough/EDID control."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.hdmi import HDMI

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def hdmi_env(tmp_path):
    """HDMI control with temp procfs-like files."""
    power = tmp_path / "power"
    hdmi_power = tmp_path / "hdmi_power"
    loopout = tmp_path / "loopout_power"

    power.write_text("on")
    hdmi_power.write_text("1")
    loopout.write_text("0")

    return HDMI(
        power_path=str(power),
        hdmi_power_path=str(hdmi_power),
        loopout_power_path=str(loopout),
    )


# ── capture ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("content", "expected"),
    [("on", True), ("off", False)],
)
def test_capture_enabled(hdmi_env, tmp_path, content, expected):
    (tmp_path / "power").write_text(content)
    assert hdmi_env.capture_enabled is expected


@pytest.mark.parametrize("enabled", [True, False])
def test_set_capture(hdmi_env, tmp_path, enabled):
    hdmi_env.set_capture(enabled)
    expect = "on" if enabled else "off"
    assert (tmp_path / "power").read_text() == expect


# ── passthrough ──────────────────────────────────────────────────────


def test_passthrough_disabled(hdmi_env, tmp_path):
    (tmp_path / "loopout_power").write_text("off")
    assert hdmi_env.passthrough_enabled is False


@pytest.mark.parametrize("enabled", [True, False])
def test_set_passthrough(hdmi_env, tmp_path, enabled):
    with patch("nanokvm_hid.hdmi.time"):
        hdmi_env.set_passthrough(enabled)
    # In both cases hdmi_power ends up "1" (re-enabled)
    assert (tmp_path / "hdmi_power").read_text() == "1"
    if enabled:
        assert (tmp_path / "loopout_power").read_text() == "1"
    else:
        assert (tmp_path / "loopout_power").read_text() == "0"


# ── current_edid ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("byte12", "expected"),
    [
        (0x12, "E18-4K30FPS"),
        (0x36, "E54-1080P60FPS"),
        (0x38, "E56-2K60FPS"),
    ],
)
def test_current_edid_known(tmp_path, byte12, expected):
    snapshot = tmp_path / "edid_snapshot"
    snapshot.write_bytes(bytes(12) + bytes([byte12]) + bytes(100))

    with patch("nanokvm_hid.hdmi._LT6911_EDID_SNAPSHOT", str(snapshot)):
        assert HDMI().current_edid == expected


def test_current_edid_custom(tmp_path):
    snapshot = tmp_path / "edid_snapshot"
    snapshot.write_bytes(bytes(12) + bytes([0xFF]) + bytes(100))

    flag = tmp_path / "edid_flag"
    flag.write_text("my-custom.bin")

    with (
        patch("nanokvm_hid.hdmi._LT6911_EDID_SNAPSHOT", str(snapshot)),
        patch("nanokvm_hid.hdmi._CUSTOM_EDID_FLAG", str(flag)),
    ):
        assert HDMI().current_edid == "my-custom.bin"


def test_current_edid_unknown(tmp_path):
    snapshot = tmp_path / "edid_snapshot"
    snapshot.write_bytes(bytes(12) + bytes([0xFF]) + bytes(100))

    with (
        patch("nanokvm_hid.hdmi._LT6911_EDID_SNAPSHOT", str(snapshot)),
        patch(
            "nanokvm_hid.hdmi._CUSTOM_EDID_FLAG",
            str(tmp_path / "nope"),
        ),
    ):
        assert HDMI().current_edid == "unknown"


# ── list_edids ───────────────────────────────────────────────────────


def test_list_edids(tmp_path):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    (builtin / "E54-1080P60FPS.bin").write_bytes(b"\x00")
    (builtin / "E56-2K60FPS.bin").write_bytes(b"\x00")

    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "my-monitor.bin").write_bytes(b"\x00")

    with (
        patch("nanokvm_hid.hdmi._EDID_DIR", str(builtin)),
        patch("nanokvm_hid.hdmi._CUSTOM_EDID_DIR", str(custom)),
    ):
        edids = HDMI().list_edids()

    assert len(edids) == 3
    assert "E54-1080P60FPS" in edids
    assert "my-monitor.bin" in edids


# ── switch_edid ──────────────────────────────────────────────────────


def test_switch_edid_builtin(tmp_path):
    builtin = tmp_path / "builtin"
    builtin.mkdir()
    data = b"\x00\x01\x02\x03"
    (builtin / "E54-1080P60FPS.bin").write_bytes(data)
    target = tmp_path / "edid_proc"

    with (
        patch("nanokvm_hid.hdmi._EDID_DIR", str(builtin)),
        patch("nanokvm_hid.hdmi._LT6911_EDID", str(target)),
    ):
        HDMI().switch_edid("E54-1080P60FPS")

    assert target.read_bytes() == data


def test_switch_edid_not_found(tmp_path):
    with (
        patch("nanokvm_hid.hdmi._EDID_DIR", str(tmp_path / "a")),
        patch("nanokvm_hid.hdmi._CUSTOM_EDID_DIR", str(tmp_path / "b")),
        pytest.raises(FileNotFoundError),
    ):
        HDMI().switch_edid("nonexistent")


# ── upload / delete ──────────────────────────────────────────────────


def test_upload_edid(tmp_path):
    custom = tmp_path / "custom"
    src = tmp_path / "my-edid.bin"
    src.write_bytes(b"\xaa\xbb")

    with patch("nanokvm_hid.hdmi._CUSTOM_EDID_DIR", str(custom)):
        name = HDMI().upload_edid(str(src))

    assert name == "my-edid.bin"
    assert (custom / "my-edid.bin").read_bytes() == b"\xaa\xbb"


def test_delete_edid(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()
    (custom / "old.bin").write_bytes(b"\x00")

    with patch("nanokvm_hid.hdmi._CUSTOM_EDID_DIR", str(custom)):
        HDMI().delete_edid("old.bin")

    assert not (custom / "old.bin").exists()


def test_delete_edid_not_found(tmp_path):
    custom = tmp_path / "custom"
    custom.mkdir()

    with (
        patch("nanokvm_hid.hdmi._CUSTOM_EDID_DIR", str(custom)),
        pytest.raises(FileNotFoundError),
    ):
        HDMI().delete_edid("nope.bin")


# ── repr ─────────────────────────────────────────────────────────────


def test_repr(hdmi_env):
    r = repr(hdmi_env)
    assert "HDMI(" in r
    assert "capture=" in r
