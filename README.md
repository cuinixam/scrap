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

## Features

- **Cross-Platform**: Works on Windows, Linux, and macOS
- **No Admin Rights**: Installs tools in user space
- **Deterministic**: Pin exact versions in manifests for reproducible builds
- **Relocatable**: The apps directory is self-contained and portable

## Installation

Install via pipx(or your favorite package manager):

```bash
pipx install poks
```

## Quick Start

Create a `poks.json` configuration file:

```json
{
    "buckets": [
        {
            "name": "main",
            "url": "https://github.com/poks/main-bucket.git"
        }
    ],
    "apps": [
        {
            "name": "cmake",
            "version": "3.28.1",
            "bucket": "main"
        }
    ]
}
```

Install the defined tools:

```bash
poks install -c poks.json
```

## CLI Commands

```bash
# Install tools from config file
poks install -c poks.json

# Install a specific tool
poks install zephyr-sdk@0.16.5-1 --bucket main

# Uninstall a specific version
poks uninstall zephyr-sdk@0.16.5-1

# Uninstall all versions of an app
poks uninstall zephyr-sdk

# Uninstall everything
poks uninstall --all
```

## Documentation

For detailed specifications and manifest format, see [docs/specs.md](docs/specs.md).

## Development

This project uses [pypeline](https://github.com/cuinixam/pypeline) for build automation.

```bash
# Run full pipeline (lint + tests)
pypeline run

# Run only linting
pypeline run --step PreCommit

# Run tests with specific Python version
pypeline run --step CreateVEnv --step PyTest --single --input python_version=3.13
```

For AI agents and contributors, see [AGENTS.md](AGENTS.md) for development guidelines.

## Credits

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)

This package was created with
[Copier](https://copier.readthedocs.io/) and the
[browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template)
project template.
