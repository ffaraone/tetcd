"""Shared pytest fixtures for the tetcd test suite."""

from __future__ import annotations

import pytest

from tetcd.etcd.client import EtcdNode


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
