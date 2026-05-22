"""Typer-based CLI entry point for the tetcd TUI."""

from __future__ import annotations

import typer

from tetcd import __version__
from tetcd.config import settings
from tetcd.etcd.client import EtcdClientProtocol
from tetcd.etcd.v2 import EtcdV2Client
from tetcd.etcd.v3 import EtcdV3Client
from tetcd.tui.app import TetcdApp

app = typer.Typer(name="tetcd", help="A TUI for managing etcd (v2 and v3).", add_completion=False)


def _version_callback(value: bool) -> None:
    """Print the installed tetcd version and exit when ``--version`` is passed."""
    if value:
        typer.echo(f"tetcd {__version__}")
        raise typer.Exit()


@app.command()
def main(
    host: str = typer.Option(None, "--host", "-H", help="etcd host"),
    port: int = typer.Option(None, "--port", "-p", help="etcd port"),
    api_version: str = typer.Option(None, "--api", "-v", help="etcd API version: v2 or v3"),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the tetcd version and exit.",
    ),
) -> None:
    """Launch the tetcd TUI browser against the resolved etcd endpoint.

    Connection parameters are resolved with CLI flags taking precedence over
    ``TETCD_*`` environment variables and ``settings.toml`` defaults.
    """
    resolved_host: str = host or settings.get("etcd_host", "localhost")
    resolved_port: int = port or settings.get("etcd_port", 2379)
    resolved_version: str = api_version or settings.get("etcd_version", "v3")

    client: EtcdClientProtocol
    if resolved_version == "v2":
        client = EtcdV2Client(host=resolved_host, port=resolved_port)
    else:
        client = EtcdV3Client(host=resolved_host, port=resolved_port)

    TetcdApp(client=client).run()


if __name__ == "__main__":
    app()
