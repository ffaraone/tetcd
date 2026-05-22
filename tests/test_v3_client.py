from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tetcd.etcd.v3 import EtcdV3Client


@pytest.fixture
def mock_etcd3gw() -> MagicMock:
    mock_client = MagicMock()
    with patch("tetcd.etcd.v3.etcd3gw") as mock_module:
        mock_module.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def client(mock_etcd3gw: MagicMock) -> EtcdV3Client:
    return EtcdV3Client(host="localhost", port=2379)


def test_get_existing_key(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.get.return_value = [b"localhost"]
    node = client.get("/app/host")
    assert node is not None
    assert node.key == "/app/host"
    assert node.value == "localhost"
    assert not node.is_dir


def test_get_missing_key(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.get.return_value = []
    node = client.get("/missing")
    assert node is None


def test_list_flat_keys(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.get_prefix.return_value = [
        (b"localhost", {"key": b"/app/host"}),
        (b"8080", {"key": b"/app/port"}),
    ]
    nodes = client.list("/app")
    assert len(nodes) == 2
    keys = {n.key for n in nodes}
    assert "/app/host" in keys
    assert "/app/port" in keys


def test_list_creates_virtual_dirs(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.get_prefix.return_value = [
        (b"true", {"key": b"/app/config/debug"}),
        (b"localhost", {"key": b"/app/host"}),
    ]
    nodes = client.list("/app")
    node_map = {n.key: n for n in nodes}
    assert "/app/config" in node_map
    assert node_map["/app/config"].is_dir
    assert "/app/host" in node_map
    assert not node_map["/app/host"].is_dir


def test_put(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    client.put("/app/host", "newhost")
    mock_etcd3gw.put.assert_called_once_with("/app/host", "newhost")


def test_delete_single(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    client.delete("/app/host", recursive=False)
    mock_etcd3gw.delete.assert_called_once_with("/app/host")


def test_delete_recursive(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    client.delete("/app", recursive=True)
    mock_etcd3gw.delete_prefix.assert_called_once_with("/app")


def test_health_ok(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.status.return_value = {"version": "3.5.0"}
    assert client.health() is True


def test_health_fail(client: EtcdV3Client, mock_etcd3gw: MagicMock) -> None:
    mock_etcd3gw.status.side_effect = Exception("connection refused")
    assert client.health() is False
