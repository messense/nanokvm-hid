---
name: nanokvm-hid
description: Control a remote computer via NanoKVM Pro IP-KVM hardware — keyboard, mouse, and screen capture. Use when asked to interact with a NanoKVM-controlled machine, automate GUI tasks via IP-KVM, take screenshots through HDMI capture, or perform computer-use agent (CUA) style operations on a remote display.
---

# NanoKVM HID — Remote Computer Control via IP-KVM

Control a remote computer's keyboard, mouse, and screen through a NanoKVM Pro device using the `nanokvm-hid` Python library.

## Overview

NanoKVM Pro is an IP-KVM device that sits between a host computer and its peripherals, exposing USB HID gadget devices (`/dev/hidg0–2`). This skill lets you:

- **See** the remote screen (JPEG capture via HDMI)
- **Type** text and press key combos (keyboard HID)
- **Click, move, scroll, drag** (mouse + absolute touchpad HID)

All coordinates are **normalised to `[0.0, 1.0]`** — no need to know pixel dimensions.

## Setup

### Determine where you are running

There are two scenarios:

1. **On the NanoKVM itself** — the HID devices are local at `/dev/hidg0–2`. Install and use directly.
2. **On a remote machine** (your laptop, a CI server, etc.) — you SSH into the NanoKVM to run commands. The NanoKVM default credentials are `root@<ip>` with an empty password or `root`.

### Install the library

```bash
# On the NanoKVM (SSH in first if remote)
ssh root@<NANOKVM_IP>
pip install nanokvm-hid
```

The library has **zero runtime dependencies** (stdlib only) and works on Python ≥ 3.10.

### Verify the device

```bash
# On the NanoKVM
nanokvm-hid info
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
| `mouse move <x> <y>` | Move cursor (normalised 0.0–1.0) | `nanokvm-hid mouse move 0.5 0.5` |
| `mouse click <x> <y> [-r] [-d]` | Click (right, double flags) | `nanokvm-hid mouse click -d 0.5 0.5` |
| `mouse scroll-down [steps]` | Scroll down | `nanokvm-hid mouse scroll-down 3` |
| `mouse scroll-up [steps]` | Scroll up | `nanokvm-hid mouse scroll-up` |
| `mouse drag <x0> <y0> <x1> <y1>` | Drag between two points | `nanokvm-hid mouse drag 0.1 0.1 0.9 0.9` |
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
