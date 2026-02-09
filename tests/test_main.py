from typer.testing import CliRunner

from poks.main import app

runner = CliRunner()


def test_help() -> None:
    result = runner.invoke(
        app,
        [
            "--help",
        ],
    )
    assert result.exit_code == 0
