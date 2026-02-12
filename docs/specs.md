# Poks Package Manager

## Abstract

This document introduces **Poks**, a cross-platform (Windows, Linux, macOS), user-space package manager for Yanga. Inspired by [Scoop](https://scoop.sh/), Poks provides a uniform way to install and manage developer tools (compilers, SDKs, CLI utilities) using simple JSON manifests. It eliminates the need for OS-specific setup scripts and ensures deterministic build environments across different platforms.

## Motivation

### Problem

Developing embedded software (e.g., Zephyr projects) often requires a specific set of tools:

- **CMake**, **Ninja**, **Python**
- **Compilers** (ARM GCC, LLVM)
- **SDKs** (Zephyr SDK, ESP-IDF)
- **Host Tools** (J-Link, OpenOCD, QEMU)

Setting up these environments is currently fragmented. Users often rely on system package managers (Scoop, Apt, Homebrew) which:

1. **Update unpredictably**: A `git pull` or `apt upgrade` might change the compiler version.
2. **Require Admin Rights**: Often needed for system-wide installs.
3. **Lack Isolation**: One project might need GCC 10, another GCC 12.

### Desired State

A standalone Python application (`poks`) that:

- **Standalone**: Can be installed via `pipx install poks`.
- **Configurable**: Uses a configuration file (e.g., `poks.json`) to define *buckets* (manifest sources) and *apps* to install.
- **Deterministic**: Installs **EXACT** versions of tools into a user-defined directory.
- **No global shims**: Tools are made available via environment variables for the current process/shell only.
- **Platform Agnostic**: Uses **JSON manifests** to describe installation (URL, hash, extraction, PATH updates) for any OS.
- **Relocatable**: The apps directory works as a self-contained unit that can be easily relocated. This supports creating standalone environments (incorporating both sources and tools) for distribution, testing, or long-term archiving.

## Proposal

### Core Concepts

#### 1. Manifests

A JSON file describing an application. It supports multiple versions, each with archives for different platforms and a generic URL in case no archive URL is specified.

**Example `zephyr-sdk.json`**:

```json
{
    "description": "Zephyr SDK Bundle",
    "license": "Apache-2.0",
    "versions": [
        {
            "version": "0.16.5-1",
            "url": "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${version}/zephyr-sdk-${version}_${os}-${arch}${ext}",
            "archives": [
                {
                    "os": "windows",
                    "arch": "x86_64",
                    "ext": ".7z",
                    "sha256": "..."
                },
                {
                    "os": "linux",
                    "arch": "x86_64",
                    "ext": ".tar.xz",
                    "sha256": "..."
                },
                {
                    "os": "macos",
                    "arch": "aarch64",
                    "ext": ".tar.xz",
                    "sha256": "..."
                }
            ],
            "extract_dir": "zephyr-sdk-0.16.5-1",
            "env": {
                "ZEPHYR_SDK_INSTALL_DIR": "${dir}"
            }
        },
        {
            "version": "0.16.4",
            "url": "https://github.com/zephyrproject-rtos/sdk-ng/releases/download/v${version}/zephyr-sdk-${version}_${os}-${arch}${ext}",
            "archives": [
                {
                    "os": "linux",
                    "arch": "x86_64",
                    "ext": ".tar.xz",
                    "sha256": "..."
                }
            ],
            "extract_dir": "zephyr-sdk-0.16.4",
            "env": {
                "ZEPHYR_SDK_INSTALL_DIR": "${dir}"
            }
        }
    ]
}
```

**URL Resolution**:
If an archive entry does not specify a `url`, Poks constructs it using the root `url` template and the variables defined in the archive entry (plus `version`).

**Variable Expansion**:
Manifests support variable expansion using `${variable}` syntax:

- `${version}`: The app version from the manifest.
- `${os}`: The target operating system.
- `${arch}`: The target architecture.
- `${ext}`: The file extension from the archive entry.
- `${dir}`: The app's installation directory (e.g., `~/.poks/apps/zephyr-sdk/0.16.5-1`). Used in `env`.

**Archives List**:
The `archives` field is a list where each element defines:

- `os`: The operating system (`windows`, `linux`, `macos`).
- `arch`: The architecture (`x86_64`, `aarch64`).
- `ext`: The file extension (e.g., `.7z`, `.tar.gz`). Used for generic URL expansion. If omitted when `url` is specified, Poks auto-detects the format from the URL.
- `url`: (Optional within archive) The direct download URL. Overrides the generic URL.
- `sha256`: The SHA256 hash for verification.

**Supported Platforms**:
Poks iterates through the `archives` list to find a match for the current `(os, arch)`. If no match is found, the platform is unsupported.

#### 2. Configuration File (`poks.json`)

To install tools, the user defines a configuration file listing the *buckets* (where to find manifests) and the *apps* to install.

**Example `poks.json`**:

```json
{
    "buckets": [
        {
            "name": "main",
            "url": "https://github.com/poks/main-bucket.git"
        },
        {
            "name": "extras",
            "url": "https://github.com/poks/extras-bucket.git"
        }
    ],
    "apps": [
        {
            "name": "zephyr-sdk",
            "version": "0.16.5-1",
            "bucket": "main"
        },
        {
            "name": "cmake",
            "version": "3.28.1",
            "bucket": "main"
        },
        {
            "name": "mingw-libs",
            "version": "1.0.0",
            "bucket": "extras",
            "os": ["windows"]
        },
        {
            "name": "build-essential",
            "version": "1.0.0",
            "bucket": "extras",
            "os": ["linux", "macos"]
        }
    ]
}
```

- **Buckets**: A Git URL pointing to a repository containing manifest files. Poks clones/pulls them to resolve manifest names.
- **Apps**: Specifies the `name`, `version`, and `bucket` (required). The manifest is looked up in the specified bucket.
- **Platform Filtering**: Apps can be restricted to specific operating systems (`os`) or architectures (`arch`).
  - `os`: List of supported OSs (e.g., `["windows", "linux"]`). If omitted, supports all.
  - `arch`: List of supported architectures (e.g., `["x86_64"]`). If omitted, supports all.

#### 3. Installation Flow

1. **Resolve**:
    - Parse `poks.json`.
    - Fetch/Update buckets.
    - Find manifest for each app in the buckets (e.g., `buckets/main/cmake.json`).
    - Select the requested version from the manifest's `versions` list.
2. **Download**: Fetch archive defined in the version entry for the current platform.
3. **Verify**: Check SHA256 hash.
4. **Extract**: Unpack to `apps/<app>/<version>`.
5. **Configure**:
    - Generate an environment object (PATH, env_vars) for the installed toolset.

### Architecture

#### Directory Structure

```text
~/.poks/
  ├── apps/
  │   ├── zephyr-sdk/
  │   │   └── 0.16.5-1/
  │   └── cmake/
  │       └── 3.28.1/
  ├── buckets/
  │   ├── main/
  │   └── extras/
  └── cache/
```

- **apps/**: Extracted application files, organized by name and version.
- **buckets/**: Cloned Git repositories containing manifest files.
- **cache/**: Downloaded archives. Poks checks the cache before downloading. Cache entries can be manually cleared.

#### Python API

Python modules can interact with Poks programmatically.

```python
from poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")
# Install apps from config file
env_updates = poks.install("path/to/poks.json")

# env_updates contains modified PATH and other vars
# e.g., {'PATH': '/home/user/.poks/apps/zephyr-sdk/0.16.5-1/bin:...', 'ZEPHYR_SDK_INSTALL_DIR': ...}
```

## Specification

### Manifest Schema

```python
@dataclass
class PoksBucket:
    name: str
    url: str

@dataclass
class PoksApp:
    name: str
    version: str
    bucket: str  # Required - no default bucket
    os: Optional[List[str]] = None
    arch: Optional[List[str]] = None

@dataclass
class PoksConfig:
    buckets: List[PoksBucket]
    apps: List[PoksApp]

@dataclass
class PoksArchive:
    os: str
    arch: str
    sha256: str
    ext: Optional[str] = None  # Auto-detected from url if omitted
    url: Optional[str] = None

@dataclass
class PoksAppVersion:
    version: str
    archives: list[PoksArchive]
    extract_dir: str | None = None
    bin: list[str] | None = None
    env: dict[str, str] | None = None
    license: str | None = None
    yanked: str | None = None  # Reason string if yanked
    url: str | None = None # Generic URL template for this version

@dataclass
class PoksManifest:
    description: str
    versions: list[PoksAppVersion]
    schema_version: str = "1.0.0"
    license: str | None = None
    homepage: str | None = None
```

### Archive Support

- **Zip**: Built-in `zipfile`.
- **Tar (gz, xz, bz2)**: Built-in `tarfile`.
- **7z**: `py7zr` (third-party dependency).

### CLI Commands

Poks intentionally does **not** have `update` or `clean` commands. Different projects may require different versions of the same tool, so multiple versions can coexist. Users explicitly manage which versions to uninstall.

```bash
# Install tools defined in poks.json
poks install -c poks.json

# Install a specific tool (searches all local buckets)
poks install zephyr-sdk@0.16.5-1

# Install from a specific local bucket
poks install zephyr-sdk@0.16.5-1 --bucket main

# Install from a bucket URL (cloned on-the-fly)
poks install zephyr-sdk@0.16.5-1 --bucket https://github.com/poks/main-bucket.git

# Uninstall a specific version of an app
poks uninstall zephyr-sdk@0.16.5-1

# Uninstall all versions of an app
poks uninstall zephyr-sdk

# Uninstall all apps (reset)
poks uninstall --all
```

## Benefits

- **True Cross-Platform**: Same config for Windows, Mac, Linux.
- **Zero System Dependencies**: Only Python is required.
- **Isolation**: Tools are installed in user space, avoiding system conflicts.
- **Reproducibility**: Exact versions of tools are pinned in manifests.
