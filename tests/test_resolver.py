import pytest

from poks.domain import PoksAppVersion, PoksArchive
from poks.resolver import expand_variables, resolve_archive, resolve_download_url


@pytest.mark.parametrize(
    ("template", "variables", "expected"),
    [
        ("v${version}", {"version": "1.0"}, "v1.0"),
        ("${os}-${arch}${ext}", {"os": "linux", "arch": "x86_64", "ext": ".tar.gz"}, "linux-x86_64.tar.gz"),
        ("${unknown} stays", {"version": "1.0"}, "${unknown} stays"),
        ("no placeholders", {}, "no placeholders"),
        ("${a}${b}", {"a": "X", "b": "Y"}, "XY"),
        ("", {"key": "val"}, ""),
    ],
)
def test_expand_variables(template, variables, expected):
    assert expand_variables(template, variables) == expected


VERSION = PoksAppVersion(
    version="0.16.5-1",
    url="https://example.com/sdk-${version}_${os}-${arch}${ext}",
    archives=[
        PoksArchive(os="windows", arch="x86_64", ext=".7z", sha256="aaa"),
        PoksArchive(os="linux", arch="x86_64", sha256="bbb", url="https://mirror.example.com/sdk-linux.tar.xz"),
        PoksArchive(os="macos", arch="aarch64", ext=".tar.xz", sha256="ccc"),
    ],
)


@pytest.mark.parametrize(
    ("target_os", "target_arch", "expected_sha"),
    [
        ("windows", "x86_64", "aaa"),
        ("linux", "x86_64", "bbb"),
        ("macos", "aarch64", "ccc"),
    ],
)
def test_resolve_archive(target_os, target_arch, expected_sha):
    archive = resolve_archive(VERSION, target_os, target_arch)
    assert archive.sha256 == expected_sha


def test_resolve_archive_unsupported():
    with pytest.raises(ValueError, match="No archive for os='linux', arch='aarch64'"):
        resolve_archive(VERSION, "linux", "aarch64")


def test_resolve_download_url_uses_archive_url():
    archive = resolve_archive(VERSION, "linux", "x86_64")
    url = resolve_download_url(VERSION, archive)
    assert url == "https://mirror.example.com/sdk-linux.tar.xz"


def test_resolve_download_url_uses_manifest_template():
    archive = resolve_archive(VERSION, "windows", "x86_64")
    url = resolve_download_url(VERSION, archive)
    assert url == "https://example.com/sdk-0.16.5-1_windows-x86_64.7z"


def test_resolve_download_url_no_url():
    version = PoksAppVersion(
        version="1.0",
        archives=[PoksArchive(os="linux", arch="x86_64", sha256="aaa")],
    )
    with pytest.raises(ValueError, match="No URL"):
        resolve_download_url(version, version.archives[0])
