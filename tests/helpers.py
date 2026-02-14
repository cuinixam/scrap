"""Reusable test helpers for building archives and Git bucket repositories."""

from __future__ import annotations

import hashlib
import json
import tarfile
import zipfile
from collections.abc import Callable
from io import BytesIO
from pathlib import Path

import zstandard
from git import Repo

from poks.domain import InstalledApp, InstallResult


def assert_install_result(result: InstallResult, expected_count: int) -> list[InstalledApp]:
    """Assert the expected number of installed apps and return them."""
    assert len(result.apps) == expected_count, f"Expected {expected_count} installed apps, found {len(result.apps)}"
    return result.apps


def assert_installed_app(
    result: InstallResult,
    name: str,
    filter_fn: Callable[[InstalledApp], bool] | None = None,
) -> InstalledApp:
    """Assert exactly one installed app matches the name (and optional filter) and return it."""
    matches = [app for app in result.apps if app.name == name]
    if filter_fn:
        matches = [app for app in matches if filter_fn(app)]
    assert len(matches) == 1, f"Expected 1 app named '{name}', found {len(matches)}"
    return matches[0]


def create_archive(
    base_dir: Path,
    files: dict[str, str],
    fmt: str = "tar.gz",
    top_dir: str | None = None,
    conda_patches: list[dict[str, str]] | None = None,
) -> tuple[Path, str]:
    """
    Create an archive with the given files and return ``(path, sha256)``.

    Args:
        base_dir: Directory where the archive file will be written.
        files: Mapping of filename → text content.
        fmt: Archive format, ``"tar.gz"``, ``"zip"``, or ``"conda"``.
        top_dir: Optional top-level directory inside the archive.
        conda_patches: Optional list of patch entries for .conda archives (paths.json content).

    Returns:
        Tuple of (archive_path, sha256_hex).

    """
    if fmt == "conda":
        archive_path = _create_conda(base_dir, files, top_dir, patches=conda_patches)
    else:
        creators: dict[str, Callable[..., Path]] = {"tar.gz": _create_tar_gz, "zip": _create_zip}
        creator = creators.get(fmt)
        if creator is None:
            raise ValueError(f"Unsupported test archive format: {fmt!r}. Use 'tar.gz', 'zip', or 'conda'.")
        archive_path = creator(base_dir, files, top_dir)
    sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    return archive_path, sha256


def update_test_bucket_repo(repo_dir: Path, manifests: dict[str, str]) -> str:
    """
    Update (or create) a non-bare Git repo with manifest JSON files.

    Args:
        repo_dir: Directory for the bucket repository.
        manifests: Mapping of filename (e.g. ``"my-tool.json"``) → JSON string content.

    Returns:
        A ``file://`` URL pointing to the repository.

    """
    if not (repo_dir / ".git").exists():
        Repo.init(repo_dir)

    for name, content in manifests.items():
        (repo_dir / name).write_text(content)

    # Ensure there is always something to commit
    if not manifests:
        (repo_dir / ".gitkeep").write_text("")

    repo = Repo(repo_dir)
    repo.index.add([str(repo_dir / name) for name in (manifests or {".gitkeep": ""})])
    repo.index.commit("Update manifests")

    return repo_dir.as_uri()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _create_tar_gz(base_dir: Path, files: dict[str, str], top_dir: str | None) -> Path:
    archive_path = base_dir / "archive.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tf:
        for name, content in files.items():
            entry_name = f"{top_dir}/{name}" if top_dir else name
            data = content.encode()
            info = tarfile.TarInfo(name=entry_name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
    return archive_path


def _create_zip(base_dir: Path, files: dict[str, str], top_dir: str | None) -> Path:
    archive_path = base_dir / "archive.zip"
    with zipfile.ZipFile(archive_path, "w") as zf:
        for name, content in files.items():
            entry_name = f"{top_dir}/{name}" if top_dir else name
            zf.writestr(entry_name, content)
    return archive_path


def _make_tar_zst(files: dict[str, bytes]) -> bytes:
    """Build a tar.zst archive in memory from a dict of name -> bytes."""
    tar_buf = BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
    cctx = zstandard.ZstdCompressor()
    return cctx.compress(tar_buf.getvalue())


def _create_conda(
    base_dir: Path,
    files: dict[str, str],
    top_dir: str | None,
    patches: list[dict[str, str]] | None = None,
) -> Path:
    """Build a .conda archive (zip with pkg-*.tar.zst and info-*.tar.zst inside)."""
    pkg_name = "test-pkg-1.0-h0_0"
    pkg_files = {(f"{top_dir}/{name}" if top_dir else name): content.encode() for name, content in files.items()}
    pkg_tar_zst = _make_tar_zst(pkg_files)

    paths_json: dict[str, list[dict[str, str]]] = {"paths": patches or []}
    info_files = {"paths.json": json.dumps(paths_json).encode()}
    info_tar_zst = _make_tar_zst(info_files)

    metadata = json.dumps({"conda_pkg_format_version": 2}).encode()

    archive_path = base_dir / "archive.conda"
    with zipfile.ZipFile(archive_path, "w") as zf:
        zf.writestr("metadata.json", metadata)
        zf.writestr(f"pkg-{pkg_name}.tar.zst", pkg_tar_zst)
        zf.writestr(f"info-{pkg_name}.tar.zst", info_tar_zst)
    return archive_path
