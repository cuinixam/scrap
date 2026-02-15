"""Install a single app from a bucket."""

from pathlib import Path

from poks.poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")

# Install from a bucket URL (cloned on-the-fly if not already present)
installed = poks.install_app("cmake", "4.2.3", bucket="https://github.com/cuinixam/poks-bucket.git")

# Search all local buckets for the app
installed = poks.install_app("cmake", "4.2.3")

print(f"Installed {installed.name}@{installed.version} -> {installed.install_dir}")
