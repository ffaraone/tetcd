from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.pilot import Pilot
from textual.widgets import TextArea

from tests.conftest import make_server
from tetcd.etcd.client import EtcdNode, Server
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen
from tetcd.tui.widgets.key_value import KeyValuePanel


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

    async def enter_edit(pilot: Pilot) -> None:
        await pilot.pause()
        panel = pilot.app.screen.query_one(KeyValuePanel)
        panel.selected_node = EtcdNode(key="/version", value="1.0.0")
        panel.start_edit(target_key="/version", initial_value="1.0.0")
        await pilot.pause()

    assert snap_compare(
        TetcdApp(servers=_multi_servers(), show_splash=False),
        run_before=enter_edit,
    )


def test_browser_inline_editor_dirty_snapshot(snap_compare: Any) -> None:
    """Browser with the editor showing the dirty indicator after a buffer edit."""

    async def make_dirty(pilot: Pilot) -> None:
        await pilot.pause()
        panel = pilot.app.screen.query_one(KeyValuePanel)
        panel.selected_node = EtcdNode(key="/version", value="1.0.0")
        panel.start_edit(target_key="/version", initial_value="1.0.0")
        await pilot.pause()
        pilot.app.screen.query_one("#kv-value-editor", TextArea).text = "1.0.1"
        await pilot.pause()

    assert snap_compare(
        TetcdApp(servers=_multi_servers(), show_splash=False),
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
    """The simplified add-key modal that only collects a path."""
    assert snap_compare(
        _ModalHost(lambda: AddKeyScreen(prefix="/app")),
        run_before=_settle,
    )


def test_add_dir_modal_snapshot(snap_compare: Any) -> None:
    assert snap_compare(
        _ModalHost(lambda: AddDirScreen(prefix="/app")),
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
