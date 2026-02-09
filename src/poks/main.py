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


@app.command(help="Install apps from configuration file.")
@time_it("install")
def install(
    config_file: Annotated[Path, typer.Option("-c", "--config", help="Path to poks.json configuration file.")],
    root_dir: Annotated[Path, typer.Option("--root", help="Root directory for Poks.")] = DEFAULT_ROOT_DIR,
) -> None:
    poks = Poks(root_dir=root_dir)
    poks.install(config_file)


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
