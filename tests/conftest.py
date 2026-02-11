"""Shared pytest fixtures for Poks integration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from poks.domain import PoksApp, PoksBucket, PoksConfig, PoksManifest
from poks.poks import Poks
from tests.helpers import create_archive, create_bare_bucket


@dataclass
class PoksEnv:
    """A self-contained Poks environment rooted in a temporary directory."""

    root_dir: Path
    apps_dir: Path
    buckets_dir: Path
    cache_dir: Path
    archives_dir: Path
    bucket_url: str
    poks: Poks
    _manifests: dict[str, str] = field(default_factory=dict, repr=False)

    def add_manifest(self, name: str, manifest: PoksManifest) -> None:
        """Commit a manifest JSON file into the test bucket repository."""
        filename = f"{name}.json"
        self._manifests[filename] = manifest.to_json_string()
        # Rebuild the bare repo with all accumulated manifests
        bucket_base = self.root_dir / "bucket-src"
        bucket_base.mkdir(parents=True, exist_ok=True)
        self.bucket_url = create_bare_bucket(bucket_base, self._manifests)

    def make_archive(
        self,
        files: dict[str, str],
        fmt: str = "tar.gz",
        top_dir: str | None = None,
    ) -> tuple[Path, str]:
        """Create a test archive and return ``(path, sha256)``."""
        return create_archive(self.archives_dir, files, fmt=fmt, top_dir=top_dir)

    def create_config(self, apps: list[dict[str, str]]) -> Path:
        """Write a ``poks.json`` config file referencing the test bucket."""
        config = PoksConfig(
            buckets=[PoksBucket(name="test", url=self.bucket_url)],
            apps=[PoksApp(name=app["name"], version=app["version"], bucket="test") for app in apps],
        )
        config_path = self.root_dir / "poks.json"
        config.to_json_file(config_path)
        return config_path


@pytest.fixture
def poks_env(tmp_path: Path) -> PoksEnv:
    """Provide a fully wired Poks environment in a temporary directory."""
    root_dir = tmp_path / ".poks"
    root_dir.mkdir()
    apps_dir = root_dir / "apps"
    apps_dir.mkdir()
    buckets_dir = root_dir / "buckets"
    buckets_dir.mkdir()
    cache_dir = root_dir / "cache"
    cache_dir.mkdir()
    archives_dir = tmp_path / "archives"
    archives_dir.mkdir()

    # Create an initial empty bucket repo
    bucket_base = root_dir / "bucket-src"
    bucket_base.mkdir()
    bucket_url = create_bare_bucket(bucket_base, {})

    poks = Poks(root_dir=root_dir)

    return PoksEnv(
        root_dir=root_dir,
        apps_dir=apps_dir,
        buckets_dir=buckets_dir,
        cache_dir=cache_dir,
        archives_dir=archives_dir,
        bucket_url=bucket_url,
        poks=poks,
    )
