# tetcd — Requirements, Design & Implementation Plan

## 1. Overview

**tetcd** is a terminal user interface (TUI) for browsing and managing [etcd](https://etcd.io) key-value stores. It supports both the etcd v2 HTTP API and the etcd v3 gRPC-gateway API. The interface is keyboard-driven and designed to feel like a file-manager for etcd namespaces.

---

## 2. Functional Requirements

| ID  | Requirement |
|-----|-------------|
| F01 | Browse the etcd key space as a hierarchical tree, using `/` as the path separator |
| F02 | View the value of a selected key in a side panel |
| F03 | Add a new key with an arbitrary value |
| F04 | Add a new directory (folder) at any path |
| F05 | Edit the value of an existing key in a modal editor |
| F06 | Delete a single key |
| F07 | Delete a directory recursively (all descendant keys) |
| F08 | Refresh the tree to reflect external changes |
| F09 | Support etcd API v2 (HTTP REST) |
| F10 | Support etcd API v3 (via gRPC-gateway HTTP) |
| F11 | Configure connection parameters via CLI flags, environment variables, or config file |

---

## 3. Non-Functional Requirements

| ID  | Requirement |
|-----|-------------|
| N01 | Keyboard-only navigation; no mouse required |
| N02 | Responsive: lazy loading — only fetch children when a node is expanded |
| N03 | Graceful error display (connection failures, 404s) shown inline without crashing |
| N04 | Configuration precedence: CLI flags > env vars (`TETCD_*`) > `settings.toml` |
| N05 | All operations confirmed before destructive actions (delete) |
| N06 | Python 3.11+ |
| N07 | Type-safe: passes `mypy --strict` |

---

## 4. Technology Stack

| Concern | Library |
|---------|---------|
| TUI | [Textual](https://github.com/Textualize/textual) ≥ 0.80 |
| CLI entry point | [Typer](https://typer.tiangolo.com/) ≥ 0.12 |
| Configuration | [Dynaconf](https://www.dynaconf.com/) ≥ 3.2 |
| etcd v2 HTTP | [httpx](https://www.python-httpx.org/) ≥ 0.27 |
| etcd v3 gRPC-gateway | [etcd3gw](https://github.com/dims/etcd3-gateway) ≥ 2.3 |
| Testing | [pytest](https://pytest.org/) + [respx](https://lundberg.github.io/respx/) (HTTP mocking) |
| Linting & formatting | [Ruff](https://docs.astral.sh/ruff/) ≥ 0.6 |
| Type checking | [mypy](https://mypy-lang.org/) ≥ 1.10 (strict mode) |
| Package management | [uv](https://docs.astral.sh/uv/) |
| Dev environment | Dev Containers (Docker Compose) |

---

## 5. Architecture

### 5.1 Layer Diagram

```
┌──────────────────────────────────────────┐
│              CLI (Typer)                 │  tetcd.main
│  --host  --port  --api  version          │
└────────────────────┬─────────────────────┘
                     │
┌────────────────────▼─────────────────────┐
│           Textual TUI Application         │  tetcd.tui
│  ┌──────────────────────────────────────┐ │
│  │  BrowserScreen                       │ │
│  │  ┌─────────────┐  ┌───────────────┐  │ │
│  │  │  KeyTree    │  │ KeyValuePanel │  │ │
│  │  │  (Tree[     │  │               │  │ │
│  │  │  EtcdNode]) │  │ key + value   │  │ │
│  │  └─────────────┘  └───────────────┘  │ │
│  └──────────────────────────────────────┘ │
│  Modal Screens: EditKey, AddKey,           │
│                 AddDir, Confirm            │
└────────────────────┬─────────────────────┘
                     │ EtcdClientProtocol
┌────────────────────▼─────────────────────┐
│           etcd Client Layer               │  tetcd.etcd
│  ┌──────────────┐  ┌───────────────────┐  │
│  │ EtcdV2Client │  │  EtcdV3Client     │  │
│  │  (httpx)     │  │  (etcd3gw)        │  │
│  └──────────────┘  └───────────────────┘  │
└──────────────────────────────────────────┘
```

### 5.2 Key Data Model

```python
@dataclass
class EtcdNode:
    key: str           # Full etcd key path (e.g. "/app/config/host")
    value: str | None  # None for directories
    is_dir: bool       # True if this key has children
    children: list[EtcdNode]  # Populated on-demand
```

### 5.3 Client Protocol

Both `EtcdV2Client` and `EtcdV3Client` satisfy `EtcdClientProtocol`:

```python
class EtcdClientProtocol(Protocol):
    def get(self, key: str) -> EtcdNode | None: ...
    def list(self, prefix: str) -> list[EtcdNode]: ...
    def put(self, key: str, value: str) -> None: ...
    def make_dir(self, key: str) -> None: ...
    def delete(self, key: str, recursive: bool = False) -> None: ...
    def health(self) -> bool: ...
```

### 5.4 etcd v2 vs v3 Differences

| Concern | v2 | v3 |
|---------|----|----|
| API style | HTTP REST (`/v2/keys/...`) | gRPC-gateway HTTP (`/v3/kv/...` via etcd3gw) |
| Directories | First-class (`dir=true`) | Flat store; simulated with key prefix conventions |
| Make dir | `PUT /v2/keys/path?dir=true` | Write a sentinel key (`path/.keep`) |
| Delete dir | `DELETE /v2/keys/path?recursive=true` | `delete_prefix(path)` |

### 5.5 TUI Layout

```
┌─ tetcd ──────────────────────────────────────────────────────────┐
│ Header                                                           │
├──────────────────────┬───────────────────────────────────────────┤
│ Keys                 │ Value                                     │
│                      │                                           │
│ ▼ /                  │ Key: /app/config/host                     │
│   ▼ :open_file_folder: app    │ localhost                                  │
│     ▼ :open_file_folder: config│                                           │
│       :page_facing_up: host   │                                           │
│       :page_facing_up: port   │                                           │
│   :page_facing_up: service    │                                           │
│                      │                                           │
├──────────────────────┴───────────────────────────────────────────┤
│ a Add Key  d Add Dir  D Delete  e Edit  r Refresh  q Quit       │
└──────────────────────────────────────────────────────────────────┘
```

---

## 6. Configuration

Configuration is layered (highest priority first):

1. **CLI flags** (`--host`, `--port`, `--api`)
2. **Environment variables** — prefix `TETCD_`, e.g. `TETCD_ETCD_HOST=my-etcd`
3. **`settings.toml`** — committed defaults per environment
4. **`.secrets.toml`** — local overrides and credentials (gitignored)

### Default `settings.toml`

```toml
[default]
etcd_version = "v3"
etcd_host    = "localhost"
etcd_port    = 2379
log_level    = "INFO"
```

---

## 7. Project Structure

```
tetcd/
├── .devcontainer/
│   ├── devcontainer.json      # VS Code Dev Containers config
│   └── docker-compose.yml     # app + etcd services
├── src/
│   └── tetcd/
│       ├── __init__.py
│       ├── main.py            # Typer CLI entry point
│       ├── config.py          # Dynaconf settings
│       ├── etcd/
│       │   ├── client.py      # EtcdNode dataclass + EtcdClientProtocol
│       │   ├── v2.py          # etcd v2 HTTP client (httpx)
│       │   └── v3.py          # etcd v3 client (etcd3gw)
│       └── tui/
│           ├── app.py         # TetcdApp (Textual App)
│           ├── screens/
│           │   ├── browser.py # Main browser screen
│           │   └── editor.py  # Edit/Add/Confirm modal screens
│           └── widgets/
│               ├── key_tree.py    # Lazy-loading Tree widget
│               └── key_value.py   # Value display panel
├── tests/
│   ├── conftest.py
│   ├── test_v2_client.py      # v2 client tests (respx HTTP mocks)
│   ├── test_v3_client.py      # v3 client tests (unittest.mock)
│   └── test_tui.py            # TUI smoke tests (Textual Pilot)
├── pyproject.toml
├── settings.toml
├── .secrets.toml              # gitignored
├── .gitignore
└── REQUIREMENTS.md
```

---

## 8. Implementation Plan

### Phase 1 — Project Bootstrap ✅
- [x] Initialize project with `uv`, `pyproject.toml`, `src/` layout
- [x] Configure Ruff, mypy, pytest in `pyproject.toml`
- [x] Set up Dynaconf (`settings.toml`, `.secrets.toml`)
- [x] Add `.devcontainer/` with etcd Docker Compose service
- [x] Set up `.gitignore`

### Phase 2 — etcd Client Layer ✅
- [x] Define `EtcdNode` dataclass and `EtcdClientProtocol`
- [x] Implement `EtcdV2Client` (httpx, full CRUD)
- [x] Implement `EtcdV3Client` (etcd3gw, full CRUD, virtual-dir simulation)
- [x] Unit tests for both clients with mocked HTTP

### Phase 3 — TUI Skeleton ✅
- [x] `TetcdApp` wiring Typer → Textual
- [x] `BrowserScreen` with horizontal split layout
- [x] `KeyTree` widget with lazy child loading
- [x] `KeyValuePanel` widget

### Phase 4 — Operations & Modals ✅
- [x] `EditKeyScreen` modal (TextArea editor)
- [x] `AddKeyScreen` modal
- [x] `AddDirScreen` modal
- [x] `ConfirmScreen` modal for destructive ops
- [x] Keybinding actions wired in `BrowserScreen`

### Phase 5 — Polish & Testing
- [ ] TUI integration tests with `textual.testing.Pilot`
- [ ] Error toasts for all operations
- [ ] Connection health check on startup with user-friendly message
- [ ] Support TLS/mTLS for production etcd clusters (add cert options)
- [ ] Watch mode: live refresh when etcd keys change
- [ ] Copy key/value to clipboard

### Phase 6 — Release
- [ ] Package and publish to PyPI via `uv build` + `twine`
- [ ] GitHub Actions CI: ruff, mypy, pytest matrix (3.11, 3.12)
- [ ] Changelog and versioning with `bump-my-version`

---

## 9. Running the Project

```bash
# Install dependencies
uv sync

# Run the TUI (defaults to v3, localhost:2379)
uv run tetcd

# Connect to a specific etcd
uv run tetcd --host my-etcd.internal --port 2379 --api v3

# Use etcd v2
uv run tetcd --api v2

# Run tests
uv run pytest

# Lint + format
uv run ruff check src tests
uv run ruff format src tests

# Type check
uv run mypy
```

### Dev Container

Open the project in VS Code and select **"Reopen in Container"**. The container starts an etcd 3.5 service automatically on port 2379. The `TETCD_ETCD_HOST=etcd` environment variable is pre-set so `uv run tetcd` connects straight away.
