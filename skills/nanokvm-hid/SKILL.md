---
name: nanokvm-hid
description: Control a remote computer via NanoKVM Pro IP-KVM hardware — keyboard, mouse, screen capture, GPIO power/reset, HDMI, virtual media, stream encoder, and more. Use when asked to interact with a NanoKVM-controlled machine, automate GUI tasks via IP-KVM, take screenshots through HDMI capture, manage KVM hardware, or perform computer-use agent (CUA) style operations on a remote display.
---

# NanoKVM HID — Remote Computer Control via IP-KVM

Control a remote computer's keyboard, mouse, and screen through a NanoKVM Pro device using the `nanokvm-hid` Python library. Also control GPIO (power/reset buttons, LEDs), HDMI capture/passthrough, virtual USB media, mouse jiggler, stream encoder, Wake-on-LAN, and more.

## Overview

NanoKVM Pro is an IP-KVM device that sits between a host computer and its peripherals, exposing USB HID gadget devices (`/dev/hidg0–2`). This skill lets you:

- **See** the remote screen (JPEG capture via HDMI)
- **Type** text and press key combos (keyboard HID)
- **Click, move, scroll, drag** (mouse + absolute touchpad HID)
- **Power control** — press power/reset buttons, read LED status (GPIO)
- **Virtual media** — mount ISO/IMG files as USB drives or CD-ROMs
- **HDMI control** — capture on/off, passthrough (loopout), EDID management
- **Stream encoder** — set FPS, GOP, quality, bitrate, rate-control, stream mode (MJPEG, H.264, H.265)
- **Mouse jiggler** — keep-alive to prevent screensaver/sleep
- **HID management** — reset stuck USB gadgets, switch normal/hid-only mode
- **Virtual USB devices** — toggle network adapter (NCM), microphone (UAC2), disk (SD/eMMC)
- **Wake-on-LAN** — send magic packets to power on machines

All coordinates are **normalised to `[0.0, 1.0]`** — no need to know pixel dimensions.

## Setup

### Determine where you are running

There are two scenarios:

1. **On the NanoKVM itself** — the HID devices are local at `/dev/hidg0–2`. Install and use directly.
2. **On a remote machine** (your laptop, a CI server, etc.) — you SSH into the NanoKVM to run commands. The NanoKVM default credentials are `root@<ip>` with an empty password or `root`.

### Install the library (if not already installed)

```bash
# On the NanoKVM (SSH in first if remote)
ssh root@<NANOKVM_IP> "command -v nanokvm-hid || pip install nanokvm-hid"
```

The library has **zero runtime dependencies** (stdlib only) and works on Python ≥ 3.10.

### Verify the device

```bash
# On the NanoKVM
ssh root@<NANOKVM_IP> "nanokvm-hid info"
```

Expected output:
```
  Keyboard    /dev/hidg0  ✅ available
  Mouse       /dev/hidg1  ✅ available
  Touchpad    /dev/hidg2  ✅ available
  Screen      3840×2160
```

## Usage Patterns

### Pattern A: Direct CLI via SSH (simplest)

Run individual commands over SSH from your local machine:

