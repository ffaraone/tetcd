"""Modal screens for collecting key paths and confirming destructive actions.

Editing a value is no longer a modal — it happens inline in the value pane.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Grid
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label


class AddKeyScreen(ModalScreen[str | None]):
    """Modal screen for picking the path of a new key.

    The value is *not* collected here: once the user confirms a path, the
    parent screen switches the value pane into edit mode so the value can be
    typed in place with full-screen real estate.

    The dialog shows the selected ``<server>://<prefix>`` context above the
    input and pre-fills the input with the prefix so the user only has to
    type the leaf name. A submission equal to the prefix alone is rejected
    so callers never receive an empty leaf.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddKeyScreen {
        align: center middle;
        background: $background 50%;
    }
    AddKeyScreen #dialog {
        grid-size: 2 4;
        grid-rows: 1 1 3 3;
        grid-gutter: 1 2;
        padding: 0 2 1 2;
        width: 60;
        height: 13;
        border: thick $background 80%;
        background: $surface;
    }
    AddKeyScreen #dialog-title {
        column-span: 2;
        height: 1;
        width: 1fr;
        content-align: center middle;
        background: $panel;
        color: $foreground;
        text-style: bold;
    }
    AddKeyScreen #field-label {
        column-span: 2;
        height: 1;
        color: $text-muted;
    }
    AddKeyScreen #key-input {
        column-span: 2;
    }
    AddKeyScreen Button {
        width: 100%;
    }
    """

    def __init__(self, prefix: str = "/", server_label: str | None = None) -> None:
        """Pre-fill the input with ``prefix`` under the selected ``server_label``."""
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"
        self._server_label = server_label

    def compose(self) -> ComposeResult:
        """Yield the dialog grid: title bar, context line, input, action buttons."""
        yield Grid(
            Label("Add Key", id="dialog-title"),
            Label(_under_label(self._server_label, self._prefix), id="field-label"),
            Input(value=self._prefix, placeholder=f"{self._prefix}my-key", id="key-input"),
            Button("Next", variant="primary", id="btn-add"),
            Button("Cancel", id="btn-cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Park the cursor at the end of the pre-filled prefix and focus."""
        key_input = self.query_one("#key-input", Input)
        key_input.cursor_position = len(self._prefix)
        key_input.focus()

    def action_cancel(self) -> None:
        """Dismiss returning ``None`` so the caller skips opening the editor."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the key path on ``btn-add``; cancel otherwise.

        Empty inputs and submissions equal to just the pre-filled prefix are
        ignored so the modal stays open until the user types a leaf name or
        explicitly cancels.
        """
        if event.button.id == "btn-add":
            key = self.query_one("#key-input", Input).value.strip().rstrip("/")
            if key and key != self._prefix.rstrip("/"):
                self.dismiss(key)
        else:
            self.dismiss(None)


