from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Label, Static, TextArea

from tests.conftest import make_server
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


def _text(widget: Label | Static) -> str:
    """Return the plain-text body of a Label/Static, regardless of renderable type."""
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    return str(plain) if plain is not None else str(rendered)


class _KvHost(App[None]):
    """Host app exposing a ``KeyValuePanel`` and recording its messages."""

    def __init__(self) -> None:
        super().__init__()
        self.save_messages: list[KeyValuePanel.SaveRequested] = []
        self.cancel_messages: list[KeyValuePanel.CancelRequested] = []

    def compose(self) -> ComposeResult:
        yield KeyValuePanel(id="kv")

    def on_key_value_panel_save_requested(self, event: KeyValuePanel.SaveRequested) -> None:
        self.save_messages.append(event)

    def on_key_value_panel_cancel_requested(self, event: KeyValuePanel.CancelRequested) -> None:
        self.cancel_messages.append(event)


# ── Read-only display ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_key_value_panel_none_state() -> None:
    """A null selection renders the placeholder label."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = None
        await pilot.pause()
        assert "No key" in _text(app.query_one("#kv-key-label", Label))


@pytest.mark.asyncio
async def test_key_value_panel_directory_state() -> None:
    """Directory nodes render the ``<directory>`` placeholder."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/d", is_dir=True)
        await pilot.pause()
        assert "/d" in _text(app.query_one("#kv-key-label", Label))
        assert "directory" in _text(app.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_value_state() -> None:
    """A leaf with a value renders the value verbatim."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/k", value="hello")
        await pilot.pause()
        assert "hello" in _text(app.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_empty_value_state() -> None:
    """A leaf with no value renders the ``<empty>`` placeholder."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/empty", value=None, is_dir=False)
        await pilot.pause()
        assert "empty" in _text(app.query_one("#kv-value-content", Static))


# ── Inline editor ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_panel_enters_edit_mode_with_initial_value() -> None:
    """``start_edit`` flips ``edit_mode`` and pre-fills the editor."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/k", initial_value="hello")
        await pilot.pause()
        assert panel.edit_mode is True
        assert panel.dirty is False
        editor = app.query_one("#kv-value-editor", TextArea)
        assert editor.text == "hello"
        assert editor.display is True
        assert app.query_one("#kv-value-content", Static).display is False
        assert "/k" in _text(app.query_one("#kv-key-label", Label))
        assert "editing" in _text(app.query_one("#kv-status-label", Label))


@pytest.mark.asyncio
async def test_panel_tracks_dirty_on_text_change() -> None:
    """Editing the buffer flips ``dirty``; reverting clears it."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/k", initial_value="hello")
        await pilot.pause()
        editor = app.query_one("#kv-value-editor", TextArea)
        editor.text = "world"
        await pilot.pause()
        assert panel.dirty is True
        assert "●" in _text(app.query_one("#kv-status-label", Label))
        editor.text = "hello"
        await pilot.pause()
        assert panel.dirty is False
        assert "●" not in _text(app.query_one("#kv-status-label", Label))


@pytest.mark.asyncio
async def test_panel_save_posts_message() -> None:
    """``ctrl+s`` posts ``SaveRequested`` carrying the buffer and key."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/k", initial_value="hello", is_new=False)
        await pilot.pause()
        editor = app.query_one("#kv-value-editor", TextArea)
        editor.text = "updated"
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert len(app.save_messages) == 1
    msg = app.save_messages[0]
    assert msg.key == "/k"
    assert msg.value == "updated"
    assert msg.is_new is False


@pytest.mark.asyncio
async def test_panel_save_for_new_key_carries_is_new_flag() -> None:
    """``is_new=True`` propagates through to ``SaveRequested.is_new``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/new", initial_value="", is_new=True)
        await pilot.pause()
        editor = app.query_one("#kv-value-editor", TextArea)
        editor.text = "fresh"
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.save_messages[0].is_new is True


@pytest.mark.asyncio
async def test_panel_cancel_posts_message_with_dirty_flag() -> None:
    """``escape`` posts ``CancelRequested`` whose ``dirty`` matches state."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/k", initial_value="hello")
        await pilot.pause()
        app.query_one("#kv-value-editor", TextArea).text = "modified"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert len(app.cancel_messages) == 1
    assert app.cancel_messages[0].dirty is True


@pytest.mark.asyncio
async def test_panel_clean_cancel_reports_not_dirty() -> None:
    """A cancel without edits reports ``dirty=False``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.start_edit(target_key="/k", initial_value="hello")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.cancel_messages[0].dirty is False


