# EP-003-05: Close Testing Gaps

## Context

The test suite has good coverage overall, but the code review identified several gaps in edge case and negative path testing.

## Problems

### 1. No test for yanked version rejection

`poks.py:198-199` raises `ValueError` when a yanked version is requested, but no test exercises this path.

### 2. Zephyr integration test runs real downloads without opt-in marker

`test_zephyr_integration.py` downloads ~100-200MB of real artifacts. It has a `skipif` for unsupported platforms but no `@pytest.mark.slow` or similar marker to skip it by default in local development and CI. This makes the test suite slow and flaky on network issues.

### 3. No test for cache path collision

Given the collision risk in `_cache_path_for` (see EP-003-02), there is no test verifying behavior when two URLs share the same filename.

### 4. CI matrix missing macOS

The GitHub Actions matrix tests Ubuntu + Windows but not macOS, despite macOS being a supported platform with its own platform mapping (`darwin` -> `macos`).

## Acceptance Criteria

- [x] Add a test that installing a yanked version raises `ValueError` with the yanked reason.
- [x] Add a `@pytest.mark.slow` (or similar) marker to `test_zephyr_integration.py` and configure pytest to skip it by default (run with `--run-slow` or `-m slow`).
- [x] Add a test for cache path behavior with colliding URL filenames (scope depends on EP-003-02).
- [x] Consider adding `macos-latest` to the CI matrix (at least for one Python version to limit cost).
- [x] All existing tests continue to pass.

## Files to Modify

- `tests/test_install.py`
- `tests/test_zephyr_integration.py`
- `tests/test_downloader.py`
- `pyproject.toml` (pytest markers configuration)
- `.github/workflows/ci.yml` (optional: macOS CI)
