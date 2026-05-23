"""Tests for the in-memory etcd fake used by other test modules."""

from __future__ import annotations

import pytest

from tests.fakes import InMemoryEtcdClient
from tetcd.etcd.client import EtcdNode

# ── get / list / put round-trip ─────────────────────────────────────────────


def test_put_then_get_returns_stored_value() -> None:
    """A leaf written via ``put`` is read back by ``get`` with the same value."""
    client = InMemoryEtcdClient()
    client.put("/k", "hello")
    node = client.get("/k")
    assert node is not None
    assert node.key == "/k"
    assert node.value == "hello"
    assert node.is_dir is False


def test_put_then_list_surfaces_leaf_under_parent() -> None:
    """A leaf written under a parent appears in ``list(parent)`` immediately."""
    client = InMemoryEtcdClient()
    client.put("/app/host", "localhost")
    children = client.list("/app")
    assert children == [EtcdNode(key="/app/host", value="localhost")]


def test_list_root_returns_top_level_entries() -> None:
    """``list('/')`` returns immediate children regardless of how prefix is spelled."""
    client = InMemoryEtcdClient(values={"/k": "v", "/app/host": "h"})
    keys_for_root = sorted(n.key for n in client.list("/"))
    assert keys_for_root == ["/app", "/k"]


def test_list_surfaces_intermediate_dirs_implicitly() -> None:
    """An intermediate path segment appears as a directory in its parent's listing."""
    client = InMemoryEtcdClient(values={"/a/b/c": "v"})
    children = client.list("/")
    assert children == [EtcdNode(key="/a", is_dir=True)]


def test_explicit_make_dir_appears_in_listing() -> None:
    """``make_dir`` surfaces the path as an explicit directory entry."""
    client = InMemoryEtcdClient()
    client.make_dir("/empty")
    children = client.list("/")
    assert children == [EtcdNode(key="/empty", is_dir=True)]


def test_get_for_unknown_key_returns_none() -> None:
    """``get`` returns ``None`` when the path has no leaf or directory."""
    client = InMemoryEtcdClient()
    assert client.get("/nope") is None


def test_get_returns_dir_node_for_implicit_directory() -> None:
    """``get`` on an implicit directory returns a directory node."""
    client = InMemoryEtcdClient(values={"/a/b": "v"})
    node = client.get("/a")
    assert node is not None
    assert node.is_dir is True


# ── delete ──────────────────────────────────────────────────────────────────


def test_delete_removes_leaf() -> None:
    """``delete`` removes a single leaf and ``get`` then returns ``None``."""
    client = InMemoryEtcdClient(values={"/k": "v"})
    client.delete("/k")
    assert client.get("/k") is None


def test_recursive_delete_removes_subtree() -> None:
    """``delete(recursive=True)`` removes every leaf beneath the prefix."""
    client = InMemoryEtcdClient(values={"/app/a": "1", "/app/b": "2", "/other": "x"})
    client.delete("/app", recursive=True)
    remaining = sorted(n.key for n in client.list("/"))
    assert remaining == ["/other"]


def test_non_recursive_delete_leaves_subtree_intact() -> None:
    """Non-recursive delete on a parent leaves its children in place."""
    client = InMemoryEtcdClient(values={"/app/a": "1"})
    client.delete("/app")
    children = client.list("/app")
    assert children == [EtcdNode(key="/app/a", value="1")]


# ── put overwrites + dir/leaf coexistence ───────────────────────────────────


def test_put_overrides_existing_dir_marker() -> None:
    """Writing a leaf at a path that was an explicit dir replaces the dir marker."""
    client = InMemoryEtcdClient()
    client.make_dir("/x")
    client.put("/x", "now-a-leaf")
    node = client.get("/x")
    assert node is not None
    assert node.is_dir is False
    assert node.value == "now-a-leaf"


def test_health_is_always_true() -> None:
    """The fake reports a healthy cluster unconditionally."""
    assert InMemoryEtcdClient().health() is True


# ── leading slash / normalization ───────────────────────────────────────────


@pytest.mark.parametrize("key", ["/k", "k", "/k/", "//k//"])
def test_keys_are_normalized_to_leading_slash_no_trailing(key: str) -> None:
    """``put``/``get`` normalize keys so equivalent spellings address the same entry."""
    client = InMemoryEtcdClient()
    client.put(key, "v")
    stored = client.get("/k")
    assert stored is not None
    assert stored.value == "v"
