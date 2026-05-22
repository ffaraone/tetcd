# tetcd Development Guidelines

## Project

`tetcd` is a terminal user interface (TUI) for browsing and managing
[etcd](https://etcd.io) key-value stores. The interface is keyboard-driven and
designed to feel like a file manager for etcd namespaces. The project supports
both the etcd v2 HTTP API and the etcd v3 gRPC-gateway HTTP API behind a
single `EtcdClientProtocol`, so the TUI is agnostic to the backend version.

It ships as a single CLI entry point (`tetcd`) and is distributed on PyPI.
Targets Python 3.12+; dependency, virtualenv, and build management is handled
by [uv](https://docs.astral.sh/uv/).

## Requirements and design

The full functional and non-functional requirements, layer diagram, data
model, and the v2-vs-v3 differences live in [`REQUIREMENTS.md`](REQUIREMENTS.md).
Read it before changing the etcd client layer, the `EtcdNode` data model, or
the configuration precedence rules.

Highlights you should know without opening that file:

* **Configuration precedence** (highest first): CLI flags → `TETCD_*` env
  vars → `settings.toml` → `.secrets.toml` (gitignored).
* **Lazy tree loading** — children are fetched only when a directory node is
  expanded; do not eagerly walk the keyspace.
* **All destructive operations are confirmed** through `ConfirmScreen` before
  hitting the etcd client.
* **v3 has no native directories** — they are simulated with key prefixes and
  a `.keep` sentinel key. Preserve that convention when touching `EtcdV3Client`.

## Project structure

```
tetcd/
├── src/tetcd/
│   ├── __init__.py          # package version
│   ├── main.py              # Typer CLI entry point (`tetcd` command)
│   ├── config.py            # Dynaconf settings loader
│   ├── etcd/
│   │   ├── client.py        # EtcdNode dataclass + EtcdClientProtocol
│   │   ├── v2.py            # EtcdV2Client (httpx)
│   │   └── v3.py            # EtcdV3Client (etcd3gw)
│   └── tui/
│       ├── app.py           # TetcdApp (Textual App)
│       ├── screens/
│       │   ├── browser.py   # main browser screen
│       │   ├── editor.py    # Edit/Add/Confirm modal screens
│       │   └── splash.py    # startup splash modal
│       └── widgets/
│           ├── key_tree.py  # lazy-loading Tree widget
│           └── key_value.py # value display panel
├── tests/                   # pytest suite; mirrors the src/ layout
│   └── __snapshots__/       # pytest-textual-snapshot baselines
├── .github/workflows/       # CI: test on PR, publish to PyPI on release
├── .devcontainer/           # VS Code dev container with an etcd service
├── pyproject.toml           # project metadata, tool configs (ruff, ty, pytest, coverage)
├── settings.toml            # default Dynaconf settings
└── REQUIREMENTS.md          # full requirements & design doc
```

All tool caches (ruff, pytest, coverage) are written under `.cache/` and are
gitignored.

## Mandatory checks on every change

Every change MUST pass the following checks before being proposed for
merge. They run locally and in CI; do not bypass them.

```bash
uv run pytest                             # full suite + coverage report
uv run prek run --all-files               # all pre-commit hooks (ruff, mypy, etc.)
```

If any of the above fails, fix the root cause — do not silence checks or
disable hooks.

## Per-change workflow

For every change you MUST:

1. **Change the code.** One logical change at a time.
2. **Add or fix tests.** New behavior needs new tests; bug fixes need a
   regression test that fails without the fix. Use the `python-testing`
   skill to write tests.

## Branches and commits

* `main` is **protected**. No direct pushes — every change lands via PR.
* Branch names use the format `<type>/<slug>`, where `<type>` is one of
  `feat`, `fix`, `docs`, `refactor`, `test`, `chore`.
* Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `build:`,
  `ci:`.
* Subject line in **imperative mood**, ≤72 characters. The body explains
  **why**, not how.
* **One logical change per commit.** Rebase to clean up before opening a
  PR; do not merge `main` into the branch.


## Third-party dependencies

If a change requires a new third-party open-source library:

1. The library MUST be **actively maintained** (recent releases, responsive
   to issues, healthy community).
2. The license MUST be **OSI-approved, popular and have a strong
   community** — see
   <https://opensource.org/licenses?categories=popular-strong-community>.
   Anything outside that list requires explicit approval before adoption.

## Coding rules

### 0. Follow PEP 20 (The Zen of Python)

* Beautiful is better than ugly.
* Explicit is better than implicit.
* Simple is better than complex.
* Complex is better than complicated.
* Flat is better than nested.
* Sparse is better than dense.
* Readability counts.
* Special cases aren't special enough to break the rules.
* Although practicality beats purity.
* Errors should never pass silently.
* Unless explicitly silenced.
* In the face of ambiguity, refuse the temptation to guess.
* There should be one-- and preferably only one --obvious way to do it.
* Although that way may not be obvious at first unless you're Dutch.
* Now is better than never.
* Although never is often better than *right* now.
* If the implementation is hard to explain, it's a bad idea.
* If the implementation is easy to explain, it may be a good idea.
* Namespaces are one honking great idea -- let's do more of those!

### 1. Imports

* All imports stay at the **top of the file**. No inline imports inside
  functions.

### 2. Type annotations

* Type annotations are **always mandatory** — on every function, method,
  parameter, and return value.

### 3. Circular imports

* To avoid circular imports, **always refactor first**. Lazy imports are
  not an acceptable shortcut.

### 4. Function ordering

* The **public interface** of a module comes first; private functions
  follow.

### 5. Private functions

* Underscore-prefixed functions are allowed **only when used within the
  same module**. Importing an underscore-prefixed symbol from another
  module is **prohibited**.

### 6. Method ordering

* The **public interface** of a class comes first; private methods follow.

### 7. Constants

* Constant values stay **immediately after the imports** at the top of the
  module.

### 8. Import aliases

* Avoid import aliases unless **strictly necessary** (e.g. resolving a
  name clash).

### 9. Comments

* Code should be **self-explanatory**. Add comments only when strictly
  needed to surface a non-obvious *why*: a hidden constraint, a subtle
  invariant, or a workaround.

## Docstring rules

1. Every public function, class, and module gets a docstring. **Google
   style** for parser code; a one-paragraph summary for everything else
   is fine.
2. **Docstrings are self-contained.** Do not write "see file X" or
   "described in §Y of doc Z". A reader landing on the symbol from an
   IDE should understand it without leaving the file.
3. Document **what** the function returns and **why** it might raise —
   not the obvious **how**.
4. Surface **non-obvious invariants** (e.g. "rules-file values win over
   spec values") in the docstring of the function that enforces them.
5. Docstrings must honour the project max line length.

## Skills

* Use the **`python-testing`** skill whenever writing, refactoring, or
  debugging tests.
* Use the **`technical-writer`** skill whenever writing or editing the
  user-facing documentation under `docs/` or the README.
