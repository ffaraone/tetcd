"""Main browser screen: multi-server key tree plus inline value editor."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Footer, Header, Tree
from textual.widgets.tree import TreeNode

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode, Server
from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen
from tetcd.tui.widgets.key_tree import KeyTree, TreeData
from tetcd.tui.widgets.key_value import KeyValuePanel


@dataclass
class _ClipboardItem:
    """A pending copy or cut operation waiting to be pasted."""

    operation: Literal["copy", "cut"]
    client: EtcdClientProtocol
    node: EtcdNode


class BrowserScreen(Screen[None]):
    """Main browser screen: server tree on the left, value pane on the right."""

    BINDINGS = [
        Binding("a", "add_key", "Add Key"),
        Binding("d", "add_dir", "Add Dir"),
        Binding("D", "delete", "Delete"),
        Binding("e", "edit", "Edit"),
        Binding("c", "copy", "Copy"),
        Binding("x", "cut", "Cut"),
        Binding("v", "paste", "Paste"),
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
    }
    """

    def __init__(self, servers: list[Server]) -> None:
        """Bind the screen to one or more configured etcd ``servers``."""
        super().__init__()
        self.servers = servers
        self._clipboard: _ClipboardItem | None = None
        self._edit_client: EtcdClientProtocol | None = None

    def compose(self) -> ComposeResult:
        """Yield header, tree/value split, and footer."""
        yield Header()
        with Horizontal():
            yield KeyTree(self.servers, id="key-tree")
            yield KeyValuePanel(id="key-value")
        yield Footer()

    def on_tree_node_selected(self, event: Tree.NodeSelected[TreeData]) -> None:
        """Update the value panel when the user selects a tree node."""
        panel = self.query_one("#key-value", KeyValuePanel)
        if panel.edit_mode:
            return
        data = event.node.data
        panel.current_server = self._server_label_for(event.node)
        panel.selected_node = data if isinstance(data, EtcdNode) else None

    # ── CRUD actions ─────────────────────────────────────────────────────────

    def action_add_key(self) -> None:
        """Ask for a key path, then open the value pane for the new entry."""
        client = self._selected_client()
        if client is None:
            self.notify("Select a server or path first.", severity="warning")
            return
        server_label = self._selected_server_label()

        def handle(result: str | None) -> None:
            if result is None:
                return
            panel = self.query_one("#key-value", KeyValuePanel)
            self._edit_client = client
            panel.start_edit(
                target_key=result,
                initial_value="",
                is_new=True,
                server_label=server_label,
            )

        self.app.push_screen(
            AddKeyScreen(prefix=self._selected_prefix(), server_label=server_label),
            handle,
        )

    def action_add_dir(self) -> None:
        """Prompt for a directory path and create it via the selected server's client."""
        client = self._selected_client()
        if client is None:
            self.notify("Select a server or path first.", severity="warning")
            return
        server_label = self._selected_server_label()

        def handle(result: str | None) -> None:
            if result is None:
                return
            try:
                client.make_dir(result)
                self._refresh_current_server()
                self.notify(f"Created directory: {result}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(
            AddDirScreen(prefix=self._selected_prefix(), server_label=server_label),
            handle,
        )

    def action_delete(self) -> None:
        """Confirm and delete the currently selected key or directory."""
        node = self._selected_etcd_node()
        client = self._selected_client()
        if node is None or client is None:
            self.notify("Select a key or directory to delete.", severity="warning")
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
                client.delete(node.key, recursive=node.is_dir)
                self._refresh_current_server()
                self.notify(f"Deleted: {node.key}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(ConfirmScreen(msg), handle)

    def action_edit(self) -> None:
        """Open the value pane in edit mode for the selected leaf."""
        node = self._selected_etcd_node()
        client = self._selected_client()
        if node is None or node.is_dir or client is None:
            self.notify("Select a key (not a directory or server) to edit.", severity="warning")
            return
        panel = self.query_one("#key-value", KeyValuePanel)
        panel.selected_node = node
        self._edit_client = client
        panel.start_edit(
            target_key=node.key,
            initial_value=node.value or "",
            server_label=self._selected_server_label(),
        )

    def action_refresh(self) -> None:
        """Re-fetch the children of every configured server."""
        tree = self.query_one("#key-tree", KeyTree)
        tree.rebuild()

    # ── clipboard ────────────────────────────────────────────────────────────

    def action_copy(self) -> None:
        """Stage the current selection for a subsequent paste (no source delete)."""
        self._stash_clipboard("copy")

    def action_cut(self) -> None:
        """Stage the current selection for a paste-then-delete operation."""
        self._stash_clipboard("cut")

    def action_paste(self) -> None:
        """Paste the staged clipboard item under the current selection.

        Confirms before overwriting any existing key at the destination. On a
        cut operation, the source is deleted only after the paste succeeds.
        """
        item = self._clipboard
        if item is None:
            self.notify("Nothing in clipboard.", severity="warning")
            return
        dst_client = self._selected_client()
        if dst_client is None:
            self.notify("Select a destination server or directory.", severity="warning")
            return
        dst_prefix = self._selected_prefix()
        new_root = dst_prefix.rstrip("/") + "/" + item.node.name

        if _destination_exists(dst_client, new_root, item.node.is_dir):

            def on_confirm(confirmed: bool | None) -> None:
                if confirmed:
                    self._perform_paste(item, dst_client, new_root)

            self.app.push_screen(
                ConfirmScreen(f"Overwrite existing '{new_root}'?"),
                on_confirm,
            )
            return

        self._perform_paste(item, dst_client, new_root)

    # ── inline-editor message handlers ───────────────────────────────────────

    def on_key_value_panel_save_requested(self, event: KeyValuePanel.SaveRequested) -> None:
        """Persist the editor buffer, refresh the tree, and select the saved key."""
        client = self._edit_client
        panel = self.query_one("#key-value", KeyValuePanel)
        if client is None:
            self.notify("No server bound to the active edit.", severity="error")
            return
        try:
            client.put(event.key, event.value)
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")
            return

        panel.exit_edit_mode()
        self._edit_client = None

        tree = self.query_one("#key-tree", KeyTree)
        server_node = tree.server_node_for(client)
        if server_node is not None:
            tree.refresh_node(server_node)
            revealed = tree.reveal_key(server_node, event.key)
            if revealed is not None:
                if isinstance(revealed.data, EtcdNode):
                    revealed.data.value = event.value
                panel.selected_node = EtcdNode(key=event.key, value=event.value, is_dir=False)
                # The freshly-added/refreshed tree nodes have ``line == -1``
                # until the next render pass, so ``select_node`` is a no-op
                # right now. Defer it so the cursor lands on the saved key
                # once the tree has been re-laid-out.
                self.call_after_refresh(tree.select_node, revealed)

        verb = "Added" if event.is_new else "Saved"
        self.notify(f"{verb}: {event.key}", severity="information")

    def on_key_value_panel_cancel_requested(self, event: KeyValuePanel.CancelRequested) -> None:
        """Leave edit mode directly; if dirty, ask for confirmation first."""
        panel = self.query_one("#key-value", KeyValuePanel)
        if not event.dirty:
            panel.exit_edit_mode()
            self._edit_client = None
            return

        def handle(confirmed: bool | None) -> None:
            if confirmed:
                panel.exit_edit_mode()
                self._edit_client = None

        self.app.push_screen(ConfirmScreen("Discard unsaved changes?"), handle)

    # ── private helpers ──────────────────────────────────────────────────────

    def _selected_node_data(self) -> TreeData | None:
        """Return the data attached to the tree's cursor, or ``None``."""
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        return cursor.data if cursor else None

    def _selected_etcd_node(self) -> EtcdNode | None:
        """Return the selected node if it is an :class:`EtcdNode`, else ``None``."""
        data = self._selected_node_data()
        return data if isinstance(data, EtcdNode) else None

    def _selected_client(self) -> EtcdClientProtocol | None:
        """Return the client owning the current selection, walking up to the server."""
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        if cursor is None:
            return None
        return tree.client_for(cursor)

    def _selected_server_label(self) -> str | None:
        """Return the label of the server hosting the current cursor, if any."""
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        if cursor is None:
            return None
        return self._server_label_for(cursor)

    def _server_label_for(self, node: TreeNode[TreeData]) -> str | None:
        """Walk up to ``node``'s enclosing server and return its display label."""
        server_node = self._enclosing_server_node(node)
        if server_node is None or not isinstance(server_node.data, Server):
            return None
        return server_node.data.config.label

    def _selected_prefix(self) -> str:
        """Return the prefix new keys/dirs/paste targets should land under."""
        data = self._selected_node_data()
        if data is None or isinstance(data, Server):
            return "/"
        if data.is_dir:
            return data.key
        return data.parent_key

    def _refresh_current_server(self) -> None:
        """Re-fetch the children of the server containing the current cursor.

        ``action_refresh`` covers the case where the tree has no cursor at all;
        this helper assumes an in-progress operation (add/edit/delete/paste)
        and therefore expects the cursor to sit under a server branch.
        """
        tree = self.query_one("#key-tree", KeyTree)
        cursor = tree.cursor_node
        if cursor is None:
            tree.rebuild()
            return
        server_node = self._enclosing_server_node(cursor)
        if server_node is not None:
            tree.refresh_node(server_node)

    def _enclosing_server_node(self, node: TreeNode[TreeData]) -> TreeNode[TreeData] | None:
        """Walk ``node``'s ancestors to find the one carrying a :class:`Server`."""
        current: TreeNode[TreeData] | None = node
        while current is not None:
            if isinstance(current.data, Server):
                return current
            current = current.parent
        return None

    def _stash_clipboard(self, operation: Literal["copy", "cut"]) -> None:
        """Capture the current selection for a future paste."""
        node = self._selected_etcd_node()
        client = self._selected_client()
        if node is None or client is None:
            self.notify("Select a key or directory before copy/cut.", severity="warning")
            return
        self._clipboard = _ClipboardItem(operation=operation, client=client, node=node)
        verb = "Copied" if operation == "copy" else "Cut"
        self.notify(f"{verb}: {node.key}", severity="information")

    def _perform_paste(
        self, item: _ClipboardItem, dst_client: EtcdClientProtocol, new_root: str
    ) -> None:
        """Copy (and optionally delete) the clipboard item into ``new_root``."""
        try:
            _copy_into(item, dst_client, new_root)
            if item.operation == "cut":
                item.client.delete(item.node.key, recursive=item.node.is_dir)
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")
            return

        self._clipboard = None
        self._refresh_current_server()
        verb = "Moved" if item.operation == "cut" else "Copied"
        self.notify(f"{verb}: {item.node.key} → {new_root}", severity="information")


def _destination_exists(client: EtcdClientProtocol, key: str, is_dir: bool) -> bool:
    """Return ``True`` if writing to ``key`` would overwrite an existing entry."""
    try:
        if is_dir:
            return bool(client.list(key))
        return client.get(key) is not None
    except Exception:
        return False


def _copy_into(item: _ClipboardItem, dst_client: EtcdClientProtocol, new_root: str) -> None:
    """Copy ``item.node`` (recursively, if a dir) into ``new_root``."""
    if not item.node.is_dir:
        dst_client.put(new_root, item.node.value or "")
        return
    src_prefix = item.node.key
    for leaf in _walk_leaves(item.client, src_prefix):
        suffix = leaf.key[len(src_prefix) :]
        dst_client.put(new_root + suffix, leaf.value or "")


def _walk_leaves(client: EtcdClientProtocol, prefix: str) -> Iterator[EtcdNode]:
    """Yield every leaf node under ``prefix`` by walking the keyspace lazily."""
    for child in client.list(prefix):
        if child.is_dir:
            yield from _walk_leaves(client, child.key)
        else:
            yield child
