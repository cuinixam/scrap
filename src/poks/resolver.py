"""Variable expansion and archive resolution for Poks manifests."""

import re

from poks.domain import PoksAppVersion, PoksArchive


def expand_variables(template: str, variables: dict[str, str]) -> str:
    """
    Replace ``${key}`` placeholders with values from *variables*.

    Unknown keys are left as-is.
    """

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return variables.get(key, match.group(0))

    return re.sub(r"\$\{(\w+)}", _replace, template)


def resolve_archive(version: PoksAppVersion, target_os: str, target_arch: str) -> PoksArchive:
    """
    Return the first archive matching the given OS and architecture.

    Raises:
        ValueError: If no archive matches the requested platform.

    """
    for archive in version.archives:
        if archive.os == target_os and archive.arch == target_arch:
            return archive
    supported = [(a.os, a.arch) for a in version.archives]
    raise ValueError(f"No archive for os={target_os!r}, arch={target_arch!r}. Supported: {supported}")


def resolve_download_url(version: PoksAppVersion, archive: PoksArchive) -> str:
    """
    Build the fully-expanded download URL for the given archive.

    Uses ``archive.url`` when present, otherwise falls back to the
    version-level URL template.

    Raises:
        ValueError: If neither the archive nor the version provides a URL.

    """
    template = archive.url or version.url
    if not template:
        raise ValueError("No URL: the archive has no url and the version has no root url template.")
    variables: dict[str, str] = {
        "version": version.version,
        "os": archive.os,
        "arch": archive.arch,
    }
    if archive.ext:
        variables["ext"] = archive.ext
    return expand_variables(template, variables)