```bash
# Take a screenshot
ssh root@<NANOKVM_IP> "nanokvm-hid capture -o /tmp/screenshot.jpg"
scp root@<NANOKVM_IP>:/tmp/screenshot.jpg ./screenshot.jpg

# Or get base64 directly
ssh root@<NANOKVM_IP> "nanokvm-hid capture --base64" > screenshot.b64

# Type text
ssh root@<NANOKVM_IP> "nanokvm-hid type 'hello world'"

# Press key combos
ssh root@<NANOKVM_IP> "nanokvm-hid key CTRL+C"
ssh root@<NANOKVM_IP> "nanokvm-hid key ALT+F4"

# Mouse operations
ssh root@<NANOKVM_IP> "nanokvm-hid mouse move 0.5 0.5"
ssh root@<NANOKVM_IP> "nanokvm-hid mouse click 0.5 0.5"
ssh root@<NANOKVM_IP> "nanokvm-hid mouse click -r 0.8 0.2"       # right-click
ssh root@<NANOKVM_IP> "nanokvm-hid mouse click -d 0.5 0.5"       # double-click
ssh root@<NANOKVM_IP> "nanokvm-hid mouse scroll-down 3"
ssh root@<NANOKVM_IP> "nanokvm-hid mouse drag 0.1 0.1 0.9 0.9"

# GPIO power/reset
ssh root@<NANOKVM_IP> "nanokvm-hid power"                         # short press
ssh root@<NANOKVM_IP> "nanokvm-hid power --duration 5000"         # force off (5s hold)
ssh root@<NANOKVM_IP> "nanokvm-hid reset-button"
ssh root@<NANOKVM_IP> "nanokvm-hid power-led"                     # exit 0=on, 1=off
ssh root@<NANOKVM_IP> "nanokvm-hid hdd-led"

# Virtual media
ssh root@<NANOKVM_IP> "nanokvm-hid storage list"
ssh root@<NANOKVM_IP> "nanokvm-hid storage mount /data/ubuntu.iso --cdrom"
ssh root@<NANOKVM_IP> "nanokvm-hid storage unmount"
ssh root@<NANOKVM_IP> "nanokvm-hid storage status"

# HDMI control
ssh root@<NANOKVM_IP> "nanokvm-hid hdmi status"
ssh root@<NANOKVM_IP> "nanokvm-hid hdmi capture on"
ssh root@<NANOKVM_IP> "nanokvm-hid hdmi passthrough on"
ssh root@<NANOKVM_IP> "nanokvm-hid hdmi edid list"
ssh root@<NANOKVM_IP> "nanokvm-hid hdmi edid switch E54-1080P60FPS"

# Stream encoder control
ssh root@<NANOKVM_IP> "nanokvm-hid stream fps 30"
ssh root@<NANOKVM_IP> "nanokvm-hid stream mode h264-webrtc"
ssh root@<NANOKVM_IP> "nanokvm-hid stream quality 80"
ssh root@<NANOKVM_IP> "nanokvm-hid stream bitrate 5000"

# Mouse jiggler
ssh root@<NANOKVM_IP> "nanokvm-hid jiggler on"
ssh root@<NANOKVM_IP> "nanokvm-hid jiggler off"
ssh root@<NANOKVM_IP> "nanokvm-hid jiggler status"

# HID management
ssh root@<NANOKVM_IP> "nanokvm-hid hid-reset"
ssh root@<NANOKVM_IP> "nanokvm-hid hid-mode"
ssh root@<NANOKVM_IP> "nanokvm-hid hid-mode hid-only"

# Virtual USB devices
ssh root@<NANOKVM_IP> "nanokvm-hid virtual-device status"
ssh root@<NANOKVM_IP> "nanokvm-hid virtual-device network"
ssh root@<NANOKVM_IP> "nanokvm-hid virtual-device disk sdcard"

# Wake-on-LAN
ssh root@<NANOKVM_IP> "nanokvm-hid wol AA:BB:CC:DD:EE:FF"
```

### Pattern B: Script file (multi-step sequences)

Create a script file and run it:

```bash
cat << 'EOF' > /tmp/login.script
# Click on the password field
mouse click 0.5 0.55
sleep 0.5

# Type the password
type "mypassword"
enter
sleep 2

# Open a terminal
key CTRL+ALT+T
sleep 1

# Run a command
type "ls -la"
enter
EOF

scp /tmp/login.script root@<NANOKVM_IP>:/tmp/
ssh root@<NANOKVM_IP> "nanokvm-hid script /tmp/login.script"
```

Or pipe commands via stdin:

```bash
echo 'key CTRL+C
sleep 0.5
type "echo done"
enter' | ssh root@<NANOKVM_IP> "nanokvm-hid script"
```

### Pattern C: Python API via SSH (for complex automation)

For multi-step operations that need logic (conditionals, loops, screen analysis):

```bash
ssh root@<NANOKVM_IP> python3 << 'PYEOF'
from nanokvm_hid import Keyboard, Mouse, Screen

kb = Keyboard()
mouse = Mouse()
screen = Screen()

# Take a screenshot
jpeg_data = screen.capture()
screen.capture_to_file("/tmp/current_screen.jpg")

# Get base64 for vision model analysis
b64 = screen.capture_base64()

# Click and type
mouse.left_click(0.5, 0.5)
kb.type("hello world")
kb.press("ENTER")

# Key combos
kb.hotkey("CTRL", "S")        # Ctrl+S
kb.press("ALT+F4")            # Alt+F4
kb.hotkey("CTRL", "SHIFT", "A")

# Mouse operations
mouse.move(0.3, 0.7)
mouse.right_click(0.8, 0.2)
mouse.double_click(0.5, 0.5)
mouse.scroll_down(3)
mouse.scroll_up(1)
mouse.drag(0.1, 0.1, 0.9, 0.9)

# Convenience keys
kb.enter()
kb.tab()
kb.escape()
kb.backspace(5)
kb.delete()
kb.space()

print("Done!")
PYEOF
```

