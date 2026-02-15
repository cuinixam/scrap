"""Install a tool directly from a manifest file (no bucket needed)."""

from pathlib import Path

from poks.poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")

# Install directly from a manifest file.
# The app name is derived from the filename (e.g., cmake.json -> cmake).
installed = poks.install_from_manifest(Path(__file__).parent / "cmake.json", version="4.2.3")

print(f"Installed {installed.name}@{installed.version} -> {installed.install_dir}")
