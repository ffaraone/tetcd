"""Main browser screen: multi-server key tree plus inline value editor.

The screen is the single writer of the shared selection/edit state. Both
:class:`KeyTree` and :class:`KeyValuePanel` are pure views over that state;
they react to it via watchers and never mutate it directly. User input
arrives as Textual messages and key bindings; the screen translates those
into state updates and etcd I/O.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.reactive import reactive
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

    # ── shared selection + edit state (watched by KeyTree and KeyValuePanel) ──
    active_server: reactive[Server | None] = reactive(None)
    active_node: reactive[EtcdNode | None] = reactive(None)
    edit_mode: reactive[bool] = reactive(False)
    edit_target_key: reactive[str] = reactive("")
    edit_initial_value: reactive[str] = reactive("")
    edit_is_new: reactive[bool] = reactive(False)

    def __init__(self, servers: list[Server]) -> None:
        """Bind the screen to one or more configured etcd ``servers``."""
        super().__init__()
        self.servers = servers
        self._clipboard: _ClipboardItem | None = None

    def compose(self) -> ComposeResult:
        """Yield header, tree/value split, and footer."""
        yield Header()
        with Horizontal():
            yield KeyTree(self.servers, id="key-tree")
            yield KeyValuePanel(id="key-value")
        yield Footer()

    # ── tree → state ─────────────────────────────────────────────────────────

    def on_tree_node_selected(self, event: Tree.NodeSelected[TreeData]) -> None:
        """Reflect the tree's cursor into the shared selection state."""
        if self.edit_mode:
            return
        data = event.node.data
        if isinstance(data, Server):
            self.active_server = data
            self.active_node = None
            return
        if isinstance(data, EtcdNode):
            server_node = self._enclosing_server_node(event.node)
            if server_node is not None and isinstance(server_node.data, Server):
                self.active_server = server_node.data
            self.active_node = data

    # ── CRUD actions ─────────────────────────────────────────────────────────

    def action_add_key(self) -> None:
        """Ask for a key path, then open the value pane for the new entry."""
        server = self.active_server
        if server is None:
            self.notify("Select a server or path first.", severity="warning")
            return

        def handle(result: str | None) -> None:
            if result is None:
                return
            self._begin_edit(result, initial_value="", is_new=True)

        self.app.push_screen(
            AddKeyScreen(prefix=self._selected_prefix(), server_label=server.config.label),
            handle,
        )

    def action_add_dir(self) -> None:
        """Prompt for a directory path and create it via the active server's client."""
        server = self.active_server
        if server is None:
            self.notify("Select a server or path first.", severity="warning")
            return
        client = server.client

        def handle(result: str | None) -> None:
            if result is None:
                return
            try:
                client.make_dir(result)
                self._refresh_active_server()
                self.notify(f"Created directory: {result}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(
            AddDirScreen(prefix=self._selected_prefix(), server_label=server.config.label),
            handle,
        )

    def action_delete(self) -> None:
        """Confirm and delete the currently selected key or directory."""
        node = self.active_node
        server = self.active_server
        if node is None or server is None:
            self.notify("Select a key or directory to delete.", severity="warning")
            return
        client = server.client

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
                self.active_node = None
                self._refresh_active_server()
                self.notify(f"Deleted: {node.key}", severity="information")
            except Exception as exc:
                self.notify(f"Error: {exc}", severity="error")

        self.app.push_screen(ConfirmScreen(msg), handle)

    def action_edit(self) -> None:
        """Open the value pane in edit mode for the active leaf."""
        node = self.active_node
        if node is None or node.is_dir or self.active_server is None:
            self.notify("Select a key (not a directory or server) to edit.", severity="warning")
            return
        self._begin_edit(node.key, initial_value=node.value or "", is_new=False)

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
        server = self.active_server
        if server is None:
            self.notify("Select a destination server or directory.", severity="warning")
            return
        dst_client = server.client
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
        server = self.active_server
        if server is None:
            self.notify("No server bound to the active edit.", severity="error")
            return
        try:
            server.client.put(event.key, event.value)
        except Exception as exc:
            self.notify(f"Error: {exc}", severity="error")
            return

        # Refresh the affected server's subtree so the next reveal sees fresh data.
        tree = self.query_one("#key-tree", KeyTree)
        server_node = tree.server_node_for(server.client)
        revealed: TreeNode[TreeData] | None = None
        if server_node is not None:
            tree.refresh_node(server_node)
            revealed = tree.reveal_key(server_node, event.key)

        # Single state transition: leave edit mode and point at the saved key.
        # Widgets re-render via their watchers; the deferred select_node call
        # is the only imperative tree poke because freshly-loaded TreeNodes
        # have ``line == -1`` until the next render pass.
        self.edit_mode = False
        if revealed is not None and isinstance(revealed.data, EtcdNode):
            self.active_node = revealed.data
            self.call_after_refresh(tree.select_node, revealed)

        verb = "Added" if event.is_new else "Saved"
        self.notify(f"{verb}: {event.key}", severity="information")

    def on_key_value_panel_cancel_requested(self, event: KeyValuePanel.CancelRequested) -> None:
        """Leave edit mode directly; if dirty, ask for confirmation first."""
        if not event.dirty:
            self.edit_mode = False
            return

        def handle(confirmed: bool | None) -> None:
            if confirmed:
                self.edit_mode = False

        self.app.push_screen(ConfirmScreen("Discard unsaved changes?"), handle)

    # ── private helpers ──────────────────────────────────────────────────────

    def _begin_edit(self, target_key: str, *, initial_value: str, is_new: bool) -> None:
        """Push the edit-context fields into state and flip on edit mode."""
        self.edit_target_key = target_key
        self.edit_initial_value = initial_value
        self.edit_is_new = is_new
        self.edit_mode = True

    def _selected_prefix(self) -> str:
        """Return the prefix new keys/dirs/paste targets should land under."""
        node = self.active_node
        if node is None:
            return "/"
        if node.is_dir:
            return node.key
        return node.parent_key

    def _refresh_active_server(self) -> None:
        """Re-fetch children of the currently active server, if any."""
        server = self.active_server
        if server is None:
            tree = self.query_one("#key-tree", KeyTree)
            tree.rebuild()
            return
        tree = self.query_one("#key-tree", KeyTree)
        server_node = tree.server_node_for(server.client)
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
        node = self.active_node
        server = self.active_server
        if node is None or server is None:
            self.notify("Select a key or directory before copy/cut.", severity="warning")
            return
        self._clipboard = _ClipboardItem(operation=operation, client=server.client, node=node)
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
        self._refresh_active_server()
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