class AddDirScreen(ModalScreen[str | None]):
    """Modal screen for adding a new directory.

    Mirrors :class:`AddKeyScreen`: shows the ``<server>://<prefix>`` context
    above the input, pre-fills the input with the prefix so the user only
    types the new directory name, and rejects submissions equal to just the
    prefix.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    AddDirScreen {
        align: center middle;
        background: $background 50%;
    }
    AddDirScreen #dialog {
        grid-size: 2 4;
        grid-rows: 1 1 3 3;
        grid-gutter: 1 2;
        padding: 0 2 1 2;
        width: 60;
        height: 13;
        border: thick $background 80%;
        background: $surface;
    }
    AddDirScreen #dialog-title {
        column-span: 2;
        height: 1;
        width: 1fr;
        content-align: center middle;
        background: $panel;
        color: $foreground;
        text-style: bold;
    }
    AddDirScreen #field-label {
        column-span: 2;
        height: 1;
        color: $text-muted;
    }
    AddDirScreen #dir-input {
        column-span: 2;
    }
    AddDirScreen Button {
        width: 100%;
    }
    """

    def __init__(self, prefix: str = "/", server_label: str | None = None) -> None:
        """Pre-fill the input with ``prefix`` under the selected ``server_label``."""
        super().__init__()
        self._prefix = prefix.rstrip("/") + "/"
        self._server_label = server_label

    def compose(self) -> ComposeResult:
        """Yield the dialog grid: title bar, context line, input, action buttons."""
        yield Grid(
            Label("Add Directory", id="dialog-title"),
            Label(_under_label(self._server_label, self._prefix), id="field-label"),
            Input(value=self._prefix, placeholder=f"{self._prefix}my-dir", id="dir-input"),
            Button("Create", variant="primary", id="btn-create"),
            Button("Cancel", id="btn-cancel"),
            id="dialog",
        )

    def on_mount(self) -> None:
        """Park the cursor at the end of the pre-filled prefix and focus."""
        dir_input = self.query_one("#dir-input", Input)
        dir_input.cursor_position = len(self._prefix)
        dir_input.focus()

    def action_cancel(self) -> None:
        """Dismiss returning ``None``."""
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Submit the directory path on ``btn-create``; cancel otherwise.

        Empty inputs and submissions equal to just the pre-filled prefix are
        ignored so the modal stays open until the user types a directory
        name or explicitly cancels.
        """
        if event.button.id == "btn-create":
            path = self.query_one("#dir-input", Input).value.strip().rstrip("/")
            if path and path != self._prefix.rstrip("/"):
                self.dismiss(path)
        else:
            self.dismiss(None)


class ConfirmScreen(ModalScreen[bool]):
    """Generic confirmation modal returning ``True`` for yes, ``False`` for no.

    Renders as a centred dialog on top of whatever screen is active. The
    translucent border keeps the underlying view partially visible so the
    user sees the context the prompt refers to.
    """

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
    ]

    DEFAULT_CSS = """
    ConfirmScreen {
        align: center middle;
        background: $background 50%;
    }
    ConfirmScreen #dialog {
        grid-size: 2 3;
        grid-rows: 1 1fr 3;
        grid-gutter: 1 2;
        padding: 0 2 1 2;
        width: 60;
        height: 11;
        border: thick $background 80%;
        background: $surface;
    }
    ConfirmScreen #dialog-title {
        column-span: 2;
        height: 1;
        width: 1fr;
        content-align: center middle;
        background: $panel;
        color: $foreground;
        text-style: bold;
    }
    ConfirmScreen #message {
        column-span: 2;
        height: 1fr;
        width: 1fr;
        content-align: center middle;
        text-style: bold;
    }
    ConfirmScreen Button {
        width: 100%;
    }
    """

    def __init__(self, message: str) -> None:
        """Show ``message`` as the confirmation prompt."""
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        """Yield the dialog grid: title bar, centred message, Yes/No buttons."""
        yield Grid(
            Label("Confirm", id="dialog-title"),
            Label(self._message, id="message"),
            Button("Yes [y]", variant="primary", id="btn-yes"),
            Button("No [n]", id="btn-no"),
            id="dialog",
        )

    def action_confirm(self) -> None:
        """Dismiss with ``True`` to confirm the action."""
        self.dismiss(True)

    def action_cancel(self) -> None:
        """Dismiss with ``False`` to abort."""
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Map ``btn-yes`` to confirm and anything else to cancel."""
        self.dismiss(event.button.id == "btn-yes")


def _under_label(server_label: str | None, prefix: str) -> str:
    """Render the ``Under: <server>://<prefix>`` context line for add modals.

    The helper centralises the formatting used by :class:`AddKeyScreen` and
    :class:`AddDirScreen` so both modals display the selected node context
    identically. ``server_label`` is omitted when ``None`` (e.g. the modal
    was opened with no selection).
    """
    target = f"{server_label}://{prefix}" if server_label else prefix
    return f"Under: {target}"
