# Story 05 — Bucket Management

## Goal

Implement fetching and updating buckets (Git repositories containing manifest files) and looking up manifests by app name within a bucket.

## Dependencies

- **Story 01** — Data Models & Config Parsing (uses `PoksBucket`)

## Reference

- [specs.md — Buckets](../specs.md#2-configuration-file-poksjson)
- [specs.md — Installation Flow](../specs.md#3-installation-flow) (step 1: Resolve)

## Scope

### Bucket Sync

Create `src/poks/bucket.py`:

- `sync_bucket(bucket: PoksBucket, buckets_dir: Path) -> Path` — clones the bucket repo to `buckets_dir/<name>` if it doesn't exist, or pulls the latest if it does. Returns the local path. Use `subprocess` to call `git clone` / `git pull`.

### Manifest Lookup

- `find_manifest(app_name: str, bucket_path: Path) -> Path` — looks for `<app_name>.json` in the bucket directory. Raises a descriptive error if not found.

### Sync All Buckets

- `sync_all_buckets(buckets: list[PoksBucket], buckets_dir: Path) -> dict[str, Path]` — syncs all buckets and returns a mapping of `bucket name -> local path`.

## Acceptance Criteria

- [x] `sync_bucket` clones a new bucket.
- [x] `sync_bucket` pulls an existing bucket.
- [x] `find_manifest` returns the correct path for an existing manifest.
- [x] `find_manifest` raises an error for a missing manifest.
- [x] Tests mock `subprocess` calls (no real Git operations).
- [x] `pypeline run` passes.
