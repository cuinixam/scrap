"""Integration tests for bucket syncing and manifest lookup."""

from __future__ import annotations

import pytest

from poks.bucket import find_manifest, sync_all_buckets, sync_bucket
from poks.domain import PoksArchive, PoksBucket, PoksManifest
from tests.conftest import PoksEnv


def test_sync_bucket_clones_new(poks_env: PoksEnv) -> None:
    manifest = PoksManifest(
        version="1.0.0",
        archives=[PoksArchive(os="linux", arch="x86_64", sha256="abc123")],
    )
    poks_env.add_manifest("tool-a", manifest)
    bucket = PoksBucket(name="main", url=poks_env.bucket_url)

    local_path = sync_bucket(bucket, poks_env.buckets_dir)

    assert local_path == poks_env.buckets_dir / "main"
    assert (local_path / "tool-a.json").exists()


def test_sync_bucket_pulls_existing(poks_env: PoksEnv) -> None:
    manifest_v1 = PoksManifest(
        version="1.0.0",
        archives=[PoksArchive(os="linux", arch="x86_64", sha256="abc123")],
    )
    poks_env.add_manifest("tool-a", manifest_v1)
    bucket = PoksBucket(name="main", url=poks_env.bucket_url)

    sync_bucket(bucket, poks_env.buckets_dir)

    # Add a second manifest and re-sync
    manifest_v2 = PoksManifest(
        version="2.0.0",
        archives=[PoksArchive(os="linux", arch="x86_64", sha256="def456")],
    )
    poks_env.add_manifest("tool-b", manifest_v2)

    local_path = sync_bucket(bucket, poks_env.buckets_dir)

    assert (local_path / "tool-a.json").exists()
    assert (local_path / "tool-b.json").exists()
    loaded = PoksManifest.from_json_file(local_path / "tool-b.json")
    assert loaded.version == "2.0.0"


def test_find_manifest_existing(tmp_path: PoksEnv) -> None:
    bucket_path = tmp_path / "bucket"
    bucket_path.mkdir()
    (bucket_path / "cmake.json").write_text("{}")

    result = find_manifest("cmake", bucket_path)

    assert result == bucket_path / "cmake.json"


def test_find_manifest_missing(tmp_path: PoksEnv) -> None:
    bucket_path = tmp_path / "bucket"
    bucket_path.mkdir()

    with pytest.raises(FileNotFoundError, match="nonexistent.json"):
        find_manifest("nonexistent", bucket_path)


def test_sync_all_buckets(poks_env: PoksEnv) -> None:
    poks_env.add_manifest(
        "tool-x",
        PoksManifest(
            version="1.0.0",
            archives=[PoksArchive(os="linux", arch="x86_64", sha256="aaa")],
        ),
    )

    buckets = [
        PoksBucket(name="alpha", url=poks_env.bucket_url),
        PoksBucket(name="beta", url=poks_env.bucket_url),
    ]

    result = sync_all_buckets(buckets, poks_env.buckets_dir)

    assert set(result.keys()) == {"alpha", "beta"}
    for name, path in result.items():
        assert path == poks_env.buckets_dir / name
        assert (path / "tool-x.json").exists()
