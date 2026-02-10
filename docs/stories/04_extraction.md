# Story 04 — Archive Extraction

## Goal

Implement extraction of downloaded archives into the `apps/<name>/<version>/` directory. Support zip and tar (gz, xz, bz2) formats.

## Dependencies

None — this story only needs a file path and a destination directory.

## Reference

- [specs.md — Installation Flow](../specs.md#3-installation-flow) (step 4: Extract)
- [specs.md — Archive Support](../specs.md#archive-support)

## Scope

### Extraction

Create `src/poks/extractor.py`:

- `extract_archive(archive_path: Path, dest_dir: Path, extract_dir: Optional[str] = None) -> Path` — detects the archive format from the file extension, extracts to `dest_dir`, and returns the final extraction path. If `extract_dir` is set, the contents of that subdirectory within the archive are extracted (or moved) to `dest_dir`.

### Format Detection

- Detect format from the file extension:
  - `.zip` → `zipfile`
  - `.tar.gz`, `.tgz` → `tarfile` (gzip)
  - `.tar.xz`, `.txz` → `tarfile` (xz)
  - `.tar.bz2`, `.tbz2` → `tarfile` (bz2)
  - `.7z` → `py7zr` (requires adding `py7zr` to `pyproject.toml` dependencies)
- Raise a clear error for unsupported formats.

> **Note**: The `py7zr` package must be added to the project dependencies in `pyproject.toml` as part of this story.

### `extract_dir` Handling

When a manifest specifies `extract_dir`, the archive may contain a top-level directory (e.g., `zephyr-sdk-0.16.5-1/`). After extraction, only the contents of that subdirectory should end up in the destination.

## Acceptance Criteria

- [x] Zip archives are extracted correctly.
- [x] Tar archives (gz, xz, bz2) are extracted correctly.
- [x] 7z archives are extracted correctly (using `py7zr`).
- [x] `extract_dir` correctly relocates nested content.
- [x] Unsupported formats raise a clear error.
- [x] Tests use `tmp_path` with small test archives created in fixtures.
- [x] `pypeline run` passes.
