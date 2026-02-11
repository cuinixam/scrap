"""Integration tests for the full Poks.install() orchestration flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from poks.domain import PoksApp, PoksArchive, PoksBucket, PoksConfig, PoksManifest
from poks.poks import Poks
from tests.helpers import create_archive


def _setup_bucket(
    bucket_dir: Path,
    manifests: dict[str, PoksManifest],
) -> None:
    """Write manifest JSON files directly into a bucket directory (no git)."""
    bucket_dir.mkdir(parents=True, exist_ok=True)
    for name, manifest in manifests.items():
        (bucket_dir / f"{name}.json").write_text(manifest.to_json_string())


@pytest.fixture
def install_env(tmp_path: Path) -> tuple[Poks, Path, Path]:
    """Provide a Poks instance and helper directories for install tests."""
    root_dir = tmp_path / ".poks"
    for sub in ("apps", "buckets", "cache"):
        (root_dir / sub).mkdir(parents=True)
    archives_dir = tmp_path / "archives"
    archives_dir.mkdir()
    return Poks(root_dir=root_dir), root_dir, archives_dir


def _make_manifest(
    archives_dir: Path,
    *,
    version: str = "1.0.0",
    target_os: str = "linux",
    target_arch: str = "x86_64",
    fmt: str = "tar.gz",
    files: dict[str, str] | None = None,
    bin_dirs: list[str] | None = None,
    env_vars: dict[str, str] | None = None,
    archive_name: str = "archive",
) -> PoksManifest:
    """Create a test archive and return a matching manifest."""
    archive_files = files or {"bin/tool": "#!/bin/sh\necho hello"}
    archive_path, sha256 = create_archive(archives_dir, archive_files, fmt=fmt, top_dir=archive_name)
    ext = f".{fmt}"
    return PoksManifest(
        version=version,
        url=archive_path.as_uri(),
        archives=[PoksArchive(os=target_os, arch=target_arch, ext=ext, sha256=sha256)],
        extract_dir=archive_name,
        bin=bin_dirs,
        env=env_vars,
    )


PLATFORM_PATCH = patch("poks.poks.get_current_platform", return_value=("linux", "x86_64"))


def test_full_install_end_to_end(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir, bin_dirs=["bin"], env_vars={"TOOL_HOME": "${dir}"})
    bucket_dir = root_dir / "buckets" / "test"
    _setup_bucket(bucket_dir, {"my-tool": manifest})

    config = PoksConfig(
        buckets=[PoksBucket(name="test", url="unused")],
        apps=[PoksApp(name="my-tool", version="1.0.0", bucket="test")],
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"test": bucket_dir},
        )
        env = poks.install(config)

    install_dir = root_dir / "apps" / "my-tool" / "1.0.0"
    assert install_dir.exists()
    assert (install_dir / "bin" / "tool").read_text() == "#!/bin/sh\necho hello"
    assert "PATH" in env
    assert str(install_dir / "bin") in env["PATH"]
    assert env["TOOL_HOME"] == str(install_dir)


def test_install_accepts_path(
    install_env: tuple[Poks, Path, Path],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    bucket_dir = root_dir / "buckets" / "main"
    _setup_bucket(bucket_dir, {"tool-a": manifest})

    config_path = tmp_path / "poks.json"
    config_path.write_text(
        json.dumps(
            {
                "buckets": [{"name": "main", "url": "unused"}],
                "apps": [{"name": "tool-a", "version": "1.0.0", "bucket": "main"}],
            }
        )
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"main": bucket_dir},
        )
        poks.install(config_path)

    assert (root_dir / "apps" / "tool-a" / "1.0.0").exists()


def test_platform_filtered_apps_skipped(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    bucket_dir = root_dir / "buckets" / "test"
    _setup_bucket(bucket_dir, {"win-only": manifest})

    config = PoksConfig(
        buckets=[PoksBucket(name="test", url="unused")],
        apps=[PoksApp(name="win-only", version="1.0.0", bucket="test", os=["windows"])],
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"test": bucket_dir},
        )
        env = poks.install(config)

    assert not (root_dir / "apps" / "win-only" / "1.0.0").exists()
    assert env == {}


def test_idempotency_skips_installed(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir, bin_dirs=["bin"])
    bucket_dir = root_dir / "buckets" / "test"
    _setup_bucket(bucket_dir, {"my-tool": manifest})

    install_dir = root_dir / "apps" / "my-tool" / "1.0.0"
    install_dir.mkdir(parents=True)
    (install_dir / "marker.txt").write_text("pre-existing")

    config = PoksConfig(
        buckets=[PoksBucket(name="test", url="unused")],
        apps=[PoksApp(name="my-tool", version="1.0.0", bucket="test")],
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"test": bucket_dir},
        )
        env = poks.install(config)

    assert (install_dir / "marker.txt").read_text() == "pre-existing"
    assert "PATH" in env


def test_multiple_apps_env_merged(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env

    dir_a = archives_dir / "a"
    dir_a.mkdir()
    manifest_a = _make_manifest(
        dir_a,
        bin_dirs=["bin"],
        files={"bin/a": "aaa"},
        archive_name="archive_a",
    )
    dir_b = archives_dir / "b"
    dir_b.mkdir()
    manifest_b = _make_manifest(
        dir_b,
        version="2.0.0",
        bin_dirs=["tools"],
        files={"tools/b": "bbb"},
        archive_name="archive_b",
    )
    bucket_dir = root_dir / "buckets" / "test"
    _setup_bucket(bucket_dir, {"tool-a": manifest_a, "tool-b": manifest_b})

    config = PoksConfig(
        buckets=[PoksBucket(name="test", url="unused")],
        apps=[
            PoksApp(name="tool-a", version="1.0.0", bucket="test"),
            PoksApp(name="tool-b", version="2.0.0", bucket="test"),
        ],
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"test": bucket_dir},
        )
        env = poks.install(config)

    assert "PATH" in env
    path_a = str(root_dir / "apps" / "tool-a" / "1.0.0" / "bin")
    path_b = str(root_dir / "apps" / "tool-b" / "2.0.0" / "tools")
    assert path_a in env["PATH"]
    assert path_b in env["PATH"]


def test_missing_config_file_raises(install_env: tuple[Poks, Path, Path]) -> None:
    poks, _root_dir, _archives_dir = install_env
    with pytest.raises(FileNotFoundError):
        poks.install(Path("/nonexistent/poks.json"))


def test_invalid_config_json_raises(
    install_env: tuple[Poks, Path, Path],
    tmp_path: Path,
) -> None:
    poks, _root_dir, _archives_dir = install_env
    bad_config = tmp_path / "bad.json"
    bad_config.write_text("not valid json")
    with pytest.raises(json.JSONDecodeError):
        poks.install(bad_config)
