"""Root Textual ``App`` that wires the etcd client to the browser screen."""

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
        """Bind the app to an etcd ``client`` and toggle the startup splash."""
        super().__init__()
        self.etcd = client
        self.show_splash = show_splash

    def compose(self) -> ComposeResult:
        """Yield the persistent header and footer (screens fill the middle)."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Push the browser screen and, optionally, the splash on top."""
        self.push_screen(BrowserScreen(self.etcd))
        if self.show_splash:
            self.push_screen(SplashScreen())
