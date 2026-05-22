"""Right-hand panel: a bordered key/status box stacked above a value box."""

from __future__ import annotations

from typing import Any

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Button, Label, Static, TextArea

from tetcd.etcd.client import EtcdNode


class KeyValuePanel(Vertical):
    """The right-hand column: a key header on top, the value pane below.

    The widget owns two bordered sub-boxes, stacked vertically:

    - **Key box** — shows the currently selected entry as ``<server>://<key>``
      on the left and, while in edit mode, a flat warning-style **Save**
      button paired with a **Cancel** button on the right so the user can
      always see how to commit or discard the buffer without remembering the
      key bindings.
    - **Value box** — either a read-only :class:`Static` rendering of the
      current value or, in edit mode, an editable :class:`TextArea`.

    Clicking the buttons, ``ctrl+s``, and ``escape`` all funnel into the same
    :class:`SaveRequested` / :class:`CancelRequested` messages so the parent
    screen owns the etcd I/O and any confirmation flow.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
    ]

    selected_node: reactive[EtcdNode | None] = reactive(None)
    current_server: reactive[str | None] = reactive(None)
    edit_mode: reactive[bool] = reactive(False)
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
        """Build the panel; edit-mode buffers start empty."""
        super().__init__(**kwargs)
        self._target_key: str = ""
        self._initial_value: str = ""
        self._is_new: bool = False

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
        """Title the boxes and hide the editor/buttons until edit mode kicks in."""
        self.query_one("#kv-value-editor", TextArea).display = False
        self.query_one("#kv-edit-actions", Horizontal).display = False
        self.query_one("#key-header-box").border_title = "Key"
        self.query_one("#value-box").border_title = "Value"

    def start_edit(
        self,
        *,
        target_key: str,
        initial_value: str = "",
        is_new: bool = False,
        server_label: str | None = None,
    ) -> None:
        """Enter edit mode for ``target_key`` pre-populated with ``initial_value``.

        Set ``is_new=True`` when the key does not yet exist, so the parent
        screen can refresh the tree after the put completes. ``server_label``
        replaces the panel's current server context so the key-header line
        renders the full ``<server>://<key>`` path during the edit.
        """
        self._target_key = target_key
        self._initial_value = initial_value
        self._is_new = is_new
        if server_label is not None:
            self.current_server = server_label
        editor = self.query_one("#kv-value-editor", TextArea)
        editor.text = initial_value
        self.dirty = False
        self.edit_mode = True
        editor.focus()

    def exit_edit_mode(self) -> None:
        """Leave edit mode and reset the buffer-tracking state."""
        self.edit_mode = False
        self.dirty = False
        self._target_key = ""
        self._initial_value = ""
        self._is_new = False

    def action_save(self) -> None:
        """Forward ``ctrl+s`` to the parent screen via :class:`SaveRequested`."""
        if not self.edit_mode:
            return
        editor = self.query_one("#kv-value-editor", TextArea)
        self.post_message(
            self.SaveRequested(key=self._target_key, value=editor.text, is_new=self._is_new)
        )

    def action_cancel(self) -> None:
        """Forward ``escape`` to the parent screen via :class:`CancelRequested`."""
        if not self.edit_mode:
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

    def watch_selected_node(self, node: EtcdNode | None) -> None:
        """Re-render the read-only view when the parent reassigns the node."""
        self._refresh_view()

    def watch_current_server(self, server: str | None) -> None:
        """Repaint the key-header label when the active server changes."""
        self._refresh_view()

    def watch_edit_mode(self, edit_mode: bool) -> None:
        """Swap the static view for the editor (or back) when the mode flips."""
        self.query_one("#kv-value-editor", TextArea).display = edit_mode
        self.query_one("#kv-value-content", Static).display = not edit_mode
        self.query_one("#kv-edit-actions", Horizontal).display = edit_mode
        self._refresh_view()

    def watch_dirty(self, dirty: bool) -> None:
        """Repaint the save button when the dirty flag flips."""
        self._refresh_view()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Update ``dirty`` after every keystroke in the editor."""
        if self.edit_mode:
            self.dirty = event.text_area.text != self._initial_value

    def _refresh_view(self) -> None:
        """Synchronise the labels with the current mode + selection state."""
        key_label = self.query_one("#kv-key-label", Label)
        content = self.query_one("#kv-value-content", Static)

        if self.edit_mode:
            key_label.update(self._format_key(self._target_key))
            save_button = self.query_one("#kv-save-button", Button)
            save_button.label = "Save *" if self.dirty else "Save"
            save_button.refresh(layout=True)
            return

        node = self.selected_node
        if node is None:
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

    def _format_key(self, key: str) -> str:
        """Prefix ``key`` with the active server label as ``<server>://<key>``."""
        server = self.current_server
        if not server:
            return key
        return f"{server}://{key}"
