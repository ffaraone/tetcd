from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, TextArea
from textual.widgets.tree import TreeNode

from tests.conftest import make_server
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.widgets.key_tree import KeyTree, TreeData
from tetcd.tui.widgets.key_value import KeyValuePanel


def _mock(server: Server) -> MagicMock:
    """Return ``server.client`` cast to ``MagicMock`` for assertion access."""
    return cast(MagicMock, server.client)


# ── fixtures ─────────────────────────────────────────────────────────────────


def _stub_client(
    listings: dict[str, list[EtcdNode]] | None = None,
    *,
    values: dict[str, str] | None = None,
) -> MagicMock:
    """Build a client whose ``list`` returns canned per-prefix data."""
    client = MagicMock()
    table = listings if listings is not None else {}
    client.list.side_effect = lambda prefix: list(table.get(prefix, []))
    if values is not None:
        client.get.side_effect = lambda key: (
            EtcdNode(key=key, value=values[key]) if key in values else None
        )
    else:
        client.get.return_value = None
    return client


@pytest.fixture
def single_server() -> list[Server]:
    """One server with a dir (``/app``) and a leaf (``/k`` = ``hello``)."""
    client = _stub_client(
        {"/": [EtcdNode(key="/app", is_dir=True), EtcdNode(key="/k", value="hello")]}
    )
    return [make_server("Local", client=client)]


@pytest.fixture
def two_servers() -> list[Server]:
    """Two servers, each with one leaf at root."""
    a = _stub_client({"/": [EtcdNode(key="/a", value="from-a")]})
    b = _stub_client({"/": [EtcdNode(key="/b", value="from-b")]})
    return [make_server("A", client=a), make_server("B", client=b)]


def _browser(app: TetcdApp) -> BrowserScreen:
    screen = app.screen
    assert isinstance(screen, BrowserScreen)
    return screen


def _server_node(tree: KeyTree, label: str) -> TreeNode[TreeData]:
    for child in tree.root.children:
        if isinstance(child.data, Server) and child.data.config.label == label:
            return child
    raise AssertionError(f"server node {label!r} not found")


def _child(node: TreeNode[TreeData], key: str) -> TreeNode[TreeData]:
    for child in node.children:
        if isinstance(child.data, EtcdNode) and child.data.key == key:
            return child
    raise AssertionError(f"child with key {key!r} not found")


