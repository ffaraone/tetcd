from __future__ import annotations

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode, EtcdNodes


def test_node_name_extracts_last_segment() -> None:
    """``EtcdNode.name`` returns the last ``/``-separated path segment."""
    assert EtcdNode(key="/app/config/host").name == "host"
    assert EtcdNode(key="/app").name == "app"


def test_node_name_root_returns_slash() -> None:
    """The root node's name is the literal ``"/"`` separator."""
    assert EtcdNode(key="/").name == "/"


def test_node_parent_key() -> None:
    """``parent_key`` strips one level; the root and top-level edge cases."""
    assert EtcdNode(key="/app/config/host").parent_key == "/app/config"
    # Top-level keys collapse to an empty parent; root collapses to "/".
    assert EtcdNode(key="/app").parent_key == ""
    assert EtcdNode(key="/").parent_key == "/"


def test_node_defaults() -> None:
    """``EtcdNode`` defaults model a leaf: no value, not a dir, empty children."""
    node = EtcdNode(key="/x")
    assert node.value is None
    assert node.is_dir is False
    assert node.children == []


def test_protocol_is_runtime_checkable() -> None:
    """A class satisfying the surface is recognised by ``isinstance``."""

    class Dummy:
        """Minimal in-memory stand-in implementing :class:`EtcdClientProtocol`."""

        def get(self, key: str) -> EtcdNode | None:
            return None

        def list(self, prefix: str) -> EtcdNodes:
            return []

        def put(self, key: str, value: str) -> None:
            return None

        def make_dir(self, key: str) -> None:
            return None

        def delete(self, key: str, recursive: bool = False) -> None:
            return None

        def health(self) -> bool:
            return True

    assert isinstance(Dummy(), EtcdClientProtocol)
