"""Tree widget showing one or more etcd servers as lazy-loaded sub-trees."""

from __future__ import annotations

from typing import Any

from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode, Server

type TreeData = Server | EtcdNode


class KeyTree(Tree[TreeData]):
    """Multi-server tree.

    Each configured :class:`Server` becomes a top-level visible node. The
    artificial Textual ``Tree`` root is hidden so users see one folder per
    server. Children of a server/directory are fetched on demand the first
    time the node is expanded, using the client that belongs to the
    enclosing server.
    """

    BORDER_TITLE = "Servers"

    def __init__(self, servers: list[Server], **kwargs: Any) -> None:
        """Build the tree pre-populated with one branch per server."""
        super().__init__("etcd", data=None, **kwargs)
        self.servers = servers
        self.guide_depth = 3
        self.show_root = False

    def on_mount(self) -> None:
        """Populate the tree and wire the cursor to the screen's selection state.

        Both ``active_server`` and ``active_node`` are watched. When either
        changes the cursor is moved to match — but only after the next render
        pass, because freshly-loaded :class:`TreeNode` instances report
        ``line == -1`` until layout completes and ``select_node`` would be a
        no-op against them otherwise.
        """
        self._populate()
        screen = self.screen
        self.watch(screen, "active_server", self._sync_cursor_from_state, init=False)
        self.watch(screen, "active_node", self._sync_cursor_from_state, init=False)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[TreeData]) -> None:
        """Lazy-load children the first time a server/directory expands."""
        node = event.node
        if node.children:
            return
        data = node.data
        if isinstance(data, Server):
            self._load_children(node, data.client, "/")
        elif isinstance(data, EtcdNode) and data.is_dir:
            client = self.client_for(node)
            if client is not None:
                self._load_children(node, client, data.key)

    def client_for(self, node: TreeNode[TreeData]) -> EtcdClientProtocol | None:
        """Return the client of the server hosting ``node`` (walking ancestors)."""
        current: TreeNode[TreeData] | None = node
        while current is not None:
            if isinstance(current.data, Server):
                return current.data.client
            current = current.parent
        return None

    def refresh_node(self, node: TreeNode[TreeData]) -> None:
        """Drop and reload all children of ``node`` from its server."""
        node.remove_children()
        data = node.data
        if isinstance(data, Server):
            self._load_children(node, data.client, "/")
        elif isinstance(data, EtcdNode) and data.is_dir:
            client = self.client_for(node)
            if client is not None:
                self._load_children(node, client, data.key)

    def rebuild(self) -> None:
        """Clear the tree and re-add the configured server branches."""
        self.clear()
        self._populate()

    def reveal_key(self, server_node: TreeNode[TreeData], key: str) -> TreeNode[TreeData] | None:
        """Expand the path under ``server_node`` to ``key`` and return its node.

        Walks the slash-separated segments of ``key`` from the server root
        downward, synchronously loading any directory whose children have not
        been fetched yet so the target ends up rendered in the tree. Returns
        ``None`` if any segment along the path is missing from the keyspace.
        """
        self._ensure_children_loaded(server_node)
        server_node.expand()

        parts = [p for p in key.strip("/").split("/") if p]
        current: TreeNode[TreeData] = server_node
        accum = ""
        for i, segment in enumerate(parts):
            accum = f"{accum}/{segment}"
            target = _find_child_by_key(current, accum)
            if target is None:
                return None
            is_last = i == len(parts) - 1
            if not is_last and isinstance(target.data, EtcdNode) and target.data.is_dir:
                self._ensure_children_loaded(target)
                target.expand()
            current = target
        return current

    def server_node_for(self, client: EtcdClientProtocol) -> TreeNode[TreeData] | None:
        """Return the top-level node bound to ``client``, or ``None`` if absent."""
        for child in self.root.children:
            if isinstance(child.data, Server) and child.data.client is client:
                return child
        return None

    def _sync_cursor_from_state(self, _value: Any) -> None:
        """Move the cursor onto the TreeNode matching the screen's active key.

        Called whenever the screen reports a new ``active_server`` or
        ``active_node``. Only ``active_node`` drives the cursor — picking a
        server but no node (e.g. via tree click on the server itself) leaves
        the existing cursor alone, which keeps repeated firings during a
        compound state update (server-then-node) from racing each other.
        """
        screen = self.screen
        server = getattr(screen, "active_server", None)
        node = getattr(screen, "active_node", None)
        if not isinstance(server, Server) or not isinstance(node, EtcdNode):
            return
        server_node = self.server_node_for(server.client)
        if server_node is None:
            return
        revealed = self.reveal_key(server_node, node.key)
        if revealed is None or self.cursor_node is revealed:
            return
        self._defer_select(revealed)

    def _defer_select(self, target: TreeNode[TreeData]) -> None:
        """Select ``target`` once Textual has assigned it a valid line.

        ``reveal_key`` synchronously adds new :class:`TreeNode` instances
        whose ``line`` attribute is ``-1`` until the next layout pass — so
        a direct ``select_node`` would be a silent no-op. We re-schedule
        via :meth:`call_after_refresh` until the line resolves, then commit.
        """
        if target.line >= 0:
            self.select_node(target)
            return
        self.app.call_after_refresh(self._defer_select, target)

    def _ensure_children_loaded(self, node: TreeNode[TreeData]) -> None:
        """Populate ``node``'s children synchronously if not loaded yet."""
        if node.children:
            return
        data = node.data
        if isinstance(data, Server):
            self._load_children(node, data.client, "/")
        elif isinstance(data, EtcdNode) and data.is_dir:
            client = self.client_for(node)
            if client is not None:
                self._load_children(node, client, data.key)

    def _populate(self) -> None:
        """Attach one expandable top-level branch per configured server."""
        for server in self.servers:
            branch = self.root.add(f":satellite: {server.config.label}", data=server)
            branch.allow_expand = True
        self.root.expand()

    def _load_children(
        self, node: TreeNode[TreeData], client: EtcdClientProtocol, prefix: str
    ) -> None:
        """Fetch the entries under ``prefix`` from ``client`` and attach them."""
        try:
            children = client.list(prefix)
        except Exception as exc:
            node.add_leaf(f"[red]Error: {exc}[/red]")
            return

        for child in sorted(children, key=lambda n: (not n.is_dir, n.name)):
            if child.is_dir:
                branch = node.add(f":open_file_folder: {child.name}", data=child)
                branch.allow_expand = True
            else:
                node.add_leaf(f":page_facing_up: {child.name}", data=child)


def _find_child_by_key(node: TreeNode[TreeData], key: str) -> TreeNode[TreeData] | None:
    """Return the direct child of ``node`` whose ``EtcdNode.key`` equals ``key``."""
    for child in node.children:
        data = child.data
        if isinstance(data, EtcdNode) and data.key == key:
            return child
    return None
