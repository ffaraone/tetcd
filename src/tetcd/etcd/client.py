from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class EtcdNode:
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
        parts = self.key.rstrip("/").rsplit("/", 1)
        return parts[0] if len(parts) > 1 else "/"


@runtime_checkable
class EtcdClientProtocol(Protocol):
    def get(self, key: str) -> EtcdNode | None: ...
    def list(self, prefix: str) -> list[EtcdNode]: ...
    def put(self, key: str, value: str) -> None: ...
    def make_dir(self, key: str) -> None: ...
    def delete(self, key: str, recursive: bool = False) -> None: ...
    def health(self) -> bool: ...
