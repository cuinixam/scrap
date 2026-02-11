"""Archive downloading, SHA256 verification, and caching for Poks."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlretrieve

from py_app_dev.core.logging import logger

_HASH_CHUNK_SIZE = 8192


class DownloadError(Exception):
    """Raised when a file download fails."""


class HashMismatchError(Exception):
    """Raised when a file's SHA256 hash does not match the expected value."""


def download_file(url: str, dest: Path) -> Path:
    """
    Download the file at *url* to *dest*.

    Args:
        url: URL to download from.
        dest: Local file path to write to.

    Returns:
        The *dest* path.

    Raises:
        DownloadError: On HTTP or network failures.

    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        urlretrieve(url, dest)  # noqa: S310
    except (URLError, OSError) as exc:
        raise DownloadError(f"Failed to download {url}: {exc}") from exc
    logger.info(f"Downloaded {url} -> {dest}")
    return dest


def verify_sha256(file_path: Path, expected_hash: str) -> None:
    """
    Verify *file_path* matches *expected_hash*.

    Raises:
        HashMismatchError: When the computed hash differs from *expected_hash*.

    """
    sha256 = hashlib.sha256()
    with file_path.open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK_SIZE):
            sha256.update(chunk)
    actual = sha256.hexdigest()
    if actual != expected_hash:
        raise HashMismatchError(f"SHA256 mismatch for {file_path.name}: expected {expected_hash}, got {actual}")


def _cache_path_for(url: str, cache_dir: Path) -> Path:
    """Derive a deterministic cache file path from a URL."""
    return cache_dir / Path(url.split("?")[0].rstrip("/")).name


def get_cached_or_download(url: str, sha256: str, cache_dir: Path) -> Path:
    """
    Return a cached copy of the archive, downloading if necessary.

    If the cached file exists but has the wrong hash it is deleted and
    re-downloaded.

    Args:
        url: Archive URL.
        sha256: Expected SHA256 hex digest.
        cache_dir: Directory used for caching downloaded archives.

    Returns:
        Path to the verified archive in the cache.

    """
    cached = _cache_path_for(url, cache_dir)
    if cached.exists():
        try:
            verify_sha256(cached, sha256)
            logger.info(f"Cache hit: {cached}")
            return cached
        except HashMismatchError:
            logger.warning(f"Corrupt cache entry {cached}, re-downloading")
            cached.unlink()
    cache_dir.mkdir(parents=True, exist_ok=True)
    download_file(url, cached)
    verify_sha256(cached, sha256)
    return cached
