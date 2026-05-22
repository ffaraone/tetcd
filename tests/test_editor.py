from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Input, TextArea

from tetcd.tui.screens.editor import AddDirScreen, AddKeyScreen, ConfirmScreen, EditKeyScreen


class _Host(App[None]):
    """Bare host app used to push modal screens under test."""

    def compose(self) -> ComposeResult:
        yield from ()


# ── EditKeyScreen ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_edit_key_save_via_button() -> None:
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(EditKeyScreen("/k", "old"), callback=result.append)
        await pilot.pause()
        editor = app.screen.query_one("#value-editor", TextArea)
        editor.text = "new-value"
        await pilot.click("#btn-save")
        await pilot.pause()
    assert result == ["new-value"]


@pytest.mark.asyncio
async def test_edit_key_save_via_ctrl_s() -> None:
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(EditKeyScreen("/k", "old"), callback=result.append)
        await pilot.pause()
        editor = app.screen.query_one("#value-editor", TextArea)
        editor.text = "saved-via-key"
        await pilot.press("ctrl+s")
        await pilot.pause()
    assert result == ["saved-via-key"]


@pytest.mark.asyncio
async def test_edit_key_cancel_via_button() -> None:
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(EditKeyScreen("/k", "old"), callback=result.append)
        await pilot.pause()
        await pilot.click("#btn-cancel")
        await pilot.pause()
    assert result == [None]


@pytest.mark.asyncio
async def test_edit_key_cancel_via_escape() -> None:
    app = _Host()
    result: list[str | None] = []
    async with app.run_test() as pilot:
        app.push_screen(EditKeyScreen("/k", "old"), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [None]


# ── AddKeyScreen ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_key_submits_key_and_value() -> None:
    app = _Host()
    result: list[tuple[str, str] | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(prefix="/app"), callback=result.append)
        await pilot.pause()
        app.screen.query_one("#key-input", Input).value = "/app/foo"
        app.screen.query_one("#value-input", Input).value = "bar"
        await pilot.click("#btn-add")
        await pilot.pause()
    assert result == [("/app/foo", "bar")]


@pytest.mark.asyncio
async def test_add_key_empty_path_does_not_dismiss() -> None:
    app = _Host()
    result: list[tuple[str, str] | None] = []
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
    app = _Host()
    result: list[tuple[str, str] | None] = []
    async with app.run_test() as pilot:
        app.push_screen(AddKeyScreen(), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [None]


# ── AddDirScreen ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_dir_submits_path() -> None:
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
    app = _Host()
    result: list[bool | None] = []
    async with app.run_test() as pilot:
        app.push_screen(ConfirmScreen("Are you sure?"), callback=result.append)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
    assert result == [False]
