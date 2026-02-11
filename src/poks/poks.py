"""Poks package manager core class."""

from __future__ import annotations

from pathlib import Path

from py_app_dev.core.logging import logger

from poks.bucket import find_manifest, sync_all_buckets
from poks.domain import PoksApp, PoksConfig, PoksManifest
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

            # Persist manifest for future reference (e.g. list command)
            (install_dir / ".manifest.json").write_text(manifest.to_json_string())

            logger.info(f"Installed {app.name}@{app.version}")
            env_updates.append(collect_env_updates(manifest, install_dir))

        return merge_env_updates(env_updates)

    def list(self) -> list[PoksApp]:
        """
        List all installed applications.

        Returns:
            List of PoksApp objects with populated details (version, dirs, env).
            Note: 'bucket' field might be generic if not tracked.

        """
        installed_apps = []
        if not self.apps_dir.exists():
            return []

        for app_dir in self.apps_dir.iterdir():
            if not app_dir.is_dir():
                continue
            app_name = app_dir.name
            for version_dir in app_dir.iterdir():
                if not version_dir.is_dir():
                    continue
                version = version_dir.name

                # Attempt to load manifest from installation dir to get details
                manifest_path = version_dir / ".manifest.json"
                dirs: list[str] = []
                env: dict[str, str] = {}
                bucket = "unknown"

                if manifest_path.exists():
                    try:
                        manifest = PoksManifest.from_json_file(manifest_path)
                        # Re-calculate env updates to populate dirs/env
                        # Note: This duplicates logic from install().
                        # Ideally, we should store the *computed* config, but manifest is a good proxy.
                        # 'dirs' corresponds to 'bin' in manifest, but relative to install dir.
                        if manifest.bin:
                            dirs = [str(version_dir / b) for b in manifest.bin]

                        # env needs to be resolved with ${dir} -> version_dir
                        if manifest.env:
                            # Simple variable expansion
                            for k, v in manifest.env.items():
                                env[k] = v.replace("${dir}", str(version_dir))

                    except Exception as e:
                        logger.warning(f"Failed to load manifest for {app_name}@{version}: {e}")

                installed_apps.append(PoksApp(name=app_name, version=version, bucket=bucket, dirs=dirs if dirs else None, env=env if env else None))

        return installed_apps

    def uninstall(self, app_name: str | None = None, version: str | None = None, all_apps: bool = False) -> None:
        """
        Uninstall apps.

        Args:
            app_name: Name of the app to uninstall. If None and all_apps is True, uninstalls everything.
            version: Specific version to uninstall. If None, uninstalls all versions of the app.
            all_apps: If True, uninstalls all apps.

        Raises:
            ValueError: If the specified app or version does not exist.

        """
        import shutil

        if all_apps:
            logger.info("Uninstalling all apps")
            for item in self.apps_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                    logger.info(f"Removed {item.name}")
            return

        if not app_name:
            logger.warning("Nothing to uninstall. Specify an app name or use --all.")
            return

        app_dir = self.apps_dir / app_name

        if version:
            version_dir = app_dir / version
            if not version_dir.exists():
                raise ValueError(f"App {app_name}@{version} is not installed")
            logger.info(f"Uninstalling {app_name}@{version}")
            shutil.rmtree(version_dir)
            logger.info(f"Removed {app_name}@{version}")
            if app_dir.exists() and not any(app_dir.iterdir()):
                app_dir.rmdir()
                logger.info(f"Removed empty directory {app_name}")
        else:
            if not app_dir.exists():
                raise ValueError(f"App {app_name} is not installed")
            logger.info(f"Uninstalling all versions of {app_name}")
            shutil.rmtree(app_dir)
            logger.info(f"Removed {app_name}")
