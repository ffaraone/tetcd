from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from tests.conftest import make_server
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens import splash as splash_module
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.screens.splash import SplashScreen
from tetcd.tui.widgets.key_tree import KeyTree


@pytest.fixture
def servers() -> list[Server]:
    """Return one Server with a stub etcd client (one dir + one leaf)."""
    client = MagicMock()
    client.list.return_value = [
        EtcdNode(key="/app", is_dir=True),
        EtcdNode(key="/config", value="test"),
    ]
    client.get.return_value = EtcdNode(key="/config", value="test")
    client.health.return_value = True
    return [make_server("Local", client=client)]


@pytest.mark.asyncio
async def test_app_starts(servers: list[Server]) -> None:
    """The Textual app boots and exposes the expected title."""
    app = TetcdApp(servers=servers, show_splash=False)
    async with app.run_test():
        assert app.title == "tetcd"


@pytest.mark.asyncio
async def test_quit_binding(servers: list[Server]) -> None:
    """Pressing ``q`` exits the app cleanly."""
    app = TetcdApp(servers=servers, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.press("q")


@pytest.mark.asyncio
async def test_key_tree_present(servers: list[Server]) -> None:
    """The browser screen mounts a ``KeyTree`` widget on startup."""
    app = TetcdApp(servers=servers, show_splash=False)
    async with app.run_test():
        assert app.screen.query_one(KeyTree) is not None


@pytest.mark.asyncio
async def test_refresh_action(servers: list[Server]) -> None:
    """Pressing ``r`` triggers refresh without crashing."""
    app = TetcdApp(servers=servers, show_splash=False)
    async with app.run_test() as pilot:
        await pilot.press("r")


@pytest.mark.asyncio
async def test_splash_shown_on_startup(servers: list[Server]) -> None:
    """``show_splash=True`` puts the splash modal on top of the stack."""
    app = TetcdApp(servers=servers, show_splash=True)
    async with app.run_test():
        assert isinstance(app.screen, SplashScreen)


@pytest.mark.asyncio
async def test_splash_dismissed_on_key(servers: list[Server]) -> None:
    """Any key press dismisses the splash and reveals the browser screen."""
    app = TetcdApp(servers=servers, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        await pilot.press("space")
        assert isinstance(app.screen, BrowserScreen)


@pytest.mark.asyncio
async def test_splash_dismissed_on_click(servers: list[Server]) -> None:
    """A mouse click dismisses the splash."""
    app = TetcdApp(servers=servers, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        await pilot.click()
        assert isinstance(app.screen, BrowserScreen)


@pytest.mark.asyncio
async def test_splash_auto_dismiss(monkeypatch: pytest.MonkeyPatch, servers: list[Server]) -> None:
    """The splash auto-dismisses after ``AUTO_DISMISS_SECONDS`` elapses."""
    monkeypatch.setattr(splash_module.SplashScreen, "AUTO_DISMISS_SECONDS", 0.5)

    app = TetcdApp(servers=servers, show_splash=True)
    async with app.run_test() as pilot:
        assert isinstance(app.screen, SplashScreen)
        for _ in range(60):
            await pilot.pause(0.1)
            if isinstance(app.screen, BrowserScreen):
                break
        assert isinstance(app.screen, BrowserScreen)
