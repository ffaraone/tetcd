from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tetcd.etcd.client import EtcdNode
from tetcd.tui.app import TetcdApp


@pytest.fixture
def mock_client() -> MagicMock:
    client = MagicMock()
    client.list.return_value = [
        EtcdNode(key="/app", is_dir=True),
        EtcdNode(key="/config", value="test"),
    ]
    client.get.return_value = EtcdNode(key="/config", value="test")
    client.health.return_value = True
    return client


@pytest.mark.asyncio
async def test_app_starts(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client)
    async with app.run_test() as _pilot:
        assert app.title == "tetcd"


@pytest.mark.asyncio
async def test_quit_binding(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client)
    async with app.run_test() as _pilot:
        await _pilot.press("q")
        # App should exit cleanly


@pytest.mark.asyncio
async def test_key_tree_present(mock_client: MagicMock) -> None:
    from tetcd.tui.widgets.key_tree import KeyTree

    app = TetcdApp(client=mock_client)
    async with app.run_test() as _pilot:
        tree = app.screen.query_one(KeyTree)
        assert tree is not None


@pytest.mark.asyncio
async def test_refresh_action(mock_client: MagicMock) -> None:
    app = TetcdApp(client=mock_client)
    async with app.run_test() as _pilot:
        await _pilot.press("r")
        # Refresh should not crash
