"""Screen capture via the NanoKVM's MJPEG video stream."""

from __future__ import annotations

import logging
import ssl
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MJPEG_URL = "https://localhost/api/stream/mjpeg"

# Screen resolution source on NanoKVM (LT6911 HDMI capture chip)
_SCREEN_WIDTH_PATH = "/proc/lt6911_info/width"
_SCREEN_HEIGHT_PATH = "/proc/lt6911_info/height"


def _make_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips certificate verification.

    The NanoKVM serves its MJPEG stream over HTTPS with a self-signed
    certificate, so verification must be disabled for localhost access.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def screen_size() -> tuple[int, int]:
    """Read the captured screen resolution from the HDMI capture chip.

    Returns ``(width, height)`` or ``(1920, 1080)`` as fallback.
    """
    try:
        w = int(Path(_SCREEN_WIDTH_PATH).read_text().strip())
        h = int(Path(_SCREEN_HEIGHT_PATH).read_text().strip())
        return w, h
    except (FileNotFoundError, ValueError, OSError) as exc:
        logger.warning("Cannot read screen size (%s), using 1920×1080", exc)
        return 1920, 1080


class Screen:
    """Capture screenshots from the NanoKVM's HDMI video stream.

    Parameters
    ----------
    url:
        URL of the MJPEG stream endpoint.
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        url: str = DEFAULT_MJPEG_URL,
        timeout: float = 10,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self._ssl_ctx = _make_ssl_context()

    def capture(self) -> bytes:
        """Capture a single JPEG frame from the MJPEG stream.

        Returns
        -------
        bytes
            Raw JPEG image data.

        Raises
        ------
        ConnectionError
            If the stream cannot be reached.
        ValueError
            If no valid JPEG frame is found.
        """
        try:
            req = urllib.request.Request(self.url)
            resp = urllib.request.urlopen(
                req, timeout=self.timeout, context=self._ssl_ctx
            )
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionError(f"Cannot connect to MJPEG stream: {exc}") from exc

        content_type = resp.headers.get("Content-Type", "")
        if "multipart/x-mixed-replace" not in content_type:
            raise ValueError(f"Unexpected Content-Type: {content_type}")

        # Extract boundary
        if "boundary=" in content_type:
            boundary = b"--" + content_type.split("boundary=")[-1].strip('";').encode()
        else:
            raise ValueError("Cannot find boundary in Content-Type header")

        buf = bytearray()
        max_frames = 3  # try up to N frames before giving up

        try:
            while True:
                chunk = resp.read(16384)
                if not chunk:
                    break
                buf.extend(chunk)

                while True:
                    pos = buf.find(boundary)
                    if pos == -1:
                        break

                    frame_data = bytes(buf[:pos])
                    del buf[: pos + len(boundary)]

                    jpeg_start = frame_data.find(b"\xff\xd8")
                    jpeg_end = frame_data.find(
                        b"\xff\xd9", jpeg_start if jpeg_start != -1 else 0
                    )
                    if jpeg_start != -1 and jpeg_end != -1:
                        jpeg_bytes = frame_data[jpeg_start : jpeg_end + 2]
                        logger.info("Captured frame: %d bytes", len(jpeg_bytes))
                        return jpeg_bytes

                    max_frames -= 1
                    if max_frames <= 0:
                        raise ValueError("Failed to extract JPEG from multiple frames")
        finally:
            resp.close()

        raise ValueError("No valid JPEG frame found in stream")

    def capture_to_file(self, path: str | Path) -> Path:
        """Capture a screenshot and save it to a file.

        Parameters
        ----------
        path:
            Destination file path (e.g. ``"screenshot.jpg"``).

        Returns
        -------
        Path
            The resolved path of the saved file.
        """
        jpeg_data = self.capture()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(jpeg_data)
        logger.info("Saved screenshot to %s (%d bytes)", out, len(jpeg_data))
        return out.resolve()

    def capture_base64(self) -> str:
        """Capture a screenshot and return it as a base64-encoded string."""
        import base64

        return base64.b64encode(self.capture()).decode("ascii")

    @staticmethod
    def screen_size() -> tuple[int, int]:
        """Read the screen resolution from the HDMI capture chip."""
        return screen_size()

    def __repr__(self) -> str:
        return f"Screen(url={self.url!r})"
