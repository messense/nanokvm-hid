"""Tests for constants and character mapping."""

import pytest

from nanokvm_hid.constants import char_to_key_descriptor


@pytest.mark.parametrize(
    ("char", "expected"),
    [
        ("a", "A"),
        ("z", "Z"),
        ("A", "SHIFT+A"),
        ("Z", "SHIFT+Z"),
        ("5", "5"),
        ("0", "0"),
        (" ", "SPACE"),
        # Unshifted symbols
        ("-", "-"),
        ("[", "["),
        ("/", "/"),
        ("`", "`"),
        # Shifted symbols
        ("!", "SHIFT+1"),
        ("@", "SHIFT+2"),
        ("~", "SHIFT+`"),
        ("#", "SHIFT+3"),
        ("{", "SHIFT+["),
    ],
)
def test_char_to_key_descriptor(char, expected):
    assert char_to_key_descriptor(char) == expected


@pytest.mark.parametrize("char", ["\n", "\t", "é", "\x00", "中"])
def test_unmappable_char_returns_none(char):
    assert char_to_key_descriptor(char) is None
