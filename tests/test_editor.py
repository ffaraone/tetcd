from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input

from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen


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
