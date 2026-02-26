"""Tests for stream encoder control (HTTP API wrapper)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from nanokvm_hid.stream import (
    RATE_CONTROL_CBR,
    RATE_CONTROL_VBR,
    STREAM_MODE_H264_DIRECT,
    STREAM_MODE_H264_WEBRTC,
    STREAM_MODE_H265_DIRECT,
    STREAM_MODE_H265_WEBRTC,
    STREAM_MODE_MJPEG,
    Stream,
)

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def stream():
    """A Stream instance (no network calls are made in construction)."""
    return Stream()


@pytest.fixture()
def mock_urlopen():
    """Patch urllib.request.urlopen to return a success response."""
    resp = MagicMock()
    resp.read.return_value = json.dumps(
        {"code": 0, "msg": "success", "data": None},
    ).encode()
    with patch("nanokvm_hid.stream.urllib.request.urlopen", return_value=resp) as m:
        yield m


# ── fps ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fps", [0, 1, 30, 60, 120])
def test_set_fps_valid(stream, mock_urlopen, fps):
    stream.set_fps(fps)
    mock_urlopen.assert_called_once()
    req = mock_urlopen.call_args[0][0]
    assert b"fps=" in req.data


@pytest.mark.parametrize("fps", [-1, 121, 200])
def test_set_fps_out_of_range(stream, fps):
    with pytest.raises(ValueError, match="FPS must be"):
        stream.set_fps(fps)


# ── gop ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("gop", [1, 50, 200])
def test_set_gop_valid(stream, mock_urlopen, gop):
    stream.set_gop(gop)
    mock_urlopen.assert_called_once()


@pytest.mark.parametrize("gop", [0, 201, -1])
def test_set_gop_out_of_range(stream, gop):
    with pytest.raises(ValueError, match="GOP must be"):
        stream.set_gop(gop)


# ── quality ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("q", [1, 50, 80, 100])
def test_set_quality_valid(stream, mock_urlopen, q):
    stream.set_quality(q)
    mock_urlopen.assert_called_once()


@pytest.mark.parametrize("q", [0, 101, -1])
def test_set_quality_out_of_range(stream, q):
    with pytest.raises(ValueError, match="Quality must be"):
        stream.set_quality(q)


# ── bitrate ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("br", [1000, 5000, 8000, 20000])
def test_set_bitrate_valid(stream, mock_urlopen, br):
    stream.set_bitrate(br)
    mock_urlopen.assert_called_once()


@pytest.mark.parametrize("br", [999, 20001, 0])
def test_set_bitrate_out_of_range(stream, br):
    with pytest.raises(ValueError, match="Bitrate must be"):
        stream.set_bitrate(br)


# ── rate control ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode",
    ["cbr", "vbr", "CBR", "VBR", RATE_CONTROL_CBR, RATE_CONTROL_VBR],
)
def test_set_rate_control_valid(stream, mock_urlopen, mode):
    stream.set_rate_control(mode)
    mock_urlopen.assert_called_once()


@pytest.mark.parametrize("mode", ["invalid", "abr"])
def test_set_rate_control_invalid(stream, mode):
    with pytest.raises(ValueError, match="Unknown rate-control"):
        stream.set_rate_control(mode)


# ── stream mode ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "mode",
    [
        STREAM_MODE_MJPEG,
        STREAM_MODE_H264_WEBRTC,
        STREAM_MODE_H264_DIRECT,
        STREAM_MODE_H265_WEBRTC,
        STREAM_MODE_H265_DIRECT,
        "MJPEG",  # case-insensitive
    ],
)
def test_set_mode_valid(stream, mock_urlopen, mode):
    stream.set_mode(mode)
    mock_urlopen.assert_called_once()


@pytest.mark.parametrize("mode", ["invalid", "h266", ""])
def test_set_mode_invalid(stream, mode):
    with pytest.raises(ValueError, match="Unknown stream mode"):
        stream.set_mode(mode)


# ── connection errors ────────────────────────────────────────────────


def test_connection_error(stream):
    import urllib.error

    with patch(
        "nanokvm_hid.stream.urllib.request.urlopen",
        side_effect=urllib.error.URLError("refused"),
    ), pytest.raises(ConnectionError, match="Cannot connect"):
        stream.set_fps(30)


# ── server error response ───────────────────────────────────────────


def test_server_error_response(stream):
    resp = MagicMock()
    resp.read.return_value = json.dumps(
        {"code": -1, "msg": "failed"},
    ).encode()
    with patch(
        "nanokvm_hid.stream.urllib.request.urlopen",
        return_value=resp,
    ), pytest.raises(RuntimeError, match="Server returned error"):
        stream.set_fps(30)


# ── repr ─────────────────────────────────────────────────────────────


def test_repr(stream):
    assert "https://localhost/api/stream" in repr(stream)
