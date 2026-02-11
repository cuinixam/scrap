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
class PoksManifest(PoksJsonMixin):
    """Application manifest describing versions, archives, and install config."""

    version: str
    archives: list[PoksArchive]
    description: str | None = None
    homepage: str | None = None
    license: str | None = None
    url: str | None = None
    extract_dir: str | None = None
    bin: list[str] | None = None
    env: dict[str, str] | None = None


@dataclass
class PoksBucket(PoksJsonMixin):
    """A bucket source pointing to a Git repository of manifests."""

    name: str
    url: str


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
class PoksConfig(PoksJsonMixin):
    """Top-level configuration file listing buckets and apps to install."""

    buckets: list[PoksBucket] = field(default_factory=list)
    apps: list[PoksApp] = field(default_factory=list)
