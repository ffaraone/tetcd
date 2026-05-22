"""Shared pytest fixtures for the tetcd test suite."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tetcd.etcd.client import EtcdNode, Server, ServerConfig


@pytest.fixture
def sample_nodes() -> list[EtcdNode]:
    """Return a fixed set of :class:`EtcdNode` instances for shared assertions."""
    return [
        EtcdNode(key="/app", is_dir=True),
        EtcdNode(key="/app/host", value="localhost"),
        EtcdNode(key="/app/port", value="8080"),
        EtcdNode(key="/app/config", is_dir=True),
        EtcdNode(key="/app/config/debug", value="true"),
    ]


def make_server(label: str, *, client: MagicMock | None = None) -> Server:
    """Build a :class:`Server` whose ``client`` is a ``MagicMock`` by default."""
    return Server(
        config=ServerConfig(label=label, api="v3", host="localhost", port=2379),
        client=client if client is not None else MagicMock(),
    )
