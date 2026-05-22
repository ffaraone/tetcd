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

    BORDER_TITLE = "Keys"

    def __init__(self, servers: list[Server], **kwargs: Any) -> None:
        """Build the tree pre-populated with one branch per server."""
        super().__init__("etcd", data=None, **kwargs)
        self.servers = servers
        self.guide_depth = 3
        self.show_root = False

    def on_mount(self) -> None:
        """Add every configured server as a top-level expandable node."""
        self._populate()

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
