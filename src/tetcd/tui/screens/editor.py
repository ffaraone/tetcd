"""Modal screens for collecting key paths and confirming destructive actions.

Editing a value is no longer a modal — it happens inline in the value pane.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class AddKeyScreen(ModalScreen[str | None]):
    """Modal screen for picking the path of a new key.

    The value is *not* collected here: once the user confirms a path, the
    parent screen switches the value pane into edit mode so the value can be
    typed in place with full-screen real estate.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddKeyScreen {
        align: center middle;
    }
    AddKeyScreen > .dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    AddKeyScreen .dialog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    AddKeyScreen .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    AddKeyScreen .button-row {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, prefix: str = "/") -> None:
        """Pre-fill the placeholder using ``prefix`` as the parent path hint."""
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"

    def compose(self) -> ComposeResult:
        """Yield the key-path input and the action buttons."""
        with Vertical(classes="dialog"):
            yield Label("Add Key", classes="dialog-title")
            yield Label("Key path:", classes="field-label")
            yield Input(placeholder=f"{self._prefix}my-key", id="key-input")
            with Horizontal(classes="button-row"):
                yield Button("Next", variant="primary", id="btn-add")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def action_cancel(self) -> None:
        """Dismiss returning ``None`` so the caller skips opening the editor."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the key path on ``btn-add``; cancel otherwise.

        A blank path is ignored so the modal stays open until the user either
        types a valid path or explicitly cancels.
        """
        if event.button.id == "btn-add":
            key = self.query_one("#key-input", Input).value.strip()
            if key:
                self.dismiss(key)
        else:
            self.dismiss(None)


class AddDirScreen(ModalScreen[str | None]):
    """Modal screen for adding a new directory."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddDirScreen {
        align: center middle;
    }
    AddDirScreen > .dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 60;
        height: auto;
    }
    AddDirScreen .dialog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    AddDirScreen .field-label {
        margin-top: 1;
        color: $text-muted;
    }
    AddDirScreen .button-row {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, prefix: str = "/") -> None:
        """Pre-fill the placeholder using ``prefix`` as the parent path."""
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"

    def compose(self) -> ComposeResult:
        """Yield the directory input and the action buttons."""
        with Vertical(classes="dialog"):
            yield Label("Add Directory", classes="dialog-title")
            yield Label("Directory path:", classes="field-label")
            yield Input(placeholder=f"{self._prefix}my-dir", id="dir-input")
            with Horizontal(classes="button-row"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def action_cancel(self) -> None:
        """Dismiss returning ``None``."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the directory path on ``btn-create``; cancel otherwise.

        A blank path is ignored so the modal stays open until the user
        either types a valid directory path or explicitly cancels.
        """
        if event.button.id == "btn-create":
            path = self.query_one("#dir-input", Input).value.strip()
            if path:
                self.dismiss(path)
        else:
            self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Generic confirmation modal returning ``True`` for yes, ``False`` for no.

    Renders as a centred dialog on top of whatever screen is active; the rest
    of the UI is dimmed so the prompt is unambiguously modal.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
        background: $background 60%;
    }
    ConfirmScreen > .dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 3;
        width: 60;
        height: auto;
    }
    ConfirmScreen .message {
        width: 100%;
        content-align: center middle;
        text-style: bold;
        margin-bottom: 1;
    }
    ConfirmScreen .button-row {
        align: center middle;
        height: auto;
        margin-top: 1;
    }
    ConfirmScreen Button {
        margin: 0 1;
        min-width: 12;
    }
    """

    def __init__(self, message: str) -> None:
        """Show ``message`` as the confirmation prompt."""
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Yield the prompt and the Yes/No buttons in a centred dialog."""
        with Vertical(classes="dialog"):
            yield Label(self._message, classes="message")
            with Horizontal(classes="button-row"):
                yield Button("Yes [y]", variant="primary", id="btn-yes")
                yield Button("No [n]", variant="default", id="btn-no")

    def action_confirm(self) -> None:
        """Dismiss with ``True`` to confirm the action."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Dismiss with ``False`` to abort."""
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Map ``btn-yes`` to confirm and anything else to cancel."""
        self.dismiss(event.button.id == "btn-yes")
