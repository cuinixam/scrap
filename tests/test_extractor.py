import json
import tarfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Literal, cast

import py7zr
import pytest
import zstandard

from poks.extractor import extract_archive

HELLO_CONTENT = "hello poks"
NESTED_CONTENT = "nested file"
CONDA_PLACEHOLDER = "/opt/anaconda1anaconda2anaconda3"


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


def _make_tar_zst(files: dict[str, bytes]) -> bytes:
    tar_buf = BytesIO()
    with tarfile.open(fileobj=tar_buf, mode="w:") as tf:
        for name, data in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tf.addfile(info, BytesIO(data))
    cctx = zstandard.ZstdCompressor()
    return cctx.compress(tar_buf.getvalue())


def _create_conda(
    path: Path,
    top_dir: str | None = None,
    patches: list[dict[str, str]] | None = None,
    pkg_files: dict[str, bytes] | None = None,
) -> Path:
    if pkg_files is None:
        prefix = f"{top_dir}/" if top_dir else ""
        pkg_files = {f"{prefix}hello.txt": HELLO_CONTENT.encode()}
    pkg_tar_zst = _make_tar_zst(pkg_files)

    paths_json = json.dumps({"paths": patches or []}).encode()
    info_tar_zst = _make_tar_zst({"paths.json": paths_json})

    archive = path / "archive.conda"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"conda_pkg_format_version": 2}))
        zf.writestr("pkg-test-1.0-h0_0.tar.zst", pkg_tar_zst)
        zf.writestr("info-test-1.0-h0_0.tar.zst", info_tar_zst)
    return archive


# -- parametrized extraction tests -------------------------------------------

ARCHIVE_CREATORS = [
    ("zip", lambda p: _create_zip(p)),
    ("tar.gz", lambda p: _create_tar(p, "gz", ".tar.gz")),
    ("tar.xz", lambda p: _create_tar(p, "xz", ".tar.xz")),
    ("tar.bz2", lambda p: _create_tar(p, "bz2", ".tar.bz2")),
    ("7z", lambda p: _create_7z(p)),
    ("conda", lambda p: _create_conda(p)),
]


@pytest.mark.parametrize(("label", "creator"), ARCHIVE_CREATORS, ids=[a[0] for a in ARCHIVE_CREATORS])
def test_extract_archive(tmp_path, label, creator):
    archive = creator(tmp_path)
    dest = tmp_path / "out"
    result = extract_archive(archive, dest)
    assert result == dest
    assert (dest / "hello.txt").read_text() == HELLO_CONTENT


EXTRACT_DIR_CREATORS = [
    ("zip", lambda p, td: _create_zip(p, top_dir=td)),
    ("tar.gz", lambda p, td: _create_tar(p, "gz", ".tar.gz", top_dir=td)),
    ("7z", lambda p, td: _create_7z(p, top_dir=td)),
]


@pytest.mark.parametrize(("label", "creator"), EXTRACT_DIR_CREATORS, ids=[a[0] for a in EXTRACT_DIR_CREATORS])
def test_extract_dir_relocates_contents(tmp_path, label, creator):
    archive = creator(tmp_path, "nested-dir")
    dest = tmp_path / "out"
    result = extract_archive(archive, dest, extract_dir="nested-dir")
    assert result == dest
    assert (dest / "hello.txt").read_text() == HELLO_CONTENT
    assert not (dest / "nested-dir").exists()


def test_extract_dir_missing_raises(tmp_path):
    archive = _create_zip(tmp_path)
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="not found in extracted archive"):
        extract_archive(archive, dest, extract_dir="nonexistent")


def test_extract_dir_traversal_rejected(tmp_path):
    archive = _create_zip(tmp_path)
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="escapes destination directory"):
        extract_archive(archive, dest, extract_dir="../escape")


