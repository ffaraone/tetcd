"""Typer-based CLI entry point for the tetcd TUI."""

from __future__ import annotations

from typing import Any

import typer

from tetcd import __version__
from tetcd.config import settings
from tetcd.etcd.client import EtcdClientProtocol, Server, ServerConfig
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
    host: str = typer.Option(None, "--host", "-H", help="etcd host (ad-hoc server)"),
    port: int = typer.Option(None, "--port", "-p", help="etcd port (ad-hoc server)"),
    api_version: str = typer.Option(
        None, "--api", "-v", help="etcd API version: v2 or v3 (ad-hoc server)"
    ),
    label: str = typer.Option(None, "--label", "-l", help="Display label for the ad-hoc server"),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the tetcd version and exit.",
    ),
) -> None:
    """Launch the tetcd TUI browser.

    If any of ``--host`` / ``--port`` / ``--api`` is supplied, a single
    ad-hoc server is built from those flags and the ``servers`` list in
    ``settings.toml`` is ignored. Otherwise the configured server list is
    used (falling back to one local server if nothing is configured).
    """
    servers = _resolve_servers(host=host, port=port, api_version=api_version, label=label)
    TetcdApp(servers=servers).run()


def _resolve_servers(
    *, host: str | None, port: int | None, api_version: str | None, label: str | None
) -> list[Server]:
    """Build the server list from CLI flags (if any) or from settings."""
    if host or port or api_version or label:
        resolved_host = host or "localhost"
        resolved_port = port or 2379
        resolved_api = api_version or "v3"
        resolved_label = label or f"{resolved_host}:{resolved_port}"
        return [
            _build(
                ServerConfig(
                    label=resolved_label,
                    api=resolved_api,
                    host=resolved_host,
                    port=resolved_port,
                )
            )
        ]

    raw = settings.get("servers", []) or []
    configured = [_to_config(entry) for entry in raw]
    if not configured:
        configured = [ServerConfig(label="Local", api="v3", host="localhost", port=2379)]
    return [_build(config) for config in configured]


def _build(config: ServerConfig) -> Server:
    """Instantiate the correct backend client for ``config``."""
    client: EtcdClientProtocol
    if config.api == "v2":
        client = EtcdV2Client(host=config.host, port=config.port)
    else:
        client = EtcdV3Client(host=config.host, port=config.port)
    return Server(config=config, client=client)


def _to_config(entry: Any) -> ServerConfig:
    """Coerce a settings entry (dict or attribute object) into a :class:`ServerConfig`."""
    if isinstance(entry, dict):
        return ServerConfig(
            label=str(entry["label"]),
            api=str(entry.get("api", "v3")),
            host=str(entry.get("host", "localhost")),
            port=int(entry.get("port", 2379)),
        )
    return ServerConfig(
        label=str(entry.label),
        api=str(getattr(entry, "api", "v3")),
        host=str(getattr(entry, "host", "localhost")),
        port=int(getattr(entry, "port", 2379)),
    )


if __name__ == "__main__":
    app()
