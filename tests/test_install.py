"""Integration tests for the full Poks.install() orchestration flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from poks.domain import PoksApp, PoksAppVersion, PoksArchive, PoksBucket, PoksConfig, PoksManifest
from poks.poks import Poks
from tests.helpers import assert_install_result, assert_installed_app, create_archive


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
    archive_bin: list[str] | None = None,
    archive_env: dict[str, str] | None = None,
    extract_dir: str | None = None,
    archive_extract_dir: str | None = None,
) -> PoksManifest:
    """Create a test archive and return a matching manifest."""
    archive_files = files or {"bin/tool": "#!/bin/sh\necho hello"}
    archive_path, sha256 = create_archive(archives_dir, archive_files, fmt=fmt)
    ext = f".{fmt}"
    return PoksManifest(
        description=f"Test manifest for {archive_name}",
        versions=[
            PoksAppVersion(
                version=version,
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(
                        os=target_os,
                        arch=target_arch,
                        ext=ext,
                        sha256=sha256,
                        extract_dir=archive_extract_dir,
                        bin_dirs=archive_bin,
                        env=archive_env,
                    )
                ],
                extract_dir=extract_dir,
                bin_dirs=bin_dirs,
                env=env_vars,
            )
        ],
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
        result = poks.install(config)

    install_dir = root_dir / "apps" / "my-tool" / "1.0.0"
    assert install_dir.exists()
    assert (install_dir / "bin" / "tool").read_text() == "#!/bin/sh\necho hello"
    app = assert_installed_app(result, "my-tool")
    assert app.install_dir == install_dir
    assert install_dir / "bin" in app.bin_dirs
    assert app.env["TOOL_HOME"] == str(install_dir)


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
        result = poks.install(config)

    assert not (root_dir / "apps" / "win-only" / "1.0.0").exists()
    assert_install_result(result, 0)


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
        result = poks.install(config)

    assert (install_dir / "marker.txt").read_text() == "pre-existing"
    app = assert_installed_app(result, "my-tool")
    assert app.bin_dirs == [install_dir / "bin"]


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
        result = poks.install(config)

    assert_install_result(result, 2)
    app_a = assert_installed_app(result, "tool-a")
    app_b = assert_installed_app(result, "tool-b")
    assert app_a.bin_dirs == [root_dir / "apps" / "tool-a" / "1.0.0" / "bin"]
    assert app_b.bin_dirs == [root_dir / "apps" / "tool-b" / "2.0.0" / "tools"]


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


def test_install_app_explicit_bucket(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    bucket_dir = root_dir / "buckets" / "my-bucket"
    _setup_bucket(bucket_dir, {"app-a": manifest})

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"my-bucket": bucket_dir},
        )
        installed = poks.install_app("app-a", "1.0.0", bucket="my-bucket")

    assert installed.name == "app-a"
    assert installed.install_dir == root_dir / "apps" / "app-a" / "1.0.0"


def test_install_app_auto_bucket(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    bucket_dir = root_dir / "buckets" / "auto-bucket"
    _setup_bucket(bucket_dir, {"app-b": manifest})

    monkeypatch.setattr(
        "poks.poks.search_all_buckets",
        lambda _name, _dir: (None, "auto-bucket"),
    )

    with PLATFORM_PATCH:
        monkeypatch.setattr(
            "poks.poks.sync_all_buckets",
            lambda _buckets, _dir: {"auto-bucket": bucket_dir},
        )
        installed = poks.install_app("app-b", "1.0.0")

    assert installed.name == "app-b"
    assert installed.install_dir == root_dir / "apps" / "app-b" / "1.0.0"


def test_parallel_install_with_progress_callback(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    calls: list[tuple[str, int, int | None]] = []
    poks.progress_callback = lambda name, downloaded, total: calls.append((name, downloaded, total))

    dir_a = archives_dir / "a"
    dir_a.mkdir()
    manifest_a = _make_manifest(dir_a, files={"bin/a": "aaa"}, archive_name="archive_a")
    dir_b = archives_dir / "b"
    dir_b.mkdir()
    manifest_b = _make_manifest(dir_b, version="2.0.0", files={"bin/b": "bbb"}, archive_name="archive_b")
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
        result = poks.install(config)

    assert len(result.apps) == 2
    app_names = {app.name for app in result.apps}
    assert app_names == {"tool-a", "tool-b"}
    reported_names = {name for name, _, _ in calls}
    assert reported_names == {"tool-a", "tool-b"}


def test_yanked_version_raises(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    # Mark the version as yanked
    manifest.versions[0].yanked = "Security vulnerability CVE-2024-1234"
    bucket_dir = root_dir / "buckets" / "test"
    _setup_bucket(bucket_dir, {"yanked-tool": manifest})

    config = PoksConfig(
        buckets=[PoksBucket(name="test", url="unused")],
        apps=[PoksApp(name="yanked-tool", version="1.0.0", bucket="test")],
    )

    with (
        PLATFORM_PATCH,
        monkeypatch.context() as m,
        pytest.raises(ValueError, match="yanked"),
    ):
        m.setattr("poks.poks.sync_all_buckets", lambda _buckets, _dir: {"test": bucket_dir})
        poks.install(config)


def test_install_from_manifest(
    install_env: tuple[Poks, Path, Path],
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir, bin_dirs=["bin"], env_vars={"TOOL_HOME": "${dir}"})
    manifest_path = archives_dir / "my-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with PLATFORM_PATCH:
        installed = poks.install_from_manifest(manifest_path, "1.0.0")

    assert installed.name == "my-tool"
    assert installed.version == "1.0.0"
    assert installed.install_dir == root_dir / "apps" / "my-tool" / "1.0.0"
    assert (installed.install_dir / "bin" / "tool").exists()
    assert installed.env["TOOL_HOME"] == str(installed.install_dir)


def test_install_from_manifest_version_not_found(
    install_env: tuple[Poks, Path, Path],
) -> None:
    poks, _root_dir, archives_dir = install_env
    manifest = _make_manifest(archives_dir)
    manifest_path = archives_dir / "my-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with pytest.raises(ValueError, match=r"Version 9\.9\.9 not found"):
        poks.install_from_manifest(manifest_path, "9.9.9")


def test_extract_dir_relocates_contents(
    install_env: tuple[Poks, Path, Path],
) -> None:
    poks, _root_dir, archives_dir = install_env
    archive_files = {"bin/tool": "#!/bin/sh\necho hello"}
    archive_path, sha256 = create_archive(archives_dir, archive_files, fmt="tar.gz", top_dir="app-1.0.0")
    ext = ".tar.gz"
    manifest = PoksManifest(
        description="Test extract_dir",
        versions=[
            PoksAppVersion(
                version="1.0.0",
                url=archive_path.as_uri(),
                archives=[PoksArchive(os="linux", arch="x86_64", ext=ext, sha256=sha256)],
                extract_dir="app-1.0.0",
                bin_dirs=["bin"],
            )
        ],
    )
    manifest_path = archives_dir / "my-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with PLATFORM_PATCH:
        installed = poks.install_from_manifest(manifest_path, "1.0.0")

    assert (installed.install_dir / "bin" / "tool").exists()
    assert not (installed.install_dir / "app-1.0.0").exists()


def test_per_archive_bin_overrides_version(
    install_env: tuple[Poks, Path, Path],
) -> None:
    poks, root_dir, archives_dir = install_env
    manifest = _make_manifest(
        archives_dir,
        bin_dirs=["default-bin"],
        env_vars={"TOOL_HOME": "${dir}"},
        archive_bin=["custom-bin"],
        archive_env={"EXTRA": "val"},
    )
    manifest_path = archives_dir / "custom-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with PLATFORM_PATCH:
        installed = poks.install_from_manifest(manifest_path, "1.0.0")

    assert installed.bin_dirs == [root_dir / "apps" / "custom-tool" / "1.0.0" / "custom-bin"]
    # archive env fully replaces version env (consistent with bin_dirs override)
    assert installed.env == {"EXTRA": "val"}
    assert "TOOL_HOME" not in installed.env


def test_default_progress_is_set(tmp_path: Path) -> None:
    poks = Poks(root_dir=tmp_path)
    assert poks.progress_callback is not None
    assert poks.extract_callback is not None


def test_explicit_none_disables_progress(tmp_path: Path) -> None:
    poks = Poks(root_dir=tmp_path, progress_callback=None, extract_callback=None)
    assert poks.progress_callback is None
    assert poks.extract_callback is None


def test_default_progress_invoked_during_install(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, _, archives_dir = install_env
    calls: list[tuple[str, int, int | None]] = []
    poks.progress_callback = lambda name, downloaded, total: calls.append((name, downloaded, total))
    poks.extract_callback = None

    manifest = _make_manifest(archives_dir)
    manifest_path = archives_dir / "spy-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with PLATFORM_PATCH:
        poks.install_from_manifest(manifest_path, "1.0.0")

    assert len(calls) > 0
    assert all(name == "spy-tool" for name, _, _ in calls)


def test_extract_callback_invoked_during_install(
    install_env: tuple[Poks, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    poks, _, archives_dir = install_env
    extract_calls: list[tuple[str, int, int | None]] = []
    poks.progress_callback = None
    poks.extract_callback = lambda name, extracted, total: extract_calls.append((name, extracted, total))

    manifest = _make_manifest(archives_dir)
    manifest_path = archives_dir / "extract-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    with PLATFORM_PATCH:
        poks.install_from_manifest(manifest_path, "1.0.0")

    assert len(extract_calls) > 0
    assert all(name == "extract-tool" for name, _, _ in extract_calls)
    assert extract_calls[-1][1] == extract_calls[-1][2]
