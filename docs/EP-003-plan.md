# EP-003 Implementation Plan

## Step 1: Add `zstandard` dependency

- **File**: `pyproject.toml`
- **Change**: Add `"zstandard>=0.20,<1"` to `dependencies`
- **AC**: `zstandard` is importable after `uv sync`

## Step 2: Create `poker.py` — prefix patching module

- **File**: `src/poks/poker.py` (new)
- **Changes**:
  - `PatchEntry` dataclass: `path`, `prefix_placeholder`, `file_mode`
  - `poke(install_dir, patches)` function:
    - Text mode: read file as text, replace all occurrences of placeholder with `str(install_dir)`, write back
    - Binary mode: read file as bytes, find placeholder bytes, replace with install_dir bytes null-padded to same length, write back
    - Error if new prefix longer than placeholder in binary mode
  - Windows: detect `\` in placeholder, convert install_dir to matching delimiter
- **AC**:
  - Text files have placeholder replaced with install dir
  - Binary files have placeholder replaced with null-padded install dir
  - Binary mode fails with clear error if install path > placeholder length
  - Windows backslash placeholders get backslash replacements

## Step 3: Extend `extractor.py` with `.conda` support

- **File**: `src/poks/extractor.py`
- **Changes**:
  - Add `".conda": "conda"` to `SUPPORTED_FORMATS`
  - Add `_parse_conda_patches(info_tar_bytes)` — extract `paths.json` from info tar.zst, return `list[PatchEntry]`
  - Add `_extract_tar_zst(data, dest_dir)` — decompress zstd, open tarfile, validate paths, extract
  - Add `_extract_conda(archive_path, dest_dir)` — orchestrate: open zip, extract info tar.zst for patches, extract pkg tar.zst, run poke
  - Update `extract_archive` to branch on `"conda"` format before the generic `_open_archive`/`_extract_all` path
- **AC**:
  - `.conda` files are detected and extracted
  - Inner `pkg-*.tar.zst` contents land in `dest_dir`
  - Prefix patching is applied based on `paths.json`
  - Path traversal in inner tar is rejected
  - `extract_dir` relocation still works for `.conda`

## Step 4: Add `_create_conda` test helper

- **File**: `tests/helpers.py`
- **Changes**:
  - Add `_create_conda()` that builds a `.conda` zip containing:
    - `metadata.json`
    - `pkg-*.tar.zst` with the requested files (with placeholder prefixes in some)
    - `info-*.tar.zst` with `paths.json` describing patch entries
  - Register in `create_archive` creators dict
- **AC**: `create_archive(base_dir, files, fmt="conda")` produces a valid `.conda` file

## Step 5: Add tests

- **File**: `tests/test_extractor.py` (extend) and `tests/test_poker.py` (new)
- **Tests for poker**:
  - Text-mode poking replaces placeholder in text files
  - Binary-mode poking replaces placeholder with null-padded prefix
  - Binary-mode fails when install path exceeds placeholder length
  - Windows backslash delimiter handling
- **Tests for extractor**:
  - `.conda` extraction produces correct files
  - `.conda` with `extract_dir` works
  - `.conda` with path traversal in inner tar is rejected
  - `.conda` with no `paths.json` extracts without poking
- **AC**: All tests pass with `pypeline run`
