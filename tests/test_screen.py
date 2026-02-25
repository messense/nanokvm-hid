"""Tests for screen capture."""

from __future__ import annotations

import base64
import io
import urllib.error
from unittest.mock import patch

import pytest

from nanokvm_hid.screen import Screen, screen_size

# A minimal valid JPEG (1x1 white pixel)
TINY_JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300080606070605080707070909080a0c"
    "140d0c0b0b0c1912130f141d1a1f1e1d1a1c1c"
    "20242e2720222c231c1c2837292c30313434341f"
    "27393d38323c2e333432ffc0000b080001000101"
    "011100ffc4001f000001050101010101010000000"
    "00000000001020304050607080910ffda00080101"
    "00003f00f57dbd4900ffd9"
)


def _build_mjpeg_body(jpeg: bytes) -> bytes:
    """Build a minimal MJPEG multipart response body."""
    boundary = b"--frame"
    return (
        boundary
        + b"\r\nContent-Type: image/jpeg\r\n"
        + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
        + jpeg
        + b"\r\n"
        + boundary
        + b"\r\n"
    )


def _mjpeg_resp(jpeg: bytes = TINY_JPEG):
    """Create a fake MJPEG HTTP response."""
    body = _build_mjpeg_body(jpeg)
    resp = io.BytesIO(body)
    resp.headers = {"Content-Type": "multipart/x-mixed-replace; boundary=frame"}
    resp.close = lambda: None
    return resp


def _pikvm_resp(data: bytes = TINY_JPEG):
    """Create a fake PiKVM snapshot HTTP response."""
    resp = io.BytesIO(data)
    resp.read = lambda: data
    resp.close = lambda: None
    return resp


# ── screen_size ──────────────────────────────────────────────────────


def test_screen_size_reads_from_proc(tmp_path):
    (tmp_path / "width").write_text("1920\n")
    (tmp_path / "height").write_text("1080\n")
    with (
        patch("nanokvm_hid.screen._SCREEN_WIDTH_PATH", str(tmp_path / "width")),
        patch("nanokvm_hid.screen._SCREEN_HEIGHT_PATH", str(tmp_path / "height")),
    ):
        assert screen_size() == (1920, 1080)


def test_screen_size_fallback():
    with (
        patch("nanokvm_hid.screen._SCREEN_WIDTH_PATH", "/nonexistent/w"),
        patch("nanokvm_hid.screen._SCREEN_HEIGHT_PATH", "/nonexistent/h"),
    ):
        assert screen_size() == (1920, 1080)


# ── MJPEG capture ────────────────────────────────────────────────────


def test_mjpeg_capture():
    with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=_mjpeg_resp()):
        result = Screen().capture()
    assert result[:2] == b"\xff\xd8"
    assert result[-2:] == b"\xff\xd9"


def test_mjpeg_capture_to_file(tmp_path):
    out = tmp_path / "shot.jpg"
    with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=_mjpeg_resp()):
        path = Screen().capture_to_file(out)
    assert path.exists()
    assert out.read_bytes()[:2] == b"\xff\xd8"


def test_mjpeg_capture_base64():
    with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=_mjpeg_resp()):
        b64 = Screen().capture_base64()
    assert base64.b64decode(b64)[:2] == b"\xff\xd8"


def test_mjpeg_connection_error():
    with (
        patch(
            "nanokvm_hid.screen.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ),
        pytest.raises(ConnectionError, match="Cannot connect"),
    ):
        Screen().capture()


def test_mjpeg_bad_content_type():
    resp = io.BytesIO(b"nope")
    resp.headers = {"Content-Type": "text/html"}
    resp.close = lambda: None
    with (
        patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=resp),
        pytest.raises(ValueError, match="Unexpected Content-Type"),
    ):
        Screen().capture()


# ── PiKVM capture ────────────────────────────────────────────────────


def test_pikvm_capture():
    with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=_pikvm_resp()):
        result = Screen(pikvm=True).capture()
    assert result[:2] == b"\xff\xd8"
    assert result[-2:] == b"\xff\xd9"


def test_pikvm_capture_to_file(tmp_path):
    out = tmp_path / "pikvm.jpg"
    with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=_pikvm_resp()):
        Screen(pikvm=True).capture_to_file(out)
    assert out.read_bytes()[:2] == b"\xff\xd8"


def test_pikvm_invalid_data():
    with (
        patch(
            "nanokvm_hid.screen.urllib.request.urlopen",
            return_value=_pikvm_resp(b"not jpeg"),
        ),
        pytest.raises(ValueError, match="did not return a valid JPEG"),
    ):
        Screen(pikvm=True).capture()


def test_pikvm_connection_error():
    with (
        patch(
            "nanokvm_hid.screen.urllib.request.urlopen",
            side_effect=urllib.error.URLError("refused"),
        ),
        pytest.raises(ConnectionError, match="PiKVM"),
    ):
        Screen(pikvm=True).capture()


def test_pikvm_custom_credentials():
    s = Screen(pikvm=True, pikvm_username="user", pikvm_password="pass123")
    assert s.pikvm_username == "user"
    assert s.pikvm_password == "pass123"


def test_pikvm_sends_basic_auth():
    with patch(
        "nanokvm_hid.screen.urllib.request.urlopen", return_value=_pikvm_resp()
    ) as mock_urlopen:
        Screen(pikvm=True, pikvm_username="admin", pikvm_password="secret").capture()

    req = mock_urlopen.call_args[0][0]
    auth = req.get_header("Authorization")
    assert auth.startswith("Basic ")
    assert base64.b64decode(auth.split(" ", 1)[1]).decode() == "admin:secret"
