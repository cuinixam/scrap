import json
import shutil
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
from poks.domain import PoksApp, PoksAppEnv, PoksBucket, PoksBucketRegistry, PoksConfig, PoksManifest
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
            apps=[PoksApp(name=app_name, version=app_version, bucket=bucket_ref)],
        )

        self.install(config)

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

    def install(self, config_or_path: Path | PoksConfig) -> dict[str, str]:
        """
        Install apps from a configuration file or config object.

        Args:
            config_or_path: Path to poks.json or a PoksConfig object.

        Returns:
            Dictionary of environment variable updates.

        """
        config = PoksConfig.from_json_file(config_or_path) if isinstance(config_or_path, Path) else config_or_path

        # Ensure any buckets in the config are registered
        self._ensure_buckets_registered(config.buckets)

        current_os, current_arch = get_current_platform()
        bucket_paths = sync_all_buckets(config.buckets, self.buckets_dir)
        env_updates: list[dict[str, str]] = []

        for app in config.apps:
            self._install_single_app(app, bucket_paths, config.buckets, current_os, current_arch, env_updates)

        return merge_env_updates(env_updates)

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
        env_updates: list[dict[str, str]],
    ) -> None:
        if not app.is_supported(current_os, current_arch):
            logger.info(f"Skipping {app.name}: not supported on {current_os}/{current_arch}")
            return

        manifest_path = find_manifest(app.name, bucket_paths[app.bucket])
        manifest = PoksManifest.from_json_file(manifest_path)

        app_version = next((v for v in manifest.versions if v.version == app.version), None)

        if not app_version:
            raise ValueError(f"Version {app.version} not found for app {app.name} in manifest")

        if app_version.yanked:
            raise ValueError(f"Version {app.version} of {app.name} is yanked: {app_version.yanked}")

        install_dir = self.apps_dir / app.name / app.version
        if install_dir.exists():
            logger.info(f"Skipping {app.name}@{app.version}: already installed")
            env_updates.append(collect_env_updates(app_version, install_dir))
            return

        archive = resolve_archive(app_version, current_os, current_arch)
        url = resolve_download_url(app_version, archive)
        archive_path = get_cached_or_download(url, archive.sha256, self.cache_dir)
        extract_archive(archive_path, install_dir, app_version.extract_dir)

        # Persist manifest and receipt for future reference
        (install_dir / ".manifest.json").write_text(manifest.to_json_string())

        self._create_receipt(install_dir, app.bucket, buckets_list)

        logger.info(f"Installed {app.name}@{app.version}")
        env_updates.append(collect_env_updates(app_version, install_dir))

    def _create_receipt(self, install_dir: Path, bucket_ref: str, buckets_list: list[PoksBucket]) -> None:
        receipt: dict[str, str | None] = {"bucket_id": None, "bucket_name": None, "bucket_url": None}

        matched_bucket = next((b for b in buckets_list if b.name == bucket_ref or b.id == bucket_ref), None)
        if matched_bucket:
            receipt["bucket_id"] = matched_bucket.id
            receipt["bucket_name"] = matched_bucket.name
            receipt["bucket_url"] = matched_bucket.url

        (install_dir / ".receipt.json").write_text(json.dumps(receipt, indent=2))

    def list_installed(self) -> list[PoksApp]:
        """
        List all installed applications.

        Returns:
            List of PoksApp objects with populated details (version, dirs, env).

        """
        installed_apps = []
        if not self.apps_dir.exists():
            return []

        registry = load_registry(self.buckets_dir / "buckets.json")

        for app_dir in self.apps_dir.iterdir():
            if not app_dir.is_dir():
                continue

            for version_dir in app_dir.iterdir():
                if not version_dir.is_dir():
                    continue

                installed_apps.append(self._get_installed_app_details(app_dir.name, version_dir, registry))

        return installed_apps

    def _get_installed_app_details(self, app_name: str, version_dir: Path, registry: PoksBucketRegistry) -> PoksApp:
        version = version_dir.name
        manifest_path = version_dir / ".manifest.json"

        bucket = self._resolve_installed_bucket(version_dir, registry)
        app_env = self._resolve_installed_env_and_dirs(app_name, version, version_dir, manifest_path)

        return PoksApp(name=app_name, version=version, bucket=bucket, dirs=app_env.dirs, env=app_env.env)

    def _resolve_installed_bucket(self, version_dir: Path, registry: PoksBucketRegistry) -> str:
        receipt_path = version_dir / ".receipt.json"
        if not receipt_path.exists():
            return "unknown"

        try:
            receipt = json.loads(receipt_path.read_text())
            bucket_name = receipt.get("bucket_name")
            bucket_url = receipt.get("bucket_url")
            bucket_id = receipt.get("bucket_id")

            if bucket_name:
                return bucket_name
            if bucket_url:
                return bucket_url
            if bucket_id:
                reg_bucket = registry.get_by_id(bucket_id)
                return (reg_bucket.name or reg_bucket.url) if reg_bucket else bucket_id
        except json.JSONDecodeError:
            logger.debug(f"Failed to parse receipt at {receipt_path}")
        except Exception as e:
            logger.debug(f"Unexpected error reading receipt at {receipt_path}: {e}")

        return "unknown"

    def _resolve_installed_env_and_dirs(self, app_name: str, version: str, version_dir: Path, manifest_path: Path) -> PoksAppEnv:
        if not manifest_path.exists():
            return PoksAppEnv()

        try:
            manifest = PoksManifest.from_json_file(manifest_path)
            app_version = next((v for v in manifest.versions if v.version == version), None)

            if not app_version:
                logger.warning(f"Version {version} not found in stored manifest for {app_name}")
                return PoksAppEnv()

            dirs = [str(version_dir / b) for b in app_version.bin] if app_version.bin else None

            env = {}
            if app_version.env:
                for k, v in app_version.env.items():
                    env[k] = v.replace("${dir}", str(version_dir))

            return PoksAppEnv(dirs=dirs, env=(env or None))

        except Exception as e:
            logger.warning(f"Failed to load manifest for {app_name}@{version}: {e}")
            return PoksAppEnv()

    def uninstall(self, app_name: str | None = None, version: str | None = None, all_apps: bool = False) -> None:
        """
        Uninstall apps.

        Args:
            app_name: Name of the app to uninstall.
            version: Specific version to uninstall.
            all_apps: If True, uninstalls all apps.

        Raises:
            ValueError: If the specified app or version does not exist.

        """
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
