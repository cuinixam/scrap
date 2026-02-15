"""CLI tests for poks main.py."""

from pathlib import Path

from typer.testing import CliRunner

from poks.domain import PoksAppVersion, PoksArchive, PoksBucket, PoksConfig, PoksManifest
from poks.main import app
from tests.conftest import PoksEnv

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "poks" in result.stdout


def test_install_from_config(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"bin/tool": "#!/bin/sh\\necho test"}, fmt="tar.gz")
    manifest = PoksManifest(
        description="Test Tool",
        versions=[
            PoksAppVersion(
                version="1.0.0",
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="macos", arch="aarch64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="windows", arch="x86_64", ext=".tar.gz", sha256=sha256),
                ],
            )
        ],
    )
    poks_env.add_manifest("test-tool", manifest)
    config_path = poks_env.create_config([{"name": "test-tool", "version": "1.0.0"}])

    result = runner.invoke(app, ["install", "-c", str(config_path), "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert (poks_env.apps_dir / "test-tool" / "1.0.0" / "bin" / "tool").exists()


def test_install_single_app_searches_all_buckets(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"data.txt": "content"}, fmt="tar.gz")
    manifest = PoksManifest(
        description="My App",
        versions=[
            PoksAppVersion(
                version="2.0.0",
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="macos", arch="aarch64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="windows", arch="x86_64", ext=".tar.gz", sha256=sha256),
                ],
            )
        ],
    )
    poks_env.add_manifest("my-app", manifest)
    poks_env.poks.install(PoksConfig(buckets=[PoksBucket(name="test", url=poks_env.bucket_url)], apps=[]))

    result = runner.invoke(app, ["install", "--app", "my-app", "--version", "2.0.0", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert (poks_env.apps_dir / "my-app" / "2.0.0" / "data.txt").exists()


def test_install_single_app_with_specific_bucket(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"file.txt": "data"}, fmt="tar.gz")
    manifest = PoksManifest(
        description="Specific App",
        versions=[
            PoksAppVersion(
                version="3.0.0",
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="macos", arch="aarch64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="windows", arch="x86_64", ext=".tar.gz", sha256=sha256),
                ],
            )
        ],
    )
    poks_env.add_manifest("specific-app", manifest)
    poks_env.poks.install(PoksConfig(buckets=[PoksBucket(name="test", url=poks_env.bucket_url)], apps=[]))

    result = runner.invoke(app, ["install", "--app", "specific-app", "--version", "3.0.0", "--bucket", "test", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert (poks_env.apps_dir / "specific-app" / "3.0.0" / "file.txt").exists()


def test_install_single_app_with_bucket_url(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"readme.md": "# Test"}, fmt="tar.gz")
    manifest = PoksManifest(
        description="Url App",
        versions=[
            PoksAppVersion(
                version="4.0.0",
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="macos", arch="aarch64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="windows", arch="x86_64", ext=".tar.gz", sha256=sha256),
                ],
            )
        ],
    )
    poks_env.add_manifest("url-app", manifest)

    result = runner.invoke(app, ["install", "--app", "url-app", "--version", "4.0.0", "--bucket", poks_env.bucket_url, "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert (poks_env.apps_dir / "url-app" / "4.0.0" / "readme.md").exists()


def test_install_no_buckets_no_url_fails(tmp_path: Path) -> None:
    empty_root = tmp_path / ".poks"
    empty_root.mkdir()

    result = runner.invoke(app, ["install", "--app", "nonexistent", "--version", "1.0.0", "--root", str(empty_root)])

    assert result.exit_code == 1


def test_install_config_and_app_mutually_exclusive(poks_env: PoksEnv, tmp_path: Path) -> None:
    config_path = tmp_path / "poks.json"
    config_path.write_text("{}")

    result = runner.invoke(app, ["install", "--app", "myapp", "--version", "1.0.0", "-c", str(config_path), "--root", str(poks_env.root_dir)])

    assert result.exit_code == 1


def test_install_requires_mode() -> None:
    result = runner.invoke(app, ["install"])

    assert result.exit_code == 1


def test_install_app_requires_version(poks_env: PoksEnv) -> None:
    result = runner.invoke(app, ["install", "--app", "myapp", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 1


def test_install_manifest_requires_version(poks_env: PoksEnv, tmp_path: Path) -> None:
    manifest_path = tmp_path / "myapp.json"
    manifest_path.write_text("{}")

    result = runner.invoke(app, ["install", "--manifest", str(manifest_path), "--root", str(poks_env.root_dir)])

    assert result.exit_code == 1


def test_install_bucket_not_found(poks_env: PoksEnv) -> None:
    result = runner.invoke(app, ["install", "--app", "myapp", "--version", "1.0.0", "--bucket", "nonexistent", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 1


def test_install_from_manifest_cli(poks_env: PoksEnv) -> None:
    archive_path, sha256 = poks_env.make_archive({"data.txt": "hello"}, fmt="tar.gz")
    manifest = PoksManifest(
        description="Manifest App",
        versions=[
            PoksAppVersion(
                version="1.0.0",
                url=archive_path.as_uri(),
                archives=[
                    PoksArchive(os="linux", arch="x86_64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="macos", arch="aarch64", ext=".tar.gz", sha256=sha256),
                    PoksArchive(os="windows", arch="x86_64", ext=".tar.gz", sha256=sha256),
                ],
            )
        ],
    )
    manifest_path = poks_env.root_dir / "my-tool.json"
    manifest_path.write_text(manifest.to_json_string())

    result = runner.invoke(app, ["install", "--manifest", str(manifest_path), "--version", "1.0.0", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert (poks_env.apps_dir / "my-tool" / "1.0.0" / "data.txt").exists()


def test_uninstall_specific_version(poks_env: PoksEnv) -> None:
    app_dir = poks_env.apps_dir / "test-app"
    (app_dir / "1.0.0").mkdir(parents=True)
    (app_dir / "1.0.0" / "file.txt").write_text("data")

    result = runner.invoke(app, ["uninstall", "test-app@1.0.0", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert not (app_dir / "1.0.0").exists()


def test_uninstall_all_versions(poks_env: PoksEnv) -> None:
    app_dir = poks_env.apps_dir / "test-app"
    (app_dir / "1.0.0").mkdir(parents=True)
    (app_dir / "2.0.0").mkdir(parents=True)

    result = runner.invoke(app, ["uninstall", "test-app", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert not app_dir.exists()


def test_uninstall_all_apps(poks_env: PoksEnv) -> None:
    (poks_env.apps_dir / "app1" / "1.0.0").mkdir(parents=True)
    (poks_env.apps_dir / "app2" / "1.0.0").mkdir(parents=True)

    result = runner.invoke(app, ["uninstall", "--all", "--root", str(poks_env.root_dir)])

    assert result.exit_code == 0
    assert not any(poks_env.apps_dir.iterdir())


def test_uninstall_requires_app_or_all() -> None:
    result = runner.invoke(app, ["uninstall"])

    assert result.exit_code == 1
