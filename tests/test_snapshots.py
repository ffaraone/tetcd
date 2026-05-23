from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import TextArea

from tests.conftest import make_server
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen


def _stub_client(prefix_listings: dict[str, list[EtcdNode]]) -> MagicMock:
    """Return a client whose ``list`` answers from ``prefix_listings``."""
    client = MagicMock()
    client.list.side_effect = lambda prefix: list(prefix_listings.get(prefix, []))
    return client


def _multi_servers() -> list[Server]:
    """Return two servers with predictable keyspaces for snapshots."""
    prod = _stub_client(
        {
            "/": [
                EtcdNode(key="/app", is_dir=True),
                EtcdNode(key="/version", value="1.0.0"),
            ]
        }
    )
    stage = _stub_client({"/": [EtcdNode(key="/config", is_dir=True)]})
    return [make_server("Production", client=prod), make_server("Staging", client=stage)]


# ── app-level snapshots ─────────────────────────────────────────────────────


def test_splash_screen_snapshot(snap_compare: Any) -> None:
    """Initial frame with the splash modal in front of the browser."""
    assert snap_compare(TetcdApp(servers=_multi_servers(), show_splash=True))


def test_browser_screen_snapshot(snap_compare: Any) -> None:
    """Multi-server browser screen with two servers configured."""
    assert snap_compare(TetcdApp(servers=_multi_servers(), show_splash=False))


def test_browser_inline_editor_snapshot(snap_compare: Any) -> None:
    """Browser with the value pane swapped into edit mode (clean buffer)."""
    servers = _multi_servers()

    async def enter_edit(pilot: Pilot) -> None:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, BrowserScreen)
        screen.active_server = servers[0]
        screen.active_node = EtcdNode(key="/version", value="1.0.0")
        screen.edit_target_key = "/version"
        screen.edit_initial_value = "1.0.0"
        screen.edit_is_new = False
        screen.edit_mode = True
        await pilot.pause()

    assert snap_compare(
        TetcdApp(servers=servers, show_splash=False),
        run_before=enter_edit,
    )


def test_browser_inline_editor_dirty_snapshot(snap_compare: Any) -> None:
    """Browser with the editor showing the dirty indicator after a buffer edit."""
    servers = _multi_servers()

    async def make_dirty(pilot: Pilot) -> None:
        await pilot.pause()
        screen = pilot.app.screen
        assert isinstance(screen, BrowserScreen)
        screen.active_server = servers[0]
        screen.active_node = EtcdNode(key="/version", value="1.0.0")
        screen.edit_target_key = "/version"
        screen.edit_initial_value = "1.0.0"
        screen.edit_is_new = False
        screen.edit_mode = True
        await pilot.pause()
        pilot.app.screen.query_one("#kv-value-editor", TextArea).text = "1.0.1"
        await pilot.pause()

    assert snap_compare(
        TetcdApp(servers=servers, show_splash=False),
        run_before=make_dirty,
    )


# ── modal-level snapshots ───────────────────────────────────────────────────


class _ModalHost(App[None]):
    """Bare host that immediately pushes a single modal for snapshotting."""

    def __init__(self, screen_factory: Any) -> None:
        super().__init__()
        self._screen_factory = screen_factory

    def compose(self) -> ComposeResult:
        yield from ()

    def on_mount(self) -> None:
        self.push_screen(self._screen_factory())


async def _settle(pilot: Pilot) -> None:
    await pilot.pause()


def test_add_key_modal_snapshot(snap_compare: Any) -> None:
    """Add-key modal with server context + prefix pre-fill."""
    assert snap_compare(
        _ModalHost(lambda: AddKeyScreen(prefix="/app", server_label="Production")),
        run_before=_settle,
    )


def test_add_dir_modal_snapshot(snap_compare: Any) -> None:
    """Add-dir modal with server context + prefix pre-fill."""
    assert snap_compare(
        _ModalHost(lambda: AddDirScreen(prefix="/app", server_label="Production")),
        run_before=_settle,
    )


def test_confirm_modal_snapshot(snap_compare: Any) -> None:
    assert snap_compare(
        _ModalHost(lambda: ConfirmScreen("Delete key '/app/host'?")),
        run_before=_settle,
    )


def test_discard_changes_confirm_snapshot(snap_compare: Any) -> None:
    """Confirmation shown when escaping out of an edited buffer."""
    assert snap_compare(
        _ModalHost(lambda: ConfirmScreen("Discard unsaved changes?")),
        run_before=_settle,
    )


def test_overwrite_paste_confirm_snapshot(snap_compare: Any) -> None:
    """Confirmation shown when a paste would overwrite an existing key."""
    assert snap_compare(
        _ModalHost(lambda: ConfirmScreen("Overwrite existing '/app/k'?")),
        run_before=_settle,
    )


def test_modal_over_browser_shows_screen_behind_snapshot(snap_compare: Any) -> None:
    """A modal pushed on top of the browser leaves the browser visible behind it."""

    async def open_confirm(pilot: Pilot) -> None:
        await pilot.pause()
        pilot.app.push_screen(ConfirmScreen("Delete key '/version'?"))
        await pilot.pause()

    assert snap_compare(
        TetcdApp(servers=_multi_servers(), show_splash=False),
        run_before=open_confirm,
    )