# ── tree / selection ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_shows_each_server_as_top_level(two_servers: list[Server]) -> None:
    """The browser tree exposes one branch per configured server."""
    app = TetcdApp(servers=two_servers, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        labels = [str(c.label) for c in tree.root.children]
        assert any("A" in label for label in labels)
        assert any("B" in label for label in labels)


@pytest.mark.asyncio
async def test_browser_selecting_leaf_updates_value_panel(
    single_server: list[Server],
) -> None:
    """Selecting a leaf inside a server feeds its data into the value panel."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        assert panel.selected_node is not None
        assert panel.selected_node.key == "/k"


@pytest.mark.asyncio
async def test_browser_selecting_server_clears_value_panel(
    single_server: list[Server],
) -> None:
    """Selecting the server branch clears the value panel (no leaf data)."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        tree.select_node(server_node)
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        assert panel.selected_node is None


@pytest.mark.asyncio
async def test_browser_selected_prefix_helpers(single_server: list[Server]) -> None:
    """``_selected_prefix`` covers no-selection, server, dir, and leaf cases."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")

        tree.select_node(server_node)
        await pilot.pause()
        assert browser._selected_prefix() == "/"

        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        assert browser._selected_prefix() == "/app"

        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        assert browser._selected_prefix() == ""


# ── add key (modal → inline editor) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_add_key_save_calls_put(single_server: list[Server]) -> None:
    """Typing a value and ``ctrl+s`` puts the new (key, value) into etcd."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/new"
        await pilot.click("#btn-add")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "val"
        await pilot.press("ctrl+s")
        await pilot.pause()
    _mock(single_server[0]).put.assert_called_with("/new", "val")


@pytest.mark.asyncio
async def test_browser_save_refreshes_tree_and_selects_edited_key(
    single_server: list[Server],
) -> None:
    """After an edit-save, the tree is refreshed and the edited key becomes the cursor."""
    client = _mock(single_server[0])
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        initial_list_calls = client.list.call_count
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "updated"
        await pilot.press("ctrl+s")
        await pilot.pause()
        cursor = tree.cursor_node
        panel = app.screen.query_one(KeyValuePanel)
    assert client.list.call_count > initial_list_calls
    assert cursor is not None
    assert isinstance(cursor.data, EtcdNode)
    assert cursor.data.key == "/k"
    assert panel.selected_node is not None
    assert panel.selected_node.value == "updated"


@pytest.mark.asyncio
async def test_browser_save_reveals_and_selects_new_nested_key(
    single_server: list[Server],
) -> None:
    """Adding a new key under a nested directory expands the path and selects the leaf."""
    client = _mock(single_server[0])
    # After the put, the refreshed listing under /app contains the new leaf.
    listings = {
        "/": [EtcdNode(key="/app", is_dir=True), EtcdNode(key="/k", value="hello")],
        "/app": [EtcdNode(key="/app/host", value="h"), EtcdNode(key="/app/new", value="val")],
    }
    client.list.side_effect = lambda prefix: list(listings.get(prefix, []))

    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/app/new"
        await pilot.click("#btn-add")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "val"
        await pilot.press("ctrl+s")
        await pilot.pause()
        cursor = tree.cursor_node
    assert cursor is not None
    assert isinstance(cursor.data, EtcdNode)
    assert cursor.data.key == "/app/new"


@pytest.mark.asyncio
async def test_browser_add_key_without_selection_warns(
    single_server: list[Server],
) -> None:
    """Without any selection the action warns and does not open the modal."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_client = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_add_key()
        await pilot.pause()
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_add_dir_flow_calls_make_dir(single_server: list[Server]) -> None:
    """The add-dir modal hits ``make_dir`` on the selected server."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/created"
        await pilot.click("#btn-create")
        await pilot.pause()
    _mock(single_server[0]).make_dir.assert_called_with("/created")


@pytest.mark.asyncio
async def test_browser_add_dir_error_notifies(single_server: list[Server]) -> None:
    """A failing ``make_dir`` notifies but does not crash."""
    _mock(single_server[0]).make_dir.side_effect = RuntimeError("nope")
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/created"
        await pilot.click("#btn-create")
        await pilot.pause()


@pytest.mark.asyncio
async def test_browser_add_dir_without_selection_warns(
    single_server: list[Server],
) -> None:
    """Without any selection the add-dir action warns and stays put."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_client = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_add_dir()
        await pilot.pause()
    _mock(single_server[0]).make_dir.assert_not_called()


# ── edit (inline editor) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_edit_save_persists_value(single_server: list[Server]) -> None:
    """Editing then ``ctrl+s`` writes to etcd and leaves edit mode."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "updated"
        await pilot.press("ctrl+s")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
    _mock(single_server[0]).put.assert_called_with("/k", "updated")
    assert panel.edit_mode is False
    assert panel.selected_node is not None
    assert panel.selected_node.value == "updated"


@pytest.mark.asyncio
async def test_browser_edit_clean_cancel_exits_without_confirm(
    single_server: list[Server],
) -> None:
    """``escape`` on a clean editor leaves edit mode without a confirmation."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
    assert panel.edit_mode is False
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_dirty_cancel_confirmed_discards(
    single_server: list[Server],
) -> None:
    """``escape`` on a dirty editor opens a confirm; ``y`` discards the buffer."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "dirty-buffer"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is False
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_dirty_cancel_rejected_keeps_editor(
    single_server: list[Server],
) -> None:
    """``n`` on the discard-confirm keeps the editor open with the buffer."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "dirty-buffer"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
        editor = _browser(app).query_one("#kv-value-editor", TextArea)
    assert panel.edit_mode is True
    assert editor.text == "dirty-buffer"


@pytest.mark.asyncio
async def test_browser_edit_directory_warns(single_server: list[Server]) -> None:
    """Pressing ``e`` on a directory shows a warning and never opens the editor."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is False
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_no_selection_warns(single_server: list[Server]) -> None:
    """Without a selected node, the edit action warns and stays in read mode."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_etcd_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_edit()
        await pilot.pause()
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_error_keeps_editor_open(
    single_server: list[Server],
) -> None:
    """A failing put on edit-save notifies but leaves the editor in edit mode."""
    _mock(single_server[0]).put.side_effect = RuntimeError("nope")
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "boom"
        await pilot.press("ctrl+s")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is True


# ── delete ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_delete_leaf_confirmed(single_server: list[Server]) -> None:
    """Deleting a leaf hits ``delete(key, recursive=False)`` after confirming."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    _mock(single_server[0]).delete.assert_called_with("/k", recursive=False)


@pytest.mark.asyncio
async def test_browser_delete_directory_is_recursive(
    single_server: list[Server],
) -> None:
    """Deleting a directory passes ``recursive=True``."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    _mock(single_server[0]).delete.assert_called_with("/app", recursive=True)


@pytest.mark.asyncio
async def test_browser_delete_cancelled(single_server: list[Server]) -> None:
    """Saying ``no`` to the confirm modal skips the delete."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    _mock(single_server[0]).delete.assert_not_called()


@pytest.mark.asyncio
async def test_browser_delete_without_selection_warns(
    single_server: list[Server],
) -> None:
    """Without a leaf/dir selection the delete action warns."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_etcd_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_delete()
        await pilot.pause()
    _mock(single_server[0]).delete.assert_not_called()


@pytest.mark.asyncio
async def test_browser_delete_error_notifies(single_server: list[Server]) -> None:
    """A failing delete notifies but doesn't crash the app."""
    _mock(single_server[0]).delete.side_effect = RuntimeError("boom")
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()


# ── clipboard (copy / cut / paste) ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_copy_paste_within_same_server(
    single_server: list[Server],
) -> None:
    """Copy a leaf, select a directory, paste — ``put`` runs at the new path."""
    # Seed the source leaf to be copied: /k = hello (root level).
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    client = _mock(single_server[0])
    client.put.assert_called_with("/app/k", "hello")
    client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_browser_cut_paste_moves_and_deletes(
    single_server: list[Server],
) -> None:
    """A cut + paste copies the leaf and then deletes the source."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("x")
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    client = _mock(single_server[0])
    client.put.assert_called_with("/app/k", "hello")
    client.delete.assert_called_with("/k", recursive=False)


@pytest.mark.asyncio
async def test_browser_paste_across_servers(two_servers: list[Server]) -> None:
    """Copying from server A and pasting into server B writes onto B's client."""
    app = TetcdApp(servers=two_servers, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        a_node = _server_node(tree, "A")
        b_node = _server_node(tree, "B")
        a_node.expand()
        await pilot.pause()
        tree.select_node(_child(a_node, "/a"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(b_node)
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    _mock(two_servers[0]).put.assert_not_called()
    _mock(two_servers[1]).put.assert_called_with("/a", "from-a")


@pytest.mark.asyncio
async def test_browser_paste_directory_walks_children(
    single_server: list[Server],
) -> None:
    """Copying a dir copies every leaf under it onto the new prefix."""
    client = _mock(single_server[0])
    # Source: /app contains /app/host = "h", and /app/sub/ with one leaf.
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/app", is_dir=True), EtcdNode(key="/dst", is_dir=True)],
        "/app": [EtcdNode(key="/app/host", value="h"), EtcdNode(key="/app/sub", is_dir=True)],
        "/app/sub": [EtcdNode(key="/app/sub/k", value="v")],
        "/dst": [],
        "/dst/app": [],
        "/dst/app/sub": [],
    }.get(prefix, [])

    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(_child(server_node, "/dst"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    written = sorted({call.args for call in client.put.call_args_list})
    assert ("/dst/app/host", "h") in written
    assert ("/dst/app/sub/k", "v") in written


@pytest.mark.asyncio
async def test_browser_paste_with_collision_confirms_overwrite(
    single_server: list[Server],
) -> None:
    """When the destination already exists, the user is asked to confirm."""
    client = _mock(single_server[0])
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/k", value="hello"), EtcdNode(key="/app", is_dir=True)],
        "/app": [EtcdNode(key="/app/k", value="existing")],
    }.get(prefix, [])
    # Destination key /app/k already exists, so the dst client.get returns it.
    client.get.side_effect = lambda key: (
        EtcdNode(key=key, value="existing") if key == "/app/k" else None
    )

    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
        # ConfirmScreen is on top; reject the overwrite.
        await pilot.press("n")
        await pilot.pause()
    client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_paste_with_collision_confirmed_yes_overwrites(
    single_server: list[Server],
) -> None:
    """Confirming the overwrite prompt actually performs the put."""
    client = _mock(single_server[0])
    client.list.side_effect = lambda prefix: {
        "/": [EtcdNode(key="/k", value="hello"), EtcdNode(key="/app", is_dir=True)],
        "/app": [EtcdNode(key="/app/k", value="existing")],
    }.get(prefix, [])
    client.get.side_effect = lambda key: (
        EtcdNode(key=key, value="existing") if key == "/app/k" else None
    )

    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    client.put.assert_called_with("/app/k", "hello")


@pytest.mark.asyncio
async def test_browser_paste_without_clipboard_warns(
    single_server: list[Server],
) -> None:
    """Pasting with no clipboard staged just warns."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_copy_without_etcd_selection_warns(
    single_server: list[Server],
) -> None:
    """Copy with only the server node selected warns and stages nothing."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        browser = _browser(app)
    assert browser._clipboard is None


@pytest.mark.asyncio
async def test_browser_tree_selection_ignored_in_edit_mode(
    single_server: list[Server],
) -> None:
    """Tree clicks during edit mode do not overwrite the panel's selection."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        leaf = _child(server_node, "/k")
        tree.select_node(leaf)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        original = panel.selected_node
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        assert panel.selected_node == original
        assert panel.edit_mode is True


@pytest.mark.asyncio
async def test_browser_add_key_cancel_modal_skips_editor(
    single_server: list[Server],
) -> None:
    """Cancelling the add-key modal leaves the panel in read mode."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
        assert panel.edit_mode is False
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_add_dir_cancel_modal_does_nothing(
    single_server: list[Server],
) -> None:
    """Cancelling the add-dir modal skips ``make_dir``."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_server_node(tree, "Local"))
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    _mock(single_server[0]).make_dir.assert_not_called()


@pytest.mark.asyncio
async def test_browser_paste_without_destination_warns(
    single_server: list[Server],
) -> None:
    """Without a destination selection, paste warns instead of writing."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        browser = _browser(app)
        browser._selected_client = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_paste()
        await pilot.pause()
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_save_without_edit_client_notifies(
    single_server: list[Server],
) -> None:
    """A save with no bound client (rare; defensive) notifies and skips put."""
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._edit_client = None
        browser.on_key_value_panel_save_requested(
            KeyValuePanel.SaveRequested(key="/k", value="v", is_new=False)
        )
        await pilot.pause()
    _mock(single_server[0]).put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_paste_error_notifies(single_server: list[Server]) -> None:
    """A failing ``put`` during paste notifies but doesn't crash."""
    client = _mock(single_server[0])
    client.put.side_effect = RuntimeError("nope")
    app = TetcdApp(servers=single_server, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        server_node = _server_node(tree, "Local")
        server_node.expand()
        await pilot.pause()
        tree.select_node(_child(server_node, "/k"))
        await pilot.pause()
        await pilot.press("c")
        await pilot.pause()
        tree.select_node(_child(server_node, "/app"))
        await pilot.pause()
        await pilot.press("v")
        await pilot.pause()
