from __future__ import annotations

from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from tetcd.etcd.client import EtcdClientProtocol, EtcdNode


class KeyTree(Tree[EtcdNode]):
    """Tree widget that lazily loads etcd keys as directories are expanded."""

    BORDER_TITLE = "Keys"

    def __init__(self, client: EtcdClientProtocol, **kwargs: object) -> None:
        super().__init__("/", data=EtcdNode(key="/", is_dir=True), **kwargs)  # type: ignore[arg-type]
        self.etcd = client
        self.guide_depth = 3
        self.show_root = True

    def on_mount(self) -> None:
        self.root.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[EtcdNode]) -> None:
        node = event.node
        if node.data and node.data.is_dir and not node.children:
            self._load_children(node, node.data.key)

    def _load_children(self, node: TreeNode[EtcdNode], prefix: str) -> None:
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

    def refresh_node(self, node: TreeNode[EtcdNode]) -> None:
        node.remove_children()
        if node.data and node.data.is_dir:
            self._load_children(node, node.data.key)
