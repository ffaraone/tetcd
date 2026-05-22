"""Tree widget that lazily loads etcd keys when a directory is expanded."""

from __future__ import annotations

from typing import Any

from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode


class KeyTree(Tree[EtcdNode]):
    """Tree widget that lazily loads etcd keys as directories are expanded."""

    BORDER_TITLE = "Keys"

    def __init__(self, client: EtcdClientProtocol, **kwargs: Any) -> None:
        """Build the tree with the etcd ``/`` root as its initial node."""
        super().__init__("/", data=EtcdNode(key="/", is_dir=True), **kwargs)
        self.etcd = client
        self.guide_depth = 3
        self.show_root = True

    def on_mount(self) -> None:
        """Expand the root automatically so the first level is visible."""
        self.root.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[EtcdNode]) -> None:
        """Load children on demand the first time a directory expands."""
        node = event.node
        if node.data and node.data.is_dir and not node.children:
            self._load_children(node, node.data.key)

    def refresh_node(self, node: TreeNode[EtcdNode]) -> None:
        """Drop and reload all children of ``node`` from etcd."""
        node.remove_children()
        if node.data and node.data.is_dir:
            self._load_children(node, node.data.key)

    def _load_children(self, node: TreeNode[EtcdNode], prefix: str) -> None:
        """Fetch the entries under ``prefix`` and attach them to ``node``."""
        try:
            children = self.etcd.list(prefix)
        except Exception as exc:
            node.add_leaf(f"[red]Error: {exc}[/red]")
            return

        for child in sorted(children, key=lambda n: (not n.is_dir, n.name)):
            if child.is_dir:
                branch = node.add(f":open_file_folder: {child.name}", data=child)
                branch.allow_expand = True
            else:
                node.add_leaf(f":page_facing_up: {child.name}", data=child)
