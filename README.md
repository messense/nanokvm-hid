# nanokvm-hid

Python library for controlling [NanoKVM Pro](https://wiki.sipeed.com/nanokvm) hardware via direct device access. Runs on-device on the NanoKVM itself.

The NanoKVM Pro sits between a host computer and its peripherals, exposing USB HID gadget devices (`/dev/hidg0–2`) that allow hardware-level input injection — indistinguishable from a real keyboard and mouse. This library provides a clean, Pythonic API on top of those raw HID interfaces, plus control of GPIO, HDMI, virtual media, and more.

## Features

- **Keyboard** — key combos (`CTRL+C`, `ALT+F4`, `GUI+L`), media keys (`VOLUME_UP`), string typing
- **Mouse** — absolute positioning, left/right click, double-click, scroll, drag
- **Screen capture** — grab JPEG screenshots from the HDMI video stream
- **GPIO control** — power/reset button press, power/HDD LED status
- **Virtual media** — mount/unmount ISO/IMG files as USB drives
- **HDMI control** — capture on/off, passthrough (loopout), EDID management
- **Mouse jiggler** — background keep-alive with relative/absolute modes
- **HID management** — reset stuck USB gadgets, switch normal/hid-only mode
- **Virtual USB devices** — toggle network adapter (NCM), microphone (UAC2), disk (SD/eMMC)
- **Stream control** — FPS, GOP, quality, bitrate, rate-control, stream mode via server HTTP API
- **Wake-on-LAN** — send magic packets to power on machines
- **Pure Python** — no dependencies beyond the standard library
- **OS-agnostic target** — works on any OS the KVM-controlled computer runs (Windows, Linux, macOS, BIOS, UEFI…)

## Installation

```bash
# On the NanoKVM itself
uv pip install .

# Or for development
uv sync --dev
```

## Quick Start

```python
from nanokvm_hid import Keyboard, Mouse

kb = Keyboard()
mouse = Mouse()

# Move cursor and click
mouse.left_click(0.5, 0.5)       # click center of screen

# Type text
kb.type("hello world")
kb.press("ENTER")

# Key combos
kb.hotkey("CTRL", "S")           # Ctrl+S
kb.press("ALT+F4")              # Alt+F4

# Mouse operations
mouse.right_click(0.8, 0.2)     # right-click near top-right
mouse.double_click(0.3, 0.7)    # double-click
mouse.scroll_down(3)             # scroll down 3 steps
mouse.drag(0.1, 0.1, 0.9, 0.9) # drag from corner to corner
```

## API Reference

### `Keyboard(device="/dev/hidg0", inter_report_delay=0.02)`

| Method | Description |
|---|---|
| `press(combo)` | Send a key combination: `"A"`, `"CTRL+C"`, `"ALT+F4"`, `"VOLUME_UP"` |
| `type(text)` | Type a string of printable ASCII characters |
| `backspace(n)` | Press Backspace *n* times |
| `hotkey(*keys)` | `hotkey("CTRL", "SHIFT", "A")` → `press("CTRL+SHIFT+A")` |
| `enter()` | Press Enter |
| `tab()` | Press Tab |
| `escape()` | Press Escape |

### `Mouse(mouse_device="/dev/hidg1", touchpad_device="/dev/hidg2", screen_size=None)`

All coordinates are **normalised** to `[0.0, 1.0]` relative to screen dimensions.

| Method | Description |
|---|---|
| `move(x, y)` | Move cursor to absolute position |
| `left_click(x, y)` | Left-click at position |
| `right_click(x, y)` | Right-click at position |
| `double_click(x, y)` | Double-click at position |
| `click(x, y, button=)` | Click with specified button |
| `scroll_down(steps)` | Scroll down |
| `scroll_up(steps)` | Scroll up |
| `drag(x0, y0, x1, y1)` | Drag from start to end position |

### `Screen(url="https://localhost/api/stream/mjpeg", timeout=10)`

```python
from nanokvm_hid import Screen

screen = Screen()
jpeg_data = screen.capture()          # raw JPEG bytes
screen.capture_to_file("shot.jpg")    # save to file
b64 = screen.capture_base64()         # base64 (for VLM APIs)
w, h = screen.screen_size()           # read resolution
```

### `GPIO()`

```python
from nanokvm_hid import GPIO

gpio = GPIO()
gpio.power()                    # short press (800ms)
gpio.power_off()                # long press (5s)
gpio.reset()                    # reset button press
print(gpio.power_led())         # True if power LED is on
print(gpio.hdd_led())           # True if HDD LED is on
```

### `Storage()`

```python
from nanokvm_hid import Storage

storage = Storage()
images = storage.list_images()                   # find .iso/.img files
storage.mount("/data/ubuntu.iso", cdrom=True)    # mount as CD-ROM
print(storage.mounted())                         # current mount info
storage.unmount()
```

### `HDMI()`

```python
from nanokvm_hid import HDMI

hdmi = HDMI()
hdmi.set_capture(True)              # enable HDMI capture
hdmi.set_passthrough(True)          # enable loopout
print(hdmi.current_edid)            # e.g. "E54-1080P60FPS"
print(hdmi.list_edids())            # available profiles
hdmi.switch_edid("E54-1080P60FPS")  # switch EDID profile
hdmi.upload_edid("custom.bin")      # upload custom EDID
hdmi.delete_edid("custom.bin")      # delete custom EDID
```

### `Jiggler()`

```python
from nanokvm_hid import Jiggler

jiggler = Jiggler()
jiggler.start(mode="relative")   # or "absolute"
print(jiggler.is_running)
jiggler.stop()
```

### `VirtualDevices()`

```python
from nanokvm_hid import VirtualDevices

vdev = VirtualDevices()
print(vdev.status())          # all device states
vdev.toggle_network()         # toggle USB NCM adapter
vdev.toggle_mic()             # toggle USB UAC2 mic
vdev.set_disk("sdcard")       # expose SD card as USB drive
vdev.set_disk(None)           # disable virtual disk
```

### HID Management

```python
from nanokvm_hid import reset_hid, get_hid_mode, set_hid_mode

reset_hid()                   # restart USB gadgets
print(get_hid_mode())         # "normal" or "hid-only"
set_hid_mode("hid-only")     # switch mode
```

### Wake-on-LAN

```python
from nanokvm_hid import wake_on_lan

wake_on_lan("AA:BB:CC:DD:EE:FF")
```

### `Stream()`

Control the hardware video encoder via the NanoKVM server's local API
(no auth required from localhost):

```python
from nanokvm_hid import Stream

stream = Stream()
stream.set_fps(30)                  # cap at 30 FPS (0 = auto)
stream.set_gop(50)                  # GOP length (1–200)
stream.set_quality(80)              # MJPEG quality (1–100)
stream.set_bitrate(5000)            # H264/H265 bitrate (1000–20000 kbps)
stream.set_rate_control("vbr")      # "cbr" or "vbr"
stream.set_mode("h264-webrtc")      # mjpeg, h264-webrtc, h264-direct, h265-*
```

### `HIDTransport(device_path)`

Low-level transport for sending raw HID reports:

```python
from nanokvm_hid import HIDTransport

tp = HIDTransport("/dev/hidg0")
tp.send(bytes([0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00]))  # press 'A'
tp.send(bytes(8))  # release
```

## Command Line

After installing, the `nanokvm-hid` command is available:

```bash
# Device info
nanokvm-hid info

# Keyboard
nanokvm-hid key CTRL+C
nanokvm-hid key ALT+F4
nanokvm-hid key CTRL+A BACKSPACE           # multiple combos in sequence
nanokvm-hid type "hello world"
nanokvm-hid backspace 5
nanokvm-hid enter
nanokvm-hid tab
nanokvm-hid escape

# Mouse (coordinates are normalised 0.0–1.0)
nanokvm-hid mouse move 0.5 0.5
nanokvm-hid mouse click 0.3 0.7            # left-click
nanokvm-hid mouse click -r 0.8 0.2         # right-click
nanokvm-hid mouse click -d 0.5 0.5         # double-click
nanokvm-hid mouse scroll-down 3
nanokvm-hid mouse scroll-up
nanokvm-hid mouse drag 0.1 0.1 0.9 0.9

# GPIO — power/reset/LEDs
nanokvm-hid power                           # short press (800ms)
nanokvm-hid power --duration 5000           # force off (5s hold)
nanokvm-hid reset-button                    # reset press
nanokvm-hid power-led                       # exit 0=on, 1=off
nanokvm-hid hdd-led

# Virtual media — mount ISO/IMG
nanokvm-hid storage list
nanokvm-hid storage mount /data/ubuntu.iso --cdrom
nanokvm-hid storage unmount
nanokvm-hid storage status

# HDMI control
nanokvm-hid hdmi status
nanokvm-hid hdmi capture on
nanokvm-hid hdmi capture off
nanokvm-hid hdmi passthrough on
nanokvm-hid hdmi edid list
nanokvm-hid hdmi edid current
nanokvm-hid hdmi edid switch E54-1080P60FPS

# Mouse jiggler
nanokvm-hid jiggler on
nanokvm-hid jiggler on --mode absolute
nanokvm-hid jiggler off
nanokvm-hid jiggler status

# HID management
nanokvm-hid hid-reset
nanokvm-hid hid-mode                        # show current mode
nanokvm-hid hid-mode hid-only
nanokvm-hid hid-mode normal

# Virtual USB devices
nanokvm-hid virtual-device status
nanokvm-hid virtual-device network          # toggle
nanokvm-hid virtual-device mic              # toggle
nanokvm-hid virtual-device disk sdcard
nanokvm-hid virtual-device disk emmc

# Wake-on-LAN
nanokvm-hid wol AA:BB:CC:DD:EE:FF

# Stream encoder control
nanokvm-hid stream fps 30                   # set FPS (0 = auto)
nanokvm-hid stream gop 50                   # set GOP length
nanokvm-hid stream quality 80               # MJPEG quality
nanokvm-hid stream bitrate 5000             # H264/H265 bitrate (kbps)
nanokvm-hid stream rate-control vbr         # cbr or vbr
nanokvm-hid stream mode h264-webrtc         # stream mode

# Delay
nanokvm-hid sleep 1.5

# Screenshot
nanokvm-hid capture -o screenshot.jpg
```

### Scripting

Run a sequence of commands from a file (or pipe from stdin):

```bash
nanokvm-hid script commands.txt
echo 'key CTRL+C' | nanokvm-hid script
```

Script files support comments and blank lines:

```bash
# login.script — unlock a workstation
mouse click 0.5 0.5
sleep 0.5
type "mypassword"
enter
sleep 2
# open a terminal
key CTRL+ALT+T
```

## Supported Keys

**Modifiers:** `CTRL`, `SHIFT`, `ALT`, `GUI` (+ `WIN`, `SUPER`, `META`, `CMD` aliases), with `LEFT_`/`RIGHT_` variants.

**Function keys:** `F1`–`F12`

**Navigation:** `UP_ARROW`, `DOWN_ARROW`, `LEFT_ARROW`, `RIGHT_ARROW`, `HOME`, `END`, `PAGE_UP`, `PAGE_DOWN`, `INSERT`, `DELETE`

**Control:** `ENTER`, `ESCAPE`, `BACKSPACE`, `TAB`, `SPACE`, `CAPS_LOCK`, `PRINT_SCREEN`, `SCROLL_LOCK`, `PAUSE`

**Media:** `PLAY_PAUSE`, `VOLUME_UP`, `VOLUME_DOWN`, `MUTE`, `SCAN_NEXT_TRACK`, `SCAN_PREVIOUS_TRACK`, `STOP`

## License

MIT
