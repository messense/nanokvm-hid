"""Screen capture via the NanoKVM's MJPEG video stream or PiKVM snapshot API."""

from __future__ import annotations

import base64
import logging
import ssl
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_MJPEG_URL = "https://localhost/api/stream/mjpeg"
DEFAULT_PIKVM_SNAPSHOT_URL = (
    "https://localhost/api/streamer/snapshot?save=1&preview_quality=95"
)
DEFAULT_PIKVM_USERNAME = "admin"
DEFAULT_PIKVM_PASSWORD = "admin"

# Screen resolution source on NanoKVM (LT6911 HDMI capture chip)
_SCREEN_WIDTH_PATH = "/proc/lt6911_info/width"
_SCREEN_HEIGHT_PATH = "/proc/lt6911_info/height"


def _make_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips certificate verification.

    The NanoKVM serves its streams over HTTPS with a self-signed
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

    Supports two capture backends:

    * **MJPEG** (default) — grabs a frame from the live MJPEG stream.
      Works with the NanoKVM's native firmware.
    * **PiKVM snapshot API** — uses the ``/api/streamer/snapshot``
      endpoint with HTTP Basic Auth.  Works when the NanoKVM is running
      in PiKVM-compatible mode.

    Parameters
    ----------
    url:
        URL of the MJPEG stream endpoint (used by default).
    timeout:
        HTTP request timeout in seconds.
    pikvm:
        If ``True``, use the PiKVM snapshot API instead of MJPEG.
    pikvm_url:
        URL of the PiKVM snapshot endpoint.
    pikvm_username:
        HTTP Basic Auth username for the PiKVM API.
    pikvm_password:
        HTTP Basic Auth password for the PiKVM API.
    """

    def __init__(
        self,
        url: str = DEFAULT_MJPEG_URL,
        timeout: float = 10,
        *,
        pikvm: bool = False,
        pikvm_url: str = DEFAULT_PIKVM_SNAPSHOT_URL,
        pikvm_username: str = DEFAULT_PIKVM_USERNAME,
        pikvm_password: str = DEFAULT_PIKVM_PASSWORD,
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.pikvm = pikvm
        self.pikvm_url = pikvm_url
        self.pikvm_username = pikvm_username
        self.pikvm_password = pikvm_password
        self._ssl_ctx = _make_ssl_context()

    def capture(self) -> bytes:
        """Capture a single JPEG screenshot.

        Uses the PiKVM snapshot API if ``pikvm=True`` was set, otherwise
        grabs a frame from the MJPEG stream.

        Returns
        -------
        bytes
            Raw JPEG image data.

        Raises
        ------
        ConnectionError
            If the endpoint cannot be reached.
        ValueError
            If no valid JPEG data is found.
        """
        if self.pikvm:
            return self._capture_pikvm()
        return self._capture_mjpeg()

    def _capture_pikvm(self) -> bytes:
        """Capture via the PiKVM snapshot API."""
        credentials = f"{self.pikvm_username}:{self.pikvm_password}"
        auth_header = "Basic " + base64.b64encode(credentials.encode()).decode("ascii")

        req = urllib.request.Request(self.pikvm_url)
        req.add_header("Authorization", auth_header)

        try:
            resp = urllib.request.urlopen(
                req, timeout=self.timeout, context=self._ssl_ctx
            )
            data = resp.read()
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to PiKVM snapshot API: {exc}"
            ) from exc

        if len(data) < 3 or data[:2] != b"\xff\xd8":
            raise ValueError(
                f"PiKVM snapshot did not return a valid JPEG "
                f"(got {len(data)} bytes, starts with {data[:20]!r})"
            )

        logger.info("Captured PiKVM snapshot: %d bytes", len(data))
        return data

    def _capture_mjpeg(self) -> bytes:
        """Capture a single JPEG frame from the MJPEG stream."""
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
                        logger.info("Captured MJPEG frame: %d bytes", len(jpeg_bytes))
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
        return base64.b64encode(self.capture()).decode("ascii")

    @staticmethod
    def screen_size() -> tuple[int, int]:
        """Read the screen resolution from the HDMI capture chip."""
        return screen_size()

    def __repr__(self) -> str:
        mode = "pikvm" if self.pikvm else "mjpeg"
        url = self.pikvm_url if self.pikvm else self.url
        return f"Screen(mode={mode!r}, url={url!r})"
