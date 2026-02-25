"""Tests for constants and character mapping."""

from nanokvm_hid.constants import char_to_key_descriptor


class TestCharToKeyDescriptor:
    def test_lowercase_letter(self) -> None:
        assert char_to_key_descriptor("a") == "A"  # unshifted

    def test_uppercase_letter(self) -> None:
        assert char_to_key_descriptor("A") == "SHIFT+A"

    def test_digit(self) -> None:
        assert char_to_key_descriptor("5") == "5"

    def test_shifted_symbol(self) -> None:
        assert char_to_key_descriptor("!") == "SHIFT+1"
        assert char_to_key_descriptor("@") == "SHIFT+2"
        assert char_to_key_descriptor("~") == "SHIFT+`"

    def test_unshifted_symbol(self) -> None:
        assert char_to_key_descriptor("-") == "-"
        assert char_to_key_descriptor("[") == "["
        assert char_to_key_descriptor("/") == "/"

    def test_space(self) -> None:
        assert char_to_key_descriptor(" ") == "SPACE"

    def test_unmappable_char(self) -> None:
        assert char_to_key_descriptor("\n") is None
        assert char_to_key_descriptor("\t") is None
        assert char_to_key_descriptor("é") is None
