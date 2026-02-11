# Story 06 — Install Orchestration

## Goal

Wire together all the pieces in `Poks.install()`: parse config, sync buckets, resolve manifests, download, verify, extract, and collect environment updates. This is the integration story.

## Dependencies

- **Story 02** — Variable Expansion & Archive Resolution
- **Story 03** — Archive Download & Caching
- **Story 04** — Archive Extraction
- **Story 05** — Bucket Management
- **Story 08** — Environment Configuration

## Reference

- [specs.md — Installation Flow](../specs.md#3-installation-flow) (all steps)
- [specs.md — Python API](../specs.md#python-api)

## Scope

### `Poks.install()` Implementation

Replace the current stub in `src/poks/poks.py` with the full flow. The method should accept either a `Path` (to a `poks.json` file) or a `PoksConfig` object directly (to support single-app install from Story 09):

1. `PoksConfig.from_json_file(config_file)` → `PoksConfig` (or use config directly if already provided)
2. `sync_all_buckets(config.buckets, self.buckets_dir)` → bucket paths
3. For each app in `config.apps`:
   - Skip if `not app.is_supported(current_os, current_arch)`
   - `find_manifest(app.name, bucket_paths[app.bucket])` → manifest path
   - `PoksManifest.from_json_file(manifest_path)` → `PoksManifest`
   - `resolve_archive(manifest, current_os, current_arch)` → `PoksArchive`
   - `resolve_download_url(manifest, archive)` → URL
   - `get_cached_or_download(url, archive.sha256, self.cache_dir)` → archive path
   - `extract_archive(archive_path, self.apps_dir / app.name / app.version, manifest.extract_dir)`
   - `collect_env_updates(manifest, install_dir)` → env dict
4. Merge all env updates and return

### Platform Detection

Add a utility to detect the current OS and architecture:

- `get_current_platform() -> tuple[str, str]` — returns `(os, arch)` using `platform` stdlib. Map to Poks conventions (e.g., `darwin` → `macos`, `AMD64` → `x86_64`).

### Idempotency

- If `apps/<name>/<version>/` already exists, skip download and extraction for that app (log a message).

## Acceptance Criteria

- [x] Full install flow works end-to-end with all components wired together.
- [x] `Poks.install()` accepts both a `Path` and a `PoksConfig` object.
- [x] Platform detection maps correctly on all supported OS variants.
- [x] Apps already installed are skipped.
- [x] Platform-filtered apps are skipped with a log message.
- [x] The returned dict contains correct PATH and env entries.
- [x] Invalid or missing config files raise descriptive errors.
- [x] Integration test using mocked download and Git (no real network calls).
- [x] `pypeline run` passes.
