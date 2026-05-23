from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from textual.app import App
from textual.widgets import Button, Label, Static, TextArea

from tests.conftest import make_server
from tests.fakes import BrowserStateHostScreen
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


def _text(widget: Label | Static) -> str:
    """Return the plain-text body of a Label/Static, regardless of renderable type."""
    rendered = widget.render()
    plain = getattr(rendered, "plain", None)
    return str(plain) if plain is not None else str(rendered)


def _button_label(button: Button) -> str:
    """Return the plain-text label currently shown on ``button``."""
    label = button.label
    plain = getattr(label, "plain", None)
    return str(plain) if plain is not None else str(label)


# ── KeyValuePanel host ──────────────────────────────────────────────────────


class _KvHost(App[None]):
    """Host app exposing a ``KeyValuePanel`` rooted on a state-bearing screen.

    ``state`` mirrors the reactive surface the panel reads in production
    (``active_server`` / ``active_node`` / ``edit_*``), so tests drive
    panel behaviour by writing to those attributes — never by reaching into
    the panel's internals.
    """

    def __init__(self) -> None:
        super().__init__()
        self.save_messages: list[KeyValuePanel.SaveRequested] = []
        self.cancel_messages: list[KeyValuePanel.CancelRequested] = []
        self.state = BrowserStateHostScreen([lambda: KeyValuePanel(id="kv")])

    def on_mount(self) -> None:
        self.push_screen(self.state)

    def on_key_value_panel_save_requested(self, event: KeyValuePanel.SaveRequested) -> None:
        self.save_messages.append(event)

    def on_key_value_panel_cancel_requested(self, event: KeyValuePanel.CancelRequested) -> None:
        self.cancel_messages.append(event)


def _begin_edit(
    state: BrowserStateHostScreen,
    *,
    target_key: str,
    initial_value: str = "",
    is_new: bool = False,
    server: Server | None = None,
) -> None:
    """Drive the state into edit mode the same way :class:`BrowserScreen` does."""
    if server is not None:
        state.active_server = server
    state.edit_target_key = target_key
    state.edit_initial_value = initial_value
    state.edit_is_new = is_new
    state.edit_mode = True


