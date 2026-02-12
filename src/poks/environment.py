"""Environment variable collection and merging for installed apps."""

from __future__ import annotations

import os
from pathlib import Path

from py_app_dev.core.logging import logger

from poks.domain import PoksAppVersion


def collect_env_updates(version: PoksAppVersion, install_dir: Path) -> dict[str, str]:
    """
    Build a dictionary of environment variable updates from a version spec.

    Resolves ``bin`` paths relative to *install_dir* into a ``PATH`` entry and
    expands ``${dir}`` in ``env`` values.
    """
    result: dict[str, str] = {}
    if version.bin:
        paths = [str(install_dir / entry) for entry in version.bin]
        result["PATH"] = os.pathsep.join(paths)
    if version.env:
        dir_str = str(install_dir)
        for key, value in version.env.items():
            result[key] = value.replace("${dir}", dir_str)
    return result


def merge_env_updates(updates: list[dict[str, str]]) -> dict[str, str]:
    """
    Merge multiple env-update dicts into one.

    ``PATH`` entries are concatenated with the OS path separator.  For other
    keys, last writer wins and a warning is emitted on conflicts.
    """
    merged: dict[str, str] = {}
    for env in updates:
        for key, value in env.items():
            if key == "PATH":
                merged[key] = os.pathsep.join(filter(None, [merged.get(key), value]))
            elif key in merged and merged[key] != value:
                logger.warning(f"Conflicting env var {key!r}: overwriting {merged[key]!r} with {value!r}")
                merged[key] = value
            else:
                merged[key] = value
    return merged
