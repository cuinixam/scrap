# Story: Update Install Logic for Multi-version Manifests

## Description

Update `src/poks/poks.py` to handle the new `PoksManifest` structure during installation.
The install process must now find the requested version within the manifest's `versions` list.

## Tasks

1. Update `Poks.install` method:
    - After loading `PoksManifest`, do NOT expect it to have version/archives directly.
    - Iterate through `manifest.versions` to find the entry matching `app.version`.
    - Raise `ValueError` if version is not found.
    - Check if version is `yanked` and raise error if so.
    - Pass the found `PoksAppVersion` object to `resolve_archive`, `resolve_download_url`, and `collect_env_updates`.
    - When persisting `.manifest.json`, we can still persist the whole `PoksManifest` or just the `PoksAppVersion`. EP suggests persisting "manifest". Persisting the whole manifest is safer for provenance, but `list` command needs to know which version is installed. The directory structure `apps/<name>/<version>` implies the version.
2. Refactor `install_app` if needed (it calls `install`, so mainly `install` needs changes).

## Acceptance Criteria

- `poks install` works with the new manifest format.
- `poks install` fails if version is not found in manifest.
- `poks install` fails if version is yanked.