# ── Read-only display ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_key_value_panel_none_state() -> None:
    """A null selection renders the placeholder label."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = None
        await pilot.pause()
        assert "No key" in _text(app.screen.query_one("#kv-key-label", Label))


@pytest.mark.asyncio
async def test_key_value_panel_directory_state() -> None:
    """Directory nodes render the ``<directory>`` placeholder."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = EtcdNode(key="/d", is_dir=True)
        await pilot.pause()
        assert "/d" in _text(app.screen.query_one("#kv-key-label", Label))
        assert "directory" in _text(app.screen.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_value_state() -> None:
    """A leaf with a value renders the value verbatim."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = EtcdNode(key="/k", value="hello")
        await pilot.pause()
        assert "hello" in _text(app.screen.query_one("#kv-value-content", Static))


@pytest.mark.asyncio
async def test_key_value_panel_empty_value_state() -> None:
    """A leaf with no value renders the ``<empty>`` placeholder."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = EtcdNode(key="/empty", value=None, is_dir=False)
        await pilot.pause()
        assert "empty" in _text(app.screen.query_one("#kv-value-content", Static))


# ── Inline editor ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_panel_enters_edit_mode_with_initial_value() -> None:
    """Flipping ``edit_mode`` reveals the action buttons and pre-fills the editor."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        editor = app.screen.query_one("#kv-value-editor", TextArea)
        assert editor.text == "hello"
        assert editor.display is True
        assert app.screen.query_one("#kv-value-content", Static).display is False
        assert "/k" in _text(app.screen.query_one("#kv-key-label", Label))
        assert app.screen.query_one("#kv-edit-actions").display is True


@pytest.mark.asyncio
async def test_panel_tracks_dirty_on_save_button_label() -> None:
    """Dirty buffer adds a trailing ``*`` marker to the Save button; reverting clears it."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        panel = app.screen.query_one("#kv", KeyValuePanel)
        save = app.screen.query_one("#kv-save-button", Button)
        editor = app.screen.query_one("#kv-value-editor", TextArea)
        editor.text = "world"
        await pilot.pause()
        assert panel.dirty is True
        assert "*" in _button_label(save)
        editor.text = "hello"
        await pilot.pause()
        assert panel.dirty is False
        assert "*" not in _button_label(save)


@pytest.mark.asyncio
async def test_panel_renders_server_prefix_for_selected_node() -> None:
    """A selected node renders the header as ``<server>:<key>`` when active_server is set."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_server = make_server("Prod")
        app.state.active_node = EtcdNode(key="/my/key", value="v")
        await pilot.pause()
        assert "Prod:/my/key" in _text(app.screen.query_one("#kv-key-label", Label))


@pytest.mark.asyncio
async def test_panel_renders_server_prefix_in_edit_mode() -> None:
    """In edit mode the header formats the target key as ``<server>:<key>``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/my/key", initial_value="", server=make_server("Stage"))
        await pilot.pause()
        assert "Stage:/my/key" in _text(app.screen.query_one("#kv-key-label", Label))


@pytest.mark.asyncio
async def test_panel_omits_server_prefix_when_unset() -> None:
    """With no active_server, the header shows the bare key without a prefix."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = EtcdNode(key="/my/key", value="v")
        await pilot.pause()
        text = _text(app.screen.query_one("#kv-key-label", Label))
        assert "/my/key" in text
        assert "://" not in text


@pytest.mark.asyncio
async def test_panel_save_button_click_posts_message() -> None:
    """Clicking the Save button posts ``SaveRequested`` just like ``ctrl+s``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "updated"
        await pilot.pause()
        await pilot.click("#kv-save-button")
        await pilot.pause()
    assert len(app.save_messages) == 1
    msg = app.save_messages[0]
    assert msg.key == "/k"
    assert msg.value == "updated"


@pytest.mark.asyncio
async def test_panel_cancel_button_click_posts_message() -> None:
    """Clicking the Cancel button posts ``CancelRequested`` just like ``escape``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "modified"
        await pilot.pause()
        await pilot.click("#kv-cancel-button")
        await pilot.pause()
    assert len(app.cancel_messages) == 1
    assert app.cancel_messages[0].dirty is True


@pytest.mark.asyncio
async def test_panel_action_buttons_hidden_outside_edit_mode() -> None:
    """The Save/Cancel action row stays hidden until edit mode is entered."""
    app = _KvHost()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen.query_one("#kv-edit-actions").display is False


@pytest.mark.asyncio
async def test_panel_save_posts_message() -> None:
    """``ctrl+s`` posts ``SaveRequested`` carrying the buffer and key."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello", is_new=False)
        await pilot.pause()
        editor = app.screen.query_one("#kv-value-editor", TextArea)
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
    """``edit_is_new=True`` propagates through to ``SaveRequested.is_new``."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/new", initial_value="", is_new=True)
        await pilot.pause()
        editor = app.screen.query_one("#kv-value-editor", TextArea)
        editor.text = "fresh"
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert app.save_messages[0].is_new is True


@pytest.mark.asyncio
async def test_panel_cancel_posts_message_with_dirty_flag() -> None:
    """``escape`` posts ``CancelRequested`` whose ``dirty`` matches state."""
    app = _KvHost()
    async with app.run_test() as pilot:
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "modified"
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
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert app.cancel_messages[0].dirty is False


@pytest.mark.asyncio
async def test_panel_leaving_edit_mode_restores_read_view() -> None:
    """Clearing ``edit_mode`` hides the editor and shows the read view again."""
    app = _KvHost()
    async with app.run_test() as pilot:
        app.state.active_node = EtcdNode(key="/k", value="hello")
        _begin_edit(app.state, target_key="/k", initial_value="hello")
        await pilot.pause()
        app.state.edit_mode = False
        await pilot.pause()
        assert app.screen.query_one("#kv-value-editor", TextArea).display is False
        assert app.screen.query_one("#kv-value-content", Static).display is True


@pytest.mark.asyncio
async def test_panel_save_outside_edit_mode_is_noop() -> None:
    """Save action is ignored when the panel is not in edit mode."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.screen.query_one("#kv", KeyValuePanel)
        panel.action_save()
        await pilot.pause()
    assert app.save_messages == []


@pytest.mark.asyncio
async def test_panel_cancel_outside_edit_mode_is_noop() -> None:
    """Cancel action is ignored when the panel is not in edit mode."""
    app = _KvHost()
    async with app.run_test() as pilot:
        panel = app.screen.query_one("#kv", KeyValuePanel)
        panel.action_cancel()
        await pilot.pause()
    assert app.cancel_messages == []


