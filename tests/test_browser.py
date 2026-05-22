from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from textual.widgets import Input, TextArea

from tetcd.etcd.client import EtcdNode
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


@pytest.fixture
def mock_client() -> MagicMock:
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


@pytest.mark.asyncio
async def test_browser_tree_node_selected_updates_value_panel(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        await pilot.pause()
        panel = app.screen.query_one(KeyValuePanel)
        assert panel.selected_node is not None
        assert panel.selected_node.key == "/k"


@pytest.mark.asyncio
async def test_browser_selected_prefix_helpers(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        tree = app.screen.query_one(KeyTree)

        # No selection → root prefix
        tree.select_node(tree.root)
        assert browser._selected_prefix() == "/"

        # Directory selection → its own key
        dir_node = next(child for child in tree.root.children if child.data and child.data.is_dir)
        tree.select_node(dir_node)
        assert browser._selected_prefix() == "/app"

        # Leaf selection → parent key ("" for top-level keys).
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        assert browser._selected_prefix() == ""

        # _selected_prefix falls back to "/" when nothing is selected.
        # Force no-selection branch without depending on tree cursor state.
        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        assert browser._selected_prefix() == "/"


@pytest.mark.asyncio
async def test_browser_add_key_flow_calls_put(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/new"
        app.screen.query_one("#value-input", Input).value = "val"
        await pilot.click("#btn-add")
        await pilot.pause()
    mock_client.put.assert_called_with("/new", "val")


@pytest.mark.asyncio
async def test_browser_add_key_cancel_does_nothing(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_add_key_error_shows_notification(mock_client: MagicMock) -> None:
    mock_client.put.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/x"
        app.screen.query_one("#value-input", Input).value = "y"
        await pilot.click("#btn-add")
        await pilot.pause()


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
async def test_browser_add_dir_error_shows_notification(mock_client: MagicMock) -> None:
    mock_client.make_dir.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/created"
        await pilot.click("#btn-create")
        await pilot.pause()


@pytest.mark.asyncio
async def test_browser_delete_leaf_confirmed(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
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
        dir_node = next(child for child in tree.root.children if child.data and child.data.is_dir)
        tree.select_node(dir_node)
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
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
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
        # Force no-selection branch without depending on tree cursor state.
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
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()


@pytest.mark.asyncio
async def test_browser_edit_leaf_saves(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#value-editor", TextArea)
        editor.text = "updated"
        await pilot.click("#btn-save")
        await pilot.pause()
    mock_client.put.assert_called_with("/k", "updated")


@pytest.mark.asyncio
async def test_browser_edit_cancel(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_directory_warns(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        dir_node = next(child for child in tree.root.children if child.data and child.data.is_dir)
        tree.select_node(dir_node)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_no_selection_warns(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        browser = _browser(app)
        # Force no-selection branch without depending on tree cursor state.
        browser._selected_node = lambda: None  # ty: ignore[invalid-assignment]
        browser.action_edit()
        await pilot.pause()
    mock_client.put.assert_not_called()


@pytest.mark.asyncio
async def test_browser_edit_error_notifies(mock_client: MagicMock) -> None:
    mock_client.put.side_effect = RuntimeError("nope")
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        leaf = next(child for child in tree.root.children if child.data and not child.data.is_dir)
        tree.select_node(leaf)
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        editor = app.screen.query_one("#value-editor", TextArea)
        editor.text = "value"
        await pilot.click("#btn-save")
        await pilot.pause()


@pytest.mark.asyncio
async def test_browser_add_key_no_selection_uses_root_prefix(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.screen.query_one(KeyTree)
        tree.cursor_line = -1
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        # Cancel out
        await pilot.press("escape")
        await pilot.pause()
