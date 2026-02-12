"""Integration test demonstrating the full fixture flow."""

from __future__ import annotations

import pytest
from git import Repo

from poks.domain import PoksAppVersion, PoksArchive, PoksConfig, PoksManifest
from poks.downloader import get_cached_or_download
from poks.extractor import extract_archive
from tests.conftest import PoksEnv


def test_full_flow_create_bucket_add_manifest_extract(poks_env: PoksEnv) -> None:
    archive_files = {"bin/tool": "#!/bin/sh\necho hello", "README.md": "# My Tool"}
    archive_path, sha256 = poks_env.make_archive(archive_files, fmt="tar.gz")

    manifest = PoksManifest(
        description="My Tool",
        versions=[
            PoksAppVersion(
                version="1.0.0",
                url=archive_path.as_uri(),
                archives=[PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256)],
            )
        ],
    )
    poks_env.add_manifest("my-tool", manifest)

    # Clone the bucket and verify the manifest is there
    clone_dir = poks_env.root_dir / "bucket-verify"
    Repo.clone_from(poks_env.bucket_url, str(clone_dir))
    manifest_file = clone_dir / "my-tool.json"
    assert manifest_file.exists()
    loaded = PoksManifest.from_json_file(manifest_file)
    assert loaded.versions[0].version == "1.0.0"
    assert loaded.versions[0].archives[0].sha256 == sha256

    # Extract the archive and verify files on disk
    dest = poks_env.apps_dir / "my-tool" / "1.0.0"
    extract_archive(archive_path, dest)
    assert (dest / "bin" / "tool").read_text() == "#!/bin/sh\necho hello"
    assert (dest / "README.md").read_text() == "# My Tool"


def test_zip_archive_with_config(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"data.txt": "zip content"}, fmt="zip")

    manifest = PoksManifest(
        description="Zip Tool",
        versions=[
            PoksAppVersion(
                version="2.0.0",
                url=archive_path.as_uri(),
                archives=[PoksArchive(os="macos", arch="aarch64", ext=".zip", sha256=sha256)],
            )
        ],
    )
    poks_env.add_manifest("zip-tool", manifest)

    config_path = poks_env.create_config([{"name": "zip-tool", "version": "2.0.0"}])
    config = PoksConfig.from_json_file(config_path)
    assert len(config.apps) == 1
    assert config.apps[0].name == "zip-tool"
    assert config.buckets[0].url == poks_env.bucket_url

    dest = poks_env.apps_dir / "zip-tool" / "2.0.0"
    extract_archive(archive_path, dest)
    assert (dest / "data.txt").read_text() == "zip content"


def test_download_verify_cache_flow(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"hello.txt": "world"}, fmt="tar.gz")
    url = archive_path.as_uri()

    # First call: downloads and caches
    cached = get_cached_or_download(url, sha256, poks_env.cache_dir)
    assert cached.exists()
    assert cached.parent == poks_env.cache_dir

    original_mtime = cached.stat().st_mtime

    # Second call: reuses the cached file (no re-download)
    cached_again = get_cached_or_download(url, sha256, poks_env.cache_dir)
    assert cached_again == cached
    assert cached_again.stat().st_mtime == original_mtime

    # Corrupt the cache, next call should re-download
    cached.write_bytes(b"corrupt")
    redownloaded = get_cached_or_download(url, sha256, poks_env.cache_dir)
    assert redownloaded == cached
    assert redownloaded.read_bytes() == archive_path.read_bytes()


def test_uninstall_specific_version(poks_env: PoksEnv) -> None:
    app_dir = poks_env.apps_dir / "my-tool"
    v1_dir = app_dir / "1.0.0"
    v2_dir = app_dir / "2.0.0"
    v1_dir.mkdir(parents=True)
    v2_dir.mkdir(parents=True)
    (v1_dir / "file.txt").write_text("version 1")
    (v2_dir / "file.txt").write_text("version 2")

    poks_env.poks.uninstall("my-tool", "1.0.0")

    assert not v1_dir.exists()
    assert v2_dir.exists()
    assert app_dir.exists()


def test_uninstall_specific_version_cleans_up_parent(poks_env: PoksEnv) -> None:
    app_dir = poks_env.apps_dir / "my-tool"
    version_dir = app_dir / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "file.txt").write_text("data")

    poks_env.poks.uninstall("my-tool", "1.0.0")

    assert not version_dir.exists()
    assert not app_dir.exists()


def test_uninstall_all_versions(poks_env: PoksEnv) -> None:
    my_tool_dir = poks_env.apps_dir / "my-tool"
    (my_tool_dir / "1.0.0").mkdir(parents=True)
    (my_tool_dir / "2.0.0").mkdir(parents=True)
    (my_tool_dir / "1.0.0" / "file.txt").write_text("v1")
    (my_tool_dir / "2.0.0" / "file.txt").write_text("v2")

    other_tool_dir = poks_env.apps_dir / "other-tool"
    (other_tool_dir / "1.0.0").mkdir(parents=True)
    (other_tool_dir / "1.0.0" / "file.txt").write_text("other")

    poks_env.poks.uninstall("my-tool")

    assert not my_tool_dir.exists()
    assert other_tool_dir.exists()


def test_uninstall_all_apps(poks_env: PoksEnv) -> None:
    tool1_dir = poks_env.apps_dir / "tool1"
    tool2_dir = poks_env.apps_dir / "tool2"
    (tool1_dir / "1.0.0").mkdir(parents=True)
    (tool2_dir / "1.0.0").mkdir(parents=True)
    (tool2_dir / "2.0.0").mkdir(parents=True)
    (tool1_dir / "1.0.0" / "file.txt").write_text("data1")
    (tool2_dir / "1.0.0" / "file.txt").write_text("data2")
    (tool2_dir / "2.0.0" / "file.txt").write_text("data3")

    poks_env.poks.uninstall(all_apps=True)

    assert poks_env.apps_dir.exists()
    assert not any(poks_env.apps_dir.iterdir())


def test_uninstall_nonexistent_app_raises_error(poks_env: PoksEnv) -> None:
    with pytest.raises(ValueError, match=r"App nonexistent is not installed"):
        poks_env.poks.uninstall("nonexistent")


def test_uninstall_nonexistent_version_raises_error(poks_env: PoksEnv) -> None:
    app_dir = poks_env.apps_dir / "my-tool"
    version_dir = app_dir / "1.0.0"
    version_dir.mkdir(parents=True)
    (version_dir / "file.txt").write_text("data")

    with pytest.raises(ValueError, match=r"App my-tool@2.0.0 is not installed"):
        poks_env.poks.uninstall("my-tool", "2.0.0")
