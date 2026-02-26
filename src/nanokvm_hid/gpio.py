"""GPIO control for power/reset buttons and LED status on NanoKVM Pro.

The NanoKVM Pro has GPIO pins connected to the target machine's
power switch, reset switch, and front-panel LED headers.  This module
provides a clean interface for pressing those buttons and reading
the LED states.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

# NanoKVM Pro GPIO pin mappings (from hardware config)
DEFAULT_GPIO_POWER = "/sys/class/gpio/gpio7/value"
DEFAULT_GPIO_RESET = "/sys/class/gpio/gpio35/value"
DEFAULT_GPIO_POWER_LED = "/sys/class/gpio/gpio75/value"
DEFAULT_GPIO_HDD_LED = "/sys/class/gpio/gpio74/value"


def _write_gpio(device: str, value: str) -> None:
    """Write a value to a GPIO sysfs file."""
    Path(device).write_text(value)


def _read_gpio(device: str) -> bool:
    """Read a GPIO value.  Returns True when the LED is active (value == 0)."""
    content = Path(device).read_text().strip()
    try:
        return int(content) == 0
    except ValueError:
        logger.warning("Unexpected GPIO value %r from %s", content, device)
        return False


class GPIO:
    """Control power/reset buttons and read LED states on the target machine.

    The NanoKVM Pro's GPIO pins are directly wired to the target
    machine's front-panel header, allowing hardware-level power
    and reset control — just like pressing the physical buttons.

    Parameters
    ----------
    power_pin:
        Sysfs path for the power button GPIO.
    reset_pin:
        Sysfs path for the reset button GPIO.
    power_led_pin:
        Sysfs path for the power LED GPIO.
    hdd_led_pin:
        Sysfs path for the HDD activity LED GPIO.
    """

    def __init__(
        self,
        power_pin: str = DEFAULT_GPIO_POWER,
        reset_pin: str = DEFAULT_GPIO_RESET,
        power_led_pin: str = DEFAULT_GPIO_POWER_LED,
        hdd_led_pin: str = DEFAULT_GPIO_HDD_LED,
    ) -> None:
        self.power_pin = power_pin
        self.reset_pin = reset_pin
        self.power_led_pin = power_led_pin
        self.hdd_led_pin = hdd_led_pin

    def _press(self, pin: str, duration_ms: int) -> None:
        """Pulse a GPIO pin high for the given duration, then release."""
        _write_gpio(pin, "1")
        time.sleep(duration_ms / 1000.0)
        _write_gpio(pin, "0")

    # ------------------------------------------------------------------
    # Power button
    # ------------------------------------------------------------------

    def power(self, duration_ms: int = 800) -> None:
        """Press the power button.

        Parameters
        ----------
        duration_ms:
            How long to hold the button in milliseconds.
            Short press (~800 ms) = normal power on/off.
            Long press (~5000 ms) = force power off.

        Examples::

            gpio = GPIO()
            gpio.power()             # short press — toggle power
            gpio.power(5000)         # long press — force off
        """
        self._press(self.power_pin, duration_ms)
        logger.info("power button pressed for %d ms", duration_ms)

    def power_off(self, duration_ms: int = 5000) -> None:
        """Force power off by long-pressing the power button.

        Parameters
        ----------
        duration_ms:
            Duration of the long press (default: 5000 ms).
        """
        self.power(duration_ms)

    # ------------------------------------------------------------------
    # Reset button
    # ------------------------------------------------------------------

    def reset(self, duration_ms: int = 800) -> None:
        """Press the reset button.

        Parameters
        ----------
        duration_ms:
            How long to hold the button in milliseconds.
        """
        self._press(self.reset_pin, duration_ms)
        logger.info("reset button pressed for %d ms", duration_ms)

    # ------------------------------------------------------------------
    # LED status
    # ------------------------------------------------------------------

    def power_led(self) -> bool:
        """Read the power LED state.

        Returns
        -------
        bool
            ``True`` if the target machine's power LED is on (machine is
            powered), ``False`` otherwise.
        """
        state = _read_gpio(self.power_led_pin)
        logger.debug("power LED: %s", "on" if state else "off")
        return state

    def hdd_led(self) -> bool:
        """Read the HDD activity LED state.

        Returns
        -------
        bool
            ``True`` if the HDD LED is active.
        """
        state = _read_gpio(self.hdd_led_pin)
        logger.debug("HDD LED: %s", "on" if state else "off")
        return state

    def __repr__(self) -> str:
        return (
            f"GPIO(power={self.power_pin!r}, reset={self.reset_pin!r}, "
            f"power_led={self.power_led_pin!r}, hdd_led={self.hdd_led_pin!r})"
        )
