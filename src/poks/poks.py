"""Poks package manager core class."""

from __future__ import annotations

from pathlib import Path

from py_app_dev.core.logging import logger

from poks.bucket import (
    find_manifest,
    is_bucket_url,
    search_all_buckets,
    sync_all_buckets,
    sync_bucket,
)
from poks.domain import PoksApp, PoksAppVersion, PoksBucket, PoksConfig, PoksManifest
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

    def install_app(self, app_spec: str, bucket: str | None = None) -> None:
        """
        Install a single application.

        Args:
            app_spec: Application specification (name@version).
            bucket: Optional bucket name or URL.

        Raises:
            ValueError: If app_spec is invalid or bucket is not found.

        """
        if "@" not in app_spec:
            raise ValueError(f"Invalid app spec '{app_spec}'. Use format: name@version")

        app_name, app_version = app_spec.split("@", 1)

        if bucket:
            if is_bucket_url(bucket):
                temp_bucket = PoksBucket(name="temp", url=bucket)
                bucket_path = sync_bucket(temp_bucket, self.buckets_dir)
                find_manifest(app_name, bucket_path)
                bucket_name = "temp"
            else:
                bucket_path = self.buckets_dir / bucket
                if not bucket_path.exists():
                    raise ValueError(f"Bucket '{bucket}' not found in {self.buckets_dir}")
                find_manifest(app_name, bucket_path)
                bucket_name = bucket
        else:
            _, bucket_name = search_all_buckets(app_name, self.buckets_dir)

        config = PoksConfig(
            buckets=[PoksBucket(name=bucket_name, url="")],
            apps=[PoksApp(name=app_name, version=app_version, bucket=bucket_name)],
        )

        self.install(config)

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

            manifest_path = find_manifest(app.name, bucket_paths[app.bucket])
            manifest = PoksManifest.from_json_file(manifest_path)

            app_version: PoksAppVersion | None = None
            for v in manifest.versions:
                if v.version == app.version:
                    app_version = v
                    break

            if not app_version:
                raise ValueError(f"Version {app.version} not found for app {app.name} in manifest")

            if app_version.yanked:
                raise ValueError(f"Version {app.version} of {app.name} is yanked: {app_version.yanked}")

            install_dir = self.apps_dir / app.name / app.version
            if install_dir.exists():
                logger.info(f"Skipping {app.name}@{app.version}: already installed")
                env_updates.append(collect_env_updates(app_version, install_dir))
                continue

            archive = resolve_archive(app_version, current_os, current_arch)
            url = resolve_download_url(app_version, archive)
            archive_path = get_cached_or_download(url, archive.sha256, self.cache_dir)
            extract_archive(archive_path, install_dir, app_version.extract_dir)

            # Persist manifest for future reference (e.g. list command)
            (install_dir / ".manifest.json").write_text(manifest.to_json_string())

            logger.info(f"Installed {app.name}@{app.version}")
            env_updates.append(collect_env_updates(app_version, install_dir))

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
                        app_version: PoksAppVersion | None = None
                        for v in manifest.versions:
                            if v.version == version:
                                app_version = v
                                break

                        if app_version:
                            if app_version.bin:
                                dirs = [str(version_dir / b) for b in app_version.bin]

                            # env needs to be resolved with ${dir} -> version_dir
                            if app_version.env:
                                # Simple variable expansion
                                for k, v in app_version.env.items():
                                    env[k] = v.replace("${dir}", str(version_dir))
                        else:
                            logger.warning(f"Version {version} not found in stored manifest for {app_name}")

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
