from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.events import Click, Key
from textual.screen import ModalScreen
from textual.widgets import Static

_LOGO_LINES = (
    r" ████████╗███████╗████████╗ ██████╗██████╗ ",
    r" ╚══██╔══╝██╔════╝╚══██╔══╝██╔════╝██╔══██╗",
    r"    ██║   █████╗     ██║   ██║     ██║  ██║",
    r"    ██║   ██╔══╝     ██║   ██║     ██║  ██║",
    r"    ██║   ███████╗   ██║   ╚██████╗██████╔╝",
    r"    ╚═╝   ╚══════╝   ╚═╝    ╚═════╝╚═════╝ ",
)
_LOGO_COLORS = (
    "bright_cyan",
    "cyan",
    "bright_blue",
    "magenta",
    "bright_magenta",
    "red",
)
LOGO = "\n".join(f"[bold {c}]{line}[/]" for line, c in zip(_LOGO_LINES, _LOGO_COLORS, strict=False))


class SplashScreen(ModalScreen[None]):
    """Splash screen shown briefly at startup."""

    AUTO_DISMISS_SECONDS = 5.0

    DEFAULT_CSS = """
    SplashScreen {
        align: center middle;
        background: $surface 70%;
    }
    SplashScreen > .splash {
        background: $panel;
        border: thick $primary;
        padding: 2 4;
        width: auto;
        height: auto;
    }
    SplashScreen .logo {
        width: auto;
        height: auto;
        content-align: center middle;
    }
    SplashScreen .tagline {
        margin-top: 1;
        width: 100%;
        color: $accent;
        text-style: italic;
        content-align: center middle;
    }
    SplashScreen .hint {
        margin-top: 1;
        width: 100%;
        color: $text-muted;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        with Container(classes="splash"):
            yield Static(LOGO, classes="logo")
            yield Static("a keyboard-driven TUI for etcd", classes="tagline")
            yield Static("press any key or click to continue", classes="hint")

    def on_mount(self) -> None:
        self.set_timer(self.AUTO_DISMISS_SECONDS, self._auto_dismiss)

    def _auto_dismiss(self) -> None:
        if self.is_attached:
            self.dismiss(None)

    def on_key(self, event: Key) -> None:
        event.stop()
        self.dismiss(None)

    def on_click(self, event: Click) -> None:
        event.stop()
        self.dismiss(None)
