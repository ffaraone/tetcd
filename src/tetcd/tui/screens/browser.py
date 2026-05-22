"""Main browser screen: a key tree on the left, a value panel on the right."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Tree

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode
from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen
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
        """Bind the screen to an etcd client implementing :class:`EtcdClientProtocol`."""
        super().__init__()
        self.etcd = client

    def compose(self) -> ComposeResult:
        """Yield header, the tree/value split, and the footer."""
        yield Header()
        with Horizontal():
            yield KeyTree(self.etcd, id="key-tree")
            yield KeyValuePanel(id="key-value")
        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected[EtcdNode]) -> None:
        """Update the value panel when the user selects a tree node."""
        panel = self.query_one("#key-value", KeyValuePanel)
        if panel.edit_mode:
            return
        panel.selected_node = event.node.data

    def action_add_key(self) -> None:
        """Ask for a key path, then open the value pane for the new entry."""

        def handle(result: str | None) -> None:
            if result is None:
                return
            panel = self.query_one("#key-value", KeyValuePanel)
            panel.start_edit(target_key=result, initial_value="", is_new=True)

        self.app.push_screen(AddKeyScreen(prefix=self._selected_prefix()), handle)

    def action_add_dir(self) -> None:
        """Prompt for a directory path and create it in etcd."""

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
        """Confirm and delete the currently selected key or directory."""
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
        """Open the value pane in edit mode for the selected leaf."""
        node = self._selected_node()
        if node is None or node.is_dir:
            self.notify("Select a key (not a directory) to edit.", severity="warning")
            return
        panel = self.query_one("#key-value", KeyValuePanel)
        panel.selected_node = node
        panel.start_edit(target_key=node.key, initial_value=node.value or "")

    def action_refresh(self) -> None:
        """Clear and re-expand the key tree from the root."""
        tree = self.query_one("#key-tree", KeyTree)
        tree.clear()
        tree.root.data = EtcdNode(key="/", is_dir=True)
        tree.root.expand()

    def on_key_value_panel_save_requested(self, event: KeyValuePanel.SaveRequested) -> None:
        """Persist the editor buffer to etcd and leave edit mode on success."""
        panel = self.query_one("#key-value", KeyValuePanel)
        try:
            self.etcd.put(event.key, event.value)
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")
            return

        panel.exit_edit_mode()
        if event.is_new:
            self.action_refresh()
            self.notify(f"Added key: {event.key}", severity="information")
        else:
            panel.selected_node = EtcdNode(key=event.key, value=event.value, is_dir=False)
            self.notify(f"Saved: {event.key}", severity="information")

    def on_key_value_panel_cancel_requested(self, event: KeyValuePanel.CancelRequested) -> None:
        """Leave edit mode directly; if dirty, ask for confirmation first."""
        panel = self.query_one("#key-value", KeyValuePanel)
        if not event.dirty:
            panel.exit_edit_mode()
            return

        def handle(confirmed: bool | None) -> None:
            if confirmed:
                panel.exit_edit_mode()

        self.app.push_screen(ConfirmScreen("Discard unsaved changes?"), handle)

    def _selected_node(self) -> EtcdNode | None:
        """Return the ``EtcdNode`` attached to the tree's cursor, if any."""
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        return cursor.data if cursor else None

    def _selected_prefix(self) -> str:
        """Return the key prefix the current selection should write into.

        - No selection → ``"/"`` (the root).
        - Directory selection → that directory's own key.
        - Leaf selection → its parent key.
        """
        node = self._selected_node()
        if node is None:
            return "/"
        if node.is_dir:
            return node.key
        return node.parent_key
