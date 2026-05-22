from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label, Static

from tetcd.etcd.client import EtcdNode
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


def _text(widget: Label | Static) -> str:
    """Return the plain-text body of a Label/Static, regardless of renderable type."""
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    return str(plain) if plain is not None else str(rendered)


class _KvHost(App[None]):
    def compose(self) -> ComposeResult:
        yield KeyValuePanel(id="kv")


@pytest.mark.asyncio
async def test_key_value_panel_none_state() -> None:
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = None
        await pilot.pause()
        assert "No key" in _text(app.query_one("#kv-key-label", Label))


@pytest.mark.asyncio
async def test_key_value_panel_directory_state() -> None:
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/d", is_dir=True)
        await pilot.pause()
        assert "/d" in _text(app.query_one("#kv-key-label", Label))
        assert "directory" in _text(app.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_value_state() -> None:
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/k", value="hello")
        await pilot.pause()
        assert "hello" in _text(app.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_empty_value_state() -> None:
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/empty", value=None, is_dir=False)
        await pilot.pause()
        assert "empty" in _text(app.query_one("#kv-value-content", Static))


class _TreeHost(App[None]):
    def __init__(self, client: MagicMock) -> None:
        super().__init__()
        self.client = client

    def compose(self) -> ComposeResult:
        yield KeyTree(self.client, id="tree")


@pytest.mark.asyncio
async def test_key_tree_lists_children() -> None:
    client = MagicMock()
    client.list.return_value = [
        EtcdNode(key="/a", is_dir=True),
        EtcdNode(key="/k", value="v"),
    ]
    app = _TreeHost(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        assert len(tree.root.children) == 2


@pytest.mark.asyncio
async def test_key_tree_shows_error_on_list_failure() -> None:
    client = MagicMock()
    client.list.side_effect = RuntimeError("boom")
    app = _TreeHost(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        labels = [str(child.label) for child in tree.root.children]
        assert any("Error" in label for label in labels)


@pytest.mark.asyncio
async def test_key_tree_refresh_node_repopulates() -> None:
    client = MagicMock()
    client.list.return_value = [EtcdNode(key="/a", value="1")]
    app = _TreeHost(client)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        client.list.return_value = [
            EtcdNode(key="/a", value="1"),
            EtcdNode(key="/b", value="2"),
        ]
        tree.refresh_node(tree.root)
        await pilot.pause()
        assert len(tree.root.children) == 2
