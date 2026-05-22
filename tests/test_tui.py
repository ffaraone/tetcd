from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tetcd.etcd.client import EtcdNode
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens import splash as splash_module
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.screens.splash import SplashScreen
from tetcd.tui.widgets.key_tree import KeyTree


@pytest.fixture
def mock_client() -> MagicMock:
    """Return a stub etcd client whose ``list`` yields one dir and one key."""
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
    """The Textual app boots and exposes the expected title."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test():
        assert app.title == "tetcd"


@pytest.mark.asyncio
async def test_quit_binding(mock_client: MagicMock) -> None:
    """Pressing ``q`` exits the app cleanly."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.press("q")


@pytest.mark.asyncio
async def test_key_tree_present(mock_client: MagicMock) -> None:
    """The browser screen mounts a ``KeyTree`` widget on startup."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test():
        assert app.screen.query_one(KeyTree) is not None


@pytest.mark.asyncio
async def test_refresh_action(mock_client: MagicMock) -> None:
    """Pressing ``r`` triggers refresh without crashing."""
    app = TetcdApp(client=mock_client, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.press("r")


@pytest.mark.asyncio
async def test_splash_shown_on_startup(mock_client: MagicMock) -> None:
    """``show_splash=True`` puts the splash modal on top of the stack."""
    app = TetcdApp(client=mock_client, show_splash=True)
    async with app.run_test():
        assert isinstance(app.screen, SplashScreen)


@pytest.mark.asyncio
async def test_splash_dismissed_on_key(mock_client: MagicMock) -> None:
    """Any key press dismisses the splash and reveals the browser screen."""
    app = TetcdApp(client=mock_client, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("space")
        assert isinstance(app.screen, BrowserScreen)


@pytest.mark.asyncio
async def test_splash_dismissed_on_click(mock_client: MagicMock) -> None:
    """A mouse click dismisses the splash."""
    app = TetcdApp(client=mock_client, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        await pilot.click()
        assert isinstance(app.screen, BrowserScreen)


@pytest.mark.asyncio
async def test_splash_auto_dismiss(monkeypatch: pytest.MonkeyPatch, mock_client: MagicMock) -> None:
    """The splash auto-dismisses after ``AUTO_DISMISS_SECONDS`` elapses.

    The dismiss happens through a Textual timer plus an unawaited
    ``AwaitComplete``, so a single fixed pause was flaky on slow CI runners
    (the screen pop was still pending when the assertion ran). Poll for the
    transition with a generous overall deadline instead.
    """
    monkeypatch.setattr(splash_module.SplashScreen, "AUTO_DISMISS_SECONDS", 0.5)

    app = TetcdApp(client=mock_client, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        for _ in range(60):
            await pilot.pause(0.1)
            if isinstance(app.screen, BrowserScreen):
                break
        assert isinstance(app.screen, BrowserScreen)
