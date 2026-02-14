"""
Integration test for .conda archive support using a real conda-forge package.

This test performs a REAL DOWNLOAD of the ripgrep conda package (~20MB).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from poks.domain import PoksConfig, PoksManifest
from tests.conftest import PoksEnv
from tests.helpers import assert_installed_app


@pytest.mark.skipif(
    not (sys.platform == "linux" or sys.platform == "darwin" or sys.platform == "win32"),
    reason="Only standard platforms supported for this real-download test",
)
def test_conda_ripgrep_install(poks_env: PoksEnv) -> None:
    """Download ripgrep from conda-forge (.conda format), install, and verify ripgrep --version."""
    manifest_path = Path(__file__).parent / "data" / "ripgrep.json"
    manifest = PoksManifest.from_json_file(manifest_path)
    version = manifest.versions[0].version
    app_name = "ripgrep"

    poks_env.add_manifest(app_name, manifest)
    config_path = poks_env.create_config([{"name": app_name, "version": version}])
    install_config = PoksConfig.from_json_file(config_path)

    ripgrep = assert_installed_app(poks_env.poks.install(install_config), "ripgrep")

    assert ripgrep.install_dir.exists(), f"Install directory does not exist: {ripgrep.install_dir}"

    env = {**os.environ}
    for bin_dir in ripgrep.bin_dirs:
        env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")

    result = subprocess.run(
        ["rg", "--version"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
        env=env,
        shell=True if sys.platform == "win32" else False,
    )
    assert result.returncode == 0, f"ripgrep --version failed: {result.stderr}"
    assert version in result.stdout, f"Expected version {version} in output: {result.stdout}"

    # Verify listing works
    found = assert_installed_app(poks_env.poks.list_installed(), app_name)
    assert found.version == version
