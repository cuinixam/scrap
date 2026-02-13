"""Tests for bucket registry."""

from pathlib import Path

from poks.bucket import get_bucket_id, load_registry, save_registry
from poks.domain import PoksBucket, PoksBucketRegistry


def test_get_bucket_id() -> None:
    """Test deterministic ID generation."""
    url1 = "https://github.com/poks/main-bucket.git"
    url2 = "https://github.com/poks/main-bucket"
    url3 = "https://github.com/poks/main-bucket/"

    id1 = get_bucket_id(url1)
    id2 = get_bucket_id(url2)
    id3 = get_bucket_id(url3)

    assert id1 == id2 == id3
    assert len(id1) == 12


def test_registry_load_save(tmp_path: Path) -> None:
    """Test saving and loading the registry."""
    registry_path = tmp_path / "buckets.json"
    registry = PoksBucketRegistry()

    bucket = PoksBucket(url="https://example.com/bucket.git", name="main", id="1234567890ab")
    registry.add_or_update(bucket)

    save_registry(registry, registry_path)

    loaded = load_registry(registry_path)
    assert len(loaded.buckets) == 1
    assert loaded.buckets[0].url == bucket.url
    assert loaded.buckets[0].name == bucket.name
    assert loaded.buckets[0].id == bucket.id


def test_registry_add_or_update() -> None:
    """Test adding and updating buckets in the registry."""
    registry = PoksBucketRegistry()

    url = "https://example.com/bucket.git"
    bucket_id = get_bucket_id(url)

    # Add new
    bucket = PoksBucket(url=url, id=bucket_id)
    registry.add_or_update(bucket)
    retrieved = registry.get_by_id(bucket_id)
    assert retrieved is not None
    assert retrieved.url == url

    # Update existing by ID
    updated = PoksBucket(url=url, id=bucket_id, name="my-bucket")
    registry.add_or_update(updated)
    retrieved_updated = registry.get_by_id(bucket_id)
    assert retrieved_updated is not None
    assert retrieved_updated.name == "my-bucket"

    # Update by URL fallback (simulate missing ID in input, though add_or_update checks ID first)
    # If we pass a bucket with NEW name but SAME URL and NO ID?
    # Registry logic: check ID first. If not found, check URL.

    bucket2 = PoksBucket(url=url, name="renamed")
    # This bucket has no ID. add_or_update will search by URL.
    registry.add_or_update(bucket2)
    retrieved_renamed = registry.get_by_id(bucket_id)
    assert retrieved_renamed is not None
    assert retrieved_renamed.name == "renamed"
