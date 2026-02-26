# AGENTS.md

## Project Overview

**nanokvm-hid** is a Python library and CLI for controlling [NanoKVM Pro](https://wiki.sipeed.com/nanokvm) hardware. It runs **on-device** on the NanoKVM itself and provides hardware-level input injection and KVM control via direct file I/O — no HTTP server dependency.

The library talks to Linux kernel interfaces: `/dev/hidgN` character devices for HID, GPIO sysfs for power/reset/LEDs, USB gadget configfs for mass storage, and procfs for HDMI chip control.

## Tech Stack

- **Python ≥ 3.10**, no runtime dependencies (stdlib only)
- **Build**: hatchling
- **Package manager**: uv
- **Linting**: ruff (select: E, F, I, UP, B, SIM; line length: 88)
- **Testing**: pytest
- **CI**: GitHub Actions — lint + test on Python 3.10 and 3.14

## Development Commands

```bash
uv sync --dev              # Install dev dependencies
uv run pytest -v           # Run all tests
uv run ruff check          # Lint
uv run ruff format --check # Format check
uv run ruff check --fix    # Auto-fix lint issues
```

## Architecture & Design Principles

### Direct hardware access, not HTTP

Every module talks directly to kernel interfaces. Do **not** add HTTP client calls to the NanoKVM Go server. The library is designed to run on-device.

| Module | Kernel interface |
|---|---|
| `transport.py` | `/dev/hidg0`, `/dev/hidg1`, `/dev/hidg2` (character device writes) |
| `gpio.py` | `/sys/class/gpio/gpioN/value` (sysfs read/write) |
| `storage.py` | `/sys/kernel/config/usb_gadget/g0/.../lun.0/{file,cdrom,ro}` (configfs) |
| `hdmi.py` | `/proc/lt6911_info/{power,hdmi_power,loopout_power,edid,edid_snapshot}` (procfs) |
| `hid_manager.py` | `/kvmapp/scripts/usbdev.sh` (subprocess), `/dev/shm/tmp/hid_only` (flag file) |
| `virtual_devices.py` | `/boot/usb.{ncm,uac2,disk1.*}` (flag files) + `usbdev.sh` |
| `jiggler.py` | HID writes via `transport.py` + config at `/etc/kvm/mouse-jiggler` |
| `wol.py` | `ether-wake` (subprocess) |
| `stream.py` | NanoKVM server HTTP API (`/api/stream/*`) — no auth from localhost |
| `screen.py` | MJPEG stream or PiKVM-compatible API (HTTP — the only exception, for video capture) |

### Module patterns

- **Constructors accept path overrides** for all sysfs/procfs paths, making tests work without mocking file I/O. The defaults are the real NanoKVM paths.
- **No global state.** Each class is independently instantiatable.
- **Logging** via `logging.getLogger(__name__)` — no print statements in library code.

### CLI structure

`cli.py` uses argparse with subcommands. The `main()` function dispatches to module methods. All hardware module imports are **lazy** (inside dispatch functions) so the CLI parser itself has no import side effects.

## Testing Conventions

- **Function-style tests** — no test classes unless grouping is necessary for fixtures.
- **`pytest.mark.parametrize`** wherever there are multiple input/output pairs.
- **Mock at the right level**: mock sysfs/procfs/subprocess, not internal methods. Use `tmp_path` with real file I/O when possible (e.g., storage, HDMI EDID tests).
- **FakeTransport** in `conftest.py` records HID reports for keyboard/mouse tests.
- **Patch import paths**: CLI tests must patch at the source module path (e.g., `nanokvm_hid.gpio.GPIO.power`), not `nanokvm_hid.cli.GPIO.power`, because CLI uses lazy imports.

## Scope Boundaries

**In scope** — KVM-specific hardware interfaces:
- HID input injection (keyboard, mouse, touchpad)
- GPIO power/reset control and LED status
- USB gadget mass-storage (ISO/IMG mount)
- HDMI capture/passthrough/EDID
- Mouse jiggler
- HID gadget reset and mode switching
- Virtual USB devices (network, mic, disk)
- Wake-on-LAN
- Stream encoder control (FPS, GOP, quality, bitrate, rate-control, mode)
- Screen capture

**Out of scope** — standard Linux operations:
- Hostname, timezone, locale
- Reboot, shutdown (of the NanoKVM itself)
- SSH toggle, mDNS
- Package management, firmware updates
- Network configuration

**Deferred** — requires exclusive hardware access:
- HDMI frame capture via libkvm — encoder channels are exclusively owned by the running NanoKVM server; use the MJPEG HTTP stream instead
- Direct libkvm.so ctypes for stream parameters — encoder state is per-process, so ctypes `kvmv_set_*` only modifies the calling process, not the server's live stream; use the HTTP API instead

## Post-Change Checklist

After any code change (new features, API changes, renamed modules, new CLI commands):

1. **Update README.md** — keep the Features list, API Reference, and CLI section in sync with the actual code.
2. **Update AGENTS.md** — update the kernel interface table, scope boundaries, or hardware details if affected.
3. **Keep `__init__.py` version in sync with `pyproject.toml`.**

## Key Hardware Details (NanoKVM Pro)

- **GPIO pins**: power button = `gpio7`, reset = `gpio35`, power LED = `gpio75`, HDD LED = `gpio74`. LEDs are active-low (0 = on).
- **HID gadgets**: `hidg0` = keyboard, `hidg1` = mouse (relative), `hidg2` = touchpad (absolute).
- **EDID binaries**: built-in at `/kvmcomm/edid/`, custom at `/etc/kvm/edid/`. Flag file at `/etc/kvm/edid/edid_flag`.
- **Image directories**: `/data/` and `/sdcard/` for `.iso`/`.img` files.
- **USB device script**: `/kvmapp/scripts/usbdev.sh` with args `restart`, `stop`, `start`, `hid-only`.
- **libkvm.so**: at `/dev/shm/kvmapp/server/dl_lib/libkvm.so`. Requires `kvmv_init()` before `set_*` calls; `kvmv_get_fps()` works without init. Encoder channel creation (`kvmv_read_img`) fails when the NanoKVM server is running (exclusive access), but parameter set functions (`kvmv_set_fps`, `kvmv_set_gop`, `kvmv_set_rate_control`) work fine alongside the server.
