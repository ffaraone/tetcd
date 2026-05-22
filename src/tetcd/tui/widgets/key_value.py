from __future__ import annotations

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Static

from tetcd.etcd.client import EtcdNode


class KeyValuePanel(Widget):
    """Displays the full key path and value for the currently selected node."""

    BORDER_TITLE = "Value"

    selected_node: reactive[EtcdNode | None] = reactive(None)

    DEFAULT_CSS = """
    KeyValuePanel {
        border: round $primary;
        padding: 1 2;
        height: 100%;
    }
    KeyValuePanel .kv-key {
        color: $accent;
        text-style: bold;
        margin-bottom: 1;
    }
    KeyValuePanel .kv-hint {
        color: $text-muted;
        text-style: italic;
    }
    KeyValuePanel .kv-value {
        color: $text;
    }
    """

    def compose(self) -> ComposeResult:
        yield Label("", classes="kv-key", id="kv-key-label")
        yield Static("", classes="kv-value", id="kv-value-content")

    def watch_selected_node(self, node: EtcdNode | None) -> None:
        key_label = self.query_one("#kv-key-label", Label)
        value_content = self.query_one("#kv-value-content", Static)

        if node is None:
            key_label.update("No key selected")
            value_content.update("")
            return

        key_label.update(f"Key: {node.key}")
        if node.is_dir:
            value_content.update("[dim italic]<directory>[/dim italic]")
        elif node.value is not None:
            value_content.update(node.value)
        else:
            value_content.update("[dim italic]<empty>[/dim italic]")
