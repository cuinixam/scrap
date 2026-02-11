"""Unit tests for the downloader module."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

import pytest

from poks.downloader import (
    DownloadError,
    HashMismatchError,
    download_file,
    get_cached_or_download,
    verify_sha256,
)

SAMPLE_CONTENT = b"hello poks"
SAMPLE_SHA256 = hashlib.sha256(SAMPLE_CONTENT).hexdigest()


def _fake_urlretrieve(dest: Path) -> None:
    """Write sample content to *dest*, simulating a download."""
    dest.write_bytes(SAMPLE_CONTENT)


# -- download_file -----------------------------------------------------------


def test_download_file_success(tmp_path: Path) -> None:
    dest = tmp_path / "sub" / "archive.tar.gz"

    with patch(
        "poks.downloader.urlretrieve", side_effect=lambda _url, d: _fake_urlretrieve(d)
    ):
        result = download_file("https://example.com/archive.tar.gz", dest)

    assert result == dest
    assert dest.read_bytes() == SAMPLE_CONTENT


def test_download_file_network_error(tmp_path: Path) -> None:
    dest = tmp_path / "archive.tar.gz"

    with (
        patch(
            "poks.downloader.urlretrieve", side_effect=URLError("connection refused")
        ),
        pytest.raises(DownloadError, match="connection refused"),
    ):
        download_file("https://example.com/archive.tar.gz", dest)


# -- verify_sha256 -----------------------------------------------------------


def test_verify_sha256_valid(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(SAMPLE_CONTENT)

    verify_sha256(path, SAMPLE_SHA256)


def test_verify_sha256_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(SAMPLE_CONTENT)

    with pytest.raises(HashMismatchError, match="SHA256 mismatch"):
        verify_sha256(path, "bad" * 16)


# -- get_cached_or_download --------------------------------------------------


def test_cached_file_reused(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_file = cache_dir / "archive.tar.gz"
    cached_file.write_bytes(SAMPLE_CONTENT)

    with patch("poks.downloader.urlretrieve") as mock_dl:
        result = get_cached_or_download(
            "https://example.com/archive.tar.gz", SAMPLE_SHA256, cache_dir
        )

    assert result == cached_file
    mock_dl.assert_not_called()


def test_corrupt_cache_redownloaded(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_file = cache_dir / "archive.tar.gz"
    cached_file.write_bytes(b"corrupt data")

    with patch(
        "poks.downloader.urlretrieve", side_effect=lambda _url, d: _fake_urlretrieve(d)
    ):
        result = get_cached_or_download(
            "https://example.com/archive.tar.gz", SAMPLE_SHA256, cache_dir
        )

    assert result == cached_file
    assert cached_file.read_bytes() == SAMPLE_CONTENT


def test_missing_cache_downloads(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"

    with patch(
        "poks.downloader.urlretrieve", side_effect=lambda _url, d: _fake_urlretrieve(d)
    ):
        result = get_cached_or_download(
            "https://example.com/archive.tar.gz", SAMPLE_SHA256, cache_dir
        )

    assert result == cache_dir / "archive.tar.gz"
    assert result.read_bytes() == SAMPLE_CONTENT
