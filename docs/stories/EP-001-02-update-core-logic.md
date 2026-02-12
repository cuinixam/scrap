# Story: Update Core Logic to use PoksAppVersion

## Description

Update `src/poks/resolver.py` and `src/poks/environment.py` to operate on `PoksAppVersion` instead of `PoksManifest`.
The core logic for resolving archives, URLs, and environment variables now belongs to a specific version of an app, not the top-level manifest.

## Tasks

1. Update `src/poks/resolver.py`:
    - Change `resolve_archive(manifest: PoksManifest, ...)` to `resolve_archive(version: PoksAppVersion, ...)`.
    - Change `resolve_download_url(manifest: PoksManifest, ...)` to `resolve_download_url(version: PoksAppVersion, ...)`.
    - Update logic to access fields from `PoksAppVersion`.
2. Update `src/poks/environment.py`:
    - Change `collect_env_updates(manifest: PoksManifest, ...)` to `collect_env_updates(version: PoksAppVersion, ...)`.
    - Update logic to access fields from `PoksAppVersion`.

## Acceptance Criteria

- `resolver.py` and `environment.py` type hints are updated.
- Functions operate correctly on `PoksAppVersion` objects.
- Existing tests for these modules will fail until this story and the next ones are integrated (or tests updated).
