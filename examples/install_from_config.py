"""Install tools defined in a poks.json configuration file."""

from pathlib import Path

from poks.poks import Poks

poks = Poks(root_dir=Path.home() / ".poks")

# Install all apps defined in the config file.
# The config lists buckets (git repos with manifests) and apps to install.
result = poks.install(Path(__file__).parent / "poks.json")

# Use the result to set up the environment
for app in result.apps:
    print(app.format_status())
    for bin_dir in app.bin_dirs:
        print(f"  PATH += {bin_dir}")
    for key, value in app.env.items():
        print(f"  {key}={value}")
