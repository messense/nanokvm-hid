"""Tests for GPIO power/reset/LED control."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.gpio import GPIO, _read_gpio

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def gpio():
    return GPIO(
        power_pin="/tmp/test_gpio_power",
        reset_pin="/tmp/test_gpio_reset",
        power_led_pin="/tmp/test_gpio_power_led",
        hdd_led_pin="/tmp/test_gpio_hdd_led",
    )


# ── _read_gpio ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ("0\n", True),   # active-low: 0 means LED on
        ("1\n", False),  # 1 means LED off
        ("0", True),
        ("1", False),
    ],
)
def test_read_gpio(tmp_path, content, expected):
    f = tmp_path / "gpio"
    f.write_text(content)
    assert _read_gpio(str(f)) is expected


# ── power button ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "duration", "pin_attr"),
    [
        ("power", 800, "power_pin"),
        ("power", 5000, "power_pin"),
        ("reset", 800, "reset_pin"),
        ("reset", 200, "reset_pin"),
    ],
)
@patch("nanokvm_hid.gpio._write_gpio")
@patch("nanokvm_hid.gpio.time")
def test_button_press(
    mock_time, mock_write, gpio, method, duration, pin_attr,
):
    getattr(gpio, method)(duration_ms=duration)
    pin = getattr(gpio, pin_attr)
    mock_write.assert_any_call(pin, "1")
    mock_write.assert_any_call(pin, "0")
    assert mock_write.call_count == 2
    mock_time.sleep.assert_called_once_with(duration / 1000.0)


@patch("nanokvm_hid.gpio._write_gpio")
@patch("nanokvm_hid.gpio.time")
def test_power_off_defaults_to_5s(mock_time, mock_write, gpio):
    gpio.power_off()
    mock_time.sleep.assert_called_once_with(5.0)


# ── LED reads ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "pin_attr"),
    [
        ("power_led", "power_led_pin"),
        ("hdd_led", "hdd_led_pin"),
    ],
)
@pytest.mark.parametrize("value", [True, False])
@patch("nanokvm_hid.gpio._read_gpio")
def test_led_read(mock_read, gpio, method, pin_attr, value):
    mock_read.return_value = value
    assert getattr(gpio, method)() is value
    mock_read.assert_called_once_with(getattr(gpio, pin_attr))


# ── repr ─────────────────────────────────────────────────────────────


def test_repr(gpio):
    r = repr(gpio)
    assert "GPIO(" in r
    assert "power=" in r
