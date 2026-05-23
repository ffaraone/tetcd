"""Test-only fakes: an in-memory etcd client and a state-bearing host Screen.

The fake :class:`InMemoryEtcdClient` stores leaves and explicit directory
markers in plain dicts so ``put`` / ``make_dir`` / ``delete`` mutations are
immediately visible to the next ``list`` or ``get`` call from the same
instance. That removes the need for the ad-hoc ``client.list.side_effect``
patching that ``MagicMock``-based fixtures had to perform whenever a test
expected a write to round-trip.

:class:`BrowserStateHostScreen` exposes the same reactive selection / edit
attributes as :class:`tetcd.tui.screens.browser.BrowserScreen` so widget-
under-test fixtures can host :class:`KeyValuePanel` / :class:`KeyTree`
without dragging in the full browser screen and its bindings.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget

from tetcd.etcd.client import EtcdNode, EtcdNodes, Server


class InMemoryEtcdClient:
    """Tracking fake whose ``list``/``get`` reflect prior ``put``/``delete`` calls."""

    def __init__(
        self,
        *,
        values: dict[str, str] | None = None,
        dirs: Iterable[str] | None = None,
    ) -> None:
        """Pre-populate the keyspace with ``values`` leaves and ``dirs`` directories."""
        self._values: dict[str, str] = {}
        self._dirs: set[str] = set()
        if values:
            for key, value in values.items():
                self._values[_normalize(key)] = value
        if dirs:
            for path in dirs:
                self._dirs.add(_normalize(path))

    def get(self, key: str) -> EtcdNode | None:
        """Return the node at ``key`` or ``None`` if the key is not present."""
        normalized = _normalize(key)
        if normalized in self._values:
            return EtcdNode(key=normalized, value=self._values[normalized])
        if normalized in self._dirs or self._has_descendant(normalized):
            return EtcdNode(key=normalized, is_dir=True)
        return None

    def list(self, prefix: str) -> EtcdNodes:
        """Return the immediate children of ``prefix`` (leaves and directories)."""
        parent = _normalize_prefix(prefix)
        children: dict[str, EtcdNode] = {}

        for key, value in self._values.items():
            if not key.startswith(parent + "/"):
                continue
            rest = key[len(parent) + 1 :]
            if "/" in rest:
                first = rest.split("/", 1)[0]
                implicit = f"{parent}/{first}"
                children.setdefault(implicit, EtcdNode(key=implicit, is_dir=True))
            else:
                children[key] = EtcdNode(key=key, value=value)

        for path in self._dirs:
            if not path.startswith(parent + "/"):
                continue
            rest = path[len(parent) + 1 :]
            first = rest.split("/", 1)[0]
            direct = f"{parent}/{first}"
            children[direct] = EtcdNode(key=direct, is_dir=True)

        return list(children.values())

    def put(self, key: str, value: str) -> None:
        """Store ``value`` under ``key``, overwriting any prior leaf or dir marker."""
        normalized = _normalize(key)
        self._values[normalized] = value
        self._dirs.discard(normalized)

    def make_dir(self, key: str) -> None:
        """Register ``key`` as an explicit directory. Idempotent."""
        normalized = _normalize(key)
        self._dirs.add(normalized)

    def delete(self, key: str, recursive: bool = False) -> None:
        """Delete ``key``; with ``recursive=True`` remove everything beneath it too."""
        normalized = _normalize(key)
        self._values.pop(normalized, None)
        self._dirs.discard(normalized)
        if recursive:
            prefix = normalized + "/"
            for stored in list(self._values):
                if stored.startswith(prefix):
                    del self._values[stored]
            for stored in list(self._dirs):
                if stored.startswith(prefix):
                    self._dirs.discard(stored)

    def health(self) -> bool:
        """The fake is always healthy."""
        return True

    def _has_descendant(self, prefix: str) -> bool:
        """Return ``True`` if any stored entry lives beneath ``prefix``."""
        marker = prefix + "/"
        return any(k.startswith(marker) for k in self._values) or any(
            d.startswith(marker) for d in self._dirs
        )


def _normalize(key: str) -> str:
    """Collapse a key to its canonical leading-slash, no-trailing-slash, no-empty-segments form."""
    segments = [s for s in key.strip().split("/") if s]
    return "/" + "/".join(segments) if segments else "/"


def _normalize_prefix(prefix: str) -> str:
    """Return the ``parent`` form used internally for child matching ('' for root)."""
    normalized = _normalize(prefix)
    return "" if normalized == "/" else normalized


class BrowserStateHostScreen(Screen[None]):
    """Test host Screen mirroring the reactive surface of ``BrowserScreen``.

    Widget-under-test fixtures push this screen and yield the widget(s) being
    exercised as its children. The widgets' ``self.watch(self.screen, ...)``
    subscriptions then resolve against these reactives, letting tests drive
    panel/tree behaviour by writing to the attributes directly — exactly as
    :class:`BrowserScreen` does in production.
    """

    active_server: reactive[Server | None] = reactive(None)
    active_node: reactive[EtcdNode | None] = reactive(None)
    edit_mode: reactive[bool] = reactive(False)
    edit_target_key: reactive[str] = reactive("")
    edit_initial_value: reactive[str] = reactive("")
    edit_is_new: reactive[bool] = reactive(False)

    def __init__(self, child_factories: Iterable[Callable[[], Widget]]) -> None:
        """Build the host with ``child_factories``; each factory yields one child widget."""
        super().__init__()
        self._child_factories = list(child_factories)

    def compose(self) -> ComposeResult:
        """Yield the configured child widgets in order."""
        for factory in self._child_factories:
            yield factory()
