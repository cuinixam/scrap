"""Conda prefix patching — poke packages into shape for their new home."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PatchEntry:
    """A single file that needs prefix replacement."""

    path: str
    prefix_placeholder: str
    file_mode: str  # "text" or "binary"


def poke(install_dir: Path, patches: list[PatchEntry]) -> None:
    """
    Replace conda build prefixes with the actual install directory.

    Text-mode patches do a straightforward string replacement.
    Binary-mode patches do a null-padded byte replacement preserving file size.
    On Windows, backslash delimiters in the placeholder are matched in the replacement.
    """
    new_prefix = str(install_dir)
    for entry in patches:
        target = install_dir / entry.path
        if not target.is_file():
            logger.warning("Skipping patch for missing file: %s", entry.path)
            continue

        if entry.file_mode == "text":
            _poke_text(target, entry.prefix_placeholder, new_prefix)
        elif entry.file_mode == "binary":
            _poke_binary(target, entry.prefix_placeholder, new_prefix)
        else:
            logger.warning("Unknown file_mode %r for %s, skipping", entry.file_mode, entry.path)


def _poke_text(target: Path, placeholder: str, new_prefix: str) -> None:
    content = target.read_text(encoding="utf-8", errors="surrogateescape")
    updated = content.replace(placeholder, new_prefix)
    if "\\" in placeholder:
        updated = updated.replace(placeholder.replace("\\", "/"), new_prefix.replace("\\", "/"))
    target.write_text(updated, encoding="utf-8", errors="surrogateescape")


def _poke_binary(target: Path, placeholder: str, new_prefix: str) -> None:
    placeholder_bytes = placeholder.encode("utf-8")
    new_bytes = new_prefix.encode("utf-8")
    if len(new_bytes) > len(placeholder_bytes):
        raise ValueError(f"Cannot poke '{target.name}': install path ({len(new_bytes)} bytes) exceeds placeholder ({len(placeholder_bytes)} bytes)")
    padded = new_bytes + b"\x00" * (len(placeholder_bytes) - len(new_bytes))
    data = target.read_bytes()
    updated = data.replace(placeholder_bytes, padded)
    if "\\" in placeholder:
        fwd_placeholder = placeholder.replace("\\", "/").encode("utf-8")
        fwd_new = new_prefix.replace("\\", "/").encode("utf-8")
        fwd_padded = fwd_new + b"\x00" * (len(fwd_placeholder) - len(fwd_new))
        updated = updated.replace(fwd_placeholder, fwd_padded)
    target.write_bytes(updated)
