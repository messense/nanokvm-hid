"""Tests for USB mass-storage (ISO/IMG mount) control."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from nanokvm_hid.storage import Storage

# ── fixtures ─────────────────────────────────────────────────────────


@pytest.fixture()
def storage_env(tmp_path):
    """Temporary storage environment with mock sysfs files."""
    mount_file = tmp_path / "lun0_file"
    cdrom_file = tmp_path / "lun0_cdrom"
    ro_file = tmp_path / "lun0_ro"

    mount_file.write_text("")
    cdrom_file.write_text("0")
    ro_file.write_text("0")

    image_dir = tmp_path / "data"
    image_dir.mkdir()

    return Storage(
        mount_device=str(mount_file),
        cdrom_flag=str(cdrom_file),
        ro_flag=str(ro_file),
        image_dirs=[str(image_dir)],
    )


# ── list_images ──────────────────────────────────────────────────────


def test_list_images_empty(storage_env):
    assert storage_env.list_images() == []


@pytest.mark.parametrize(
    ("filenames", "expected_count"),
    [
        (["ubuntu.iso"], 1),
        (["ubuntu.iso", "windows.img"], 2),
        (["ubuntu.iso", "readme.txt"], 1),  # txt ignored
        (["test.ISO", "test2.Img"], 2),  # case insensitive
    ],
)
def test_list_images_filters(
    storage_env,
    tmp_path,
    filenames,
    expected_count,
):
    image_dir = tmp_path / "data"
    for name in filenames:
        (image_dir / name).write_text("fake")

    assert len(storage_env.list_images()) == expected_count


def test_list_images_nested(storage_env, tmp_path):
    nested = tmp_path / "data" / "linux"
    nested.mkdir()
    (nested / "arch.iso").write_text("fake")
    assert len(storage_env.list_images()) == 1


# ── mount ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("cdrom", "read_only", "expect_cdrom", "expect_ro"),
    [
        (False, False, "0", "0"),
        (True, False, "1", "1"),  # cdrom implies read-only
        (False, True, "0", "1"),
        (True, True, "1", "1"),
    ],
)
@patch("nanokvm_hid.storage._restart_usb")
def test_mount(
    mock_restart,
    storage_env,
    tmp_path,
    cdrom,
    read_only,
    expect_cdrom,
    expect_ro,
):
    image = tmp_path / "data" / "test.iso"
    image.write_text("fake")

    storage_env.mount(str(image), cdrom=cdrom, read_only=read_only)

    assert (tmp_path / "lun0_file").read_text() == str(image)
    assert (tmp_path / "lun0_cdrom").read_text() == expect_cdrom
    assert (tmp_path / "lun0_ro").read_text() == expect_ro
    mock_restart.assert_called_once_with(enable=True)


def test_mount_nonexistent_raises(storage_env):
    with pytest.raises(FileNotFoundError):
        storage_env.mount("/nonexistent/file.iso")


# ── unmount ──────────────────────────────────────────────────────────


@patch("nanokvm_hid.storage._restart_usb")
def test_unmount(mock_restart, storage_env, tmp_path):
    (tmp_path / "lun0_file").write_text("/data/test.iso")
    storage_env.unmount()
    assert (tmp_path / "lun0_file").read_text() == "\n"
    mock_restart.assert_called_once_with(enable=False)


# ── mounted ──────────────────────────────────────────────────────────


def test_mounted_nothing(storage_env):
    assert storage_env.mounted() is None


@pytest.mark.parametrize(
    ("cdrom_val", "ro_val", "expect_cdrom", "expect_ro"),
    [
        ("0", "0", False, False),
        ("1", "1", True, True),
        ("0", "1", False, True),
    ],
)
def test_mounted_with_flags(
    storage_env,
    tmp_path,
    cdrom_val,
    ro_val,
    expect_cdrom,
    expect_ro,
):
    (tmp_path / "lun0_file").write_text("/data/test.iso")
    (tmp_path / "lun0_cdrom").write_text(cdrom_val)
    (tmp_path / "lun0_ro").write_text(ro_val)

    info = storage_env.mounted()
    assert info is not None
    assert info["file"] == "/data/test.iso"
    assert info["cdrom"] is expect_cdrom
    assert info["read_only"] is expect_ro
