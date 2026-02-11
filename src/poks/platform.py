"""Platform detection utilities for Poks."""

from __future__ import annotations

import platform
import sys

_OS_MAP: dict[str, str] = {
    "win32": "windows",
    "linux": "linux",
    "darwin": "macos",
}

_ARCH_MAP: dict[str, str] = {
    "x86_64": "x86_64",
    "amd64": "x86_64",
    "aarch64": "aarch64",
    "arm64": "aarch64",
}


def get_current_platform() -> tuple[str, str]:
    """
    Return the current ``(os, arch)`` using Poks naming conventions.

    Raises:
        ValueError: If the current OS or architecture is not recognized.

    """
    raw_os = sys.platform
    raw_arch = platform.machine().lower()
    poks_os = _OS_MAP.get(raw_os)
    if poks_os is None:
        raise ValueError(f"Unsupported OS: {raw_os!r}. Supported: {sorted(_OS_MAP)}")
    poks_arch = _ARCH_MAP.get(raw_arch)
    if poks_arch is None:
        raise ValueError(f"Unsupported architecture: {raw_arch!r}. Supported: {sorted(_ARCH_MAP)}")
    return poks_os, poks_arch
