# Story: Update List Logic and Tests

## Description

Update `Poks.list` to work with the new persisted manifest format and ensure all tests pass.

## Tasks

1. Update `Poks.list` in `src/poks/poks.py`:
    - It reads `.manifest.json` from the version directory.
    - If `.manifest.json` now contains the full `PoksManifest` (with all versions), `list` needs to extract the specific version details.
    - However, `Poks.list` iterates directories `apps/<name>/<version>`. So we know the version.
    - Find the matching `PoksAppVersion` in the loaded `PoksManifest` using the directory name (version).
    - Use that `PoksAppVersion` to populate `bin` (dirs) and `env`.
2. Update Tests:
    - Update `tests/data/riscv64-zephyr-elf.json` (or similar test data) to new format.
    - Update unit tests in `tests/` that rely on old manifest structure.
    - Add new tests for multi-version selection and yanked versions.
    - Ensure `poks install` and `poks list` tests pass.

## Acceptance Criteria

- `poks list` correctly shows installed apps with details.
- All tests pass (`pytest`).
- Linter passes (`ruff`).
