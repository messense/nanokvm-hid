"""Tests for mouse jiggler."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.jiggler import Jiggler

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def jiggler(tmp_path):
    """Jiggler backed by fake transports and temp config."""
    cfg = str(tmp_path / "jiggler-config")
    with patch("nanokvm_hid.jiggler._CONFIG_FILE", cfg):
        j = Jiggler(
            mouse_device="/dev/null",
            touchpad_device="/dev/null",
            interval=0.1,
        )
        yield j
        if j.is_running:
            j.stop()


# ── start / stop ─────────────────────────────────────────────────────


@pytest.mark.parametrize("mode", ["relative", "absolute"])
def test_start_and_stop(jiggler, mode):
    with (
        patch.object(jiggler._mouse, "send"),
        patch.object(jiggler._touchpad, "send"),
    ):
        jiggler.start(mode=mode)
        assert jiggler.is_running
        assert jiggler.mode == mode
        assert jiggler.enabled
        jiggler.stop()
        assert not jiggler.is_running


def test_invalid_mode_raises(jiggler):
    with pytest.raises(ValueError, match="Invalid jiggler mode"):
        jiggler.start(mode="invalid")


def test_stop_when_not_running(jiggler):
    jiggler.stop()  # should not raise


# ── jiggle movements ────────────────────────────────────────────────


def test_relative_jiggle(jiggler):
    with (
        patch.object(jiggler._mouse, "send") as mock_send,
        patch("nanokvm_hid.jiggler.time"),
    ):
        jiggler._mode = "relative"
        jiggler._jiggle()
        assert mock_send.call_count == 2
        mock_send.assert_any_call(bytes([0x00, 0x0A, 0x0A, 0x00]))
        mock_send.assert_any_call(bytes([0x00, 0xF6, 0xF6, 0x00]))


def test_absolute_jiggle(jiggler):
    with (
        patch.object(jiggler._touchpad, "send") as mock_send,
        patch("nanokvm_hid.jiggler.time"),
    ):
        jiggler._mode = "absolute"
        jiggler._jiggle()
        assert mock_send.call_count == 2


# ── persistence ──────────────────────────────────────────────────────


def test_config_saved_on_start(jiggler, tmp_path):
    cfg = tmp_path / "jiggler-config"
    with (
        patch("nanokvm_hid.jiggler._CONFIG_FILE", str(cfg)),
        patch.object(jiggler._mouse, "send"),
        patch.object(jiggler._touchpad, "send"),
    ):
        jiggler.start(mode="absolute")
        assert cfg.exists()
        assert cfg.read_text() == "absolute"
        jiggler.stop()


def test_config_removed_on_stop(jiggler, tmp_path):
    cfg = tmp_path / "jiggler-config"
    cfg.write_text("relative")
    with patch("nanokvm_hid.jiggler._CONFIG_FILE", str(cfg)):
        jiggler.stop()
        assert not cfg.exists()


# ── repr ─────────────────────────────────────────────────────────────


def test_repr_stopped(jiggler):
    assert "stopped" in repr(jiggler)


def test_repr_running(jiggler):
    with (
        patch.object(jiggler._mouse, "send"),
        patch.object(jiggler._touchpad, "send"),
    ):
        jiggler.start()
        assert "running" in repr(jiggler)
        jiggler.stop()
