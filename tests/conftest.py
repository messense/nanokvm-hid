"""Shared test fixtures."""

from __future__ import annotations

import pytest

from nanokvm_hid.transport import HIDTransport


class FakeTransport(HIDTransport):
    """A transport that records reports instead of writing to a device."""

    def __init__(self) -> None:
        super().__init__("/dev/null")
        self.reports: list[bytes] = []

    def send(self, report: bytes | bytearray) -> None:
        self.reports.append(bytes(report))


@pytest.fixture()
def fake_transport() -> FakeTransport:
    return FakeTransport()
