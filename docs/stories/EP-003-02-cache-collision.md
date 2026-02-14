# EP-003-02: Fix Cache Path Collision Risk

## Context

The download cache in `downloader.py` derives filenames solely from the URL's last path segment. This can cause silent data corruption when two different URLs share the same filename.

## Problem

`_cache_path_for` (`downloader.py:66`) does:

```python
return cache_dir / Path(url.split("?")[0].rstrip("/")).name
```

Two different URLs like:
- `https://example.com/v1/archive.tar.gz`
- `https://example.com/v2/archive.tar.gz`

Both resolve to `cache/archive.tar.gz`. The SHA256 check will detect the mismatch and re-download, but this defeats caching when both packages are needed simultaneously — each install overwrites the other's cache entry.

## Acceptance Criteria

- [x] Cache filenames incorporate a URL-derived hash to prevent collisions (e.g., `{sha256(url)[:8]}_{filename}`).
- [x] Existing cached files are still usable (graceful migration or acceptable cache miss on upgrade).
- [x] Add a test demonstrating that two URLs with the same filename produce distinct cache paths.
- [x] All existing tests continue to pass.

## Files to Modify

- `src/poks/downloader.py`
- `tests/test_downloader.py`
