"""
Integration test for Zephyr riscv64 toolchain.

This test performs REAL DOWNLOADS of the toolchain artifacts (~100-200MB).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from poks.domain import PoksConfig, PoksManifest
from tests.conftest import PoksEnv


@pytest.mark.skipif(
    not (sys.platform == "linux" or sys.platform == "darwin" or sys.platform == "win32"),
    reason="Only standard platforms supported for this real-download test",
)
def test_zephyr_lifecycle(poks_env: PoksEnv, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Test full lifecycle of Zephyr toolchain: Install -> Idempotency -> List -> Uninstall -> Reinstall.

    This test performs REAL DOWNLOADS of the toolchain artifacts (~100-200MB).
    """
    manifest_path = Path(__file__).parent / "data" / "riscv64-zephyr-elf.json"
    manifest = PoksManifest.from_json_file(manifest_path)
    version = manifest.versions[0].version

    app_name = "riscv64-zephyr-elf"

    # 1. Setup: Create repository with manifest
    poks_env.add_manifest(app_name, manifest)

    # Create poks file for installation
    config_path = poks_env.create_config([{"name": app_name, "version": version}])
    install_config = PoksConfig.from_json_file(config_path)

    # 2. Install
    print(f"Starting download of {app_name}...")
    poks_env.poks.install(install_config)
    print("Download and installation complete.")

    # EP-002: Verify registry creation
    registry_path = poks_env.buckets_dir / "buckets.json"
    assert registry_path.exists(), "buckets.json should be created after install"
    registry_content = registry_path.read_text()
    assert '"name": "test"' in registry_content or f'"url": "{poks_env.bucket_url}"' in registry_content

    install_dir = poks_env.apps_dir / app_name / version
    assert install_dir.exists(), f"Install directory {install_dir} does not exist"

    # Check expected directories/files
    found_files = list(install_dir.rglob("*"))
    assert len(found_files) > 10, "Toolchain installation seems too empty"
    binaries = [file_path.name for file_path in found_files if "gcc" in file_path.name]
    assert binaries, "Could not find any gcc binary in the installed toolchain"

    # 3. Idempotency: Run install again
    # It shall not create the app again but skip the installation because it already exists
    # We capture verification by checking logs or verifying file timestamps haven't changed substantially
    # or relying on capsys if logger prints to stdout/stderr
    time.sleep(1)  # Ensure timestamp diff if it were to reinstall
    mtime_before = install_dir.stat().st_mtime

    poks_env.poks.install(install_config)

    mtime_after = install_dir.stat().st_mtime
    assert mtime_before == mtime_after, "Installation should have been skipped (dir modified)"

    # 4. List command
    # Check that it finds the app with the proper information
    apps = poks_env.poks.list_installed()
    assert len(apps) == 1
    found_app = apps[0]
    assert found_app.name == app_name
    assert found_app.version == version
    # Since we installed from a config defining "test" bucket (via create_config),
    # but poks.list_installed() might not resolve the bucket name if not persisted,
    # let's check what we expect.
    # poks.list_installed() implementation tries to resolve bucket but defaults to "unknown" if not tracked perfectly
    # or "test" if we updated it.
    # In test_list.py it was "unknown". Let's see if our install persists enough info.
    # The current implementation of list() initializes bucket="unknown".
    assert found_app.name == app_name

    # 5. Uninstall
    poks_env.poks.uninstall(app_name=app_name)

    # Check there are no apps when listed
    assert not install_dir.exists(), "App directory should be removed after uninstall"
    apps_after_uninstall = poks_env.poks.list_installed()
    assert len(apps_after_uninstall) == 0, "List should be empty after uninstall"

    # 6. Reinstall (using cache)
    # Install it again and it shall use the cache
    # First, capture the cache state
    cache_files = list(poks_env.cache_dir.iterdir())
    assert len(cache_files) == 1, f"Expected 1 cache file, found {len(cache_files)}"
    cache_file = cache_files[0]
    cache_mtime_before = cache_file.stat().st_mtime

    start_time = time.time()
    poks_env.poks.install(install_config)
    duration = time.time() - start_time

    # Verification
    assert install_dir.exists(), "App should be reinstalled"

    # Verify cache was preserved (not re-downloaded)
    assert cache_file.exists(), "Cache file should still exist"
    cache_mtime_after = cache_file.stat().st_mtime
    assert cache_mtime_before == cache_mtime_after, "Cache file was modified (re-downloaded?)"

    # Optional: Log duration for info, but don't fail on it
    print(f"Reinstall duration: {duration:.2f}s")

    # List it and shall be there
    apps_reinstalled = poks_env.poks.list_installed()
    assert len(apps_reinstalled) == 1
    assert apps_reinstalled[0].name == app_name
