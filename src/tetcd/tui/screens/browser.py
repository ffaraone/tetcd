from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Tree

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode
from tetcd.tui.screens.editor import (
    AddDirScreen,
    AddKeyScreen,
    ConfirmScreen,
    EditKeyScreen,
)
from tetcd.tui.widgets.key_tree import KeyTree
from tetcd.tui.widgets.key_value import KeyValuePanel


class BrowserScreen(Screen[None]):
    """Main browser screen: tree on the left, value panel on the right."""

    BINDINGS = [
        Binding("a", "add_key", "Add Key"),
        Binding("d", "add_dir", "Add Dir"),
        Binding("D", "delete", "Delete"),
        Binding("e", "edit", "Edit"),
        Binding("r", "refresh", "Refresh"),
        Binding("q", "app.quit", "Quit"),
    ]

    DEFAULT_CSS = """
    BrowserScreen Horizontal {
        height: 1fr;
    }
    BrowserScreen KeyTree {
        width: 35%;
        min-width: 25;
        border: round $primary;
    }
    BrowserScreen KeyValuePanel {
        width: 1fr;
        border: round $primary;
    }
    """

    def __init__(self, client: EtcdClientProtocol) -> None:
        super().__init__()
        self.etcd = client

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield KeyTree(self.etcd, id="key-tree")
            yield KeyValuePanel(id="key-value")
        yield Footer()

    # ── tree selection ────────────────────────────────────────────────────────

    def on_tree_node_selected(self, event: Tree.NodeSelected[EtcdNode]) -> None:
        panel = self.query_one("#key-value", KeyValuePanel)
        panel.selected_node = event.node.data

    # ── actions ───────────────────────────────────────────────────────────────

    def _selected_node(self) -> EtcdNode | None:
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        return cursor.data if cursor else None

    def _selected_prefix(self) -> str:
        node = self._selected_node()
        if node is None:
            return "/"
        if node.is_dir:
            return node.key
        return node.parent_key

    def action_add_key(self) -> None:
        def handle(result: tuple[str, str] | None) -> None:
            if result is None:
                return
            key, value = result
            try:
                self.etcd.put(key, value)
                self.action_refresh()
                self.notify(f"Added key: {key}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(AddKeyScreen(prefix=self._selected_prefix()), handle)

    def action_add_dir(self) -> None:
        def handle(result: str | None) -> None:
            if result is None:
                return
            try:
                self.etcd.make_dir(result)
                self.action_refresh()
                self.notify(f"Created directory: {result}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(AddDirScreen(prefix=self._selected_prefix()), handle)

    def action_delete(self) -> None:
        node = self._selected_node()
        if node is None:
            self.notify("No key selected.", severity="warning")
            return

        msg = (
            f"Delete directory '{node.key}' and all its children?"
            if node.is_dir
            else f"Delete key '{node.key}'?"
        )

        def handle(confirmed: bool | None) -> None:
            if not confirmed:
                return
            try:
                self.etcd.delete(node.key, recursive=node.is_dir)
                self.action_refresh()
                self.notify(f"Deleted: {node.key}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(ConfirmScreen(msg), handle)

    def action_edit(self) -> None:
        node = self._selected_node()
        if node is None or node.is_dir:
            self.notify("Select a key (not a directory) to edit.", severity="warning")
            return

        def handle(new_value: str | None) -> None:
            if new_value is None:
                return
            try:
                self.etcd.put(node.key, new_value)
                # Refresh value panel immediately
                panel = self.query_one("#key-value", KeyValuePanel)
                panel.selected_node = EtcdNode(key=node.key, value=new_value, is_dir=False)
                self.notify(f"Saved: {node.key}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(EditKeyScreen(node.key, node.value or ""), handle)

    def action_refresh(self) -> None:
        tree = self.query_one("#key-tree", KeyTree)
        tree.clear()
        tree.root.data = EtcdNode(key="/", is_dir=True)
        tree.root.expand()
