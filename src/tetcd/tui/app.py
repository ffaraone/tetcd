from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from tetcd.etcd.client import EtcdClientProtocol
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.screens.splash import SplashScreen


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

    def __init__(self, client: EtcdClientProtocol, show_splash: bool = True) -> None:
        super().__init__()
        self.etcd = client
        self.show_splash = show_splash

    def on_mount(self) -> None:
        self.push_screen(BrowserScreen(self.etcd))
        if self.show_splash:
            self.push_screen(SplashScreen())

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
