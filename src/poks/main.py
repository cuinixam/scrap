"""CLI entry point for Poks package manager."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger, time_it

from poks import __version__
from poks.poks import Poks
from poks.scoop import convert_scoop_manifest

package_name = "poks"
DEFAULT_ROOT_DIR = Path.home() / ".poks"


app = typer.Typer(
    name=package_name,
    help="A lightweight archive downloader for pre-built binary dependencies.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback(invoke_without_command=True)
def version(
    version: bool = typer.Option(None, "--version", "-v", is_eager=True, help="Show version and exit."),
) -> None:
    if version:
        typer.echo(f"{package_name} {__version__}")
        raise typer.Exit()


@app.command(help="Search for apps in available buckets.")
@time_it("search")
def search(
    query: Annotated[str, typer.Argument(help="Search query (substring).")],
    update: Annotated[bool, typer.Option("--update/--no-update", help="Update buckets before searching.")] = True,
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)
    results = poks.search(query, update=update)

    if not results:
        typer.echo(f"No apps found matching '{query}'.")
        return

    typer.echo(f"Found {len(results)} matching apps:")
    for app_name in results:
        typer.echo(f"  {app_name}")


def _validate_install_args(
    config_file: Path | None,
    app_name: str | None,
    version: str | None,
    manifest: Path | None,
    bucket: str | None,
) -> bool:
    """Validate install command arguments. Returns True if valid, logs error and returns False otherwise."""
    modes = sum(bool(x) for x in (config_file, app_name, manifest))
    if modes == 0:
        logger.error("Specify one of: --config, --app, or --manifest")
        return False
    if modes > 1:
        logger.error("Options --config, --app, and --manifest are mutually exclusive.")
        return False
    if (app_name or manifest) and not version:
        logger.error("--version is required with --app or --manifest.")
        return False
    if manifest and bucket:
        logger.error("--bucket cannot be used with --manifest.")
        return False
    if config_file and (version or bucket):
        logger.error("--version and --bucket cannot be used with --config.")
        return False
    return True


@app.command(help="Install apps from a config file, a bucket, or a manifest file.")
@time_it("install")
def install(
    app_name: Annotated[str | None, typer.Option("--app", help="App name to install.")] = None,
    version: Annotated[str | None, typer.Option("--version", help="Version to install.")] = None,
    manifest: Annotated[Path | None, typer.Option("--manifest", "-m", help="Path to an app manifest file.")] = None,
    config_file: Annotated[Path | None, typer.Option("-c", "--config", help="Path to poks.json configuration file.")] = None,
    bucket: Annotated[str | None, typer.Option("--bucket", help="Bucket name or URL.")] = None,
    cache: Annotated[bool, typer.Option("--cache/--no-cache", help="Use download cache.")] = True,
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    if not _validate_install_args(config_file, app_name, version, manifest, bucket):
        raise typer.Exit(1)

    poks = Poks(root_dir=root_dir, use_cache=cache)

    try:
        if config_file:
            result = poks.install(config_file)
            for app in result.apps:
                logger.info(app.format_status())
        elif manifest:
            app = poks.install_from_manifest(manifest, version)  # type: ignore[arg-type]
            logger.info(app.format_status())
        elif app_name:
            app = poks.install_app(app_name, version, bucket)  # type: ignore[arg-type]
            logger.info(app.format_status())
    except (ValueError, FileNotFoundError) as e:
        logger.error(str(e))
        raise typer.Exit(1) from e


@app.command(help="Uninstall apps.")
@time_it("uninstall")
def uninstall(
    app_spec: Annotated[str | None, typer.Argument(help="App to uninstall. Format: name or name@version")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Uninstall all apps.")] = False,
    wipe: Annotated[bool, typer.Option("--wipe", help="Also remove the download cache.")] = False,
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)

    if all_apps:
        poks.uninstall(all_apps=True, wipe=wipe)
    elif app_spec:
        if "@" in app_spec:
            name, version = app_spec.split("@", 1)
            poks.uninstall(app_name=name, version=version, wipe=wipe)
        else:
            poks.uninstall(app_name=app_spec, wipe=wipe)
    else:
        logger.error("Specify an app to uninstall or use --all")
        raise typer.Exit(1)


@app.command(name="list", help="List installed apps.")
@time_it("list")
def list_apps(
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)
    result = poks.list_installed()

    if not result.apps:
        typer.echo("No apps installed.")
        return

    # Simple table formatting
    typer.echo(f"{'Name':<20} {'Version':<15} {'Install Dir'}")
    typer.echo("-" * 70)
    for installed_app in result.apps:
        typer.echo(f"{installed_app.name:<20} {installed_app.version:<15} {installed_app.install_dir}")


@app.command(name="convert-scoop", help="Convert a Scoop manifest to a Poks manifest.")
def convert_scoop(
    scoop_manifest: Annotated[Path, typer.Argument(help="Path to a Scoop manifest.json file.")],
    output: Annotated[Path | None, typer.Option("--output", "-o", help="Output file path.")] = None,
) -> None:
    if not scoop_manifest.exists():
        logger.error(f"File not found: {scoop_manifest}")
        raise typer.Exit(1)

    manifest = convert_scoop_manifest(scoop_manifest)

    if output is None:
        # Derive app name from scoop directory structure: apps/<name>/<version>/manifest.json
        parent_parts = scoop_manifest.resolve().parts
        app_name = scoop_manifest.stem
        if len(parent_parts) >= 3 and parent_parts[-1].lower() == "manifest.json":
            app_name = parent_parts[-3]
        output = Path.cwd() / f"{app_name}.json"

    manifest.to_json_file(output)
    typer.echo(f"Poks manifest written to: {output}")


def main() -> int:
    try:
        setup_logger()
        app()
        return 0
    except UserNotificationException as e:
        logger.error(f"{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