# ── KeyTree ─────────────────────────────────────────────────────────────────


class _TreeHost(App[None]):
    """Host app for ``KeyTree`` with the state reactives the tree subscribes to."""

    def __init__(self, servers: list[Server]) -> None:
        super().__init__()
        self.servers = servers
        self.state = BrowserStateHostScreen([lambda: KeyTree(servers, id="tree")])

    def on_mount(self) -> None:
        self.push_screen(self.state)


@pytest.mark.asyncio
async def test_key_tree_lists_servers_as_top_level_nodes() -> None:
    """Each configured server becomes a top-level branch in the tree."""
    app = _TreeHost([make_server("Prod"), make_server("Stage")])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
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
        tree = app.screen.query_one("#tree", KeyTree)
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
        tree = app.screen.query_one("#tree", KeyTree)
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
        tree = app.screen.query_one("#tree", KeyTree)
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
        tree = app.screen.query_one("#tree", KeyTree)
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
        tree = app.screen.query_one("#tree", KeyTree)
        tree.rebuild()
        await pilot.pause()
        assert len(tree.root.children) == 2


@pytest.mark.asyncio
async def test_key_tree_client_for_root_returns_none() -> None:
    """The hidden Tree root has no server ancestor so ``client_for`` is None."""
    app = _TreeHost([make_server("A")])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
        assert tree.client_for(tree.root) is None


@pytest.mark.asyncio
async def test_key_tree_reveal_key_expands_path_and_returns_leaf() -> None:
    """``reveal_key`` lazily loads each directory on the path and returns the leaf."""
    client = MagicMock()
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/a", is_dir=True)],
        "/a": [EtcdNode(key="/a/b", is_dir=True)],
        "/a/b": [EtcdNode(key="/a/b/c", value="v")],
    }.get(prefix, [])
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        revealed = tree.reveal_key(server_node, "/a/b/c")
        assert revealed is not None
        assert isinstance(revealed.data, EtcdNode)
        assert revealed.data.key == "/a/b/c"


@pytest.mark.asyncio
async def test_key_tree_reveal_key_returns_none_for_missing_path() -> None:
    """``reveal_key`` returns ``None`` when a segment of the path is absent."""
    client = MagicMock()
    client.list.side_effect = lambda prefix: (
        [EtcdNode(key="/a", is_dir=True)] if prefix == "/" else []
    )
    app = _TreeHost([make_server("Local", client=client)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
        server_node = tree.root.children[0]
        assert tree.reveal_key(server_node, "/a/missing") is None


@pytest.mark.asyncio
async def test_key_tree_server_node_for_resolves_client() -> None:
    """``server_node_for`` returns the top-level node bound to the given client."""
    client_a = MagicMock()
    client_a.list.return_value = []
    client_b = MagicMock()
    client_b.list.return_value = []
    app = _TreeHost([make_server("A", client=client_a), make_server("B", client=client_b)])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
        node_a = tree.server_node_for(client_a)
        node_b = tree.server_node_for(client_b)
        assert node_a is not None and isinstance(node_a.data, Server)
        assert node_a.data.config.label == "A"
        assert node_b is not None and isinstance(node_b.data, Server)
        assert node_b.data.config.label == "B"
        assert tree.server_node_for(MagicMock()) is None


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
        tree = app.screen.query_one("#tree", KeyTree)
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


@pytest.mark.asyncio
async def test_key_tree_cursor_follows_active_node_state() -> None:
    """Writing ``active_node`` to the host screen moves the tree cursor to that key."""
    client = MagicMock()
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/a", is_dir=True), EtcdNode(key="/k", value="v")],
        "/a": [EtcdNode(key="/a/b", value="x")],
    }.get(prefix, [])
    server = make_server("Local", client=client)
    app = _TreeHost([server])
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one("#tree", KeyTree)
        app.state.active_server = server
        app.state.active_node = EtcdNode(key="/a/b", value="x")
        for _ in range(5):
            await pilot.pause()
        cursor = tree.cursor_node
        assert cursor is not None
        assert isinstance(cursor.data, EtcdNode)
        assert cursor.data.key == "/a/b"


_: Any = None
