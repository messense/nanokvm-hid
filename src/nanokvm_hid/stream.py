"""Stream encoder control and video capture via the NanoKVM server.

Controls the hardware video encoder parameters by calling the NanoKVM
server's local API endpoints.  The server's ``CheckToken`` middleware
skips authentication for localhost requests, so no credentials are
needed when running on-device.

The NanoKVM server is the single owner of the hardware encoder
(``libkvm.so``).  Encoder state is per-process, so only HTTP requests
to the server can modify the live stream parameters.

Supported stream modes: MJPEG, H.264 (WebRTC/direct), H.265 (WebRTC/direct).
The NanoKVM Pro hardware (AX620Q SoC) and server binary fully support
H.265/HEVC encoding.  The web dashboard hides H.265 options because most
browsers lack H.265 WebRTC support, but this library can enable it.

Video capture
~~~~~~~~~~~~~

The ``h264-direct`` and ``h265-direct`` modes stream raw NAL units over
a WebSocket connection.  Each binary message has a 9-byte header::

    byte[0]     is_key_frame  (0 = P-frame, 1 = I-frame/keyframe)
    byte[1..8]  timestamp_us  (uint64 LE, microseconds since stream start)
    byte[9..]   NAL unit data (starts with ``00 00 00 01``)

Use :meth:`Stream.capture` (async generator) for frame-by-frame access,
or :meth:`Stream.record` (synchronous) to write a raw bitstream file.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import AsyncIterator

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


# ── Video frame ──────────────────────────────────────────────────


@dataclasses.dataclass(frozen=True, slots=True)
class VideoFrame:
    """A single video frame from the NanoKVM hardware encoder.

    The NanoKVM server streams raw NAL units over WebSocket
    (``h264-direct`` or ``h265-direct`` mode).

    Attributes
    ----------
    is_key_frame:
        ``True`` if this is an I-frame (keyframe).
    timestamp_us:
        Microseconds since the stream started.
    data:
        Raw NAL unit bytes (starts with ``00 00 00 01``).
    codec:
        ``"h264"`` or ``"h265"``.
    """

    is_key_frame: bool
    timestamp_us: int
    data: bytes
    codec: str


_VALID_CODECS = frozenset({"h264", "h265"})
_FRAME_HEADER_SIZE = 9  # 1 byte key flag + 8 bytes uint64 LE timestamp


def _parse_frame(msg: bytes, codec: str) -> VideoFrame | None:
    """Parse a direct-stream WebSocket binary message into a VideoFrame.

    Returns ``None`` if *msg* is too short or not bytes.
    """
    if not isinstance(msg, bytes) or len(msg) <= _FRAME_HEADER_SIZE:
        return None
    return VideoFrame(
        is_key_frame=msg[0] != 0,
        timestamp_us=struct.unpack_from("<Q", msg, 1)[0],
        data=msg[_FRAME_HEADER_SIZE:],
        codec=codec,
    )


# ── SSL helper ───────────────────────────────────────────────────


def _make_ssl_context() -> ssl.SSLContext:
    """Create an SSL context that skips certificate verification."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


# ── Stream class ─────────────────────────────────────────────────


