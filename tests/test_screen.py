"""Tests for screen capture."""

from __future__ import annotations

import io
from pathlib import Path
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
    part = (
        boundary
        + b"\r\n"
        + b"Content-Type: image/jpeg\r\n"
        + f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
        + jpeg
        + b"\r\n"
        + boundary
        + b"\r\n"
    )
    return part


class TestScreenSize:
    def test_reads_from_proc(self, tmp_path: Path) -> None:
        w_file = tmp_path / "width"
        h_file = tmp_path / "height"
        w_file.write_text("1920\n")
        h_file.write_text("1080\n")

        with (
            patch("nanokvm_hid.screen._SCREEN_WIDTH_PATH", str(w_file)),
            patch("nanokvm_hid.screen._SCREEN_HEIGHT_PATH", str(h_file)),
        ):
            assert screen_size() == (1920, 1080)

    def test_fallback_on_missing(self) -> None:
        with (
            patch("nanokvm_hid.screen._SCREEN_WIDTH_PATH", "/nonexistent/w"),
            patch("nanokvm_hid.screen._SCREEN_HEIGHT_PATH", "/nonexistent/h"),
        ):
            assert screen_size() == (1920, 1080)


class TestCapture:
    def test_capture_parses_jpeg_from_mjpeg(self) -> None:
        body = _build_mjpeg_body(TINY_JPEG)
        content_type = "multipart/x-mixed-replace; boundary=frame"

        resp = io.BytesIO(body)
        resp.headers = {"Content-Type": content_type}
        resp.close = lambda: None

        screen = Screen()
        with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=resp):
            result = screen.capture()

        assert result[:2] == b"\xff\xd8"  # JPEG SOI
        assert result[-2:] == b"\xff\xd9"  # JPEG EOI

    def test_capture_to_file(self, tmp_path: Path) -> None:
        body = _build_mjpeg_body(TINY_JPEG)
        content_type = "multipart/x-mixed-replace; boundary=frame"

        resp = io.BytesIO(body)
        resp.headers = {"Content-Type": content_type}
        resp.close = lambda: None

        screen = Screen()
        out = tmp_path / "shot.jpg"
        with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=resp):
            result_path = screen.capture_to_file(out)

        assert result_path.exists()
        data = out.read_bytes()
        assert data[:2] == b"\xff\xd8"

    def test_capture_base64(self) -> None:
        import base64

        body = _build_mjpeg_body(TINY_JPEG)
        content_type = "multipart/x-mixed-replace; boundary=frame"

        resp = io.BytesIO(body)
        resp.headers = {"Content-Type": content_type}
        resp.close = lambda: None

        screen = Screen()
        with patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=resp):
            b64 = screen.capture_base64()

        decoded = base64.b64decode(b64)
        assert decoded[:2] == b"\xff\xd8"

    def test_capture_connection_error(self) -> None:
        import urllib.error

        screen = Screen()
        with (
            patch(
                "nanokvm_hid.screen.urllib.request.urlopen",
                side_effect=urllib.error.URLError("refused"),
            ),
            pytest.raises(ConnectionError, match="Cannot connect"),
        ):
            screen.capture()

    def test_capture_bad_content_type(self) -> None:
        resp = io.BytesIO(b"not mjpeg")
        resp.headers = {"Content-Type": "text/html"}
        resp.close = lambda: None

        screen = Screen()
        with (
            patch("nanokvm_hid.screen.urllib.request.urlopen", return_value=resp),
            pytest.raises(ValueError, match="Unexpected Content-Type"),
        ):
            screen.capture()
