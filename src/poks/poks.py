import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from git import Repo
from git.exc import InvalidGitRepositoryError, NoSuchPathError
from py_app_dev.core.logging import logger

from poks.bucket import (
    find_manifest,
    get_bucket_id,
    is_bucket_url,
    load_registry,
    save_registry,
    search_all_buckets,
    search_apps_in_buckets,
    sync_all_buckets,
    update_local_buckets,
)
from poks.domain import InstalledApp, InstallResult, PoksApp, PoksAppVersion, PoksBucket, PoksBucketRegistry, PoksConfig, PoksManifest
from poks.downloader import ProgressCallback, get_cached_or_download
from poks.extractor import extract_archive
from poks.platform import get_current_platform
from poks.resolver import resolve_archive, resolve_download_url


class Poks:
    """Cross-platform package manager for developer tools."""

    def __init__(
        self,
        root_dir: Path,
        progress_callback: ProgressCallback | None = None,
        use_cache: bool = True,
    ) -> None:
        """
        Initialize Poks with a root directory.

        Args:
            root_dir: Root directory for Poks (apps, buckets, cache).
            progress_callback: Optional callback invoked during downloads
                with ``(app_name, bytes_downloaded, total_bytes_or_none)``.
            use_cache: If False, skip the download cache and always re-download.

        """
        self.root_dir = root_dir
        self.apps_dir = root_dir / "apps"
        self.buckets_dir = root_dir / "buckets"
        self.cache_dir = root_dir / "cache"
        self.progress_callback = progress_callback
        self.use_cache = use_cache

    def install_app(self, app_name: str, version: str, bucket: str | None = None) -> InstalledApp:
        """
        Install a single application from a bucket.

        Args:
            app_name: Application name.
            version: Version to install.
            bucket: Optional bucket name or URL.

        Returns:
            Details about the installed application.

        Raises:
            ValueError: If bucket is not found or version is missing.

        """
        registry_path = self.buckets_dir / "buckets.json"
        registry = load_registry(registry_path)

        bucket_obj = self._resolve_bucket(bucket, app_name, registry)
        bucket_ref = bucket_obj.id or bucket_obj.name or "unknown"

        # If we created a new bucket entry (e.g. from URL), save the registry
        if bucket and is_bucket_url(bucket) and not registry.get_by_id(bucket_obj.id or ""):
            registry.add_or_update(bucket_obj)
            save_registry(registry, registry_path)

        config = PoksConfig(
            buckets=[bucket_obj],
            apps=[PoksApp(name=app_name, version=version, bucket=bucket_ref)],
        )

        result = self.install(config)
        return result.apps[0]

    def install_from_manifest(self, manifest_path: Path, version: str) -> InstalledApp:
        """
        Install an application directly from a manifest file.

        Args:
            manifest_path: Path to the manifest JSON file. The app name is derived from the filename stem.
            version: Version to install.

        Returns:
            Details about the installed application.

        Raises:
            ValueError: If the version is not found or is yanked.
            FileNotFoundError: If the manifest file does not exist.

        """
        app_name = manifest_path.stem
        manifest = PoksManifest.from_json_file(manifest_path)
        current_os, current_arch = get_current_platform()

        app_version = next((v for v in manifest.versions if v.version == version), None)
        if not app_version:
            raise ValueError(f"Version {version} not found for app {app_name} in manifest")
        if app_version.yanked:
            raise ValueError(f"Version {version} of {app_name} is yanked: {app_version.yanked}")

        install_dir = self.apps_dir / app_name / version
        if not install_dir.exists():
            archive = resolve_archive(app_version, current_os, current_arch)
            url = resolve_download_url(app_version, archive)
            archive_path = get_cached_or_download(
                url,
                archive.sha256,
                self.cache_dir,
                app_name=app_name,
                progress_callback=self.progress_callback,
                use_cache=self.use_cache,
            )
            extract_archive(archive_path, install_dir, app_version.extract_dir)
            (install_dir / ".manifest.json").write_text(manifest.to_json_string())
            self._create_receipt(install_dir, "", [])
            if not self.progress_callback:
                logger.info(f"Installed {app_name}@{version}")
        else:
            if not self.progress_callback:
                logger.info(f"Skipping {app_name}@{version}: already installed")

        return self._build_installed_app(app_name, version, install_dir, app_version)

    def _resolve_bucket(self, bucket_arg: str | None, app_name: str, registry: PoksBucketRegistry) -> PoksBucket:
        """Resolve the bucket logic for installation to avoid nesting."""
        if bucket_arg:
            if is_bucket_url(bucket_arg):
                return self._resolve_bucket_url(bucket_arg, registry)
            return self._resolve_bucket_name(bucket_arg, registry)

        return self._resolve_bucket_from_search(app_name, registry)

    def _resolve_bucket_url(self, url: str, registry: PoksBucketRegistry) -> PoksBucket:
        bucket_id = get_bucket_id(url)
        # Check if exists in registry
        existing = registry.get_by_id(bucket_id) or registry.get_by_url(url)
        if existing:
            return existing

        # New bucket from URL
        return PoksBucket(name=None, url=url, id=bucket_id)

    def _resolve_bucket_name(self, name: str, registry: PoksBucketRegistry) -> PoksBucket:
        bucket_obj = registry.get_by_name(name)
        if bucket_obj:
            return bucket_obj

        # Legacy fallback: check local directories
        logger.warning(f"Bucket '{name}' not found in registry. Checking local directories.")
        bucket_path = self.buckets_dir / name
        if not bucket_path.exists():
            raise ValueError(f"Bucket '{name}' not found in registry or {self.buckets_dir}")

        # Try to infer URL from git config
        url = ""
        try:
            url = Repo(bucket_path).remotes.origin.url
        except (InvalidGitRepositoryError, NoSuchPathError, AttributeError):
            pass

        return PoksBucket(name=name, url=url or "", id=get_bucket_id(url) if url else None)

    def _resolve_bucket_from_search(self, app_name: str, registry: PoksBucketRegistry) -> PoksBucket:
        _, found_bucket_name = search_all_buckets(app_name, self.buckets_dir)

        # Resolve this name to a registry entry if possible
        bucket_obj = registry.get_by_name(found_bucket_name)
        if not bucket_obj:
            # Check by ID if dir name is ID
            bucket_obj = registry.get_by_id(found_bucket_name)

        if bucket_obj:
            return bucket_obj

        # Legacy/unregistered local bucket
        return PoksBucket(name=found_bucket_name, url="")

    def install(self, config_or_path: Path | PoksConfig) -> InstallResult:
        """
        Install apps from a configuration file or config object.

        Args:
            config_or_path: Path to poks.json or a PoksConfig object.

        Returns:
            Install result with per-app details and aggregated environment helpers.

        """
        config = PoksConfig.from_json_file(config_or_path) if isinstance(config_or_path, Path) else config_or_path

        # Ensure any buckets in the config are registered
        self._ensure_buckets_registered(config.buckets)

        current_os, current_arch = get_current_platform()
        bucket_paths = sync_all_buckets(config.buckets, self.buckets_dir)

        installed_apps = self._install_apps_parallel(config.apps, bucket_paths, config.buckets, current_os, current_arch)
        return InstallResult(apps=installed_apps)

    def _install_apps_parallel(
        self,
        apps: list[PoksApp],
        bucket_paths: dict[str, Path],
        buckets_list: list[PoksBucket],
        current_os: str,
        current_arch: str,
    ) -> list[InstalledApp]:
        if len(apps) <= 1:
            results = [self._install_single_app(app, bucket_paths, buckets_list, current_os, current_arch) for app in apps]
            return [r for r in results if r is not None]

        # Map future -> index to preserve config ordering
        with ThreadPoolExecutor(max_workers=len(apps)) as executor:
            futures = {executor.submit(self._install_single_app, app, bucket_paths, buckets_list, current_os, current_arch): idx for idx, app in enumerate(apps)}
            ordered: dict[int, InstalledApp | None] = {}
            for future in as_completed(futures):
                ordered[futures[future]] = future.result()

        return [app for idx in sorted(ordered) if (app := ordered[idx]) is not None]

    def _ensure_buckets_registered(self, buckets: list[PoksBucket]) -> None:
        registry = load_registry(self.buckets_dir / "buckets.json")
        registry_updated = False
        for bucket in buckets:
            if bucket.url:
                if not bucket.id:
                    bucket.id = get_bucket_id(bucket.url)

                existing = registry.get_by_id(bucket.id) or registry.get_by_url(bucket.url)
                if not existing:
                    registry.add_or_update(bucket)
                    registry_updated = True
                elif existing.name != bucket.name and bucket.name:
                    existing.name = bucket.name
                    registry.add_or_update(existing)
                    registry_updated = True

        if registry_updated:
            save_registry(registry, self.buckets_dir / "buckets.json")

    def _install_single_app(
        self,
        app: PoksApp,
        bucket_paths: dict[str, Path],
        buckets_list: list[PoksBucket],
        current_os: str,
        current_arch: str,
    ) -> InstalledApp | None:
        if not app.is_supported(current_os, current_arch):
            logger.info(f"Skipping {app.name}: not supported on {current_os}/{current_arch}")
            return None

        bucket_path = bucket_paths.get(app.bucket)
        if not bucket_path:
            raise ValueError(f"Bucket '{app.bucket}' not found. Available buckets: {', '.join(bucket_paths)}")
        manifest_path = find_manifest(app.name, bucket_path)
        manifest = PoksManifest.from_json_file(manifest_path)

        app_version = next((v for v in manifest.versions if v.version == app.version), None)

        if not app_version:
            raise ValueError(f"Version {app.version} not found for app {app.name} in manifest")

        if app_version.yanked:
            raise ValueError(f"Version {app.version} of {app.name} is yanked: {app_version.yanked}")

        install_dir = self.apps_dir / app.name / app.version
        if not install_dir.exists():
            archive = resolve_archive(app_version, current_os, current_arch)
            url = resolve_download_url(app_version, archive)
            archive_path = get_cached_or_download(
                url,
                archive.sha256,
                self.cache_dir,
                app_name=app.name,
                progress_callback=self.progress_callback,
                use_cache=self.use_cache,
            )
            extract_archive(archive_path, install_dir, app_version.extract_dir)

            # Persist manifest and receipt for future reference
            (install_dir / ".manifest.json").write_text(manifest.to_json_string())
            self._create_receipt(install_dir, app.bucket, buckets_list)
            if not self.progress_callback:
                logger.info(f"Installed {app.name}@{app.version}")
        else:
            if not self.progress_callback:
                logger.info(f"Skipping {app.name}@{app.version}: already installed")

        return self._build_installed_app(app.name, app.version, install_dir, app_version)

    def _create_receipt(self, install_dir: Path, bucket_ref: str, buckets_list: list[PoksBucket]) -> None:
        receipt: dict[str, str | None] = {"bucket_id": None, "bucket_name": None, "bucket_url": None}

        matched_bucket = next((b for b in buckets_list if b.name == bucket_ref or b.id == bucket_ref), None)
        if matched_bucket:
            receipt["bucket_id"] = matched_bucket.id
            receipt["bucket_name"] = matched_bucket.name
            receipt["bucket_url"] = matched_bucket.url

        (install_dir / ".receipt.json").write_text(json.dumps(receipt, indent=2))

    def list_installed(self) -> InstallResult:
        """
        List all installed applications.

        Returns:
            Install result with per-app details and aggregated environment helpers.

        """
        installed_apps: list[InstalledApp] = []
        if not self.apps_dir.exists():
            return InstallResult(apps=[])

        for app_dir in self.apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            for version_dir in app_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                installed = self._load_installed_app(app_dir.name, version_dir)
                if installed:
                    installed_apps.append(installed)

        return InstallResult(apps=installed_apps)

    def _load_installed_app(self, app_name: str, version_dir: Path) -> InstalledApp | None:
        version = version_dir.name
        manifest_path = version_dir / ".manifest.json"

        if not manifest_path.exists():
            return InstalledApp(name=app_name, version=version, install_dir=version_dir, bin_dirs=[], env={})

        try:
            manifest = PoksManifest.from_json_file(manifest_path)
            app_version = next((v for v in manifest.versions if v.version == version), None)

            if not app_version:
                logger.warning(f"Version {version} not found in stored manifest for {app_name}")
                return InstalledApp(name=app_name, version=version, install_dir=version_dir, bin_dirs=[], env={})

            return self._build_installed_app(app_name, version, version_dir, app_version)

        except Exception as e:
            logger.warning(f"Failed to load manifest for {app_name}@{version}: {e}")
            return InstalledApp(name=app_name, version=version, install_dir=version_dir, bin_dirs=[], env={})

    @staticmethod
    def _build_installed_app(name: str, version: str, install_dir: Path, app_version: PoksAppVersion) -> InstalledApp:
        bin_dirs = [install_dir / entry for entry in app_version.bin] if app_version.bin else []
        env: dict[str, str] = {}
        if app_version.env:
            dir_str = str(install_dir)
            for k, v in app_version.env.items():
                env[k] = str(Path(v.replace("${dir}", dir_str)))
        return InstalledApp(name=name, version=version, install_dir=install_dir, bin_dirs=bin_dirs, env=env)

    def uninstall(self, app_name: str | None = None, version: str | None = None, all_apps: bool = False, wipe: bool = False) -> None:
        """
        Uninstall apps.

        Args:
            app_name: Name of the app to uninstall.
            version: Specific version to uninstall.
            all_apps: If True, uninstalls all apps.
            wipe: If True, also remove the download cache.

        Raises:
            ValueError: If the specified app or version does not exist.

        """
        if all_apps:
            logger.info("Uninstalling all apps")
            if not self.apps_dir.exists():
                return
            for item in self.apps_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(item)
                    logger.info(f"Removed {item.name}")
            if wipe and self.cache_dir.exists():
                shutil.rmtree(self.cache_dir)
                logger.info("Removed download cache")
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

        if wipe and self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            logger.info("Removed download cache")

    def search(self, query: str, update: bool = True) -> list[str]:
        """
        Search for apps in all local buckets.

        Args:
            query: Search term.
            update: If True, update buckets before searching.

        Returns:
            List of matching app names.

        """
        if update:
            update_local_buckets(self.buckets_dir)

        return search_apps_in_buckets(query, self.buckets_dir)
