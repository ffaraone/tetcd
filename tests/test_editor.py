from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, Label

from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen


def _label_text(label: Label) -> str:
    """Return the plain-text body of ``label``, regardless of renderable type."""
    rendered = label.render()
    plain = getattr(rendered, "plain", None)
    return str(plain) if plain is not None else str(rendered)


class _Host(App[None]):
    """Bare host app used to push modal screens under test."""

    def compose(self) -> ComposeResult:
        yield from ()


# ── AddKeyScreen ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_key_submits_path() -> None:
    """``AddKeyScreen`` dismisses with the typed path (no value field)."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app"), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/app/foo"
        await pilot.click("#btn-add")
        await pilot.pause()
    assert result == ["/app/foo"]


@pytest.mark.asyncio
async def test_add_key_empty_path_does_not_dismiss() -> None:
    """An empty path leaves the modal open until the user cancels."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = ""
        await pilot.click("#btn-add")
        await pilot.pause()
        assert result == []
        await pilot.click("#btn-cancel")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_key_escape_cancels() -> None:
    """``escape`` dismisses the modal with ``None``."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_key_prefills_input_with_prefix() -> None:
    """The key input is pre-filled with the prefix so the user only types the leaf."""
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app"))
        await pilot.pause()
        key_input = app.screen.query_one("#key-input", Input)
        assert key_input.value == "/app/"
        assert key_input.cursor_position == len("/app/")


@pytest.mark.asyncio
async def test_add_key_rejects_prefix_only_submission() -> None:
    """Submitting the pre-filled prefix alone (no leaf appended) is ignored."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app"), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-add")
        await pilot.pause()
        assert result == []
        await pilot.click("#btn-cancel")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_key_shows_server_and_prefix_context() -> None:
    """The dialog renders ``Under: <server>://<prefix>`` when given a server label."""
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app", server_label="Production"))
        await pilot.pause()
        context = app.screen.query_one("#field-label", Label)
        assert "Production:///app/" in _label_text(context)


@pytest.mark.asyncio
async def test_add_key_context_label_omits_server_when_unknown() -> None:
    """Without a server label, the context line falls back to the bare prefix."""
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app"))
        await pilot.pause()
        text = _label_text(app.screen.query_one("#field-label", Label))
        assert "/app/" in text
        assert "://" not in text


# ── AddDirScreen ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_dir_submits_path() -> None:
    """``AddDirScreen`` dismisses with the typed directory path."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(prefix="/"), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = "/new"
        await pilot.click("#btn-create")
        await pilot.pause()
    assert result == ["/new"]


@pytest.mark.asyncio
async def test_add_dir_empty_does_not_dismiss_then_cancel() -> None:
    """An empty path leaves the modal open until the user explicitly cancels."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#dir-input", Input).value = ""
        await pilot.click("#btn-create")
        await pilot.pause()
        assert result == []
        await pilot.click("#btn-cancel")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_dir_escape_cancels() -> None:
    """``escape`` dismisses the modal with ``None``."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_dir_prefills_input_with_prefix() -> None:
    """The dir input is pre-filled with the prefix and the cursor sits at the end."""
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(prefix="/app"))
        await pilot.pause()
        dir_input = app.screen.query_one("#dir-input", Input)
        assert dir_input.value == "/app/"
        assert dir_input.cursor_position == len("/app/")


@pytest.mark.asyncio
async def test_add_dir_rejects_prefix_only_submission() -> None:
    """Submitting the pre-filled prefix alone (no name appended) is ignored."""
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(prefix="/app"), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-create")
        await pilot.pause()
        assert result == []
        await pilot.click("#btn-cancel")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_add_dir_shows_server_and_prefix_context() -> None:
    """The dir dialog renders the same ``Under: <server>://<prefix>`` context line."""
    app = _Host()
    async with app.run_test() as pilot:
        app.push_screen(AddDirScreen(prefix="/app", server_label="Staging"))
        await pilot.pause()
        context = app.screen.query_one("#field-label", Label)
        assert "Staging:///app/" in _label_text(context)


# ── ConfirmScreen ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_yes_via_button() -> None:
    """Clicking ``Yes`` dismisses with ``True``."""
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-yes")
        await pilot.pause()
    assert result == [True]


@pytest.mark.asyncio
async def test_confirm_no_via_button() -> None:
    """Clicking ``No`` dismisses with ``False``."""
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-no")
        await pilot.pause()
    assert result == [False]


@pytest.mark.asyncio
async def test_confirm_y_key() -> None:
    """Pressing ``y`` confirms."""
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.press("y")
        await pilot.pause()
    assert result == [True]


@pytest.mark.asyncio
async def test_confirm_n_key() -> None:
    """Pressing ``n`` cancels."""
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
    assert result == [False]


@pytest.mark.asyncio
async def test_confirm_escape_cancels() -> None:
    """``escape`` is treated as cancel."""
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [False]
