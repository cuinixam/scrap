"""Install a tool directly from a manifest file (no bucket needed)."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from poks.poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")

# Install directly from a manifest file.
# The app name is derived from the filename (e.g., cmake.json -> cmake).
installed = poks.install_from_manifest(Path(__file__).parent / "cmake.json", version="4.2.3")

print(f"Installed {installed.name}@{installed.version} -> {installed.install_dir}")
# Add bin to path and call "cmake --version"

# Add bin to path (installed.bin_dirs is a list of paths)
print(f"Bin dirs: {installed.bin_dirs}")
for bin_dir in installed.bin_dirs:
    os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
# which cmake
print(f"Which cmake: {shutil.which('cmake')}")
# Call "cmake --version"
subprocess.run(["cmake", "--version"], shell=True if sys.platform == "win32" else False)  # noqa: S607
