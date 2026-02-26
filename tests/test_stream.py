"""Tests for stream encoder control (HTTP API wrapper) and video capture."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch

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
    VideoFrame,
    _parse_frame,
)

# ── helpers ──────────────────────────────────────────────────────────


def _make_ws_msg(
    is_key: bool = False,
    timestamp_us: int = 0,
    nal_data: bytes = b"\x00\x00\x00\x01\x65",
) -> bytes:
    """Build a binary WebSocket message in the direct-stream format."""
    msg = bytes([1 if is_key else 0])
    msg += struct.pack("<Q", timestamp_us)
    msg += nal_data
    return msg


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


# ── VideoFrame ───────────────────────────────────────────────────────


def test_video_frame_creation():
    frame = VideoFrame(
        is_key_frame=True, timestamp_us=12345, data=b"\xab" * 10, codec="h264"
    )
    assert frame.is_key_frame is True
    assert frame.timestamp_us == 12345
    assert len(frame.data) == 10
    assert frame.codec == "h264"


def test_video_frame_frozen():
    frame = VideoFrame(is_key_frame=True, timestamp_us=0, data=b"", codec="h264")
    with pytest.raises(dataclasses.FrozenInstanceError):
        frame.is_key_frame = False  # type: ignore[misc]


def test_video_frame_equality():
    data = b"\x00\x00\x00\x01\x65"
    a = VideoFrame(is_key_frame=True, timestamp_us=100, data=data, codec="h264")
    b = VideoFrame(is_key_frame=True, timestamp_us=100, data=data, codec="h264")
    assert a == b


# ── _parse_frame ─────────────────────────────────────────────────────


def test_parse_frame_keyframe():
    nal = b"\x00\x00\x00\x01\x65" + b"\xab" * 50
    msg = _make_ws_msg(is_key=True, timestamp_us=99000, nal_data=nal)
    frame = _parse_frame(msg, "h264")
    assert frame is not None
    assert frame.is_key_frame is True
    assert frame.timestamp_us == 99000
    assert frame.data == nal
    assert frame.codec == "h264"


def test_parse_frame_non_key():
    msg = _make_ws_msg(is_key=False, timestamp_us=33000)
    frame = _parse_frame(msg, "h265")
    assert frame is not None
    assert frame.is_key_frame is False
    assert frame.codec == "h265"


def test_parse_frame_too_short():
    # Exactly header size (9 bytes) — no data after header
    assert _parse_frame(b"\x00" * 9, "h264") is None
    assert _parse_frame(b"\x00" * 5, "h264") is None
    assert _parse_frame(b"", "h264") is None


def test_parse_frame_not_bytes():
    assert _parse_frame("text message", "h264") is None  # type: ignore[arg-type]


def test_parse_frame_minimal():
    """10 bytes = 9 header + 1 data byte — should parse."""
    msg = b"\x01" + struct.pack("<Q", 42) + b"\xff"
    frame = _parse_frame(msg, "h264")
    assert frame is not None
    assert frame.is_key_frame is True
    assert frame.timestamp_us == 42
    assert frame.data == b"\xff"


# ── _ws_url ──────────────────────────────────────────────────────────


def test_ws_url_https(stream):
    assert stream._ws_url("h264") == "wss://localhost/api/stream/h264/direct"
    assert stream._ws_url("h265") == "wss://localhost/api/stream/h265/direct"


def test_ws_url_http():
    s = Stream(base_url="http://localhost/api/stream")
    assert s._ws_url("h264") == "ws://localhost/api/stream/h264/direct"


def test_ws_url_custom_base():
    s = Stream(base_url="https://10.0.0.1:8443/api/stream")
    assert s._ws_url("h265") == "wss://10.0.0.1:8443/api/stream/h265/direct"


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

    with (
        patch(
            "nanokvm_hid.stream.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ),
        pytest.raises(ConnectionError, match="Cannot connect"),
    ):
        stream.set_fps(30)


# ── server error response ───────────────────────────────────────────


def test_server_error_response(stream):
    resp = MagicMock()
    resp.read.return_value = json.dumps(
        {"code": -1, "msg": "failed"},
    ).encode()
    with (
        patch(
            "nanokvm_hid.stream.urllib.request.urlopen",
            return_value=resp,
        ),
        pytest.raises(RuntimeError, match="Server returned error"),
    ):
        stream.set_fps(30)


# ── status ───────────────────────────────────────────────────────────


def test_status(stream):
    """status() should parse the /api/streamer/local response."""
    body = {
        "ok": True,
        "result": {
            "streamer": {
                "h264": {
                    "bitrate": 8000,
                    "real_bitrate": 8000,
                    "fps": 25,
                    "gop": 30,
                    "online": False,
                },
                "source": {
                    "captured_fps": 12,
                    "desired_fps": 0,
                    "online": False,
                    "resolution": {"height": 2160, "width": 3840},
                },
            },
        },
    }
    resp = MagicMock()
    resp.read.return_value = json.dumps(body).encode()
    with patch(
        "nanokvm_hid.stream.urllib.request.urlopen",
        return_value=resp,
    ):
        info = stream.status()
    assert info["fps"] == 25
    assert info["gop"] == 30
    assert info["bitrate"] == 8000
    assert info["resolution"] == {"width": 3840, "height": 2160}
    assert info["captured_fps"] == 12


def test_status_empty_response(stream):
    """status() should handle missing fields gracefully."""
    resp = MagicMock()
    resp.read.return_value = json.dumps({"ok": True, "result": {}}).encode()
    with patch(
        "nanokvm_hid.stream.urllib.request.urlopen",
        return_value=resp,
    ):
        info = stream.status()
    assert info["fps"] == 0
    assert info["gop"] == 0
    assert info["bitrate"] == 0
    assert info["resolution"] == {"width": 0, "height": 0}
    assert info["captured_fps"] == 0


def test_status_connection_error(stream):
    import urllib.error

    with (
        patch(
            "nanokvm_hid.stream.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ),
        pytest.raises(ConnectionError, match="Cannot connect"),
    ):
        stream.status()


# ── record (sync) ────────────────────────────────────────────────────


def test_record_h264(tmp_path, stream):
    """record() should write NAL data to file and return stats."""
    nal1 = b"\x00\x00\x00\x01" + b"\x65" * 100
    nal2 = b"\x00\x00\x00\x01" + b"\x41" * 50
    msgs = [
        _make_ws_msg(is_key=True, timestamp_us=0, nal_data=nal1),
        _make_ws_msg(is_key=False, timestamp_us=33000, nal_data=nal2),
    ]

    mock_ws = MagicMock()
    mock_ws.recv = MagicMock(side_effect=msgs + [TimeoutError()])
    mock_ws.close = MagicMock()

    output = str(tmp_path / "test.h264")

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        result = stream.record(output, codec="h264")

    assert result["frames"] == 2
    assert result["bytes"] == len(nal1) + len(nal2)
    assert result["codec"] == "h264"
    assert result["file"] == output
    assert result["duration"] >= 0

    with open(output, "rb") as f:
        data = f.read()
    assert data == nal1 + nal2


def test_record_h265(tmp_path, stream):
    """record() should work with h265 codec."""
    nal = b"\x00\x00\x00\x01\x40\x01" + b"\xab" * 80
    msgs = [_make_ws_msg(is_key=True, timestamp_us=0, nal_data=nal)]

    mock_ws = MagicMock()
    mock_ws.recv = MagicMock(side_effect=msgs + [TimeoutError()])
    mock_ws.close = MagicMock()

    output = str(tmp_path / "test.h265")

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        result = stream.record(output, codec="h265")

    assert result["frames"] == 1
    assert result["codec"] == "h265"


def test_record_max_frames(tmp_path, stream):
    """record() should stop after max_frames."""
    msgs = [
        _make_ws_msg(timestamp_us=i * 33000, nal_data=b"\x00\x00\x00\x01" + b"\x41")
        for i in range(10)
    ]

    mock_ws = MagicMock()
    mock_ws.recv = MagicMock(side_effect=msgs)
    mock_ws.close = MagicMock()

    output = str(tmp_path / "test.h264")

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        result = stream.record(output, max_frames=3)

    assert result["frames"] == 3


def test_record_invalid_codec(stream):
    with pytest.raises(ValueError, match="codec must be"):
        stream.record("out.h264", codec="vp9")


def test_record_connection_error(stream):
    with (
        patch("websockets.sync.client.connect", side_effect=OSError("refused")),
        pytest.raises(ConnectionError, match="Cannot connect"),
    ):
        stream.record("out.h264")


def test_record_skips_short_messages(tmp_path, stream):
    """record() should skip messages that are too short to parse."""
    nal = b"\x00\x00\x00\x01\x65" * 20
    msgs = [
        b"\x00" * 5,  # too short — skipped
        _make_ws_msg(is_key=True, timestamp_us=0, nal_data=nal),
    ]

    mock_ws = MagicMock()
    mock_ws.recv = MagicMock(side_effect=msgs + [TimeoutError()])
    mock_ws.close = MagicMock()

    output = str(tmp_path / "test.h264")

    with patch("websockets.sync.client.connect", return_value=mock_ws):
        result = stream.record(output)

    assert result["frames"] == 1


def test_record_closes_websocket_on_error(tmp_path, stream):
    """record() should always close the websocket, even on file error."""
    mock_ws = MagicMock()
    mock_ws.close = MagicMock()

    # Point to a non-writable path
    output = str(tmp_path / "nonexistent_dir" / "test.h264")

    with (
        patch("websockets.sync.client.connect", return_value=mock_ws),
        pytest.raises(FileNotFoundError),
    ):
        stream.record(output)

    mock_ws.close.assert_called_once()


# ── capture (async) ──────────────────────────────────────────────────


def test_capture_basic(stream):
    """capture() should yield VideoFrame objects."""
    nal = b"\x00\x00\x00\x01\x65" * 20
    msgs = [
        _make_ws_msg(is_key=(i == 0), timestamp_us=i * 33000, nal_data=nal)
        for i in range(5)
    ]

    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=msgs)
    mock_ws.close = AsyncMock()

    async def _test():
        frames = []
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            async for frame in stream.capture("h264", max_frames=3):
                frames.append(frame)
        return frames

    frames = asyncio.run(_test())
    assert len(frames) == 3
    assert frames[0].is_key_frame is True
    assert frames[0].codec == "h264"
    assert frames[1].is_key_frame is False


def test_capture_h265(stream):
    """capture() should work with h265 codec."""
    nal = b"\x00\x00\x00\x01\x40\x01" * 10
    msgs = [_make_ws_msg(is_key=True, timestamp_us=0, nal_data=nal)]

    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=msgs)
    mock_ws.close = AsyncMock()

    async def _test():
        frames = []
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            async for frame in stream.capture("h265", max_frames=1):
                frames.append(frame)
        return frames

    frames = asyncio.run(_test())
    assert len(frames) == 1
    assert frames[0].codec == "h265"


def test_capture_invalid_codec(stream):
    """capture() should reject invalid codecs without connecting."""

    async def _test():
        async for _ in stream.capture("vp9"):
            pass

    with pytest.raises(ValueError, match="codec must be"):
        asyncio.run(_test())


def test_capture_connection_error(stream):
    """capture() should raise ConnectionError on connect failure."""

    async def _test():
        with patch("websockets.connect", AsyncMock(side_effect=OSError("refused"))):
            async for _ in stream.capture("h264"):
                pass

    with pytest.raises(ConnectionError, match="Cannot connect"):
        asyncio.run(_test())


def test_capture_timeout_stops(stream):
    """capture() should stop when recv() times out."""
    msgs = [
        _make_ws_msg(timestamp_us=0),
        _make_ws_msg(timestamp_us=33000),
    ]

    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=msgs + [TimeoutError()])
    mock_ws.close = AsyncMock()

    async def _test():
        frames = []
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            async for frame in stream.capture("h264"):
                frames.append(frame)
        return frames

    frames = asyncio.run(_test())
    assert len(frames) == 2


def test_capture_skips_short_messages(stream):
    """capture() should skip unparseable messages."""
    nal = b"\x00\x00\x00\x01\x65"
    msgs = [
        b"\x00" * 3,  # too short
        _make_ws_msg(is_key=True, timestamp_us=0, nal_data=nal),
    ]

    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=msgs + [TimeoutError()])
    mock_ws.close = AsyncMock()

    async def _test():
        frames = []
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            async for frame in stream.capture("h264"):
                frames.append(frame)
        return frames

    frames = asyncio.run(_test())
    assert len(frames) == 1
    assert frames[0].is_key_frame is True


def test_capture_closes_websocket(stream):
    """capture() should close the websocket even if iteration stops early."""
    msgs = [_make_ws_msg(timestamp_us=i * 33000) for i in range(10)]

    mock_ws = AsyncMock()
    mock_ws.recv = AsyncMock(side_effect=msgs)
    mock_ws.close = AsyncMock()

    async def _test():
        with patch("websockets.connect", AsyncMock(return_value=mock_ws)):
            async for _ in stream.capture("h264", max_frames=2):
                pass

    asyncio.run(_test())
    mock_ws.close.assert_called_once()


# ── repr ─────────────────────────────────────────────────────────────


def test_repr(stream):
    assert "https://localhost/api/stream" in repr(stream)
