"""Tests for stream encoder control (libkvm ctypes wrapper)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from nanokvm_hid.stream import (
    RATE_CONTROL_CBR,
    RATE_CONTROL_VBR,
    Stream,
)

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def mock_lib():
    """A mock ctypes CDLL with kvmv_* functions."""
    lib = MagicMock()
    lib.kvmv_init.return_value = None
    lib.kvmv_deinit.return_value = None
    lib.kvmv_get_fps.return_value = 0
    lib.kvmv_set_fps.return_value = 0
    lib.kvmv_set_gop.return_value = 0
    lib.kvmv_set_rate_control.return_value = 0
    lib.kvmv_hdmi_control.return_value = 0
    return lib


@pytest.fixture()
def stream(mock_lib, tmp_path):
    """Stream backed by a mock library."""
    fake_so = tmp_path / "libkvm.so"
    fake_so.write_bytes(b"\x00")

    with (
        patch("nanokvm_hid.stream.ctypes.CDLL", return_value=mock_lib),
        patch("nanokvm_hid.stream.Path.exists", return_value=True),
    ):
        s = Stream(lib_path=str(fake_so))
        yield s
        s.close()


# ── init / close ─────────────────────────────────────────────────────


def test_init_calls_kvmv_init(mock_lib, stream):
    mock_lib.kvmv_init.assert_called_once()


def test_close(mock_lib, stream):
    stream.close()
    mock_lib.kvmv_deinit.assert_called_once()


def test_close_idempotent(mock_lib, stream):
    stream.close()
    stream.close()
    assert mock_lib.kvmv_deinit.call_count == 1


def test_context_manager(mock_lib, tmp_path):
    fake_so = tmp_path / "libkvm.so"
    fake_so.write_bytes(b"\x00")

    with (
        patch("nanokvm_hid.stream.ctypes.CDLL", return_value=mock_lib),
        patch("nanokvm_hid.stream.Path.exists", return_value=True),
        Stream(lib_path=str(fake_so)),
    ):
        pass
    mock_lib.kvmv_deinit.assert_called_once()


def test_lib_not_found():
    with pytest.raises(FileNotFoundError, match="libkvm.so not found"):
        Stream(lib_path="/nonexistent/libkvm.so")


# ── fps ──────────────────────────────────────────────────────────────


def test_get_fps(mock_lib, stream):
    mock_lib.kvmv_get_fps.return_value = 30
    assert stream.fps == 30


@pytest.mark.parametrize("fps", [0, 1, 30, 60, 120])
def test_set_fps_valid(mock_lib, stream, fps):
    stream.set_fps(fps)
    mock_lib.kvmv_set_fps.assert_called_once()


@pytest.mark.parametrize("fps", [-1, 121, 200])
def test_set_fps_out_of_range(stream, fps):
    with pytest.raises(ValueError, match="FPS must be"):
        stream.set_fps(fps)


def test_set_fps_hw_failure(mock_lib, stream):
    mock_lib.kvmv_set_fps.return_value = -1
    with pytest.raises(RuntimeError, match="kvmv_set_fps"):
        stream.set_fps(30)


# ── gop ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("gop", [1, 50, 200])
def test_set_gop_valid(mock_lib, stream, gop):
    stream.set_gop(gop)
    mock_lib.kvmv_set_gop.assert_called_once()


@pytest.mark.parametrize("gop", [0, 201, -1])
def test_set_gop_out_of_range(stream, gop):
    with pytest.raises(ValueError, match="GOP must be"):
        stream.set_gop(gop)


def test_set_gop_hw_failure(mock_lib, stream):
    mock_lib.kvmv_set_gop.return_value = -1
    with pytest.raises(RuntimeError, match="kvmv_set_gop"):
        stream.set_gop(50)


# ── rate control ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode",
    ["cbr", "vbr", "CBR", "VBR", RATE_CONTROL_CBR, RATE_CONTROL_VBR],
)
def test_set_rate_control_valid(mock_lib, stream, mode):
    stream.set_rate_control(mode)
    mock_lib.kvmv_set_rate_control.assert_called_once()


@pytest.mark.parametrize("mode", ["invalid", 5, "abr"])
def test_set_rate_control_invalid(stream, mode):
    with pytest.raises(ValueError, match="Unknown rate-control"):
        stream.set_rate_control(mode)


def test_set_rate_control_hw_failure(mock_lib, stream):
    mock_lib.kvmv_set_rate_control.return_value = -1
    with pytest.raises(RuntimeError, match="kvmv_set_rate_control"):
        stream.set_rate_control("cbr")


# ── closed ───────────────────────────────────────────────────────────


def test_fps_after_close(mock_lib, stream):
    stream.close()
    with pytest.raises(RuntimeError, match="closed"):
        _ = stream.fps


def test_set_fps_after_close(mock_lib, stream):
    stream.close()
    with pytest.raises(RuntimeError, match="closed"):
        stream.set_fps(30)


# ── repr ─────────────────────────────────────────────────────────────


def test_repr_open(mock_lib, stream):
    mock_lib.kvmv_get_fps.return_value = 25
    assert "fps=25" in repr(stream)


def test_repr_closed(mock_lib, stream):
    stream.close()
    assert "closed" in repr(stream)
