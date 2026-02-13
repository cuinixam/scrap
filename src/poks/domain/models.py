"""Poks domain models for manifests and configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from mashumaro.config import BaseConfig
from mashumaro.mixins.json import DataClassJSONMixin


@dataclass
class PoksJsonMixin(DataClassJSONMixin):
    """Shared mixin providing mashumaro config and JSON file I/O."""

    class Config(BaseConfig):
        omit_none = True

    @classmethod
    def from_json_file(cls, file_path: Path) -> PoksJsonMixin:
        return cls.from_dict(json.loads(file_path.read_text()))

    def to_json_string(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_json_file(self, file_path: Path) -> None:
        file_path.write_text(self.to_json_string())


@dataclass
class PoksArchive(PoksJsonMixin):
    """A platform-specific archive entry within a manifest."""

    os: str
    arch: str
    sha256: str
    ext: str | None = None
    url: str | None = None


@dataclass
class PoksAppVersion(PoksJsonMixin):
    """Specific version details for an application."""

    version: str
    archives: list[PoksArchive]
    extract_dir: str | None = None
    bin: list[str] | None = None
    env: dict[str, str] | None = None
    license: str | None = None
    yanked: str | None = None
    url: str | None = None


@dataclass
class PoksManifest(PoksJsonMixin):
    """Application manifest describing versions and metadata."""

    description: str
    versions: list[PoksAppVersion]
    schema_version: str = "1.0.0"
    license: str | None = None
    homepage: str | None = None


@dataclass
class PoksBucket(PoksJsonMixin):
    """A bucket source pointing to a Git repository of manifests."""

    url: str
    name: str | None = None
    id: str | None = None


@dataclass
class PoksBucketRegistry(PoksJsonMixin):
    """Registry of known buckets."""

    buckets: list[PoksBucket] = field(default_factory=list)

    def get_by_name(self, name: str) -> PoksBucket | None:
        """Find a bucket by its name."""
        for bucket in self.buckets:
            if bucket.name == name:
                return bucket
        return None

    def get_by_url(self, url: str) -> PoksBucket | None:
        """Find a bucket by its URL."""
        for bucket in self.buckets:
            if bucket.url == url:
                return bucket
        return None

    def get_by_id(self, bucket_id: str) -> PoksBucket | None:
        """Find a bucket by its ID."""
        for bucket in self.buckets:
            if bucket.id == bucket_id:
                return bucket
        return None

    def add_or_update(self, bucket: PoksBucket) -> None:
        """Add a bucket or update it if it exists (by ID)."""
        existing = self.get_by_id(bucket.id) if bucket.id else None

        # If not found by ID, check by URL to be safe, though ID should be hash of URL
        if not existing:
            existing = self.get_by_url(bucket.url)

        if existing:
            existing.name = bucket.name or existing.name
            existing.url = bucket.url
            existing.id = bucket.id or existing.id
        else:
            self.buckets.append(bucket)

    def remove(self, bucket_id: str) -> None:
        """Remove a bucket by ID."""
        self.buckets = [b for b in self.buckets if b.id != bucket_id]


@dataclass
class PoksApp(PoksJsonMixin):
    """An application entry in the configuration file."""

    name: str
    version: str
    bucket: str
    os: list[str] | None = None
    arch: list[str] | None = None
    dirs: list[str] | None = None
    env: dict[str, str] | None = None

    def is_supported(self, os: str, arch: str) -> bool:
        """
        Check if this app supports the given platform.

        Returns True when the app's os/arch filters include the given
        values or are None (meaning all platforms are supported).
        """
        os_ok = self.os is None or os in self.os
        arch_ok = self.arch is None or arch in self.arch
        return os_ok and arch_ok


@dataclass
class PoksAppEnv(PoksJsonMixin):
    """Resolved environment and directory paths for an installed application."""

    dirs: list[str] | None = None
    env: dict[str, str] | None = None


@dataclass
class PoksConfig(PoksJsonMixin):
    """Top-level configuration file listing buckets and apps to install."""

    buckets: list[PoksBucket] = field(default_factory=list)
    apps: list[PoksApp] = field(default_factory=list)
