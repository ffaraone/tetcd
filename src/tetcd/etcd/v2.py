from __future__ import annotations

from typing import Any

import httpx

from tetcd.etcd.client import EtcdNode


class EtcdV2Client:
    """etcd v2 HTTP API client."""

    def __init__(self, host: str = "localhost", port: int = 2379) -> None:
        self._base = f"http://{host}:{port}/v2/keys"
        self._health_url = f"http://{host}:{port}/health"
        self._http = httpx.Client(timeout=5.0)

    def get(self, key: str) -> EtcdNode | None:
        resp = self._http.get(f"{self._base}{key}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return self._parse_node(resp.json()["node"])

    def list(self, prefix: str = "/") -> list[EtcdNode]:
        resp = self._http.get(f"{self._base}{prefix}")
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        node = resp.json()["node"]
        return [self._parse_node(n) for n in node.get("nodes", [])]

    def put(self, key: str, value: str) -> None:
        resp = self._http.put(f"{self._base}{key}", data={"value": value})
        resp.raise_for_status()

    def make_dir(self, key: str) -> None:
        resp = self._http.put(f"{self._base}{key}", data={"dir": "true"})
        resp.raise_for_status()

    def delete(self, key: str, recursive: bool = False) -> None:
        params: dict[str, str] = {}
        if recursive:
            params["recursive"] = "true"
        node = self.get(key)
        if node and node.is_dir and not recursive:
            params["dir"] = "true"
        resp = self._http.delete(f"{self._base}{key}", params=params)
        resp.raise_for_status()

    def health(self) -> bool:
        try:
            resp = self._http.get(self._health_url)
            return resp.status_code == 200
        except httpx.RequestError:
            return False

    def _parse_node(self, data: dict[str, Any]) -> EtcdNode:
        return EtcdNode(
            key=data["key"],
            value=data.get("value"),
            is_dir=data.get("dir", False),
            children=[self._parse_node(n) for n in data.get("nodes", [])],
        )
