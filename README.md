# nanokvm-hid

Python library for controlling keyboard, mouse, and touchpad via USB HID gadgets on [NanoKVM Pro](https://wiki.sipeed.com/nanokvm).

The NanoKVM Pro sits between a host computer and its peripherals, exposing USB HID gadget devices (`/dev/hidg0–2`) that allow hardware-level input injection — indistinguishable from a real keyboard and mouse. This library provides a clean, Pythonic API on top of those raw HID interfaces.

## Features

- **Keyboard** — key combos (`CTRL+C`, `ALT+F4`, `GUI+L`), media keys (`VOLUME_UP`), string typing
- **Mouse** — absolute positioning, left/right click, double-click, scroll, drag
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

# Mouse (coordinates are normalised 0.0–1.0)
nanokvm-hid mouse move 0.5 0.5             # move to center
nanokvm-hid mouse click 0.3 0.7            # left-click
nanokvm-hid mouse click -r 0.8 0.2         # right-click
nanokvm-hid mouse click -d 0.5 0.5         # double-click
nanokvm-hid mouse scroll-down 3
nanokvm-hid mouse scroll-up
nanokvm-hid mouse drag 0.1 0.1 0.9 0.9

# Options
nanokvm-hid --delay 0.05 type "fast typing"
```

## Supported Keys

**Modifiers:** `CTRL`, `SHIFT`, `ALT`, `GUI` (+ `WIN`, `SUPER`, `META`, `CMD` aliases), with `LEFT_`/`RIGHT_` variants.

**Function keys:** `F1`–`F12`

**Navigation:** `UP_ARROW`, `DOWN_ARROW`, `LEFT_ARROW`, `RIGHT_ARROW`, `HOME`, `END`, `PAGE_UP`, `PAGE_DOWN`, `INSERT`, `DELETE`

**Control:** `ENTER`, `ESCAPE`, `BACKSPACE`, `TAB`, `SPACE`, `CAPS_LOCK`, `PRINT_SCREEN`, `SCROLL_LOCK`, `PAUSE`

**Media:** `PLAY_PAUSE`, `VOLUME_UP`, `VOLUME_DOWN`, `MUTE`, `SCAN_NEXT_TRACK`, `SCAN_PREVIOUS_TRACK`, `STOP`

## License

MIT
