from __future__ import annotations

import typer

from tetcd.config import settings
from tetcd.etcd.client import EtcdClientProtocol
from tetcd.etcd.v2 import EtcdV2Client
from tetcd.etcd.v3 import EtcdV3Client
from tetcd.tui.app import TetcdApp

app = typer.Typer(name="tetcd", help="A TUI for managing etcd (v2 and v3).", add_completion=False)


@app.command()
def run(
    host: str = typer.Option(None, "--host", "-H", help="etcd host"),
    port: int = typer.Option(None, "--port", "-p", help="etcd port"),
    api_version: str = typer.Option(None, "--api", "-v", help="etcd API version: v2 or v3"),
) -> None:
    """Launch the tetcd TUI browser."""
    resolved_host: str = host or settings.get("etcd_host", "localhost")
    resolved_port: int = port or settings.get("etcd_port", 2379)
    resolved_version: str = api_version or settings.get("etcd_version", "v3")

    client: EtcdClientProtocol
    if resolved_version == "v2":
        client = EtcdV2Client(host=resolved_host, port=resolved_port)
    else:
        client = EtcdV3Client(host=resolved_host, port=resolved_port)

    TetcdApp(client=client).run()


@app.command()
def version() -> None:
    """Show the tetcd version."""
    from tetcd import __version__

    typer.echo(f"tetcd {__version__}")


if __name__ == "__main__":
    app()
