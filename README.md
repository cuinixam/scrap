# Poks

<p align="center">
  <a href="https://github.com/cuinixam/poks/actions/workflows/ci.yml?query=branch%3Amain">
    <img src="https://img.shields.io/github/actions/workflow/status/cuinixam/poks/ci.yml?branch=main&label=CI&logo=github&style=flat-square" alt="CI Status" >
  </a>
  <a href="https://codecov.io/gh/cuinixam/poks">
    <img src="https://img.shields.io/codecov/c/github/cuinixam/poks.svg?logo=codecov&logoColor=fff&style=flat-square" alt="Test coverage percentage">
  </a>
</p>
<p align="center">
  <a href="https://github.com/astral-sh/uv">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json" alt="uv">
  </a>
  <a href="https://github.com/astral-sh/ruff">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json" alt="Ruff">
  </a>
  <a href="https://github.com/cuinixam/pypeline">
    <img src="https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/cuinixam/pypeline/refs/heads/main/assets/badge/v0.json" alt="pypeline">
  </a>
  <a href="https://github.com/pre-commit/pre-commit">
    <img src="https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white&style=flat-square" alt="pre-commit">
  </a>
</p>
<p align="center">
  <a href="https://pypi.org/project/poks/">
    <img src="https://img.shields.io/pypi/v/poks.svg?logo=python&logoColor=fff&style=flat-square" alt="PyPI Version">
  </a>
  <img src="https://img.shields.io/pypi/pyversions/poks.svg?style=flat-square&logo=python&amp;logoColor=fff" alt="Supported Python versions">
  <img src="https://img.shields.io/pypi/l/poks.svg?style=flat-square" alt="License">
</p>

---

**Source Code**: <a href="https://github.com/cuinixam/poks" target="_blank">https://github.com/cuinixam/poks</a>

---

A lightweight, cross-platform archive downloader for pre-built binary dependencies. Inspired by [Scoop](https://scoop.sh/), Poks provides a uniform way to install and manage developer tools using simple JSON manifests.

While Poks includes a CLI, its **main purpose is to be used programmatically** to manage dependencies in your Python projects and automation scripts.

## Features

- **Programmatic API**: First-class Python support for integrating into your tools
- **Cross-Platform**: Works on Windows, Linux, and macOS
- **No Admin Rights**: Installs tools in user space
- **Deterministic**: Pin exact versions in manifests for reproducible builds
- **Relocatable**: The apps directory is self-contained and portable

## Installation

```bash
pip install poks
```

For CLI-only usage:

```bash
pipx install poks
```

## Concepts

- **App**: A tool or dependency you want to install (e.g., CMake, a compiler toolchain). Each app has a name and one or more versions.
- **Manifest**: A JSON file that describes an app — its download URLs, checksums, and platform-specific archives. One manifest per app (e.g., `cmake.json`). See [examples/cmake.json](examples/cmake.json).
- **Bucket**: A git repository containing a collection of manifests. Buckets are how manifests are shared and distributed.
- **Config file**: A JSON file (`poks.json`) that ties it all together — it lists which buckets to use and which apps (with versions) to install from them. See [examples/poks.json](examples/poks.json).

## Installing apps

### From a config file

Use a config file when you want to define a reproducible set of tools for a project. The config references one or more buckets and lists the apps to install from them.

```bash
poks install --config poks.json
```

### From a bucket

Install a single app directly, without a config file. Poks looks up the app's manifest in the specified bucket.

```bash
poks install --app cmake --version 3.28.1 --bucket main
poks install --app cmake --version 3.28.1 --bucket https://github.com/poks/main-bucket.git
poks install --app cmake --version 3.28.1   # searches all local buckets
```

### From a manifest file

Install directly from a local manifest file — no bucket needed. Useful for testing a manifest before publishing it to a bucket. The app name is derived from the filename.

```bash
poks install --manifest cmake.json --version 4.2.3
```

### Other commands

```bash
poks uninstall cmake@3.28.1       # specific version
poks uninstall cmake              # all versions
poks uninstall --all              # everything
poks search cmake                 # search across local buckets
poks list                         # list installed apps
```

## Python API

Poks is designed to be used programmatically. See [examples/](examples/) for complete scripts.

```python
from pathlib import Path
from poks.poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")

poks.install(Path("poks.json"))                              # from config file
poks.install_app("cmake", "3.28.1", bucket="main")           # from bucket
poks.install_from_manifest(Path("cmake.json"), "3.28.1")     # from manifest file
```

## Manifest format

For the manifest schema and detailed specifications, see [docs/specs.md](docs/specs.md).

## Contributing

This project uses [pypeline](https://github.com/cuinixam/pypeline) for build automation and `uv` for dependency management.

```bash
# Install pypeline
uv tool install pypeline-runner

# Run full pipeline (lint + tests)
pypeline run
```

For AI agents, see [AGENTS.md](AGENTS.md).

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
