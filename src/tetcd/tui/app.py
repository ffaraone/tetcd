"""Root Textual ``App`` that wires the configured servers to the browser."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header

from tetcd.etcd.client import Server
from tetcd.tui.screens.browser import BrowserScreen
from tetcd.tui.screens.splash import SplashScreen


class TetcdApp(App[None]):
    """Main tetcd application."""

    TITLE = "tetcd"
    SUB_TITLE = "etcd TUI"
    CSS = """
    BrowserScreen {
        background: $surface;
    }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, servers: list[Server], show_splash: bool = True) -> None:
        """Wire the app to one-or-more etcd ``servers`` and the startup splash."""
        super().__init__()
        self.servers = servers
        self.show_splash = show_splash

    def compose(self) -> ComposeResult:
        """Yield the persistent header and footer (screens fill the middle)."""
        yield Header()
        yield Footer()

    def on_mount(self) -> None:
        """Push the browser screen and, optionally, the splash on top."""
        self.push_screen(BrowserScreen(self.servers))
        if self.show_splash:
            self.push_screen(SplashScreen())
