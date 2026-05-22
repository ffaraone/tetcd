from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from tetcd.etcd.client import EtcdClientProtocol
from tetcd.tui.screens.browser import BrowserScreen


class TetcdApp(App[None]):
    """Main tetcd application."""

    TITLE = "tetcd"
    SUB_TITLE = "etcd TUI"
    CSS = """
    Screen {
        background: $surface;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, client: EtcdClientProtocol) -> None:
        super().__init__()
        self.etcd = client

    def on_mount(self) -> None:
        self.push_screen(BrowserScreen(self.etcd))

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
