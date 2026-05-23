"""Right-hand panel: a bordered key/status box stacked above a value box."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, TextArea

from tetcd.etcd.client import EtcdNode, Server


class KeyValuePanel(Vertical):
    """The right-hand column: a key header on top, the value pane below.

    The panel is a pure view: it reads ``active_server`` / ``active_node`` /
    ``edit_mode`` / ``edit_target_key`` / ``edit_initial_value`` from its
    enclosing screen and re-renders whenever any of them changes. It owns
    only the TextArea buffer state (and a derived ``dirty`` flag) while in
    edit mode.

    Save and Cancel intents flow up via :class:`SaveRequested` /
    :class:`CancelRequested` messages so the screen owns the etcd I/O and
    any confirmation flow.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    dirty: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    KeyValuePanel {
        height: 100%;
    }
    KeyValuePanel #key-header-box {
        height: 3;
        border: round $primary;
        padding: 0 1;
    }
    KeyValuePanel #kv-key-label {
        width: 1fr;
        content-align: left middle;
    }
    KeyValuePanel #kv-edit-actions {
        width: auto;
        height: 1;
        align: right middle;
        padding-left: 1;
    }
    KeyValuePanel #kv-save-button,
    KeyValuePanel #kv-cancel-button {
        height: 1;
        min-height: 1;
        border: none;
        padding: 0 2;
        margin: 0 0 0 1;
        text-style: bold;
    }
    KeyValuePanel #kv-save-button {
        background: $warning;
        color: $background;
        min-width: 10;
    }
    KeyValuePanel #kv-save-button:hover {
        background: $warning-lighten-1;
    }
    KeyValuePanel #kv-cancel-button {
        background: $surface-lighten-2;
        color: $text;
        text-style: none;
        min-width: 10;
    }
    KeyValuePanel #kv-cancel-button:hover {
        background: $surface-lighten-3;
    }
    KeyValuePanel #value-box {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    KeyValuePanel #kv-value-content {
        height: auto;
    }
    KeyValuePanel #kv-value-editor {
        height: 1fr;
    }
    """

    class SaveRequested(Message):
        """Posted when the user commits the editor buffer with ``ctrl+s``."""

        def __init__(self, key: str, value: str, is_new: bool) -> None:
            """Carry the target ``key``/``value`` and whether it is a new key."""
            super().__init__()
            self.key = key
            self.value = value
            self.is_new = is_new

    class CancelRequested(Message):
        """Posted when the user asks to leave edit mode with ``escape``."""

        def __init__(self, dirty: bool) -> None:
            """Tell the parent whether the buffer had unsaved changes."""
            super().__init__()
            self.dirty = dirty

    def __init__(self, **kwargs: Any) -> None:
        """Build the panel; no local state is required beyond the dirty flag."""
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        """Yield the key-header box and the value-box (with both view modes)."""
        with Horizontal(id="key-header-box"):
            yield Label("No key selected", id="kv-key-label")
            with Horizontal(id="kv-edit-actions"):
                yield Button("Save", id="kv-save-button")
                yield Button("Cancel", id="kv-cancel-button")
        with Vertical(id="value-box"):
            yield Static("", id="kv-value-content")
            yield TextArea("", id="kv-value-editor", language=None)

    def on_mount(self) -> None:
        """Title the boxes, hide the editor, and subscribe to screen state."""
        self.query_one("#kv-value-editor", TextArea).display = False
        self.query_one("#kv-edit-actions", Horizontal).display = False
        self.query_one("#key-header-box").border_title = "Key"
        self.query_one("#value-box").border_title = "Value"
        # Subscribe to the enclosing screen's selection + edit state.
        screen = self.screen
        self.watch(screen, "active_server", self._on_state_change, init=False)
        self.watch(screen, "active_node", self._on_state_change, init=False)
        self.watch(screen, "edit_mode", self._on_edit_mode_change, init=False)
        self._refresh_view()

    def action_save(self) -> None:
        """Forward ``ctrl+s`` to the parent screen via :class:`SaveRequested`."""
        if not self._read_edit_mode():
            return
        editor = self.query_one("#kv-value-editor", TextArea)
        target_key = self._read("edit_target_key", "")
        is_new = self._read("edit_is_new", False)
        self.post_message(self.SaveRequested(key=target_key, value=editor.text, is_new=is_new))

    def action_cancel(self) -> None:
        """Forward ``escape`` to the parent screen via :class:`CancelRequested`."""
        if not self._read_edit_mode():
            return
        self.post_message(self.CancelRequested(dirty=self.dirty))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route Save/Cancel button clicks through the same actions as keys."""
        if event.button.id == "kv-save-button":
            event.stop()
            self.action_save()
        elif event.button.id == "kv-cancel-button":
            event.stop()
            self.action_cancel()

    def watch_dirty(self, dirty: bool) -> None:
        """Repaint the save button when the dirty flag flips."""
        if self._read_edit_mode():
            self._refresh_save_button()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update ``dirty`` after every keystroke in the editor."""
        if self._read_edit_mode():
            self.dirty = event.text_area.text != self._read("edit_initial_value", "")

    def _on_state_change(self, _value: Any) -> None:
        """Re-render after any non-edit-mode state attribute changes."""
        self._refresh_view()

    def _on_edit_mode_change(self, edit_mode: bool) -> None:
        """Swap the static view for the editor (or back) when the mode flips."""
        editor = self.query_one("#kv-value-editor", TextArea)
        content = self.query_one("#kv-value-content", Static)
        actions = self.query_one("#kv-edit-actions", Horizontal)
        editor.display = edit_mode
        content.display = not edit_mode
        actions.display = edit_mode
        if edit_mode:
            editor.text = self._read("edit_initial_value", "")
            self.dirty = False
            editor.focus()
        self._refresh_view()

    def _refresh_view(self) -> None:
        """Synchronise the labels with the current screen + selection state."""
        key_label = self.query_one("#kv-key-label", Label)
        content = self.query_one("#kv-value-content", Static)

        if self._read_edit_mode():
            target_key = self._read("edit_target_key", "")
            key_label.update(self._format_key(target_key))
            self._refresh_save_button()
            return

        node = self._read("active_node", None)
        if not isinstance(node, EtcdNode):
            key_label.update("No key selected")
            content.update("")
            return

        key_label.update(self._format_key(node.key))
        if node.is_dir:
            content.update("<directory>")
        elif node.value is not None:
            content.update(node.value)
        else:
            content.update("<empty>")

    def _refresh_save_button(self) -> None:
        """Toggle the dirty-marker suffix on the Save button."""
        save_button = self.query_one("#kv-save-button", Button)
        save_button.label = "Save *" if self.dirty else "Save"
        save_button.refresh(layout=True)

    def _format_key(self, key: str) -> str:
        """Prefix ``key`` with the active server label as ``<server>:<key>``."""
        server = self._read("active_server", None)
        if not isinstance(server, Server):
            return key
        return f"{server.config.label}:{key}"

    def _read(self, attr: str, default: Any) -> Any:
        """Fetch ``attr`` from the enclosing screen, falling back to ``default``."""
        return getattr(self.screen, attr, default)

    def _read_edit_mode(self) -> bool:
        """Return the screen's current ``edit_mode``, defaulting to ``False``."""
        return bool(self._read("edit_mode", False))
