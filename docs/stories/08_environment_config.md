# Story 08 — Environment Configuration

## Goal

Implement the logic to generate environment variable updates (`PATH`, `env`) from installed app manifests.

## Dependencies

- **Story 01** — Data Models & Config Parsing (uses `PoksManifest`)

## Reference

- [specs.md — Installation Flow](../specs.md#3-installation-flow) (step 5: Configure)
- [specs.md — Manifest Schema](../specs.md#manifest-schema) (`bin`, `env`)

## Scope

### Environment Collection

Create `src/poks/environment.py`:

- `collect_env_updates(manifest: PoksManifest, install_dir: Path) -> dict[str, str]` — builds a dictionary of environment variable updates from the manifest:
  - **`bin`**: append each path (relative to `install_dir`) to PATH.
  - **`env`**: set each variable, expanding `${dir}` to `install_dir`.

### Merging

- `merge_env_updates(updates: list[dict[str, str]]) -> dict[str, str]` — merges multiple env update dicts. PATH entries are concatenated with the OS path separator; other variables are set (last writer wins, with a warning on conflicts).

## Acceptance Criteria

- [x] `bin` paths are correctly resolved and added to PATH.
- [x] `env` variables have `${dir}` expanded correctly.
- [x] `merge_env_updates` concatenates PATH entries.
- [x] Conflicting non-PATH env vars produce a warning.
- [x] Tests cover manifests with all, some, and no env fields.
- [x] `pypeline run` passes.
