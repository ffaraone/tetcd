from __future__ import annotations

import httpx
import pytest
import respx

from tetcd.etcd.v2 import EtcdV2Client

BASE = "http://localhost:2379/v2/keys"


@pytest.fixture
def client() -> EtcdV2Client:
    return EtcdV2Client(host="localhost", port=2379)


@respx.mock
def test_get_existing_key(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/app/host").mock(
        return_value=httpx.Response(
            200,
            json={"action": "get", "node": {"key": "/app/host", "value": "localhost"}},
        )
    )
    node = client.get("/app/host")
    assert node is not None
    assert node.key == "/app/host"
    assert node.value == "localhost"
    assert not node.is_dir


@respx.mock
def test_get_missing_key(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/missing").mock(return_value=httpx.Response(404, json={}))
    node = client.get("/missing")
    assert node is None


@respx.mock
def test_get_directory(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/app").mock(
        return_value=httpx.Response(
            200,
            json={
                "action": "get",
                "node": {
                    "key": "/app",
                    "dir": True,
                    "nodes": [
                        {"key": "/app/host", "value": "localhost"},
                        {"key": "/app/port", "value": "8080"},
                    ],
                },
            },
        )
    )
    node = client.get("/app")
    assert node is not None
    assert node.is_dir
    assert len(node.children) == 2


@respx.mock
def test_list(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/app").mock(
        return_value=httpx.Response(
            200,
            json={
                "action": "get",
                "node": {
                    "key": "/app",
                    "dir": True,
                    "nodes": [
                        {"key": "/app/host", "value": "localhost"},
                        {"key": "/app/port", "value": "8080"},
                    ],
                },
            },
        )
    )
    nodes = client.list("/app")
    assert len(nodes) == 2
    keys = {n.key for n in nodes}
    assert "/app/host" in keys
    assert "/app/port" in keys


@respx.mock
def test_put_key(client: EtcdV2Client) -> None:
    respx.put(f"{BASE}/app/host").mock(
        return_value=httpx.Response(
            201,
            json={"action": "set", "node": {"key": "/app/host", "value": "newhost"}},
        )
    )
    client.put("/app/host", "newhost")  # should not raise


@respx.mock
def test_make_dir(client: EtcdV2Client) -> None:
    respx.put(f"{BASE}/newdir").mock(
        return_value=httpx.Response(
            201,
            json={"action": "set", "node": {"key": "/newdir", "dir": True}},
        )
    )
    client.make_dir("/newdir")  # should not raise


@respx.mock
def test_delete_key(client: EtcdV2Client) -> None:
    # First GET call (inside delete to check if dir)
    respx.get(f"{BASE}/app/host").mock(
        return_value=httpx.Response(
            200,
            json={"action": "get", "node": {"key": "/app/host", "value": "localhost"}},
        )
    )
    respx.delete(f"{BASE}/app/host").mock(
        return_value=httpx.Response(200, json={"action": "delete"})
    )
    client.delete("/app/host")  # should not raise


@respx.mock
def test_health_ok(client: EtcdV2Client) -> None:
    respx.get("http://localhost:2379/health").mock(
        return_value=httpx.Response(200, json={"health": "true"})
    )
    assert client.health() is True


@respx.mock
def test_health_fail(client: EtcdV2Client) -> None:
    respx.get("http://localhost:2379/health").mock(side_effect=httpx.ConnectError("refused"))
    assert client.health() is False


@respx.mock
def test_list_missing_returns_empty(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/missing").mock(return_value=httpx.Response(404, json={}))
    assert client.list("/missing") == []


@respx.mock
def test_delete_dir_non_recursive_sends_dir_param(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/somedir").mock(
        return_value=httpx.Response(
            200,
            json={"action": "get", "node": {"key": "/somedir", "dir": True}},
        )
    )
    route = respx.delete(f"{BASE}/somedir").mock(
        return_value=httpx.Response(200, json={"action": "delete"})
    )
    client.delete("/somedir", recursive=False)
    call = route.calls[0]
    assert "dir=true" in str(call.request.url)


@respx.mock
def test_delete_recursive(client: EtcdV2Client) -> None:
    respx.get(f"{BASE}/somedir").mock(
        return_value=httpx.Response(
            200,
            json={"action": "get", "node": {"key": "/somedir", "dir": True}},
        )
    )
    route = respx.delete(f"{BASE}/somedir").mock(
        return_value=httpx.Response(200, json={"action": "delete"})
    )
    client.delete("/somedir", recursive=True)
    call = route.calls[0]
    assert "recursive=true" in str(call.request.url)
