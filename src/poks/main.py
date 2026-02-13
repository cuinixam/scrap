"""CLI entry point for Poks package manager."""

import sys
from pathlib import Path
from typing import Annotated

import typer
from py_app_dev.core.exceptions import UserNotificationException
from py_app_dev.core.logging import logger, setup_logger, time_it

from poks import __version__
from poks.poks import Poks

package_name = "poks"
DEFAULT_ROOT_DIR = Path.home() / ".poks"

app = typer.Typer(
    name=package_name,
    help="A lightweight archive downloader for pre-build binary dependencies.",
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


@app.command(help="Install apps from configuration file or install a single app.")
@time_it("install")
def install(
    app_spec: Annotated[str | None, typer.Argument(help="App to install. Format: name@version")] = None,
    config_file: Annotated[Path | None, typer.Option("-c", "--config", help="Path to poks.json configuration file.")] = None,
    bucket: Annotated[str | None, typer.Option("--bucket", help="Bucket name or URL for single-app install.")] = None,
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    if config_file and app_spec:
        logger.error("Cannot use both -c/--config and app@version. Choose one install mode.")
        raise typer.Exit(1)

    if not config_file and not app_spec:
        logger.error("Specify either -c/--config or app@version")
        raise typer.Exit(1)

    poks = Poks(root_dir=root_dir)

    if config_file:
        poks.install(config_file)
        logger.info("Installation complete.")
        return

    if not app_spec:
        logger.error("Specify either -c/--config or app@version")
        raise typer.Exit(1)

    try:
        poks.install_app(app_spec, bucket)
        name, version = app_spec.split("@", 1)
        logger.info(f"Successfully installed {name}@{version}")
    except ValueError as e:
        logger.error(str(e))
        raise typer.Exit(1) from e


@app.command(help="Uninstall apps.")
@time_it("uninstall")
def uninstall(
    app_spec: Annotated[str | None, typer.Argument(help="App to uninstall. Format: name or name@version")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="Uninstall all apps.")] = False,
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)

    if all_apps:
        poks.uninstall(all_apps=True)
    elif app_spec:
        if "@" in app_spec:
            name, version = app_spec.split("@", 1)
            poks.uninstall(app_name=name, version=version)
        else:
            poks.uninstall(app_name=app_spec)
    else:
        logger.error("Specify an app to uninstall or use --all")
        raise typer.Exit(1)


@app.command(name="list", help="List installed apps.")
@time_it("list")
def list_apps(
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)
    apps = poks.list_installed()

    if not apps:
        typer.echo("No apps installed.")
        return

    # Simple table formatting
    # Header
    typer.echo(f"{'Name':<20} {'Version':<15} {'Bucket':<15}")
    typer.echo("-" * 52)
    for app in apps:
        typer.echo(f"{app.name:<20} {app.version:<15} {app.bucket:<15}")


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
