# Story 03 — Archive Download & Caching

## Goal

Implement downloading archives from URLs with SHA256 verification and a local file cache that avoids re-downloading.

## Dependencies

None — this story works with URLs and file paths only, no import-level model dependencies. At integration time (Story 06), values like `sha256` and download URLs flow from Story 01/02 models.

## Reference

- [specs.md — Installation Flow](../specs.md#3-installation-flow) (steps 2–3: Download, Verify)
- [specs.md — Directory Structure](../specs.md#directory-structure) (`cache/`)

## Scope

### Download

Create `src/poks/downloader.py`:

- `download_file(url: str, dest: Path) -> Path` — downloads the file at `url` to `dest`. Use `urllib.request` (stdlib). Raise an error on HTTP failures.

### SHA256 Verification

- `verify_sha256(file_path: Path, expected_hash: str) -> None` — compute the SHA256 hash of the file and raise an error if it doesn't match `expected_hash`.

### Cache Logic

- `get_cached_or_download(url: str, sha256: str, cache_dir: Path) -> Path` — derive a cache filename from the URL. If it exists and the hash matches, return it. Otherwise download, verify, and return it.

The cache filename should be deterministic based on the URL (e.g., URL basename or a hash of the URL).

## Acceptance Criteria

- [x] Files are downloaded correctly (test with a small fixture or mock).
- [x] SHA256 mismatch raises a descriptive error.
- [x] Cached files are reused when the hash matches.
- [x] Corrupt cached files are re-downloaded.
- [x] Tests use `tmp_path` and do not make real network calls (mock `urllib`).
- [x] `pypeline run` passes.
