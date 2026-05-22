from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from textual.app import App, ComposeResult
from textual.pilot import Pilot

from tetcd.etcd.client import EtcdNode
from tetcd.tui.app import TetcdApp
from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen, EditKeyScreen


def _client() -> MagicMock:
    client = MagicMock()
    client.list.return_value = [
        EtcdNode(key="/app", is_dir=True),
        EtcdNode(key="/config", is_dir=True),
        EtcdNode(key="/version", value="1.0.0"),
    ]
    client.get.return_value = EtcdNode(key="/version", value="1.0.0")
    client.health.return_value = True
    return client


def test_splash_screen_snapshot(snap_compare: Any) -> None:
    assert snap_compare(TetcdApp(client=_client(), show_splash=True))


def test_browser_screen_snapshot(snap_compare: Any) -> None:
    assert snap_compare(TetcdApp(client=_client(), show_splash=False))


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
    assert snap_compare(
        _ModalHost(lambda: AddKeyScreen(prefix="/app")),
        run_before=_settle,
    )


def test_add_dir_modal_snapshot(snap_compare: Any) -> None:
    assert snap_compare(
        _ModalHost(lambda: AddDirScreen(prefix="/app")),
        run_before=_settle,
    )


def test_edit_key_modal_snapshot(snap_compare: Any) -> None:
    assert snap_compare(
        _ModalHost(lambda: EditKeyScreen("/app/host", "localhost")),
        run_before=_settle,
    )


def test_confirm_modal_snapshot(snap_compare: Any) -> None:
    assert snap_compare(
        _ModalHost(lambda: ConfirmScreen("Delete key '/app/host'?")),
        run_before=_settle,
    )
