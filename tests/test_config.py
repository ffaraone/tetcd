from __future__ import annotations

import importlib

import pytest

import tetcd.config


def test_settings_object_importable() -> None:
    """The Dynaconf settings instance is importable and exposes ``get``."""
    assert tetcd.config.settings is not None
    assert hasattr(tetcd.config.settings, "get")


def test_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TETCD_*`` environment variables override settings on a fresh load."""
    monkeypatch.setenv("TETCD_ETCD_HOST", "my-etcd.internal")
    importlib.reload(tetcd.config)
    assert tetcd.config.settings.get("etcd_host") == "my-etcd.internal"
