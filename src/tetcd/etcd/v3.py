"""etcd v3 client built on the gRPC-gateway HTTP API via ``etcd3gw``.

etcd v3 has a flat key space; directory semantics expected by the TUI are
simulated here using ``/``-separated key prefixes and a ``.keep`` sentinel
key for empty directories.
"""

from __future__ import annotations

from typing import Any

import etcd3gw

from tetcd.etcd.client import EtcdNode, EtcdNodes


class EtcdV3Client:
    """etcd v3 client via the gRPC-gateway HTTP API (etcd3gw)."""

    def __init__(self, host: str = "localhost", port: int = 2379) -> None:
        """Connect an ``etcd3gw`` client pointing at ``host:port``."""
        self._client: Any = etcd3gw.client(host=host, port=port)

    def get(self, key: str) -> EtcdNode | None:
        """Return the leaf node at ``key`` or ``None`` if absent."""
        result: list[Any] = self._client.get(key)
        if not result:
            return None
        raw = result[0]
        value = raw.decode() if isinstance(raw, bytes) else str(raw)
        return EtcdNode(key=key, value=value, is_dir=False)

    def list(self, prefix: str = "/") -> EtcdNodes:
        """Return the immediate children of ``prefix``.

        Because v3 stores a flat key space, this method synthesises virtual
        directory nodes whenever a child key contains a further ``/``
        separator beneath ``prefix``.
        """
        normalized = prefix.rstrip("/") + "/"
        all_pairs: list[Any] = self._client.get_prefix(normalized)
        seen: dict[str, EtcdNode] = {}

        for entry in all_pairs:
            value_raw, metadata = entry if isinstance(entry, tuple) else (entry, {})
            raw_key = metadata.get("key", b"") if isinstance(metadata, dict) else b""
            full_key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
            relative = full_key[len(normalized) :]
            parts = [p for p in relative.split("/") if p]
            if not parts:
                continue
            immediate = normalized + parts[0]
            if len(parts) > 1:
                if immediate not in seen:
                    seen[immediate] = EtcdNode(key=immediate, is_dir=True)
            else:
                decoded = value_raw.decode() if isinstance(value_raw, bytes) else str(value_raw)
                seen[immediate] = EtcdNode(key=immediate, value=decoded, is_dir=False)

        return list(seen.values())

    def put(self, key: str, value: str) -> None:
        """Write ``value`` under ``key``."""
        self._client.put(key, value)

    def make_dir(self, key: str) -> None:
        """Simulate a directory by writing an empty ``<key>/.keep`` sentinel."""
        marker = key.rstrip("/") + "/.keep"
        self._client.put(marker, "")

    def delete(self, key: str, recursive: bool = False) -> None:
        """Delete ``key``; use ``delete_prefix`` when ``recursive`` is true."""
        if recursive:
            self._client.delete_prefix(key)
        else:
            self._client.delete(key)

    def health(self) -> bool:
        """Return ``True`` when the cluster responds to ``status()``."""
        try:
            status: Any = self._client.status()
            return bool(status)
        except Exception:
            return False
