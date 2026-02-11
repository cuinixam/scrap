"""Tests for environment variable collection and merging."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from poks.domain import PoksArchive, PoksManifest
from poks.environment import collect_env_updates, merge_env_updates

DUMMY_ARCHIVE = [PoksArchive(os="linux", arch="x86_64", sha256="abc")]


@pytest.mark.parametrize(
    ("bin_dirs", "env_vars", "expected_keys"),
    [
        (["bin", "tools/bin"], {"SDK_DIR": "${dir}"}, {"PATH", "SDK_DIR"}),
        (["bin"], None, {"PATH"}),
        (None, {"FOO": "${dir}/lib"}, {"FOO"}),
        (None, None, set()),
    ],
    ids=["full", "bin-only", "env-only", "neither"],
)
def test_collect_env_updates(
    bin_dirs: list[str] | None,
    env_vars: dict[str, str] | None,
    expected_keys: set[str],
) -> None:
    install_dir = Path("/apps/tool/1.0")
    manifest = PoksManifest(version="1.0", archives=DUMMY_ARCHIVE, bin=bin_dirs, env=env_vars)

    result = collect_env_updates(manifest, install_dir)

    assert set(result) == expected_keys
    if bin_dirs:
        expected_path = os.pathsep.join(str(install_dir / entry) for entry in bin_dirs)
        assert result["PATH"] == expected_path
    if env_vars:
        for key, value in env_vars.items():
            assert result[key] == value.replace("${dir}", str(install_dir))


def test_merge_concatenates_path() -> None:
    updates = [{"PATH": "/a/bin"}, {"PATH": "/b/bin"}]

    merged = merge_env_updates(updates)

    assert merged["PATH"] == os.pathsep.join(["/a/bin", "/b/bin"])


def test_merge_last_writer_wins_on_conflict() -> None:
    updates = [{"FOO": "old"}, {"FOO": "new"}]

    merged = merge_env_updates(updates)

    assert merged["FOO"] == "new"


def test_merge_empty_list() -> None:
    assert merge_env_updates([]) == {}