### Pattern D: Python API for KVM hardware control

```bash
ssh root@<NANOKVM_IP> python3 << 'PYEOF'
from nanokvm_hid import GPIO, HDMI, Storage, Stream, Jiggler, VirtualDevices
from nanokvm_hid import reset_hid, get_hid_mode, set_hid_mode, wake_on_lan

# GPIO — power/reset buttons and LED status
gpio = GPIO()
gpio.power()                    # short press (800ms)
gpio.power_off()                # long press (5s force-off)
gpio.reset()                    # reset button press
print(gpio.power_led())         # True if power LED is on
print(gpio.hdd_led())           # True if HDD LED is on

# HDMI — capture, passthrough, EDID
hdmi = HDMI()
hdmi.set_capture(True)              # enable HDMI capture
hdmi.set_passthrough(True)          # enable loopout
print(hdmi.current_edid)            # e.g. "E54-1080P60FPS"
print(hdmi.list_edids())            # available profiles
hdmi.switch_edid("E54-1080P60FPS")  # switch EDID profile

# Storage — mount ISO/IMG as USB drive
storage = Storage()
images = storage.list_images()
storage.mount("/data/ubuntu.iso", cdrom=True)
print(storage.mounted())
storage.unmount()

# Stream encoder — FPS, GOP, quality, bitrate, mode
stream = Stream()
stream.set_fps(30)                  # 0 = auto, 1–120
stream.set_gop(50)                  # GOP length (1–200)
stream.set_quality(80)              # MJPEG quality (1–100)
stream.set_bitrate(5000)            # H264/H265 bitrate in kbps (1000–20000)
stream.set_rate_control("vbr")      # "cbr" or "vbr"
stream.set_mode("h264-webrtc")      # see stream modes below

# Mouse jiggler
jiggler = Jiggler()
jiggler.start(mode="relative")   # or "absolute"
print(jiggler.is_running)
jiggler.stop()

# Virtual USB devices
vdev = VirtualDevices()
print(vdev.status())
vdev.toggle_network()         # toggle USB NCM adapter
vdev.toggle_mic()             # toggle USB UAC2 mic
vdev.set_disk("sdcard")       # expose SD card as USB drive
vdev.set_disk(None)           # disable virtual disk

# HID management
reset_hid()                   # restart USB gadgets
print(get_hid_mode())         # "normal" or "hid-only"
set_hid_mode("hid-only")     # switch mode

# Wake-on-LAN
wake_on_lan("AA:BB:CC:DD:EE:FF")
PYEOF
```

## Stream Modes

The NanoKVM server supports five stream modes:

| Mode | Description |
|---|---|
| `mjpeg` | MJPEG over HTTP (widest compatibility) |
| `h264-webrtc` | H.264 via WebRTC (default in web UI) |
| `h264-direct` | H.264 NAL units over WebSocket |
| `h265-webrtc` | H.265/HEVC via WebRTC |
| `h265-direct` | H.265/HEVC NAL units over WebSocket |

**H.265 note:** The NanoKVM Pro hardware (AX620Q SoC) and server binary fully support H.265 encoding. The web dashboard hides H.265 options because most browsers lack H.265 WebRTC support, but this library can enable it. Use `h265-direct` for WebSocket-based access which is easier to consume from custom clients.

## Computer-Use Agent (CUA) Loop

To implement a vision-model-driven automation loop (screenshot → analyse → act → repeat):

```bash
ssh root@<NANOKVM_IP> python3 << 'PYEOF'
import json, time
from nanokvm_hid import Keyboard, Mouse, Screen

kb = Keyboard()
mouse = Mouse()
screen = Screen()

# 1. Capture the current screen state
b64 = screen.capture_base64()

# 2. Save for local retrieval (or print for piping)
screen.capture_to_file("/tmp/cua_frame.jpg")

# 3. After your vision model decides what to do, execute:
# Examples of actions the model might request:

# Click at coordinates the model identified
mouse.left_click(0.45, 0.32)
time.sleep(0.5)

# Type text the model wants entered
kb.type("search query here")
kb.press("ENTER")
time.sleep(1)

# 4. Capture again to see the result
b64_after = screen.capture_base64()
screen.capture_to_file("/tmp/cua_frame_after.jpg")

print("Frame captured for next analysis round")
PYEOF
```

