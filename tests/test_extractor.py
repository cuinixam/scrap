import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

import py7zr
import pytest

from poks.extractor import extract_archive

HELLO_CONTENT = "hello poks"
NESTED_CONTENT = "nested file"


def _create_zip(path: Path, top_dir: str | None = None) -> Path:
    archive = path / ("archive.zip")
    with zipfile.ZipFile(archive, "w") as zf:
        prefix = f"{top_dir}/" if top_dir else ""
        zf.writestr(f"{prefix}hello.txt", HELLO_CONTENT)
    return archive


def _create_tar(path: Path, compression: str, ext: str, top_dir: str | None = None) -> Path:
    archive = path / f"archive{ext}"
    mode = cast(Literal["w:gz", "w:xz", "w:bz2"], f"w:{compression}")
    with tarfile.open(archive, mode) as tf:
        prefix = f"{top_dir}/" if top_dir else ""
        info = tarfile.TarInfo(name=f"{prefix}hello.txt")
        data = HELLO_CONTENT.encode()
        info.size = len(data)
        tf.addfile(info, BytesIO(data))
    return archive


def _create_7z(path: Path, top_dir: str | None = None) -> Path:
    archive = path / "archive.7z"
    src_dir = path / "src_7z"
    if top_dir:
        (src_dir / top_dir).mkdir(parents=True)
        (src_dir / top_dir / "hello.txt").write_text(HELLO_CONTENT)
    else:
        src_dir.mkdir(parents=True)
        (src_dir / "hello.txt").write_text(HELLO_CONTENT)
    with py7zr.SevenZipFile(archive, "w") as sz:
        for file in src_dir.rglob("*"):
            sz.write(file, file.relative_to(src_dir))
    return archive


ARCHIVE_CREATORS = [
    ("zip", lambda p: _create_zip(p)),
    ("tar.gz", lambda p: _create_tar(p, "gz", ".tar.gz")),
    ("tar.xz", lambda p: _create_tar(p, "xz", ".tar.xz")),
    ("tar.bz2", lambda p: _create_tar(p, "bz2", ".tar.bz2")),
    ("7z", lambda p: _create_7z(p)),
]


@pytest.mark.parametrize(("label", "creator"), ARCHIVE_CREATORS, ids=[a[0] for a in ARCHIVE_CREATORS])
def test_extract_archive(tmp_path, label, creator):
    archive = creator(tmp_path)
    dest = tmp_path / "out"
    result = extract_archive(archive, dest)
    assert result == dest
    assert (dest / "hello.txt").read_text() == HELLO_CONTENT


ARCHIVE_CREATORS_WITH_EXTRACT_DIR = [
    ("zip", lambda p: _create_zip(p, top_dir="sdk-1.0")),
    ("tar.gz", lambda p: _create_tar(p, "gz", ".tar.gz", top_dir="sdk-1.0")),
    ("7z", lambda p: _create_7z(p, top_dir="sdk-1.0")),
]


@pytest.mark.parametrize(
    ("label", "creator"),
    ARCHIVE_CREATORS_WITH_EXTRACT_DIR,
    ids=[a[0] for a in ARCHIVE_CREATORS_WITH_EXTRACT_DIR],
)
def test_extract_dir_relocates_contents(tmp_path, label, creator):
    archive = creator(tmp_path)
    dest = tmp_path / "out"
    extract_archive(archive, dest, extract_dir="sdk-1.0")
    assert (dest / "hello.txt").read_text() == HELLO_CONTENT
    assert not (dest / "sdk-1.0").exists()


def test_unsupported_format_raises(tmp_path):
    fake = tmp_path / "archive.rar"
    fake.write_text("not real")
    with pytest.raises(ValueError, match="Unsupported archive format"):
        extract_archive(fake, tmp_path / "out")


def test_extract_dir_missing_raises(tmp_path):
    archive = _create_zip(tmp_path)
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="extract_dir 'nonexistent' not found"):
        extract_archive(archive, dest, extract_dir="nonexistent")
