"""Poks package manager core class."""

from __future__ import annotations

from pathlib import Path

from py_app_dev.core.logging import logger

from poks.bucket import find_manifest, sync_all_buckets
from poks.domain import PoksConfig, PoksManifest
from poks.downloader import get_cached_or_download
from poks.environment import collect_env_updates, merge_env_updates
from poks.extractor import extract_archive
from poks.platform import get_current_platform
from poks.resolver import resolve_archive, resolve_download_url


class Poks:
    """Cross-platform package manager for developer tools."""

    def __init__(self, root_dir: Path) -> None:
        """
        Initialize Poks with a root directory.

        Args:
            root_dir: Root directory for Poks (apps, buckets, cache).

        """
        self.root_dir = root_dir
        self.apps_dir = root_dir / "apps"
        self.buckets_dir = root_dir / "buckets"
        self.cache_dir = root_dir / "cache"

    def install(self, config_or_path: Path | PoksConfig) -> dict[str, str]:
        """
        Install apps from a configuration file or config object.

        Args:
            config_or_path: Path to poks.json or a PoksConfig object.

        Returns:
            Dictionary of environment variable updates.

        """
        config = PoksConfig.from_json_file(config_or_path) if isinstance(config_or_path, Path) else config_or_path
        current_os, current_arch = get_current_platform()
        bucket_paths = sync_all_buckets(config.buckets, self.buckets_dir)
        env_updates: list[dict[str, str]] = []

        for app in config.apps:
            if not app.is_supported(current_os, current_arch):
                logger.info(f"Skipping {app.name}: not supported on {current_os}/{current_arch}")
                continue
            install_dir = self.apps_dir / app.name / app.version
            if install_dir.exists():
                logger.info(f"Skipping {app.name}@{app.version}: already installed")
                manifest = PoksManifest.from_json_file(find_manifest(app.name, bucket_paths[app.bucket]))
                env_updates.append(collect_env_updates(manifest, install_dir))
                continue
            manifest_path = find_manifest(app.name, bucket_paths[app.bucket])
            manifest = PoksManifest.from_json_file(manifest_path)
            archive = resolve_archive(manifest, current_os, current_arch)
            url = resolve_download_url(manifest, archive)
            archive_path = get_cached_or_download(url, archive.sha256, self.cache_dir)
            extract_archive(archive_path, install_dir, manifest.extract_dir)
            logger.info(f"Installed {app.name}@{app.version}")
            env_updates.append(collect_env_updates(manifest, install_dir))

        return merge_env_updates(env_updates)

    def uninstall(self, app_name: str | None = None, version: str | None = None, all_apps: bool = False) -> None:
        """
        Uninstall apps.

        Args:
            app_name: Name of the app to uninstall. If None and all_apps is True, uninstalls everything.
            version: Specific version to uninstall. If None, uninstalls all versions of the app.
            all_apps: If True, uninstalls all apps.

        """
        if all_apps:
            logger.info("Uninstalling all apps")
        elif app_name and version:
            logger.info(f"Uninstalling {app_name}@{version}")
        elif app_name:
            logger.info(f"Uninstalling all versions of {app_name}")
        else:
            logger.warning("Nothing to uninstall. Specify an app name or use --all.")
