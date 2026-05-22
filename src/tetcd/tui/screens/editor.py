from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, TextArea


class EditKeyScreen(ModalScreen[str | None]):
    """Modal screen for editing an existing key's value."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "save", "Save"),
    ]

    DEFAULT_CSS = """
    EditKeyScreen {
        align: center middle;
    }
    EditKeyScreen > .dialog {
        background: $surface;
        border: thick $primary;
        padding: 1 2;
        width: 70;
        height: auto;
        max-height: 30;
    }
    EditKeyScreen .dialog-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    EditKeyScreen .button-row {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, key: str, value: str) -> None:
        super().__init__()
        self._key = key
        self._initial_value = value

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(f"Editing: {self._key}", classes="dialog-title")
            yield TextArea(self._initial_value, id="value-editor", language=None)
            with Horizontal(classes="button-row"):
                yield Button("Save [ctrl+s]", variant="primary", id="btn-save")
                yield Button("Cancel [esc]", variant="default", id="btn-cancel")

    def action_save(self) -> None:
        editor = self.query_one("#value-editor", TextArea)
        self.dismiss(editor.text)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            self.action_save()
        else:
            self.action_cancel()


class AddKeyScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for adding a new key."""

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
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Add Key", classes="dialog-title")
            yield Label("Key path:", classes="field-label")
            yield Input(placeholder=f"{self._prefix}my-key", id="key-input")
            yield Label("Value:", classes="field-label")
            yield Input(placeholder="value", id="value-input")
            with Horizontal(classes="button-row"):
                yield Button("Add", variant="primary", id="btn-add")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-add":
            key = self.query_one("#key-input", Input).value.strip()
            value = self.query_one("#value-input", Input).value
            if key:
                self.dismiss((key, value))
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
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label("Add Directory", classes="dialog-title")
            yield Label("Directory path:", classes="field-label")
            yield Input(placeholder=f"{self._prefix}my-dir", id="dir-input")
            with Horizontal(classes="button-row"):
                yield Button("Create", variant="primary", id="btn-create")
                yield Button("Cancel", variant="default", id="btn-cancel")

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-create":
            path = self.query_one("#dir-input", Input).value.strip()
            if path:
                self.dismiss(path)
        else:
            self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Generic confirmation modal."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
    }
    ConfirmScreen > .dialog {
        background: $surface;
        border: thick $warning;
        padding: 1 2;
        width: 50;
        height: auto;
    }
    ConfirmScreen .message {
        margin-bottom: 1;
    }
    ConfirmScreen .button-row {
        align: right middle;
        height: auto;
        margin-top: 1;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog"):
            yield Label(self._message, classes="message")
            with Horizontal(classes="button-row"):
                yield Button("Yes [y]", variant="warning", id="btn-yes")
                yield Button("No [n]", variant="default", id="btn-no")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-yes")
