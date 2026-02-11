"""Unit tests for the list command and API."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from poks.domain import PoksManifest
from poks.main import app
from tests.conftest import PoksEnv

runner = CliRunner()


def test_list_api_returns_installed_apps(poks_env: PoksEnv, tmp_path: Path) -> None:
    """Test that Poks.list() returns installed apps with details."""
    # 1. Setup: Install a fake app
    # We manually create the structure to simulate installation
    app_name = "test-app"
    version = "1.0.0"
    install_dir = poks_env.apps_dir / app_name / version
    install_dir.mkdir(parents=True)

    # Write a manifest to the install dir
    manifest = PoksManifest(version=version, archives=[], bin=["bin"], env={"MY_VAR": "${dir}/data"})
    (install_dir / ".manifest.json").write_text(manifest.to_json_string())

    # Create bin dir
    (install_dir / "bin").mkdir()

    # 2. Call list()
    apps = poks_env.poks.list()

    # 3. Verify
    assert len(apps) == 1
    poks_app = apps[0]
    assert poks_app.name == app_name
    assert poks_app.version == version
    # unknown because we didn't install via config that tracks bucket
    assert poks_app.bucket == "unknown"

    # Check details
    assert poks_app.dirs == [str(install_dir / "bin")]
    assert poks_app.env is not None
    assert Path(poks_app.env["MY_VAR"]) == install_dir / "data"


def test_cli_list_command(poks_env: PoksEnv) -> None:
    """Test that 'poks list' prints the table of apps."""
    # 1. Setup: Install a fake app
    app_name = "cli-app"
    version = "2.0.0"
    install_dir = poks_env.apps_dir / app_name / version
    install_dir.mkdir(parents=True)

    # Minimal manifest
    manifest = PoksManifest(version=version, archives=[])
    (install_dir / ".manifest.json").write_text(manifest.to_json_string())

    # 2. Run CLI command
    # We need to pass the root dir to use the test environment
    result = runner.invoke(app, ["list", "--root", str(poks_env.root_dir)])

    # 3. Verify
    assert result.exit_code == 0
    assert "Name" in result.stdout
    assert "Version" in result.stdout
    assert "Bucket" in result.stdout
    assert app_name in result.stdout
    assert version in result.stdout


def test_list_empty(poks_env: PoksEnv) -> None:
    """Test list command with no apps installed."""
    result = runner.invoke(app, ["list", "--root", str(poks_env.root_dir)])
    assert result.exit_code == 0
    assert "No apps installed." in result.stdout
