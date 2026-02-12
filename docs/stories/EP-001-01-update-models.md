# Story: Update Domain Models for Multi-version Manifests

## Description

Update `src/poks/domain/models.py` to implement the new manifest structure defined in EP-001.
This involves introducing `PoksAppVersion` and updating `PoksManifest` to contain a list of versions.

## Tasks

1. Define `PoksAppVersion` dataclass in `src/poks/domain/models.py`.
    - Fields: `version`, `archives`, `extract_dir`, `bin`, `env`, `license`, `yanked`, `url` (optional generic).
2. Update `PoksManifest` dataclass in `src/poks/domain/models.py`.
    - Remove fields moved to `PoksAppVersion` (version, archives, url, extract_dir, bin, env).
    - Add `versions: list[PoksAppVersion]`.
    - Keep `description`, `homepage`, `license` (as defaults).
3. Ensure backward compatibility is NOT required (breaking change).
4. Update any `from_json_file` or mixins if necessary (likely handled by mashumaro).

## Acceptance Criteria

- `PoksManifest` can parse the new JSON format example from EP-001.
- Unit tests for models (if any) are updated or new ones created to verify parsing.