### Retrieving screenshots locally for analysis

```bash
# Capture and download
ssh root@<NANOKVM_IP> "nanokvm-hid capture -o /tmp/frame.jpg"
scp root@<NANOKVM_IP>:/tmp/frame.jpg ./frame.jpg

# Or capture as base64 in one step (no temp file)
SCREENSHOT_B64=$(ssh root@<NANOKVM_IP> "nanokvm-hid capture --base64")
```

## CLI Reference

All commands are available as `nanokvm-hid <command>`:

### Input Commands

| Command | Description | Example |
|---|---|---|
| `info` | Show device status and screen size | `nanokvm-hid info` |
| `key <combo> [...]` | Press key combination(s) | `nanokvm-hid key CTRL+C` |
| `type <text>` | Type printable ASCII string | `nanokvm-hid type "hello"` |
| `backspace <n>` | Press Backspace n times | `nanokvm-hid backspace 5` |
| `enter` | Press Enter | `nanokvm-hid enter` |
| `tab` | Press Tab | `nanokvm-hid tab` |
| `escape` | Press Escape | `nanokvm-hid escape` |
| `delete` | Press Delete | `nanokvm-hid delete` |
| `space` | Press Space | `nanokvm-hid space` |
| `sleep <seconds>` | Delay (supports decimals) | `nanokvm-hid sleep 0.5` |
| `capture [-o FILE] [--base64]` | Screenshot from HDMI | `nanokvm-hid capture --base64` |
| `capture --pikvm` | Screenshot via PiKVM API | `nanokvm-hid capture --pikvm` |

### Mouse Commands

| Command | Description | Example |
|---|---|---|
| `mouse move <x> <y>` | Move cursor (normalised 0.0–1.0) | `nanokvm-hid mouse move 0.5 0.5` |
| `mouse click <x> <y> [-r] [-d]` | Click (right, double flags) | `nanokvm-hid mouse click -d 0.5 0.5` |
| `mouse scroll-down [steps]` | Scroll down | `nanokvm-hid mouse scroll-down 3` |
| `mouse scroll-up [steps]` | Scroll up | `nanokvm-hid mouse scroll-up` |
| `mouse drag <x0> <y0> <x1> <y1>` | Drag between two points | `nanokvm-hid mouse drag 0.1 0.1 0.9 0.9` |

### GPIO Commands

| Command | Description | Example |
|---|---|---|
| `power` | Short press power button (800ms) | `nanokvm-hid power` |
| `power --duration 5000` | Long press power (force off) | `nanokvm-hid power --duration 5000` |
| `reset-button` | Press reset button | `nanokvm-hid reset-button` |
| `power-led` | Read power LED (exit 0=on, 1=off) | `nanokvm-hid power-led` |
| `hdd-led` | Read HDD LED (exit 0=on, 1=off) | `nanokvm-hid hdd-led` |

### Storage Commands

| Command | Description | Example |
|---|---|---|
| `storage list` | List available ISO/IMG files | `nanokvm-hid storage list` |
| `storage mount <path> [--cdrom]` | Mount image as USB drive/CD | `nanokvm-hid storage mount /data/ubuntu.iso --cdrom` |
| `storage unmount` | Unmount current image | `nanokvm-hid storage unmount` |
| `storage status` | Show current mount info | `nanokvm-hid storage status` |

### HDMI Commands

| Command | Description | Example |
|---|---|---|
| `hdmi status` | Show HDMI status | `nanokvm-hid hdmi status` |
| `hdmi capture on/off` | Toggle HDMI capture | `nanokvm-hid hdmi capture on` |
| `hdmi passthrough on/off` | Toggle HDMI loopout | `nanokvm-hid hdmi passthrough on` |
| `hdmi edid list` | List EDID profiles | `nanokvm-hid hdmi edid list` |
| `hdmi edid current` | Show current EDID | `nanokvm-hid hdmi edid current` |
| `hdmi edid switch <name>` | Switch EDID profile | `nanokvm-hid hdmi edid switch E54-1080P60FPS` |

### Stream Commands

