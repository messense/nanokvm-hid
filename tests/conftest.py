"""Shared test fixtures."""

from __future__ import annotations

import pytest

from nanokvm_hid.keyboard import Keyboard
from nanokvm_hid.mouse import Mouse
from nanokvm_hid.transport import HIDTransport


class FakeTransport(HIDTransport):
    """A transport that records reports instead of writing to a device."""

    def __init__(self) -> None:
        super().__init__("/dev/null")
        self.reports: list[bytes] = []

    def send(self, report: bytes | bytearray) -> None:
        self.reports.append(bytes(report))


@pytest.fixture()
def fake_transport():
    return FakeTransport()


@pytest.fixture()
def kb(fake_transport):
    """Keyboard wired to a FakeTransport."""
    k = Keyboard(inter_report_delay=0)
    k._transport = fake_transport
    return k


@pytest.fixture()
def fake_mouse():
    """Mouse backed by fake transports."""
    mouse_t = FakeTransport()
    tp_t = FakeTransport()
    m = Mouse(screen_size=(1920, 1080))
    m._mouse = mouse_t
    m._touchpad = tp_t
    return m, mouse_t, tp_t
