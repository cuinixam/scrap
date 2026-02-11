# Story 10 — Integration Test Fixtures

## Goal

Create a reusable pytest fixture infrastructure that sets up a complete Poks environment inside a temporary directory — including a bare Git bucket repository with manifest files and small test archives — so that integration tests can exercise the full install flow without network access.

## Dependencies

- **Story 01** — Data Models & Config Parsing (to generate valid manifest JSON)
- **Story 04** — Archive Extraction (to know the supported formats)

## Reference

- [specs.md — Directory Structure](../specs.md#directory-structure)
- [specs.md — Installation Flow](../specs.md#3-installation-flow)

## Scope

### Fixture: Fake Bucket

Create a `conftest.py` helper (or a dedicated `tests/fixtures/` module) that:

- Creates a bare Git repository in `tmp_path` using `git init --bare`.
- Provides a builder API to add manifest JSON files to the repo (commit them so `git clone` works).
- Returns the local `file://` URL of the bare repo, usable as a `PoksBucket.url`.

```python
# Usage example in a test
def test_install_from_config(poks_env):
    poks_env.add_manifest("my-tool", {
        "version": "1.0.0",
        "archives": [{"os": "linux", "arch": "x86_64", "ext": ".tar.gz", "sha256": "..."}],
        "url": "file://${...}/my-tool-${version}${ext}",
    })
    config = poks_env.create_config(apps=[{"name": "my-tool", "version": "1.0.0", "bucket": "test"}])
    env_updates = poks_env.poks.install(config)
    assert (poks_env.apps_dir / "my-tool" / "1.0.0").is_dir()
```

### Fixture: Fake Archives

- Provide a helper to create small tar.gz / zip archives in `tmp_path` from a dict of filename → content.
- Compute the SHA256 hash automatically and wire it into the manifest.
- Serve archives via `file://` URLs (no HTTP server needed).

### Fixture: Poks Environment

A composite fixture (`poks_env` or similar) that ties everything together:

| Component | Description |
|-----------|-------------|
| `root_dir` | `tmp_path / ".poks"` |
| `apps_dir` | `root_dir / "apps"` |
| `buckets_dir` | `root_dir / "buckets"` |
| `cache_dir` | `root_dir / "cache"` |
| `bucket_url` | `file://` URL of the bare test bucket repo |
| `poks` | A `Poks(root_dir=root_dir)` instance |
| `add_manifest(name, manifest_dict)` | Adds a manifest to the test bucket |
| `create_archive(files, format)` | Creates a test archive, returns `(path, sha256)` |
| `create_config(apps)` | Writes a `poks.json` and returns its path |

### Location

- Shared fixtures go in `tests/conftest.py`.
- Archive and repo builder helpers go in `tests/helpers.py` (or `tests/fixtures.py`).

## Acceptance Criteria

- [x] A bare Git repo can be created with manifest files and cloned by `git clone`.
- [x] Test archives (tar.gz and zip) can be generated programmatically with correct SHA256 hashes.
- [x] The `poks_env` fixture provides a fully wired `Poks` instance pointing at the temporary directory.
- [x] At least one integration test demonstrates the full flow: create bucket → add manifest → create archive → `poks.install()` → verify files extracted.
- [x] All fixture helpers are usable from any test file via `conftest.py`.
- [x] `pypeline run` passes.
