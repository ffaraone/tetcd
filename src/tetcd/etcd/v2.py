"""etcd v2 HTTP API client used by the TUI."""

from __future__ import annotations

from typing import Any

import httpx

from tetcd.etcd.client import EtcdNode, EtcdNodes


class EtcdV2Client:
    """etcd v2 HTTP API client.

    All methods raise :class:`httpx.HTTPStatusError` on non-2xx responses,
    except where explicitly handled (e.g. 404 on ``get``/``list``).
    """

    def __init__(self, host: str = "localhost", port: int = 2379) -> None:
        """Build a client pointing at ``host:port`` with a 5s HTTP timeout."""
        self._base = f"http://{host}:{port}/v2/keys"
        self._health_url = f"http://{host}:{port}/health"
        self._http = httpx.Client(timeout=5.0)

    def get(self, key: str) -> EtcdNode | None:
        """Return the node at ``key`` or ``None`` if etcd answers 404."""
        resp = self._http.get(f"{self._base}{key}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._parse_node(resp.json()["node"])

    def list(self, prefix: str = "/") -> EtcdNodes:
        """Return the immediate children of ``prefix`` (empty on 404)."""
        resp = self._http.get(f"{self._base}{prefix}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        node = resp.json()["node"]
        return [self._parse_node(n) for n in node.get("nodes", [])]

    def put(self, key: str, value: str) -> None:
        """Write ``value`` to ``key`` via ``PUT /v2/keys/<key>``."""
        resp = self._http.put(f"{self._base}{key}", data={"value": value})
        resp.raise_for_status()

    def make_dir(self, key: str) -> None:
        """Create a v2 directory at ``key`` (``PUT ?dir=true``)."""
        resp = self._http.put(f"{self._base}{key}", data={"dir": "true"})
        resp.raise_for_status()

    def delete(self, key: str, recursive: bool = False) -> None:
        """Delete ``key``. If it is a directory, set ``dir`` or ``recursive``.

        v2 requires the caller to pass ``dir=true`` when removing an empty
        directory and ``recursive=true`` when removing a non-empty one. This
        wrapper does a ``get`` first so directories are deleted with the
        right query parameter without forcing the caller to know the type.
        """
        params: dict[str, str] = {}
        if recursive:
            params["recursive"] = "true"
        node = self.get(key)
        if node and node.is_dir and not recursive:
            params["dir"] = "true"
        resp = self._http.delete(f"{self._base}{key}", params=params)
        resp.raise_for_status()

    def health(self) -> bool:
        """Return ``True`` when ``/health`` returns 200; ``False`` on any error."""
        try:
            resp = self._http.get(self._health_url)
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def _parse_node(self, data: dict[str, Any]) -> EtcdNode:
        """Recursively build an :class:`EtcdNode` from a v2 JSON node."""
        return EtcdNode(
            key=data["key"],
            value=data.get("value"),
            is_dir=data.get("dir", False),
            children=[self._parse_node(n) for n in data.get("nodes", [])],
        )
