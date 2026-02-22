"""Archive extraction for Poks."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
import zipfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Literal, cast

import py7zr
import zstandard
from py_app_dev.core.exceptions import UserNotificationException

from poks.poker import PatchEntry, poke
from poks.progress import ProgressCallback

SUPPORTED_FORMATS: dict[str, str] = {
    ".conda": "conda",
    ".zip": "zip",
    ".tar.gz": "tar:gz",
    ".tgz": "tar:gz",
    ".tar.xz": "tar:xz",
    ".txz": "tar:xz",
    ".tar.bz2": "tar:bz2",
    ".tbz2": "tar:bz2",
    ".7z": "7z",
}


def _detect_format(archive_path: Path) -> str:
    """Return the format key for the given archive path based on its suffix(es)."""
    name = archive_path.name.lower()
    for ext, fmt in SUPPORTED_FORMATS.items():
        if name.endswith(ext):
            return fmt
    supported = ", ".join(sorted(SUPPORTED_FORMATS.keys()))
    raise ValueError(f"Unsupported archive format: {archive_path.name}. Supported: {supported}")


def _validate_entry_paths(names: list[str], dest_dir: Path) -> None:
    """Reject archive entries that would escape *dest_dir* via path traversal."""
    resolved_dest = dest_dir.resolve()
    for name in names:
        target = (dest_dir / name).resolve()
        if not target.is_relative_to(resolved_dest):
            raise ValueError(f"Path traversal detected in archive entry: {name!r}")


@contextmanager
def _open_archive(archive_path: Path, fmt: str) -> Generator[Any, None, None]:
    """Open an archive file and yield the archive object."""
    if fmt == "zip":
        with zipfile.ZipFile(archive_path) as zf:
            yield zf
    elif fmt == "7z":
        with py7zr.SevenZipFile(archive_path, mode="r") as sz:
            yield sz
    else:
        tar_mode = cast(Literal["r:gz", "r:xz", "r:bz2"], f"r:{fmt.split(':')[1]}")
        with tarfile.open(archive_path, tar_mode) as tf:
            yield tf


def _extract_all(
    archive: Any,
    fmt: str,
    dest_dir: Path,
    progress_callback: ProgressCallback | None = None,
    app_name: str = "",
) -> None:
    """Extract all contents of an archive into dest_dir after validating paths."""
    if fmt == "zip":
        members = archive.infolist()
        _validate_entry_paths(archive.namelist(), dest_dir)
        total = len(members)
        for idx, member in enumerate(members, 1):
            archive.extract(member, dest_dir)
            if progress_callback:
                progress_callback(app_name, idx, total)
    elif fmt == "7z":
        names = archive.getnames()
        _validate_entry_paths(names, dest_dir)
        archive.extractall(path=dest_dir)  # noqa: S202
        if progress_callback:
            progress_callback(app_name, len(names), len(names))
    else:
        members = archive.getmembers()
        total = len(members)
        if hasattr(tarfile, "data_filter"):
            for idx, member in enumerate(members, 1):
                archive.extract(member, dest_dir, filter="data")
                if progress_callback:
                    progress_callback(app_name, idx, total)
        else:
            _validate_entry_paths([m.name for m in members], dest_dir)
            for idx, member in enumerate(members, 1):
                archive.extract(member, dest_dir)
                if progress_callback:
                    progress_callback(app_name, idx, total)


def _relocate_extract_dir(dest_dir: Path, extract_dir: str) -> None:
    """Move contents of dest_dir/extract_dir into dest_dir."""
    source = dest_dir / extract_dir
    if not source.resolve().is_relative_to(dest_dir.resolve()):
        raise ValueError(f"extract_dir '{extract_dir}' escapes destination directory")
    if not source.is_dir():
        raise ValueError(f"extract_dir '{extract_dir}' not found in extracted archive")
    for item in source.iterdir():
        shutil.move(str(item), str(dest_dir / item.name))
    source.rmdir()


def _decompress_zstd(data: bytes) -> bytes:
    """Decompress zstandard-compressed bytes."""
    dctx = zstandard.ZstdDecompressor()
    return dctx.decompress(data, max_output_size=256 * 1024 * 1024)


def _extract_tar_from_bytes(data: bytes, dest_dir: Path) -> None:
    """Extract a tar archive from raw bytes into dest_dir with path validation."""
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as tf:
        if hasattr(tarfile, "data_filter"):
            tf.extractall(dest_dir, filter="data")
        else:
            _validate_entry_paths([member.name for member in tf.getmembers()], dest_dir)
            tf.extractall(dest_dir)  # noqa: S202


def _parse_conda_patches(info_tar_zst_bytes: bytes) -> list[PatchEntry]:
    """Parse paths.json from a conda info tar.zst and return patch entries."""
    tar_bytes = _decompress_zstd(info_tar_zst_bytes)
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tf:
        for member in tf.getmembers():
            if member.name.endswith("paths.json") or member.name == "paths.json":
                extracted = tf.extractfile(member)
                if extracted is None:
                    continue
                paths_data = json.loads(extracted.read())
                return [
                    PatchEntry(
                        path=entry["_path"],
                        prefix_placeholder=entry["prefix_placeholder"],
                        file_mode=entry["file_mode"],
                    )
                    for entry in paths_data.get("paths", [])
                    if "prefix_placeholder" in entry and "file_mode" in entry
                ]
    return []


def _extract_conda(archive_path: Path, dest_dir: Path) -> None:
    """Extract a .conda archive: unzip outer, extract inner tar.zst, apply poking."""
    patches: list[PatchEntry] = []
    with zipfile.ZipFile(archive_path) as zf:
        names = zf.namelist()
        info_members = [name for name in names if name.startswith("info-") and name.endswith(".tar.zst")]
        pkg_members = [name for name in names if name.startswith("pkg-") and name.endswith(".tar.zst")]
        if not pkg_members:
            raise ValueError(f"Invalid .conda archive: no pkg-*.tar.zst found in {archive_path.name}")
        if info_members:
            info_data = zf.read(info_members[0])
            patches = _parse_conda_patches(info_data)
        pkg_data = zf.read(pkg_members[0])

    pkg_tar_bytes = _decompress_zstd(pkg_data)
    _extract_tar_from_bytes(pkg_tar_bytes, dest_dir)

    if patches:
        poke(dest_dir, patches)


def extract_archive(
    archive_path: Path,
    dest_dir: Path,
    extract_dir: str | None = None,
    progress_callback: ProgressCallback | None = None,
    app_name: str = "",
) -> Path:
    """Extract an archive into *dest_dir* and return *dest_dir*."""
    fmt = _detect_format(archive_path)
    dest_dir.mkdir(parents=True, exist_ok=True)
    try:
        if fmt == "conda":
            _extract_conda(archive_path, dest_dir)
            if progress_callback:
                progress_callback(app_name, 1, 1)
        else:
            with _open_archive(archive_path, fmt) as archive:
                _extract_all(archive, fmt, dest_dir, progress_callback, app_name)
    except py7zr.exceptions.UnsupportedCompressionMethodError as exc:
        raise UserNotificationException(f"Cannot extract '{archive_path.name}': {exc}. Try installing 7-Zip and extracting manually.") from exc
    if extract_dir:
        _relocate_extract_dir(dest_dir, extract_dir)
    return dest_dir
