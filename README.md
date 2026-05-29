# tetcd

[![PyPI version](https://img.shields.io/pypi/v/tetcd.svg)](https://pypi.org/project/tetcd/)
[![Python versions](https://img.shields.io/pypi/pyversions/tetcd.svg)](https://pypi.org/project/tetcd/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/ffaraone/tetcd/actions/workflows/test.yml/badge.svg)](https://github.com/ffaraone/tetcd/actions/workflows/test.yml)

A keyboard-driven terminal UI for browsing and managing [etcd](https://etcd.io)
key-value stores. Supports both the etcd **v2** HTTP API and the etcd **v3**
gRPC-gateway API, and feels like a file manager for your etcd namespace.

## Features

- Browse the etcd key space as a hierarchical tree (using `/` as a separator)
- View values in a side panel
- Add, edit, and delete keys
- Add and recursively delete directories
- Lazy loading: children are fetched only when a node is expanded
- Layered configuration via CLI flags, environment variables, or a config file
- Confirmation prompts before destructive operations
- Works with both etcd v2 and v3

## Installation

Install from PyPI with your tool of choice:

```bash
# pipx (recommended for CLI tools)
pipx install tetcd

# uv
uv tool install tetcd

# pip
pip install tetcd
```

Requires Python 3.12 or newer.

## Usage

```bash
# Launch the TUI (defaults: v3, localhost:2379)
tetcd

# Connect to a specific etcd
tetcd --host my-etcd.internal --port 2379 --api v3

# Use the v2 API
tetcd --api v2

# Show version
tetcd --version
```

### Keybindings

| Key | Action       |
|-----|--------------|
| `a` | Add key      |
| `d` | Add directory|
| `D` | Delete       |
| `e` | Edit value   |
| `r` | Refresh tree |
| `q` | Quit         |

## Configuration

Configuration is layered (highest priority first):

1. **CLI flags** — `--host`, `--port`, `--api`
2. **Environment variables** — prefix `TETCD_`, e.g. `TETCD_ETCD_HOST=my-etcd`
3. **`settings.toml`** — committed defaults
4. **`.secrets.toml`** — local overrides and credentials (gitignored)

Default `settings.toml`:

```toml
[default]
etcd_version = "v3"
etcd_host    = "localhost"
etcd_port    = 2379
log_level    = "INFO"
```


## Development

The project uses [uv](https://docs.astral.sh/uv/) for dependency management,
[Ruff](https://docs.astral.sh/ruff/) for linting and formatting,
[ty](https://github.com/astral-sh/ty) for type checking, and
[pytest](https://pytest.org/) for tests.

```bash
# Install dependencies
uv sync

# Run the TUI from source
uv run tetcd

# Run tests
uv run pytest

# Lint and format
uv run ruff check src tests
uv run ruff format src tests

# Type check
uv run ty check
```

### Dev container

Open the project in VS Code and choose **"Reopen in Container"**. The container
starts an etcd 3.5 service on port 2379 and pre-sets `TETCD_ETCD_HOST=etcd`,
so `uv run tetcd` connects out of the box.

## License

Licensed under the [Apache License 2.0](LICENSE).
