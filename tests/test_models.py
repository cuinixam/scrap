import json

import pytest

from poks.domain import PoksApp, PoksAppVersion, PoksArchive, PoksBucket, PoksConfig, PoksManifest

SAMPLE_MANIFEST = {
    "description": "Zephyr SDK Bundle",
    "homepage": "https://github.com/zephyrproject-rtos/sdk-ng",
    "license": "Apache-2.0",
    "versions": [
        {
            "version": "0.16.5-1",
            "url": "https://example.com/sdk-${version}_${os}-${arch}${ext}",
            "archives": [
                {"os": "windows", "arch": "x86_64", "ext": ".7z", "sha256": "abc123"},
                {"os": "linux", "arch": "x86_64", "sha256": "def456", "url": "https://mirror.example.com/sdk-linux.tar.xz"},
            ],
            "bin": ["bin"],
            "env": {"ZEPHYR_SDK_INSTALL_DIR": "${dir}"},
        }
    ],
}

MINIMAL_MANIFEST = {
    "description": "Minimal App",
    "versions": [
        {
            "version": "1.0.0",
            "archives": [{"os": "linux", "arch": "x86_64", "sha256": "aaa"}],
        }
    ],
}

SAMPLE_CONFIG = {
    "buckets": [
        {"name": "main", "url": "https://github.com/poks/main-bucket.git"},
        {"name": "extras", "url": "https://github.com/poks/extras-bucket.git"},
    ],
    "apps": [
        {"name": "cmake", "version": "3.28.1", "bucket": "main"},
        {"name": "mingw-libs", "version": "1.0.0", "bucket": "extras", "os": ["windows"]},
    ],
}


class TestPoksManifest:
    def test_from_json_file_full(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(SAMPLE_MANIFEST))
        manifest = PoksManifest.from_json_file(path)

        assert manifest.description == "Zephyr SDK Bundle"
        assert manifest.license == "Apache-2.0"
        assert len(manifest.versions) == 1

        version = manifest.versions[0]
        assert version.version == "0.16.5-1"
        assert len(version.archives) == 2
        assert version.archives[0].os == "windows"
        assert version.archives[1].url == "https://mirror.example.com/sdk-linux.tar.xz"
        assert version.bin == ["bin"]
        assert version.env == {"ZEPHYR_SDK_INSTALL_DIR": "${dir}"}

    def test_from_json_file_minimal(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(MINIMAL_MANIFEST))
        manifest = PoksManifest.from_json_file(path)

        assert manifest.description == "Minimal App"
        assert len(manifest.versions) == 1
        assert manifest.versions[0].version == "1.0.0"
        assert manifest.versions[0].url is None
        assert manifest.versions[0].bin is None
        assert manifest.versions[0].env is None

    def test_round_trip(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(SAMPLE_MANIFEST))
        original = PoksManifest.from_json_file(path)

        out_path = tmp_path / "out.json"
        original.to_json_file(out_path)
        reloaded = PoksManifest.from_json_file(out_path)

        assert original == reloaded

    def test_round_trip_omits_none(self, tmp_path):
        path = tmp_path / "manifest.json"
        path.write_text(json.dumps(MINIMAL_MANIFEST))
        manifest = PoksManifest.from_json_file(path)

        out_path = tmp_path / "out.json"
        manifest.to_json_file(out_path)
        raw = json.loads(out_path.read_text())

        # description is required now
        assert "homepage" not in raw
        # bin is in versions
        assert "bin" not in raw["versions"][0]


class TestPoksConfig:
    def test_from_json_file(self, tmp_path):
        path = tmp_path / "poks.json"
        path.write_text(json.dumps(SAMPLE_CONFIG))
        config = PoksConfig.from_json_file(path)

        assert len(config.buckets) == 2
        assert config.buckets[0] == PoksBucket(name="main", url="https://github.com/poks/main-bucket.git")
        assert len(config.apps) == 2
        assert config.apps[0].name == "cmake"
        assert config.apps[1].os == ["windows"]

    def test_round_trip(self, tmp_path):
        path = tmp_path / "poks.json"
        path.write_text(json.dumps(SAMPLE_CONFIG))
        original = PoksConfig.from_json_file(path)

        out_path = tmp_path / "out.json"
        original.to_json_file(out_path)
        reloaded = PoksConfig.from_json_file(out_path)

        assert original == reloaded


@pytest.mark.parametrize(
    ("os_filter", "arch_filter", "query_os", "query_arch", "expected"),
    [
        (None, None, "linux", "x86_64", True),
        (["windows"], None, "windows", "x86_64", True),
        (["windows"], None, "linux", "x86_64", False),
        (None, ["aarch64"], "macos", "aarch64", True),
        (None, ["aarch64"], "macos", "x86_64", False),
        (["linux", "macos"], ["x86_64"], "linux", "x86_64", True),
        (["linux", "macos"], ["x86_64"], "windows", "x86_64", False),
        (["linux"], ["aarch64"], "linux", "x86_64", False),
    ],
)
def test_is_supported(os_filter, arch_filter, query_os, query_arch, expected):
    app = PoksApp(name="tool", version="1.0", bucket="main", os=os_filter, arch=arch_filter)
    assert app.is_supported(query_os, query_arch) is expected


def test_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not valid json")
    with pytest.raises(json.JSONDecodeError):
        PoksConfig.from_json_file(path)


class TestResolveForArchive:
    def test_archive_overrides_bin(self):
        version = PoksAppVersion(
            version="1.0",
            archives=[PoksArchive(os="linux", arch="x86_64", sha256="aaa", bin=["custom/bin"])],
            bin=["default/bin"],
        )
        effective = version.resolve_for_archive(version.archives[0])
        assert effective.bin == ["custom/bin"]

    def test_env_archive_overrides_version(self):
        version = PoksAppVersion(
            version="1.0",
            archives=[PoksArchive(os="linux", arch="x86_64", sha256="aaa", env={"KEY": "archive", "EXTRA": "new"})],
            env={"KEY": "version", "HOME": "${dir}"},
        )
        effective = version.resolve_for_archive(version.archives[0])
        assert effective.env == {"KEY": "archive", "EXTRA": "new"}

    def test_no_overrides_inherits_defaults(self):
        version = PoksAppVersion(
            version="1.0",
            archives=[PoksArchive(os="linux", arch="x86_64", sha256="aaa")],
            bin=["bin"],
            env={"HOME": "${dir}"},
        )
        effective = version.resolve_for_archive(version.archives[0])
        assert effective.bin == ["bin"]
        assert effective.env == {"HOME": "${dir}"}