class Stream:
    """Control the NanoKVM hardware video encoder and capture video.

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
        stream.set_mode("h264-direct")      # switch to direct stream
        result = stream.record("clip.h264", duration=5.0)
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

    def _get(self, url: str) -> dict:
        """GET a URL and return the parsed JSON response."""
        req = urllib.request.Request(url, method="GET")
        try:
            resp = urllib.request.urlopen(
                req,
                timeout=self._timeout,
                context=self._ssl_ctx,
            )
            return json.loads(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to NanoKVM server at {url}: {exc}"
            ) from exc

    def _post(self, endpoint: str, **params: str | int) -> dict:
        """POST to a stream API endpoint and return the JSON response."""
        url = f"{self._base_url}/{endpoint}"
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method="POST")

        try:
            resp = urllib.request.urlopen(
                req,
                timeout=self._timeout,
                context=self._ssl_ctx,
            )
            body = json.loads(resp.read())
        except (urllib.error.URLError, OSError) as exc:
            raise ConnectionError(
                f"Cannot connect to NanoKVM server at {url}: {exc}"
            ) from exc

        if body.get("code") != 0:
            raise RuntimeError(f"Server returned error for {endpoint}: {body}")
        return body

    def _ws_url(self, codec: str) -> str:
        """Build WebSocket URL for direct video streaming.

        Converts ``https://…/api/stream`` → ``wss://…/api/stream/<codec>/direct``.
        """
        url = self._base_url
        if url.startswith("https://"):
            url = "wss://" + url[8:]
        elif url.startswith("http://"):
            url = "ws://" + url[7:]
        return f"{url}/{codec}/direct"

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
                f"Unknown rate-control mode: {mode!r} (use 'cbr' or 'vbr')"
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
            raise ValueError(f"Unknown stream mode: {mode!r} (choose from: {valid})")
        self._post("mode", mode=mode_lower)
        logger.info("set stream mode to %s", mode_lower)

    # ── status ─────────────────────────────────────────────────────

    def status(self) -> dict:
        """Read current stream encoder state from the server.

        Uses the PiKVM-compatible ``/api/streamer/local`` endpoint which
        returns the server's in-memory ``Screen`` struct values.

        Returns
        -------
        dict
            A dictionary with keys:

            - ``fps`` (int): current target FPS (0 = auto)
            - ``gop`` (int): current GOP length
            - ``bitrate`` (int): current bitrate in kbps
            - ``resolution`` (dict): ``{"width": int, "height": int}``
            - ``captured_fps`` (int): actual captured FPS from HDMI input

        Note
        ----
        The server does not expose ``quality``, ``stream_mode``, or
        ``rate_control`` via any GET endpoint.  Those values are only
        settable, not readable.

        Raises
        ------
        ConnectionError
            If the server cannot be reached.
        """
        # /api/streamer/local is under the API base, go up one level
        # from /api/stream to /api/streamer/local
        base = self._base_url.rsplit("/stream", 1)[0]
        url = f"{base}/streamer/local"
        body = self._get(url)

        result = body.get("result", {})
        streamer = result.get("streamer", {})
        h264 = streamer.get("h264", {})
        source = streamer.get("source", {})
        resolution = source.get("resolution", {})

        return {
            "fps": h264.get("fps", 0),
            "gop": h264.get("gop", 0),
            "bitrate": h264.get("bitrate", 0),
            "resolution": {
                "width": resolution.get("width", 0),
                "height": resolution.get("height", 0),
            },
            "captured_fps": source.get("captured_fps", 0),
        }

    # ── capture (async generator) ─────────────────────────────────

    async def capture(
        self,
        codec: str = "h264",
        *,
        max_frames: int | None = None,
        duration: float | None = None,
        timeout: float = 10.0,
    ) -> AsyncIterator[VideoFrame]:
        """Async generator yielding video frames via direct WebSocket.

        Connects to the NanoKVM server's ``h264-direct`` or
        ``h265-direct`` WebSocket endpoint and yields
        :class:`VideoFrame` objects as they arrive.

        The server automatically switches to the requested codec's
        direct-stream mode when a client connects to the endpoint.

        Parameters
        ----------
        codec:
            ``"h264"`` or ``"h265"``.
        max_frames:
            Stop after this many frames.  ``None`` = unlimited.
        duration:
            Stop after this many seconds.  ``None`` = unlimited.
        timeout:
            Seconds to wait for the next frame before stopping.

        Yields
        ------
        VideoFrame
            Parsed video frames with raw NAL unit data.

        Raises
        ------
        ValueError
            If *codec* is not ``"h264"`` or ``"h265"``.
        ConnectionError
            If the WebSocket connection cannot be established.

        Example
        -------
        ::

            stream = Stream()
            async for frame in stream.capture("h264", max_frames=100):
                print(frame.is_key_frame, len(frame.data))
        """
        import websockets
        from websockets.exceptions import ConnectionClosed, InvalidHandshake

        codec_lower = codec.lower()
        if codec_lower not in _VALID_CODECS:
            raise ValueError(f"codec must be 'h264' or 'h265', got {codec!r}")

        url = self._ws_url(codec_lower)
        try:
            ws = await websockets.connect(url, ssl=self._ssl_ctx)
        except (OSError, InvalidHandshake) as exc:
            raise ConnectionError(
                f"Cannot connect to NanoKVM stream at {url}: {exc}"
            ) from exc

        count = 0
        start = time.monotonic()
        try:
            while True:
                if max_frames is not None and count >= max_frames:
                    break
                if duration is not None and (time.monotonic() - start) >= duration:
                    break

                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except (TimeoutError, ConnectionClosed):
                    break

                frame = _parse_frame(msg, codec_lower)
                if frame is not None:
                    yield frame
                    count += 1
        finally:
            await ws.close()

    # ── record (sync) ─────────────────────────────────────────────

    def record(
        self,
        output: str,
        codec: str = "h264",
        *,
        max_frames: int | None = None,
        duration: float | None = None,
        timeout: float = 10.0,
    ) -> dict:
        """Record raw video stream to a file (synchronous).

        Connects to the NanoKVM server's direct WebSocket stream and
        writes raw NAL units to *output*.  The resulting file can be
        played with ``ffplay output.h264`` or ``mpv output.h265``.

        Parameters
        ----------
        output:
            Output file path (e.g. ``"recording.h264"``).
        codec:
            ``"h264"`` or ``"h265"``.
        max_frames:
            Stop after this many frames.
        duration:
            Stop after this many seconds.
        timeout:
            Seconds to wait for the next frame before stopping.

        Returns
        -------
        dict
            Recording statistics:

            - ``file`` (str): output file path
            - ``codec`` (str): ``"h264"`` or ``"h265"``
            - ``frames`` (int): number of frames written
            - ``bytes`` (int): total bytes written
            - ``duration`` (float): actual recording duration in seconds

        Raises
        ------
        ValueError
            If *codec* is not ``"h264"`` or ``"h265"``.
        ConnectionError
            If the WebSocket connection cannot be established.

        Example
        -------
        ::

            stream = Stream()
            result = stream.record("clip.h264", duration=5.0)
            print(result)
            # {'file': 'clip.h264', 'codec': 'h264',
            #  'frames': 150, 'bytes': 2048576, 'duration': 5.01}
        """
        from websockets.exceptions import ConnectionClosed, InvalidHandshake
        from websockets.sync.client import connect as ws_connect

        codec_lower = codec.lower()
        if codec_lower not in _VALID_CODECS:
            raise ValueError(f"codec must be 'h264' or 'h265', got {codec!r}")

        url = self._ws_url(codec_lower)
        try:
            ws = ws_connect(url, ssl=self._ssl_ctx)
        except (OSError, InvalidHandshake) as exc:
            raise ConnectionError(
                f"Cannot connect to NanoKVM stream at {url}: {exc}"
            ) from exc

        frame_count = 0
        total_bytes = 0
        start = time.monotonic()
        try:
            with open(output, "wb") as f:
                while True:
                    if max_frames is not None and frame_count >= max_frames:
                        break
                    if duration is not None and (time.monotonic() - start) >= duration:
                        break

                    try:
                        msg = ws.recv(timeout=timeout)
                    except (TimeoutError, ConnectionClosed):
                        break

                    frame = _parse_frame(msg, codec_lower)
                    if frame is not None:
                        f.write(frame.data)
                        frame_count += 1
                        total_bytes += len(frame.data)
        finally:
            ws.close()

        logger.info(
            "recorded %d frames (%d bytes) to %s",
            frame_count,
            total_bytes,
            output,
        )
        return {
            "file": output,
            "codec": codec_lower,
            "frames": frame_count,
            "bytes": total_bytes,
            "duration": round(time.monotonic() - start, 2),
        }

    # ── repr ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"Stream(url={self._base_url!r})"
