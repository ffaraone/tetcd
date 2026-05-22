"""Shared etcd data model and the protocol both client backends satisfy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class EtcdNode:
    """A single etcd entry, either a leaf key or a (virtual) directory."""

    key: str
    value: str | None = None
    is_dir: bool = False
    children: list[EtcdNode] = field(default_factory=list)

    @property
    def name(self) -> str:
        """The last path segment, used as the display label in the tree."""
        return self.key.rstrip("/").rsplit("/", 1)[-1] or "/"

    @property
    def parent_key(self) -> str:
        """The key one level up, or ``"/"`` when the node is the root."""
        parts = self.key.rstrip("/").rsplit("/", 1)
        return parts[0] if len(parts) > 1 else "/"


# Alias used in client signatures: the protocol's ``list`` method otherwise
# shadows the builtin in the class body, confusing static type checkers.
type EtcdNodes = list[EtcdNode]


@runtime_checkable
class EtcdClientProtocol(Protocol):
    """The minimal CRUD surface the TUI expects from any etcd backend.

    Both :class:`tetcd.etcd.v2.EtcdV2Client` and
    :class:`tetcd.etcd.v3.EtcdV3Client` implement this protocol so the TUI
    is independent of the underlying etcd API version.
    """

    def get(self, key: str) -> EtcdNode | None:
        """Return the node at ``key`` or ``None`` if it does not exist."""

    def list(self, prefix: str) -> EtcdNodes:
        """Return the immediate children of ``prefix``."""

    def put(self, key: str, value: str) -> None:
        """Write ``value`` under ``key``, creating it if needed."""

    def make_dir(self, key: str) -> None:
        """Create a directory at ``key`` (real on v2, simulated on v3)."""

    def delete(self, key: str, recursive: bool = False) -> None:
        """Delete ``key``; pass ``recursive=True`` to remove a subtree."""

    def health(self) -> bool:
        """Return ``True`` when the cluster responds to a health probe."""


@dataclass(frozen=True)
class ServerConfig:
    """Static configuration for a single etcd endpoint (label + connection).

    ``label`` is the human-readable name shown in the tree; ``api`` selects
    the backend implementation (``"v2"`` or ``"v3"``); ``host`` / ``port``
    are the network endpoint.
    """

    label: str
    api: str = "v3"
    host: str = "localhost"
    port: int = 2379


@dataclass
class Server:
    """A configured etcd endpoint paired with its live client.

    Top-level tree nodes carry a :class:`Server`; everything beneath them
    carries an :class:`EtcdNode`. Operations resolve the right client by
    walking up the tree to the enclosing server.
    """

    config: ServerConfig
    client: EtcdClientProtocol