def test_extract_dir_with_same_name_child(tmp_path):
    """Relocation must work when extract_dir contains a child with the same name."""
    archive = tmp_path / "archive.tar.xz"
    with tarfile.open(archive, "w:xz") as tf:
        info = tarfile.TarInfo(name="toolchain/toolchain/hello.txt")
        data = HELLO_CONTENT.encode()
        info.size = len(data)
        tf.addfile(info, BytesIO(data))
    dest = tmp_path / "out"
    extract_archive(archive, dest, extract_dir="toolchain")
    assert (dest / "toolchain" / "hello.txt").read_text() == HELLO_CONTENT


def test_unsupported_format_raises(tmp_path):
    fake = tmp_path / "archive.rar"
    fake.write_text("not real")
    with pytest.raises(ValueError, match="Unsupported archive format"):
        extract_archive(fake, tmp_path / "out")


# -- path traversal protection -----------------------------------------------


def _create_zip_with_traversal(path: Path) -> Path:
    archive = path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("../escape.txt", "pwned")
    return archive


def _create_tar_with_traversal(path: Path) -> Path:
    archive = path / "malicious.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        info = tarfile.TarInfo(name="../escape.txt")
        data = b"pwned"
        info.size = len(data)
        tf.addfile(info, BytesIO(data))
    return archive


def test_zip_path_traversal_rejected(tmp_path):
    archive = _create_zip_with_traversal(tmp_path)
    dest = tmp_path / "out"
    with pytest.raises(ValueError, match="Path traversal detected"):
        extract_archive(archive, dest)


def test_tar_path_traversal_rejected(tmp_path):
    archive = _create_tar_with_traversal(tmp_path)
    dest = tmp_path / "out"
    # Python 3.12+ raises tarfile.OutsideDestinationError via data_filter;
    # older versions hit our _validate_entry_paths raising ValueError.
    _outside = getattr(tarfile, "OutsideDestinationError", ValueError)
    with pytest.raises((ValueError, _outside)):
        extract_archive(archive, dest)


# -- .conda-specific tests ---------------------------------------------------


def test_extract_conda_applies_text_poking(tmp_path):
    script_content = f"#!/bin/sh\nexport PATH={CONDA_PLACEHOLDER}/bin:$PATH\n"
    patches = [{"_path": "bin/run.sh", "prefix_placeholder": CONDA_PLACEHOLDER, "file_mode": "text", "path_type": "hardlink"}]
    archive = _create_conda(
        tmp_path,
        pkg_files={"bin/run.sh": script_content.encode()},
        patches=patches,
    )
    dest = tmp_path / "out"
    extract_archive(archive, dest)
    result = (dest / "bin/run.sh").read_text()
    assert CONDA_PLACEHOLDER not in result
    assert str(dest) in result


def test_extract_conda_no_paths_json(tmp_path):
    pkg_tar_zst = _make_tar_zst({"hello.txt": HELLO_CONTENT.encode()})
    info_tar_zst = _make_tar_zst({})

    archive = tmp_path / "archive.conda"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"conda_pkg_format_version": 2}))
        zf.writestr("pkg-test-1.0-h0_0.tar.zst", pkg_tar_zst)
        zf.writestr("info-test-1.0-h0_0.tar.zst", info_tar_zst)

    dest = tmp_path / "out"
    extract_archive(archive, dest)
    assert (dest / "hello.txt").read_text() == HELLO_CONTENT


def test_conda_path_traversal_in_inner_tar_rejected(tmp_path):
    malicious_files = {"../escape.txt": b"pwned"}
    pkg_tar_zst = _make_tar_zst(malicious_files)
    info_tar_zst = _make_tar_zst({"paths.json": json.dumps({"paths": []}).encode()})

    archive = tmp_path / "malicious.conda"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("metadata.json", json.dumps({"conda_pkg_format_version": 2}))
        zf.writestr("pkg-test-1.0-h0_0.tar.zst", pkg_tar_zst)
        zf.writestr("info-test-1.0-h0_0.tar.zst", info_tar_zst)

    dest = tmp_path / "out"
    _outside = getattr(tarfile, "OutsideDestinationError", ValueError)
    with pytest.raises((ValueError, _outside)):
        extract_archive(archive, dest)
