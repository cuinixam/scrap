"""Archive downloading, SHA256 verification, and caching for Poks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.request import url2pathname

import requests
from py_app_dev.core.logging import logger

from poks.progress import ProgressCallback

_HASH_CHUNK_SIZE = 8192
_DOWNLOAD_TIMEOUT = 60


class DownloadError(Exception):
    """Raised when a file download fails."""


class HashMismatchError(Exception):
    """Raised when a file's SHA256 hash does not match the expected value."""


def download_file(
    url: str,
    dest: Path,
    app_name: str = "",
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """
    Download the file at *url* to *dest*.

    Args:
        url: URL to download from.
        dest: Local file path to write to.
        app_name: Application name passed to the progress callback.
        progress_callback: Optional callback invoked on each chunk.

    Returns:
        The *dest* path.

    Raises:
        DownloadError: On HTTP or network failures.

    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    if url.startswith("file://"):
        src = Path(url2pathname(url[7:]))
        file_size = src.stat().st_size
        downloaded = 0
        with src.open("rb") as src_fh, dest.open("wb") as dst_fh:
            while chunk := src_fh.read(_HASH_CHUNK_SIZE):
                dst_fh.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(app_name, downloaded, file_size)
        return dest
    _download_via_http(url, dest, app_name, progress_callback)
    return dest


def _download_via_http(
    url: str,
    dest: Path,
    app_name: str,
    progress_callback: ProgressCallback | None,
) -> None:
    try:
        with requests.get(url, stream=True, timeout=_DOWNLOAD_TIMEOUT) as response:
            response.raise_for_status()
            content_length = response.headers.get("Content-Length")
            total: int | None = int(content_length) if content_length else None
            downloaded = 0
            with dest.open("wb") as fh:
                for chunk in response.iter_content(chunk_size=_HASH_CHUNK_SIZE):
                    fh.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(app_name, downloaded, total)
    except requests.RequestException as exc:
        raise DownloadError(f"Failed to download {url}: {exc}") from exc


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
    filename = Path(url.split("?")[0].rstrip("/")).name
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:8]
    return cache_dir / f"{url_hash}_{filename}"


@dataclass
class DownloadResult:
    """Result of a download operation with cache status."""

    path: Path
    downloaded: bool


def get_cached_or_download(
    url: str,
    sha256: str,
    cache_dir: Path,
    app_name: str = "",
    progress_callback: ProgressCallback | None = None,
    use_cache: bool = True,
) -> DownloadResult:
    """
    Return a cached copy of the archive, downloading if necessary.

    If the cached file exists but has the wrong hash it is deleted and
    re-downloaded.

    Args:
        url: Archive URL.
        sha256: Expected SHA256 hex digest.
        cache_dir: Directory used for caching downloaded archives.
        app_name: Application name passed to the progress callback.
        progress_callback: Optional callback invoked during download.
        use_cache: If False, skip the cache and always download.

    Returns:
        Path to the verified archive in the cache.

    """
    cached = _cache_path_for(url, cache_dir)
    if use_cache and cached.exists():
        try:
            verify_sha256(cached, sha256)
            logger.info(f"Cache hit: {cached}")
            return DownloadResult(path=cached, downloaded=False)
        except HashMismatchError:
            logger.warning(f"Corrupt cache entry {cached}, re-downloading")
            cached.unlink()
    cache_dir.mkdir(parents=True, exist_ok=True)
    download_file(url, cached, app_name=app_name, progress_callback=progress_callback)
    verify_sha256(cached, sha256)
    return DownloadResult(path=cached, downloaded=True)
