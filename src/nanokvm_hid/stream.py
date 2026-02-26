"""Stream encoder control via libkvm.so (NanoKVM Pro).

Controls the hardware video encoder parameters (FPS, GOP, quality,
bitrate, rate-control mode) by calling into the proprietary
``libkvm.so`` shared library via ctypes.

.. note::

    The NanoKVM server (``NanoKVM-Server``) must be running — it owns
    the encoder channels.  This module modifies the *shared* encoder
    parameters that the server's active stream uses.  ``kvmv_init``
    is called to set up internal state, but encoder channel creation
    will (harmlessly) fail because the server already holds them.

    ``kvmv_read_img`` (frame capture) is **not** exposed here because
    the encoder channels are exclusively owned by the running server.
    Use the :class:`~nanokvm_hid.screen.Screen` class for frame
    capture via the MJPEG HTTP stream instead.
"""

from __future__ import annotations

import ctypes
import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

# Default path to the shared library on NanoKVM Pro
_DEFAULT_LIB_PATH = "/dev/shm/kvmapp/server/dl_lib/libkvm.so"

# Rate-control modes (match kvm_vision.h)
RATE_CONTROL_CBR = 0
RATE_CONTROL_VBR = 1

_RATE_CONTROL_NAMES = {
    RATE_CONTROL_CBR: "cbr",
    RATE_CONTROL_VBR: "vbr",
    "cbr": RATE_CONTROL_CBR,
    "vbr": RATE_CONTROL_VBR,
}


class Stream:
    """Control the NanoKVM hardware video encoder.

    Parameters
    ----------
    lib_path:
        Path to ``libkvm.so``.  Defaults to the standard on-device
        location (``/dev/shm/kvmapp/server/dl_lib/libkvm.so``).

    Example::

        from nanokvm_hid import Stream

        stream = Stream()
        print(stream.fps)           # current FPS (0 = auto)
        stream.set_fps(30)          # cap at 30 FPS
        stream.set_gop(50)          # set GOP length
        stream.set_rate_control("vbr")
        stream.close()
    """

    def __init__(
        self,
        lib_path: str = _DEFAULT_LIB_PATH,
    ) -> None:
        self._lib_path = lib_path
        self._lib: ctypes.CDLL | None = None
        self._lock = threading.Lock()
        self._init()

    # ── lifecycle ─────────────────────────────────────────────────

    def _init(self) -> None:
        """Load libkvm and call kvmv_init."""
        path = Path(self._lib_path)
        if not path.exists():
            raise FileNotFoundError(
                f"libkvm.so not found at {self._lib_path}"
            )

        lib = ctypes.CDLL(self._lib_path)

        # Declare function signatures
        lib.kvmv_init.restype = None
        lib.kvmv_init.argtypes = [ctypes.c_uint8]

        lib.kvmv_deinit.restype = None
        lib.kvmv_deinit.argtypes = []

        lib.kvmv_get_fps.restype = ctypes.c_int
        lib.kvmv_get_fps.argtypes = []

        lib.kvmv_set_fps.restype = ctypes.c_int
        lib.kvmv_set_fps.argtypes = [ctypes.c_uint8]

        lib.kvmv_set_gop.restype = ctypes.c_int
        lib.kvmv_set_gop.argtypes = [ctypes.c_uint8]

        lib.kvmv_set_rate_control.restype = ctypes.c_int
        lib.kvmv_set_rate_control.argtypes = [ctypes.c_uint8]

        lib.kvmv_hdmi_control.restype = ctypes.c_int
        lib.kvmv_hdmi_control.argtypes = [ctypes.c_uint8]

        self._lib = lib

        # Init internal state. Encoder channel creation will fail
        # (harmlessly) if the NanoKVM server is running — that's fine,
        # the set_* functions still work.
        logger.debug("calling kvmv_init(0)")
        lib.kvmv_init(ctypes.c_uint8(0))
        logger.debug("kvmv_init complete")

    def close(self) -> None:
        """Release libkvm resources."""
        with self._lock:
            if self._lib is not None:
                logger.debug("calling kvmv_deinit")
                self._lib.kvmv_deinit()
                self._lib = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> Stream:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _check(self) -> ctypes.CDLL:
        if self._lib is None:
            raise RuntimeError("Stream is closed")
        return self._lib

    # ── FPS ───────────────────────────────────────────────────────

    @property
    def fps(self) -> int:
        """Current encoder FPS setting (0 = auto/uncapped)."""
        with self._lock:
            return self._check().kvmv_get_fps()

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
        RuntimeError
            If the hardware call fails.
        """
        if not 0 <= fps <= 120:
            raise ValueError(f"FPS must be 0–120, got {fps}")
        with self._lock:
            rc = self._check().kvmv_set_fps(ctypes.c_uint8(fps))
        if rc < 0:
            raise RuntimeError(f"kvmv_set_fps({fps}) failed: {rc}")
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
        RuntimeError
            If the hardware call fails.
        """
        if not 1 <= gop <= 200:
            raise ValueError(f"GOP must be 1–200, got {gop}")
        with self._lock:
            rc = self._check().kvmv_set_gop(ctypes.c_uint8(gop))
        if rc < 0:
            raise RuntimeError(f"kvmv_set_gop({gop}) failed: {rc}")
        logger.info("set GOP to %d", gop)

    # ── rate control ──────────────────────────────────────────────

    def set_rate_control(self, mode: str | int) -> None:
        """Set encoder rate-control mode.

        Parameters
        ----------
        mode:
            ``"cbr"`` (constant bitrate) or ``"vbr"`` (variable
            bitrate), or the integer constants ``RATE_CONTROL_CBR``
            / ``RATE_CONTROL_VBR``.

        Raises
        ------
        ValueError
            If *mode* is not recognised.
        RuntimeError
            If the hardware call fails.
        """
        if isinstance(mode, str):
            key = mode.lower()
            if key not in _RATE_CONTROL_NAMES:
                raise ValueError(
                    f"Unknown rate-control mode: {mode!r}"
                    " (use 'cbr' or 'vbr')"
                )
            mode_int = _RATE_CONTROL_NAMES[key]
        elif mode in (RATE_CONTROL_CBR, RATE_CONTROL_VBR):
            mode_int = mode
        else:
            raise ValueError(
                f"Unknown rate-control mode: {mode!r}"
                " (use 'cbr' or 'vbr')"
            )

        with self._lock:
            rc = self._check().kvmv_set_rate_control(
                ctypes.c_uint8(mode_int),
            )
        if rc < 0:
            raise RuntimeError(
                f"kvmv_set_rate_control({mode_int}) failed: {rc}"
            )
        name = _RATE_CONTROL_NAMES.get(mode_int, str(mode_int))
        logger.info("set rate control to %s", name)

    # ── repr ──────────────────────────────────────────────────────

    def __repr__(self) -> str:
        if self._lib is None:
            return "Stream(closed)"
        fps = self.fps
        return f"Stream(fps={fps})"