| Command | Description | Example |
|---|---|---|
| `stream fps <n>` | Set FPS (0=auto, 1–120) | `nanokvm-hid stream fps 30` |
| `stream gop <n>` | Set GOP length (1–200) | `nanokvm-hid stream gop 50` |
| `stream quality <n>` | Set MJPEG quality (1–100) | `nanokvm-hid stream quality 80` |
| `stream bitrate <n>` | Set H264/H265 bitrate kbps (1000–20000) | `nanokvm-hid stream bitrate 5000` |
| `stream rate-control <mode>` | Set rate control (cbr/vbr) | `nanokvm-hid stream rate-control vbr` |
| `stream mode <mode>` | Set stream mode | `nanokvm-hid stream mode h265-direct` |

### Other Commands

| Command | Description | Example |
|---|---|---|
| `jiggler on [--mode relative/absolute]` | Start mouse jiggler | `nanokvm-hid jiggler on` |
| `jiggler off` | Stop mouse jiggler | `nanokvm-hid jiggler off` |
| `jiggler status` | Show jiggler status | `nanokvm-hid jiggler status` |
| `hid-reset` | Reset USB HID gadgets | `nanokvm-hid hid-reset` |
| `hid-mode [normal/hid-only]` | Get or set HID mode | `nanokvm-hid hid-mode hid-only` |
| `virtual-device status` | Show virtual device states | `nanokvm-hid virtual-device status` |
| `virtual-device network` | Toggle USB NCM adapter | `nanokvm-hid virtual-device network` |
| `virtual-device mic` | Toggle USB UAC2 mic | `nanokvm-hid virtual-device mic` |
| `virtual-device disk sdcard/emmc` | Expose storage as USB disk | `nanokvm-hid virtual-device disk sdcard` |
| `wol <MAC>` | Send Wake-on-LAN packet | `nanokvm-hid wol AA:BB:CC:DD:EE:FF` |
| `script [file]` | Run commands from file/stdin | `nanokvm-hid script commands.txt` |

## Supported Keys

**Modifiers:** `CTRL`, `SHIFT`, `ALT`, `GUI` (aliases: `WIN`, `SUPER`, `META`, `CMD`, `COMMAND`). Left/right variants: `LEFT_CTRL`, `RIGHT_SHIFT`, etc.

**Function keys:** `F1` – `F12`

**Navigation:** `UP_ARROW`, `DOWN_ARROW`, `LEFT_ARROW`, `RIGHT_ARROW`, `HOME`, `END`, `PAGE_UP`, `PAGE_DOWN`, `INSERT`, `DELETE`

**Control:** `ENTER`, `ESCAPE`, `BACKSPACE`, `TAB`, `SPACE`, `CAPS_LOCK`, `PRINT_SCREEN`, `SCROLL_LOCK`, `PAUSE`

**Media:** `VOLUME_UP`, `VOLUME_DOWN`, `MUTE`, `PLAY_PAUSE`, `SCAN_NEXT_TRACK`, `SCAN_PREVIOUS_TRACK`, `STOP`

**Combos:** Join with `+` — e.g. `CTRL+SHIFT+A`, `ALT+F4`, `GUI+L`

## Important Notes

1. **Coordinates are normalised [0.0, 1.0]** — `(0.5, 0.5)` is always the centre of the screen regardless of resolution. Values are clamped automatically.
2. **OS-agnostic** — the target computer sees a real USB keyboard and mouse. Works with any OS, BIOS, UEFI, boot loaders.
3. **Screen capture uses MJPEG by default** — the NanoKVM streams HDMI input as MJPEG over HTTPS (self-signed cert). Use `--pikvm` flag if running PiKVM firmware.
4. **Add delays after actions that change screen state** — after clicking, opening apps, or submitting forms, wait (`sleep 0.5`–`2`) before capturing the next screenshot so the display has time to update.
5. **Screen resolution is auto-detected** from `/proc/lt6911_info/{width,height}` on the NanoKVM. No configuration needed.
6. **The library is pure Python with zero dependencies** — it only uses the standard library and works on the NanoKVM's built-in Python 3.
7. **Stream control uses the server HTTP API** — encoder state is per-process, so the library talks to the NanoKVM server at `https://localhost/api/stream/*`. No auth is needed from localhost.
8. **H.265 is fully functional** — despite being hidden in the web dashboard, H.265 encoding works. Set via `stream.set_mode("h265-direct")` or `nanokvm-hid stream mode h265-direct`.
9. **GPIO LEDs are active-low** — `gpio.power_led()` returns `True` when the LED is on (GPIO value 0).
10. **Virtual media requires configfs** — the mass_storage USB gadget function must exist in `/sys/kernel/config/usb_gadget/g0/`. Not all NanoKVM configurations have this pre-configured.
