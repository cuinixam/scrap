"""Unit tests for the downloader module."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from poks.downloader import (
    DownloadError,
    HashMismatchError,
    _cache_path_for,
    download_file,
    get_cached_or_download,
    verify_sha256,
)

SAMPLE_CONTENT = b"hello poks"
SAMPLE_SHA256 = hashlib.sha256(SAMPLE_CONTENT).hexdigest()


def _mock_requests_get(content_length: str | None = None) -> MagicMock:
    """Create a mock requests.get that streams SAMPLE_CONTENT."""
    mock_response = MagicMock()
    mock_response.headers = {"Content-Length": content_length} if content_length else {}
    mock_response.iter_content = lambda chunk_size: iter([SAMPLE_CONTENT])
    mock_response.raise_for_status = MagicMock()
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=mock_response)


# -- download_file -----------------------------------------------------------


def test_download_file_success(tmp_path: Path) -> None:
    dest = tmp_path / "sub" / "archive.tar.gz"

    with patch("poks.downloader.requests.get", _mock_requests_get()):
        result = download_file("https://example.com/archive.tar.gz", dest)

    assert result == dest
    assert dest.read_bytes() == SAMPLE_CONTENT


def test_download_file_network_error(tmp_path: Path) -> None:
    dest = tmp_path / "archive.tar.gz"

    with (
        patch("poks.downloader.requests.get", side_effect=requests.RequestException("connection refused")),
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
    url = "https://example.com/archive.tar.gz"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_file = _cache_path_for(url, cache_dir)
    cached_file.write_bytes(SAMPLE_CONTENT)

    with patch("poks.downloader.requests.get") as mock_dl:
        result = get_cached_or_download(url, SAMPLE_SHA256, cache_dir)

    assert result.path == cached_file
    assert result.downloaded is False
    mock_dl.assert_not_called()


def test_corrupt_cache_redownloaded(tmp_path: Path) -> None:
    url = "https://example.com/archive.tar.gz"
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cached_file = _cache_path_for(url, cache_dir)
    cached_file.write_bytes(b"corrupt data")

    with patch("poks.downloader.requests.get", _mock_requests_get()):
        result = get_cached_or_download(url, SAMPLE_SHA256, cache_dir)

    assert result.path == cached_file
    assert result.downloaded is True
    assert cached_file.read_bytes() == SAMPLE_CONTENT


def test_missing_cache_downloads(tmp_path: Path) -> None:
    url = "https://example.com/archive.tar.gz"
    cache_dir = tmp_path / "cache"

    with patch("poks.downloader.requests.get", _mock_requests_get()):
        result = get_cached_or_download(url, SAMPLE_SHA256, cache_dir)

    assert result.path == _cache_path_for(url, cache_dir)
    assert result.downloaded is True
    assert result.path.read_bytes() == SAMPLE_CONTENT


# -- cache collision avoidance ------------------------------------------------


def test_cache_path_collision_avoidance(tmp_path: Path) -> None:
    """Two URLs with the same filename produce distinct cache paths."""
    cache_dir = tmp_path / "cache"
    path_a = _cache_path_for("https://example.com/v1/archive.tar.gz", cache_dir)
    path_b = _cache_path_for("https://example.com/v2/archive.tar.gz", cache_dir)

    assert path_a != path_b
    assert path_a.name.endswith("_archive.tar.gz")
    assert path_b.name.endswith("_archive.tar.gz")


# -- progress callback -------------------------------------------------------


def test_progress_callback_invoked_with_total(tmp_path: Path) -> None:
    dest = tmp_path / "archive.tar.gz"
    calls: list[tuple[str, int, int | None]] = []

    with patch("poks.downloader.requests.get", _mock_requests_get(content_length=str(len(SAMPLE_CONTENT)))):
        download_file(
            "https://example.com/archive.tar.gz",
            dest,
            app_name="my-tool",
            progress_callback=lambda name, downloaded, total: calls.append((name, downloaded, total)),
        )

    assert len(calls) >= 1
    assert all(name == "my-tool" for name, _, _ in calls)
    _last_name, last_downloaded, last_total = calls[-1]
    assert last_downloaded == len(SAMPLE_CONTENT)
    assert last_total == len(SAMPLE_CONTENT)


def test_progress_callback_without_content_length(tmp_path: Path) -> None:
    dest = tmp_path / "archive.tar.gz"
    calls: list[tuple[str, int, int | None]] = []

    with patch("poks.downloader.requests.get", _mock_requests_get()):
        download_file(
            "https://example.com/archive.tar.gz",
            dest,
            app_name="my-tool",
            progress_callback=lambda name, downloaded, total: calls.append((name, downloaded, total)),
        )

    assert len(calls) >= 1
    _last_name, last_downloaded, last_total = calls[-1]
    assert last_downloaded == len(SAMPLE_CONTENT)
    assert last_total is None
