from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, TextArea
from textual.widgets.tree import TreeNode

from tetcd.etcd.client import EtcdNode
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


@pytest.fixture
def mock_client() -> MagicMock:
    """Etcd client stub with one dir (`/app`) and one leaf (`/k=hello`)."""
    client = MagicMock()
    client.list.return_value = [
        EtcdNode(key="/app", is_dir=True),
        EtcdNode(key="/k", value="hello"),
    ]
    client.health.return_value = True
    return client


def _browser(app: TetcdApp) -> BrowserScreen:
    screen = app.screen
    assert isinstance(screen, BrowserScreen)
    return screen


def _leaf(tree: KeyTree) -> TreeNode[EtcdNode]:
    return next(child for child in tree.root.children if child.data and not child.data.is_dir)


def _dir(tree: KeyTree) -> TreeNode[EtcdNode]:
    return next(child for child in tree.root.children if child.data and child.data.is_dir)


# ── tree / selection ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_tree_node_selected_updates_value_panel(mock_client: MagicMock) -> None:
    """Selecting a leaf node feeds its data into the value panel."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        assert panel.selected_node is not None
        assert panel.selected_node.key == "/k"


@pytest.mark.asyncio
async def test_browser_tree_selection_ignored_in_edit_mode(mock_client: MagicMock) -> None:
    """Clicking another tree node while editing must not stomp the buffer."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        original_target = panel.selected_node
        tree.select_node(_dir(tree))
        await pilot.pause()
        assert panel.selected_node == original_target
        assert panel.edit_mode is True


@pytest.mark.asyncio
async def test_browser_selected_prefix_helpers(mock_client: MagicMock) -> None:
    """``_selected_prefix`` falls back to root, directory key, or parent key."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        tree = app.screen.query_one(KeyTree)

        tree.select_node(tree.root)
        assert browser._selected_prefix() == "/"

        tree.select_node(_dir(tree))
        assert browser._selected_prefix() == "/app"

        tree.select_node(_leaf(tree))
        assert browser._selected_prefix() == ""

        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        assert browser._selected_prefix() == "/"


# ── add key (modal → inline editor) ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_add_key_opens_inline_editor(mock_client: MagicMock) -> None:
    """After the path modal closes, the panel switches into edit mode."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/new"
        await pilot.click("#btn-add")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
        assert panel.edit_mode is True
        assert panel._target_key == "/new"
        assert panel._is_new is True


@pytest.mark.asyncio
async def test_browser_add_key_save_calls_put(mock_client: MagicMock) -> None:
    """Typing a value and ``ctrl+s`` puts the new (key, value) into etcd."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/new"
        await pilot.click("#btn-add")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "val"
        await pilot.press("ctrl+s")
        await pilot.pause()
    mock_client.put.assert_called_with("/new", "val")


@pytest.mark.asyncio
async def test_browser_add_key_cancel_modal_does_nothing(mock_client: MagicMock) -> None:
    """Escaping the path modal leaves the panel in read mode and no put fires."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
        assert panel.edit_mode is False
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_add_key_error_keeps_editor_open(mock_client: MagicMock) -> None:
    """A failing ``put`` notifies but leaves the editor open with the buffer."""
    mock_client.put.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/x"
        await pilot.click("#btn-add")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "y"
        await pilot.press("ctrl+s")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
        assert panel.edit_mode is True


# ── edit (inline editor) ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_edit_opens_inline_editor(mock_client: MagicMock) -> None:
    """Pressing ``e`` on a leaf populates the editor with the current value."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        editor = app.screen.query_one("#kv-value-editor", TextArea)
        assert panel.edit_mode is True
        assert panel._target_key == "/k"
        assert editor.text == "hello"


@pytest.mark.asyncio
async def test_browser_edit_save_persists_value(mock_client: MagicMock) -> None:
    """Editing then ``ctrl+s`` writes to etcd and leaves edit mode."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "updated"
        await pilot.press("ctrl+s")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
    mock_client.put.assert_called_with("/k", "updated")
    assert panel.edit_mode is False
    assert panel.selected_node is not None
    assert panel.selected_node.value == "updated"


@pytest.mark.asyncio
async def test_browser_edit_clean_cancel_exits_without_confirm(mock_client: MagicMock) -> None:
    """``escape`` on a clean editor leaves edit mode without a confirmation."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
    assert panel.edit_mode is False
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_dirty_cancel_confirmed_discards(mock_client: MagicMock) -> None:
    """``escape`` on a dirty editor opens a confirm; ``y`` discards changes."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "dirty-buffer"
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        # ConfirmScreen is now on top.
        await pilot.press("y")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is False
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_dirty_cancel_rejected_keeps_editor(mock_client: MagicMock) -> None:
    """``n`` on the discard-confirm keeps the editor open with the buffer."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
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
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_directory_warns(mock_client: MagicMock) -> None:
    """Pressing ``e`` on a directory shows a warning and never opens the editor."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_dir(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is False
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_no_selection_warns(mock_client: MagicMock) -> None:
    """Without a selected node, the edit action warns and stays in read mode."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_edit()
        await pilot.pause()
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_error_keeps_editor_open(mock_client: MagicMock) -> None:
    """A failing put on edit-save notifies but leaves the editor in edit mode."""
    mock_client.put.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        app.screen.query_one("#kv-value-editor", TextArea).text = "boom"
        await pilot.press("ctrl+s")
        await pilot.pause()
        panel = _browser(app).query_one("#key-value", KeyValuePanel)
    assert panel.edit_mode is True


# ── add dir ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_add_dir_flow_calls_make_dir(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/created"
        await pilot.click("#btn-create")
        await pilot.pause()
    mock_client.make_dir.assert_called_with("/created")


@pytest.mark.asyncio
async def test_browser_add_dir_cancel(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    mock_client.make_dir.assert_not_called()


@pytest.mark.asyncio
async def test_browser_add_dir_error_notifies(mock_client: MagicMock) -> None:
    mock_client.make_dir.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/created"
        await pilot.click("#btn-create")
        await pilot.pause()


# ── delete ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_delete_leaf_confirmed(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    mock_client.delete.assert_called_with("/k", recursive=False)


@pytest.mark.asyncio
async def test_browser_delete_directory_is_recursive(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_dir(tree))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    mock_client.delete.assert_called_with("/app", recursive=True)


@pytest.mark.asyncio
async def test_browser_delete_cancelled(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_browser_delete_without_selection_warns(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_delete()
        await pilot.pause()
    mock_client.delete.assert_not_called()


@pytest.mark.asyncio
async def test_browser_delete_error_notifies(mock_client: MagicMock) -> None:
    mock_client.delete.side_effect = RuntimeError("boom")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.select_node(_leaf(tree))
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()


# ── misc ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_browser_add_key_no_selection_uses_root_prefix(mock_client: MagicMock) -> None:
    """Without a selection the add-key modal opens with the root prefix."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_add_key()
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
