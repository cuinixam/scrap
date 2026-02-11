"""Environment variable collection and merging for installed apps."""

from __future__ import annotations

import os
from pathlib import Path

from py_app_dev.core.logging import logger

from poks.domain import PoksManifest


def collect_env_updates(manifest: PoksManifest, install_dir: Path) -> dict[str, str]:
    """
    Build a dictionary of environment variable updates from a manifest.

    Resolves ``bin`` paths relative to *install_dir* into a ``PATH`` entry and
    expands ``${dir}`` in ``env`` values.
    """
    result: dict[str, str] = {}
    if manifest.bin:
        paths = [str(install_dir / entry) for entry in manifest.bin]
        result["PATH"] = os.pathsep.join(paths)
    if manifest.env:
        dir_str = str(install_dir)
        for key, value in manifest.env.items():
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
