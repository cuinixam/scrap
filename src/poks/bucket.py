"""Bucket syncing and manifest lookup."""

import subprocess
from pathlib import Path

from py_app_dev.core.logging import logger

from poks.domain import PoksBucket


def sync_bucket(bucket: PoksBucket, buckets_dir: Path) -> Path:
    """Clone or pull a bucket repository and return its local path."""
    local_path = buckets_dir / bucket.name
    if local_path.exists():
        logger.info(f"Pulling latest for bucket '{bucket.name}'")
        subprocess.run(["git", "pull"], cwd=local_path, check=True, capture_output=True)
    else:
        logger.info(f"Cloning bucket '{bucket.name}' from {bucket.url}")
        subprocess.run(
            ["git", "clone", bucket.url, str(local_path)],
            check=True,
            capture_output=True,
        )
    return local_path


def find_manifest(app_name: str, bucket_path: Path) -> Path:
    """Return the path to ``<app_name>.json`` inside the bucket directory."""
    manifest_path = bucket_path / f"{app_name}.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Manifest '{app_name}.json' not found in bucket at {bucket_path}"
        )
    return manifest_path


def sync_all_buckets(buckets: list[PoksBucket], buckets_dir: Path) -> dict[str, Path]:
    """Sync every bucket and return a ``{name: local_path}`` mapping."""
    return {bucket.name: sync_bucket(bucket, buckets_dir) for bucket in buckets}
