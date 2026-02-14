from pathlib import Path

import pytest

from poks.poker import PatchEntry, poke

PLACEHOLDER = "/opt/anaconda1anaconda2anaconda3"
# Binary tests need a placeholder longer than any realistic tmp_path (~120 chars on macOS)
LONG_PLACEHOLDER = "/opt/" + "placeholder_" * 25  # ~305 chars


def _write_file(base: Path, name: str, content: str | bytes) -> Path:
    target = base / name
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        target.write_bytes(content)
    else:
        target.write_text(content)
    return target


class TestTextMode:
    def test_replaces_placeholder_in_text_file(self, tmp_path: Path) -> None:
        _write_file(tmp_path, "bin/tool", f"#!/usr/bin/env bash\nexport PATH={PLACEHOLDER}/bin:$PATH\n")
        patches = [PatchEntry(path="bin/tool", prefix_placeholder=PLACEHOLDER, file_mode="text")]

        poke(tmp_path, patches)

        result = (tmp_path / "bin/tool").read_text()
        assert str(tmp_path) in result
        assert PLACEHOLDER not in result

    def test_replaces_multiple_occurrences(self, tmp_path: Path) -> None:
        content = f"prefix={PLACEHOLDER}\nlib={PLACEHOLDER}/lib\n"
        _write_file(tmp_path, "etc/config", content)
        patches = [PatchEntry(path="etc/config", prefix_placeholder=PLACEHOLDER, file_mode="text")]

        poke(tmp_path, patches)

        result = (tmp_path / "etc/config").read_text()
        assert result.count(str(tmp_path)) == 2
        assert PLACEHOLDER not in result

    def test_skips_missing_file(self, tmp_path: Path) -> None:
        patches = [PatchEntry(path="nonexistent", prefix_placeholder=PLACEHOLDER, file_mode="text")]
        poke(tmp_path, patches)  # should not raise


class TestBinaryMode:
    def test_replaces_placeholder_with_null_padding(self, tmp_path: Path) -> None:
        binary_content = b"\x00\x00" + LONG_PLACEHOLDER.encode() + b"\x00" * 50 + b"\xff\xff"
        _write_file(tmp_path, "lib/libfoo.so", binary_content)
        patches = [PatchEntry(path="lib/libfoo.so", prefix_placeholder=LONG_PLACEHOLDER, file_mode="binary")]

        poke(tmp_path, patches)

        result = (tmp_path / "lib/libfoo.so").read_bytes()
        new_prefix = str(tmp_path).encode()
        assert new_prefix in result
        assert LONG_PLACEHOLDER.encode() not in result
        # File size must not change
        assert len(result) == len(binary_content)

    def test_fails_when_prefix_exceeds_placeholder(self, tmp_path: Path) -> None:
        short_placeholder = "/x"
        # Create a deep path that's longer than the placeholder
        deep_dir = tmp_path / ("a" * 100)
        deep_dir.mkdir(parents=True)
        _write_file(deep_dir, "bin/tool", short_placeholder.encode())
        patches = [PatchEntry(path="bin/tool", prefix_placeholder=short_placeholder, file_mode="binary")]

        with pytest.raises(ValueError, match="exceeds placeholder"):
            poke(deep_dir, patches)


class TestWindowsDelimiters:
    def test_backslash_placeholder_gets_backslash_replacement(self, tmp_path: Path) -> None:
        win_placeholder = "C:\\conda\\envs\\build"
        content = f"path={win_placeholder}\\bin\n"
        _write_file(tmp_path, "etc/config.cfg", content)
        patches = [PatchEntry(path="etc/config.cfg", prefix_placeholder=win_placeholder, file_mode="text")]

        poke(tmp_path, patches)

        result = (tmp_path / "etc/config.cfg").read_text()
        assert win_placeholder not in result
        assert str(tmp_path) in result

    def test_binary_backslash_replacement(self, tmp_path: Path) -> None:
        win_placeholder = "C:\\conda\\envs\\" + "placeholder_" * 25
        binary_content = win_placeholder.encode() + b"\x00" * 50
        _write_file(tmp_path, "lib/foo.dll", binary_content)
        patches = [PatchEntry(path="lib/foo.dll", prefix_placeholder=win_placeholder, file_mode="binary")]

        poke(tmp_path, patches)

        result = (tmp_path / "lib/foo.dll").read_bytes()
        assert win_placeholder.encode() not in result
        assert len(result) == len(binary_content)
