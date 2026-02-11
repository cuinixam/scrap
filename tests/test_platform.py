"""Tests for platform detection utilities."""

from __future__ import annotations

import pytest

from poks.platform import get_current_platform


@pytest.mark.parametrize(
    ("sys_platform", "machine", "expected"),
    [
        ("linux", "x86_64", ("linux", "x86_64")),
        ("linux", "aarch64", ("linux", "aarch64")),
        ("darwin", "arm64", ("macos", "aarch64")),
        ("darwin", "x86_64", ("macos", "x86_64")),
        ("win32", "AMD64", ("windows", "x86_64")),
        ("win32", "x86_64", ("windows", "x86_64")),
    ],
)
def test_get_current_platform(
    sys_platform: str,
    machine: str,
    expected: tuple[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("poks.platform.sys.platform", sys_platform)
    monkeypatch.setattr("poks.platform.platform.machine", lambda: machine)
    assert get_current_platform() == expected


def test_unsupported_os(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("poks.platform.sys.platform", "freebsd")
    with pytest.raises(ValueError, match="Unsupported OS"):
        get_current_platform()


def test_unsupported_arch(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("poks.platform.sys.platform", "linux")
    monkeypatch.setattr("poks.platform.platform.machine", lambda: "mips")
    with pytest.raises(ValueError, match="Unsupported architecture"):
        get_current_platform()