@pytest.mark.asyncio
async def test_panel_exit_edit_mode_restores_read_view() -> None:
    """``exit_edit_mode`` hides the editor and re-renders the read view."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.selected_node = EtcdNode(key="/k", value="hello")
        panel.start_edit(target_key="/k", initial_value="hello")
        await pilot.pause()
        panel.exit_edit_mode()
        await pilot.pause()
        assert panel.edit_mode is False
        assert panel.dirty is False
        assert app.query_one("#kv-value-editor", TextArea).display is False
        assert app.query_one("#kv-value-content", Static).display is True


@pytest.mark.asyncio
async def test_panel_save_outside_edit_mode_is_noop() -> None:
    """Save action is ignored when the panel is not in edit mode."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.action_save()
        await pilot.pause()
    assert app.save_messages == []


@pytest.mark.asyncio
async def test_panel_cancel_outside_edit_mode_is_noop() -> None:
    """Cancel action is ignored when the panel is not in edit mode."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.query_one("#kv", KeyValuePanel)
        panel.action_cancel()
        await pilot.pause()
    assert app.cancel_messages == []


# ── KeyTree ─────────────────────────────────────────────────────────────────


class _TreeHost(App[None]):
    def __init__(self, servers: list[Server]) -> None:
        super().__init__()
        self.servers = servers

    def compose(self) -> ComposeResult:
        yield KeyTree(self.servers, id="tree")


@pytest.mark.asyncio
async def test_key_tree_lists_servers_as_top_level_nodes() -> None:
    """Each configured server becomes a top-level branch in the tree."""
    app = _TreeHost([make_server("Prod"), make_server("Stage")])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        labels = [str(child.label) for child in tree.root.children]
        assert any("Prod" in label for label in labels)
        assert any("Stage" in label for label in labels)


@pytest.mark.asyncio
async def test_key_tree_lazy_loads_server_children_on_expand() -> None:
    """Expanding a server branch fetches its top-level keys."""
    client = MagicMock()
    client.list.return_value = [EtcdNode(key="/a", is_dir=True), EtcdNode(key="/k", value="v")]
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        server_node.expand()
        await pilot.pause()
        assert len(server_node.children) == 2
        client.list.assert_called_with("/")


@pytest.mark.asyncio
async def test_key_tree_shows_error_on_list_failure() -> None:
    """A failing ``list`` surfaces as a red error leaf under the server node."""
    client = MagicMock()
    client.list.side_effect = RuntimeError("boom")
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        server_node.expand()
        await pilot.pause()
        labels = [str(child.label) for child in server_node.children]
        assert any("Error" in label for label in labels)


@pytest.mark.asyncio
async def test_key_tree_client_for_walks_up_to_server() -> None:
    """``client_for`` resolves the enclosing server's client for any node."""
    client = MagicMock()
    client.list.return_value = [EtcdNode(key="/a", is_dir=True)]
    server = make_server("Local", client=client)
    app = _TreeHost([server])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        server_node.expand()
        await pilot.pause()
        leaf = server_node.children[0]
        assert tree.client_for(leaf) is client
        assert tree.client_for(server_node) is client


@pytest.mark.asyncio
async def test_key_tree_refresh_node_repopulates_server_subtree() -> None:
    """``refresh_node`` re-fetches a server's children on demand."""
    client = MagicMock()
    client.list.return_value = [EtcdNode(key="/a", value="1")]
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        server_node.expand()
        await pilot.pause()
        client.list.return_value = [
            EtcdNode(key="/a", value="1"),
            EtcdNode(key="/b", value="2"),
        ]
        tree.refresh_node(server_node)
        await pilot.pause()
        assert len(server_node.children) == 2


@pytest.mark.asyncio
async def test_key_tree_rebuild_restores_initial_layout() -> None:
    """``rebuild`` clears the tree and recreates server branches."""
    app = _TreeHost([make_server("A"), make_server("B")])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        tree.rebuild()
        await pilot.pause()
        assert len(tree.root.children) == 2


@pytest.mark.asyncio
async def test_key_tree_client_for_root_returns_none() -> None:
    """The hidden Tree root has no server ancestor so ``client_for`` is None."""
    app = _TreeHost([make_server("A")])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        assert tree.client_for(tree.root) is None


@pytest.mark.asyncio
async def test_key_tree_refresh_node_repopulates_inner_directory() -> None:
    """``refresh_node`` on a directory node walks back to its server's client."""
    client = MagicMock()
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/app", is_dir=True)],
        "/app": [EtcdNode(key="/app/host", value="h")],
    }.get(prefix, [])
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        server_node.expand()
        await pilot.pause()
        app_node = server_node.children[0]
        app_node.expand()
        await pilot.pause()
        # Mutate the listing and refresh just the /app node.
        client.list.side_effect = lambda prefix: {
            "/": [EtcdNode(key="/app", is_dir=True)],
            "/app": [
                EtcdNode(key="/app/host", value="h"),
                EtcdNode(key="/app/port", value="8080"),
            ],
        }.get(prefix, [])
        tree.refresh_node(app_node)
        await pilot.pause()
        assert len(app_node.children) == 2


_: Any = None
