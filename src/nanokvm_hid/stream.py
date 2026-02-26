"""Stream encoder control via the NanoKVM server's HTTP API.

Controls the hardware video encoder parameters by calling the NanoKVM
server's local API endpoints.  The server's ``CheckToken`` middleware
skips authentication for localhost requests, so no credentials are
needed when running on-device.

The NanoKVM server is the single owner of the hardware encoder
(``libkvm.so``).  Encoder state is per-process, so only HTTP requests
to the server can modify the live stream parameters.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

# Rate-control modes
RATE_CONTROL_CBR = "cbr"
RATE_CONTROL_VBR = "vbr"

# Stream modes (match server/common/screen.go StreamTypeMap)
STREAM_MODE_MJPEG = "mjpeg"
STREAM_MODE_H264_WEBRTC = "h264-webrtc"
STREAM_MODE_H264_DIRECT = "h264-direct"
STREAM_MODE_H265_WEBRTC = "h265-webrtc"
STREAM_MODE_H265_DIRECT = "h265-direct"

_VALID_MODES = {
    STREAM_MODE_MJPEG,
    STREAM_MODE_H264_WEBRTC,
    STREAM_MODE_H264_DIRECT,
    STREAM_MODE_H265_WEBRTC,
    STREAM_MODE_H265_DIRECT,
}


def _make_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips certificate verification."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class Stream:
    """Control the NanoKVM hardware video encoder.

    Communicates with the NanoKVM server over its local HTTPS API.
    No authentication is required when running on the device itself
    (the server skips auth for localhost connections).

    Parameters
    ----------
    base_url:
        Base URL of the NanoKVM server API.
    timeout:
        HTTP request timeout in seconds.

    Example::

        from nanokvm_hid import Stream

        stream = Stream()
        stream.set_fps(30)                  # cap at 30 FPS
        stream.set_gop(50)                  # set GOP length
        stream.set_quality(80)              # MJPEG quality (1–100)
        stream.set_bitrate(5000)            # H264/H265 bitrate (1000–20000)
        stream.set_rate_control("vbr")      # "cbr" or "vbr"
        stream.set_mode("h264-webrtc")      # stream mode
    """

    def __init__(
        self,
        base_url: str = "https://localhost/api/stream",
        timeout: float = 5,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._ssl_ctx = _make_ssl_context()

    # ── internal ──────────────────────────────────────────────────

    def _post(self, endpoint: str, **params: str | int) -> dict:
        """POST to a stream API endpoint and return the JSON response."""
        url = f"{self._base_url}/{endpoint}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")

        try:
            resp = urllib.request.urlopen(
                req, timeout=self._timeout, context=self._ssl_ctx,
            )
            body = json.loads(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to NanoKVM server at {url}: {exc}"
            ) from exc

        if body.get("code") != 0:
            raise RuntimeError(
                f"Server returned error for {endpoint}: {body}"
            )
        return body

    # ── FPS ───────────────────────────────────────────────────────

    def set_fps(self, fps: int) -> None:
        """Set encoder FPS.

        Parameters
        ----------
        fps:
            Target FPS (0–120).  0 means automatic/uncapped.

        Raises
        ------
        ValueError
            If *fps* is out of range.
        """
        if not 0 <= fps <= 120:
            raise ValueError(f"FPS must be 0–120, got {fps}")
        self._post("fps", fps=fps)
        logger.info("set FPS to %d", fps)

    # ── GOP ───────────────────────────────────────────────────────

    def set_gop(self, gop: int) -> None:
        """Set encoder GOP (group-of-pictures) length.

        Parameters
        ----------
        gop:
            GOP length (1–200).

        Raises
        ------
        ValueError
            If *gop* is out of range.
        """
        if not 1 <= gop <= 200:
            raise ValueError(f"GOP must be 1–200, got {gop}")
        self._post("gop", gop=gop)
        logger.info("set GOP to %d", gop)

    # ── quality / bitrate ─────────────────────────────────────────

    def set_quality(self, quality: int) -> None:
        """Set MJPEG quality.

        Parameters
        ----------
        quality:
            Quality level (1–100).  Higher is better.

        Raises
        ------
        ValueError
            If *quality* is out of range.
        """
        if not 1 <= quality <= 100:
            raise ValueError(f"Quality must be 1–100, got {quality}")
        self._post("quality", quality=quality)
        logger.info("set quality to %d", quality)

    def set_bitrate(self, bitrate: int) -> None:
        """Set H264/H265 encoder bitrate.

        Parameters
        ----------
        bitrate:
            Bitrate in kbps (1000–20000).

        Raises
        ------
        ValueError
            If *bitrate* is out of range.
        """
        if not 1000 <= bitrate <= 20000:
            raise ValueError(f"Bitrate must be 1000–20000, got {bitrate}")
        # The server uses the quality endpoint for both; values > 100
        # are treated as bitrate.
        self._post("quality", quality=bitrate)
        logger.info("set bitrate to %d kbps", bitrate)

    # ── rate control ──────────────────────────────────────────────

    def set_rate_control(self, mode: str) -> None:
        """Set encoder rate-control mode.

        Parameters
        ----------
        mode:
            ``"cbr"`` (constant bitrate) or ``"vbr"`` (variable bitrate).

        Raises
        ------
        ValueError
            If *mode* is not recognised.
        """
        mode_lower = mode.lower()
        if mode_lower not in (RATE_CONTROL_CBR, RATE_CONTROL_VBR):
            raise ValueError(
                f"Unknown rate-control mode: {mode!r}"
                " (use 'cbr' or 'vbr')"
            )
        self._post("rate-control", mode=mode_lower)
        logger.info("set rate control to %s", mode_lower.upper())

    # ── stream mode ───────────────────────────────────────────────

    def set_mode(self, mode: str) -> None:
        """Set the streaming mode.

        Parameters
        ----------
        mode:
            One of ``"mjpeg"``, ``"h264-webrtc"``, ``"h264-direct"``,
            ``"h265-webrtc"``, ``"h265-direct"``.

        Raises
        ------
        ValueError
            If *mode* is not recognised.
        """
        mode_lower = mode.lower()
        if mode_lower not in _VALID_MODES:
            valid = ", ".join(sorted(_VALID_MODES))
            raise ValueError(
                f"Unknown stream mode: {mode!r} (choose from: {valid})"
            )
        self._post("mode", mode=mode_lower)
        logger.info("set stream mode to %s", mode_lower)

    # ── repr ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"Stream(url={self._base_url!r})"
