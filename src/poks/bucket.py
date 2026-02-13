"""Bucket syncing and manifest lookup."""

import hashlib
import json
from pathlib import Path

from git import Repo
from git.exc import GitCommandError, InvalidGitRepositoryError, NoSuchPathError
from py_app_dev.core.logging import logger

from poks.domain import PoksBucket, PoksBucketRegistry


def get_bucket_id(url: str) -> str:
    """Generate a deterministic ID from the bucket URL."""
    # Normalize URL by removing trailing slash and .git suffix for consistency
    normalized = url.strip().rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def load_registry(registry_path: Path) -> PoksBucketRegistry:
    """Load the bucket registry from a file."""
    if not registry_path.exists():
        return PoksBucketRegistry()
    try:
        return PoksBucketRegistry.from_json_file(registry_path)
    except json.JSONDecodeError as e:
        logger.warning(f"Registry file at {registry_path} is corrupted: {e}")
        return PoksBucketRegistry()
    except Exception as e:
        logger.warning(f"Failed to load registry from {registry_path}: {e}")
        return PoksBucketRegistry()


def save_registry(registry: PoksBucketRegistry, registry_path: Path) -> None:
    """Save the bucket registry to a file."""
    try:
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry.to_json_file(registry_path)
    except OSError as e:
        logger.error(f"Failed to save registry to {registry_path}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error saving registry to {registry_path}: {e}")


def sync_bucket(bucket: PoksBucket, buckets_dir: Path) -> Path:
    """Clone or pull a bucket repository and return its local path."""
    # Use ID if available, otherwise name (legacy/config)
    dir_name = bucket.id or bucket.name
    if not dir_name:
        # Should not happen if we compute ID correctly
        raise ValueError(f"Bucket has no ID or name: {bucket}")

    local_path = buckets_dir / dir_name

    if local_path.exists():
        logger.info(f"Pulling latest for bucket '{bucket.name or bucket.id}'")
        try:
            repo = Repo(local_path)
            repo.remotes.origin.fetch()
            repo.head.reset(repo.active_branch.tracking_branch(), index=True, working_tree=True)
        except (GitCommandError, InvalidGitRepositoryError, NoSuchPathError) as e:
            logger.warning(f"Failed to update bucket '{bucket.name or bucket.id}': {e}")
        except Exception as e:
            logger.warning(f"Unexpected error updating bucket '{bucket.name or bucket.id}': {e}")
    else:
        logger.info(f"Cloning bucket '{bucket.name or bucket.id}' from {bucket.url}")
        try:
            Repo.clone_from(bucket.url, str(local_path))
        except GitCommandError as e:
            raise RuntimeError(f"Failed to clone bucket from {bucket.url}: {e}") from e

    return local_path


def find_manifest(app_name: str, bucket_path: Path) -> Path:
    """Return the path to ``<app_name>.json`` inside the bucket directory."""
    manifest_path = bucket_path / f"{app_name}.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest '{app_name}.json' not found in bucket at {bucket_path}")
    return manifest_path


def sync_all_buckets(buckets: list[PoksBucket], buckets_dir: Path) -> dict[str, Path]:
    """Sync every bucket and return a ``{name_or_id: local_path}`` mapping."""
    result = {}
    for bucket in buckets:
        path = sync_bucket(bucket, buckets_dir)
        # Map both ID and name if available to ensure lookup works
        if bucket.id:
            result[bucket.id] = path
        if bucket.name:
            result[bucket.name] = path
    return result


def is_bucket_url(value: str) -> bool:
    """Check if a string looks like a bucket URL (contains :// or ends with .git)."""
    return "://" in value or value.endswith(".git")


def search_all_buckets(app_name: str, buckets_dir: Path) -> tuple[Path, str]:
    """
    Search all local buckets for a manifest and return its path and bucket name.

    Args:
        app_name: Name of the app to search for.
        buckets_dir: Directory containing local buckets.

    Returns:
        Tuple of (manifest_path, bucket_name).

    Raises:
        FileNotFoundError: If no buckets exist or manifest not found in any bucket.

    """
    if not buckets_dir.exists() or not any(buckets_dir.iterdir()):
        raise FileNotFoundError("No local buckets available. Use --bucket with a URL to clone a bucket.")

    for bucket_dir in buckets_dir.iterdir():
        if not bucket_dir.is_dir():
            continue
        manifest_path = bucket_dir / f"{app_name}.json"
        if manifest_path.exists():
            return manifest_path, bucket_dir.name

    raise FileNotFoundError(f"Manifest '{app_name}.json' not found in any local bucket")


def search_apps_in_buckets(query: str, buckets_dir: Path) -> list[str]:
    """
    Search for apps in all local buckets matching the query.

    Args:
        query: Search term (case-insensitive substring).
        buckets_dir: Directory containing local buckets.

    Returns:
        Sorted list of matching app names.

    """
    matches = set()
    if not buckets_dir.exists():
        return []

    query = query.lower()

    for bucket_dir in buckets_dir.iterdir():
        if not bucket_dir.is_dir():
            continue

        for item in bucket_dir.iterdir():
            if item.suffix == ".json" and item.is_file():
                app_name = item.stem
                if query in app_name.lower():
                    matches.add(app_name)

    return sorted(matches)


def update_local_buckets(buckets_dir: Path) -> None:
    """
    Update all local buckets that are git repositories.

    Args:
        buckets_dir: Directory containing local buckets.

    """
    if not buckets_dir.exists():
        return

    for bucket_dir in buckets_dir.iterdir():
        if not bucket_dir.is_dir():
            continue

        # Check if it's a git repo
        if (bucket_dir / ".git").exists():
            try:
                logger.info(f"Updating bucket '{bucket_dir.name}'...")
                repo = Repo(bucket_dir)
                repo.remotes.origin.fetch()
                repo.head.reset(repo.active_branch.tracking_branch(), index=True, working_tree=True)
            except (GitCommandError, InvalidGitRepositoryError) as e:
                logger.warning(f"Failed to update bucket '{bucket_dir.name}': {e}")
            except Exception as e:
                logger.warning(f"Unexpected error updating bucket '{bucket_dir.name}': {e}")
