"""Reusable test helpers for building archives and Git bucket repositories."""

from __future__ import annotations

import hashlib
import shutil
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path

from git import Repo


def create_archive(
    base_dir: Path,
    files: dict[str, str],
    fmt: str = "tar.gz",
    top_dir: str | None = None,
) -> tuple[Path, str]:
    """
    Create an archive with the given files and return ``(path, sha256)``.

    Args:
        base_dir: Directory where the archive file will be written.
        files: Mapping of filename → text content.
        fmt: Archive format, either ``"tar.gz"`` or ``"zip"``.
        top_dir: Optional top-level directory inside the archive.

    Returns:
        Tuple of (archive_path, sha256_hex).

    """
    creators = {"tar.gz": _create_tar_gz, "zip": _create_zip}
    creator = creators.get(fmt)
    if creator is None:
        raise ValueError(f"Unsupported test archive format: {fmt!r}. Use 'tar.gz' or 'zip'.")
    archive_path = creator(base_dir, files, top_dir)
    sha256 = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    return archive_path, sha256


def create_bare_bucket(base_dir: Path, manifests: dict[str, str]) -> str:
    """
    Create a bare Git repo with manifest JSON files and return its ``file://`` URL.

    Args:
        base_dir: Directory under which the bare repo and a temporary clone are created.
        manifests: Mapping of filename (e.g. ``"my-tool.json"``) → JSON string content.

    Returns:
        A ``file://`` URL pointing to the bare repository.

    """
    bare_dir = base_dir / "bucket.git"
    clone_dir = base_dir / "bucket-clone"

    # Clean up from previous calls (e.g. add_manifest rebuilds the repo)
    if bare_dir.exists():
        shutil.rmtree(bare_dir)
    if clone_dir.exists():
        shutil.rmtree(clone_dir)

    Repo.init(bare_dir, bare=True)
    repo = Repo.clone_from(str(bare_dir), str(clone_dir))

    for name, content in manifests.items():
        (clone_dir / name).write_text(content)

    # Ensure there is always something to commit
    if not manifests:
        (clone_dir / ".gitkeep").write_text("")

    repo.index.add([str(clone_dir / name) for name in (manifests or {".gitkeep": ""})])
    repo.index.commit("Add manifests")
    repo.remote("origin").push()

    return bare_dir.as_uri()


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
